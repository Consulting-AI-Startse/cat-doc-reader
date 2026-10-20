"""codigo do fornecedor e "esta na lista de liberados" no item

Relatorio de testes da CAT (out/2026): "part number errado, MAIORIA". A linha
imprime o codigo do fornecedor e o da Caterpillar, e o modelo escolhia o do
fornecedor. A resolucao poe o part number CAT no lugar e guarda o do
fornecedor em supplier_part_number, para nao perder o que estava impresso.

part_number_released e a resposta da lista de PN para o part number final:
verdadeiro, falso, ou nulo quando nao ha lista importada para julgar. E nota
na tela ("fora da lista"), nunca descarte.

So colunas novas e nulas: sem GRANT novo, e a function antiga segue gravando
enquanto a nova nao chega.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-20

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoice_part_number_items", sa.Column("supplier_part_number", sa.Text(), nullable=True)
    )
    op.add_column(
        "invoice_part_number_items",
        sa.Column("part_number_released", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoice_part_number_items", "part_number_released")
    op.drop_column("invoice_part_number_items", "supplier_part_number")
