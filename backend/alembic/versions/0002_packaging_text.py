"""packaging vira texto (tipo + tamanho do pacote, não moeda)

Descoberta ao olhar os documentos reais: "Packaging" não é um valor monetário
(nem cm³), e sim descritivo, como "EUROPALLET 1200x800x345 mm". Por isso a coluna
passa de Numeric para texto. Exemplo de migração progressiva do schema.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-21

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "invoice_part_number_items",
        "packaging",
        existing_type=sa.Numeric(precision=18, scale=2),
        type_=sa.String(length=128),
        existing_nullable=True,
        postgresql_using="packaging::text",
    )


def downgrade() -> None:
    op.alter_column(
        "invoice_part_number_items",
        "packaging",
        existing_type=sa.String(length=128),
        type_=sa.Numeric(precision=18, scale=2),
        existing_nullable=True,
        postgresql_using="packaging::numeric",
    )
