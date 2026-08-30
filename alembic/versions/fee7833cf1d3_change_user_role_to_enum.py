"""change user role to enum

Revision ID: fee7833cf1d3
Revises: 20260830_0005
Create Date: 2026-08-30 20:11:59.535598
"""

from alembic import op
import sqlalchemy as sa


revision = "fee7833cf1d3"
down_revision = "20260830_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove TEXT default
    op.execute(
        "ALTER TABLE users ALTER COLUMN role DROP DEFAULT"
    )

    # Convert existing uppercase values to lowercase
    op.execute(
        "UPDATE users SET role = LOWER(role)"
    )

    # Convert TEXT -> ENUM
    op.alter_column(
        "users",
        "role",
        existing_type=sa.TEXT(),
        type_=sa.Enum("admin", "employee", name="user_role"),
        existing_nullable=False,
        postgresql_using="role::user_role",
    )

    # Restore default using ENUM
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN role SET DEFAULT 'employee'::user_role"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users ALTER COLUMN role DROP DEFAULT"
    )

    op.alter_column(
        "users",
        "role",
        existing_type=sa.Enum("admin", "employee", name="user_role"),
        type_=sa.TEXT(),
        existing_nullable=False,
        postgresql_using="role::text",
    )

    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN role SET DEFAULT 'employee'::text"
    )