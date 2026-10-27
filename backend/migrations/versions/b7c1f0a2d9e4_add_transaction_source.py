"""add transaction source

Records where a row came from (manual entry vs. an imported WeChat/Alipay
statement) so imports stay auditable.

Revision ID: b7c1f0a2d9e4
Revises: ae576c74bf35
Create Date: 2026-10-27

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7c1f0a2d9e4"
down_revision = "ae576c74bf35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``server_default`` keeps the column addable on SQLite (which rejects a
    # NOT NULL column without a default) and lets existing rows keep a value.
    op.add_column(
        "transactions",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
    )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("source")
