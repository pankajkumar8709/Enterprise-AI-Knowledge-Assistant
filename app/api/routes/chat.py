"""Chat endpoints (spec §8, Phase 8).

POST   /chat/conversations
GET    /chat/conversations
GET    /chat/conversations/{id}
DELETE /chat/conversations/{id}
POST   /chat/conversations/{id}/messages
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation, Message, MessageRole, MessageSource
from app.models.user import User
from app.services.answer import ChatAnswerOut, SourceOut, generate_answer
from app.services.llm import LLMUnavailableError
from app.services.retrieval.orchestrator import retrieve

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ConversationOut(BaseModel):
    id: int
    title: str | None
    archived: bool
    created_at: str

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str

    model_config = {"from_attributes": True}


class SourceOutSchema(BaseModel):
    ref: str
    kind: str
    score: float
    cited: bool
    title: str
    snippet: str | None
    chunk_id: int | None = None
    document_id: int | None = None
    section_title: str | None = None
    page: int | None = None
    okf_object_id: int | None = None
    okf_type: str | None = None
    facts: dict = {}
    origin: dict | None = None


class ChatAnswerSchema(BaseModel):
    message_id: int
    conversation_id: int
    answer: str
    answerable: bool
    route: str
    confidence: float
    confidence_label: str
    sources: list[SourceOutSchema]
    latency_ms: int


class ConversationDetailOut(BaseModel):
    id: int
    title: str | None
    archived: bool
    created_at: str
    messages: list[MessageOut]

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _own_conversation(conv_id: int, user: User, db: Session) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")
    return conv


def _history_from_db(conv_id: int, db: Session) -> list[dict[str, str]]:
    from app.core.config import settings  # noqa: PLC0415

    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    turns = msgs[-(settings.chat_history_turns * 2):]
    return [{"role": m.role.value, "content": m.content} for m in turns]


def _source_out_from_db(src: MessageSource) -> SourceOutSchema:
    extra = src.extra or {}
    return SourceOutSchema(
        ref=src.ref,
        kind=src.kind,
        score=src.score or 0.0,
        cited=src.cited,
        title=extra.get("title", ""),
        snippet=src.snippet,
        chunk_id=src.chunk_id,
        document_id=src.document_id,
        section_title=extra.get("section_title"),
        page=extra.get("page"),
        okf_object_id=src.okf_object_id,
        okf_type=extra.get("okf_type"),
        facts=extra.get("facts", {}),
        origin=extra.get("origin"),
    )


def _answer_out_to_schema(out: ChatAnswerOut) -> ChatAnswerSchema:
    return ChatAnswerSchema(
        message_id=out.message_id,
        conversation_id=out.conversation_id,
        answer=out.answer,
        answerable=out.answerable,
        route=out.route,
        confidence=out.confidence,
        confidence_label=out.confidence_label,
        sources=[
            SourceOutSchema(
                ref=s.ref,
                kind=s.kind,
                score=s.score,
                cited=s.cited,
                title=s.title or "",
                snippet=s.snippet,
                chunk_id=s.chunk_id,
                document_id=s.document_id,
                section_title=s.section_title,
                page=s.page,
                okf_object_id=s.okf_object_id,
                okf_type=s.okf_type,
                facts=s.facts,
                origin=s.origin,
            )
            for s in out.sources
        ],
        latency_ms=out.latency_ms,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationOut:
    conv = Conversation(user_id=current_user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        archived=conv.archived,
        created_at=conv.created_at.isoformat(),
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConversationOut]:
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id, Conversation.archived.is_(False))
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return [
        ConversationOut(id=c.id, title=c.title, archived=c.archived, created_at=c.created_at.isoformat())
        for c in convs
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationDetailOut:
    conv = _own_conversation(conversation_id, current_user, db)
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return ConversationDetailOut(
        id=conv.id,
        title=conv.title,
        archived=conv.archived,
        created_at=conv.created_at.isoformat(),
        messages=[
            MessageOut(id=m.id, role=m.role.value, content=m.content, created_at=m.created_at.isoformat())
            for m in msgs
        ],
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    conv = _own_conversation(conversation_id, current_user, db)
    db.delete(conv)
    db.commit()


@router.post("/conversations/{conversation_id}/messages", response_model=ChatAnswerSchema)
def send_message(
    conversation_id: int,
    payload: SendMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatAnswerSchema:
    """Send a user message and receive an AI answer (spec §8 ChatAnswer)."""
    conv = _own_conversation(conversation_id, current_user, db)

    # Auto-title from first message
    if not conv.title:
        conv.title = payload.content[:80]
        db.add(conv)
        db.flush()

    history = _history_from_db(conversation_id, db)

    retrieval = retrieve(db, current_user, payload.content, history)

    ip = request.client.host if request.client else None

    try:
        answer_out = generate_answer(
            db=db,
            user=current_user,
            conversation_id=conversation_id,
            user_content=payload.content,
            retrieval=retrieval,
            ip=ip,
        )
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LLM_UNAVAILABLE", "message": str(exc)},
        ) from exc

    return _answer_out_to_schema(answer_out)
