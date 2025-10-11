"""update user roles

Revision ID: xxx
Revises: xxx
Create Date: 2025-09-02 17:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 更新所有TEACHER角色为USER角色
    op.execute("UPDATE users SET role = 'USER' WHERE role = 'TEACHER'")
    # 更新所有STUDENT角色为USER角色
    op.execute("UPDATE users SET role = 'USER' WHERE role = 'STUDENT'")

def downgrade():
    pass
