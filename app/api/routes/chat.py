from fastapi import APIRouter, Depends, status

from app.core.deps import get_current_user

router = APIRouter()


@router.post("", status_code=status.HTTP_200_OK)
def chat_stub(current_user=Depends(get_current_user)) -> dict[str, str]:
    return {
        "message": "Pending task",
        "user": current_user.email,
    }
