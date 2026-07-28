from fastapi import APIRouter, Depends, status

from app.core.deps import get_current_user

router = APIRouter()


@router.get("", status_code=status.HTTP_200_OK)
def list_documents(current_user=Depends(get_current_user)) -> dict[str, object]:
    return {
        "items": [],
        "message": "Document APIs are scaffolded for Phase 2 implementation.",
        "requested_by": current_user.email,
    }
