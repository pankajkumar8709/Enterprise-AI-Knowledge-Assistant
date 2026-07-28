from fastapi import APIRouter, Depends, status

from app.core.deps import get_current_user

router = APIRouter()


@router.get("", status_code=status.HTTP_200_OK)
def list_knowledge(current_user=Depends(get_current_user)) -> dict[str, object]:
    return {
        "items": [],
        "message": "Knowledge APIs are scaffolded for later phases.",
        "requested_by": current_user.email,
    }
