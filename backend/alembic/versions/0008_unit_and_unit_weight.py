"""unit e unit_weight por item

Dois campos do contrato do cliente (SUBIR_FATURA_GA.xlsx) que faltavam;
'Unit' e mandatorio. 'Unit Weight' e o 'Peso Unitario' do gabarito, em kg
(3649717 -> 19,81).

unit e TEXT, nao VARCHAR(16): a 0003 existe porque um incoterm real estourou
VARCHAR(16), e unidade impressa e texto livre do mesmo jeito.

So colunas novas e nulas: sem GRANT novo, e a function antiga segue gravando
enquanto a nova nao chega.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-08

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoice_part_number_items", sa.Column("unit", sa.Text(), nullable=True))
    op.add_column(
        "invoice_part_number_items",
        sa.Column("unit_weight", sa.Numeric(precision=18, scale=5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoice_part_number_items", "unit_weight")
    op.drop_column("invoice_part_number_items", "unit")
