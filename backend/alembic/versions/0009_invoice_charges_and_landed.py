"""frete e embalagem na invoice, unitario com encargos no item

O structurer sempre calculou o frete e o custo de embalagem da fatura e o
unitario com eles rateados (unit_price_landed), mas o worker nao gravava
nenhum dos quatro: ficavam so no raw_extraction, e a tela nao os mostrava. No
relatorio de testes da CAT (out/2026) isso apareceu tres vezes -- "Logistic
Charges" e "Inland Freight" que nao chegavam ao frete, e o pedido de
"divisao no valor e frete". O gabarito pede o unitario com encargos: 395,16 =
388,46 + 603/90 na fatura CD970373103.

unit_price_landed tem 4 casas como unit_price; amount_landed 2 como amount.

So colunas novas e nulas: sem GRANT novo, e a function antiga segue gravando
enquanto a nova nao chega.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("freight", sa.Numeric(precision=18, scale=2), nullable=True))
    op.add_column(
        "invoices", sa.Column("packaging_cost", sa.Numeric(precision=18, scale=2), nullable=True)
    )
    op.add_column(
        "invoice_part_number_items",
        sa.Column("unit_price_landed", sa.Numeric(precision=18, scale=4), nullable=True),
    )
    op.add_column(
        "invoice_part_number_items",
        sa.Column("amount_landed", sa.Numeric(precision=18, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoice_part_number_items", "amount_landed")
    op.drop_column("invoice_part_number_items", "unit_price_landed")
    op.drop_column("invoices", "packaging_cost")
    op.drop_column("invoices", "freight")
