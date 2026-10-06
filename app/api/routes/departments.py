from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin, get_current_user
from app.db.session import get_db
from app.models.department import Department
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter()


class DepartmentRead(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class DepartmentWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


@router.get("", response_model=list[DepartmentRead], status_code=status.HTTP_200_OK)
def list_departments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Department]:
    return db.query(Department).order_by(Department.name.asc()).all()


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentWrite,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> Department:
    existing = db.query(Department).filter(Department.name == payload.name).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department already exists")
    department = Department(name=payload.name, description=payload.description)
    db.add(department)
    db.commit()
    db.refresh(department)
    record_audit(
        db,
        action="department.create",
        entity_type="department",
        entity_id=str(department.id),
        user_id=current_user.id,
        ip=request.client.host if request.client else None,
    )
    return department


@router.patch("/{department_id}", response_model=DepartmentRead, status_code=status.HTTP_200_OK)
def update_department(
    department_id: int,
    payload: DepartmentWrite,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> Department:
    department = db.query(Department).filter(Department.id == department_id).first()
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    department.name = payload.name
    department.description = payload.description
    db.add(department)
    db.commit()
    db.refresh(department)
    record_audit(
        db,
        action="department.update",
        entity_type="department",
        entity_id=str(department.id),
        user_id=current_user.id,
        ip=request.client.host if request.client else None,
    )
    return department


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> None:
    department = db.query(Department).filter(Department.id == department_id).first()
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    from app.models.user import User as UserModel

    in_use = db.query(UserModel).filter(UserModel.department_id == department_id).count()
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department is still referenced by users",
        )
    db.delete(department)
    db.commit()
    record_audit(
        db,
        action="department.delete",
        entity_type="department",
        entity_id=str(department_id),
        user_id=current_user.id,
        ip=request.client.host if request.client else None,
    )
