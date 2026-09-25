"""serial number por item

Motor repete o MESMO part number, uma vez para cada serial -- entao serial e
coluna do item, nao tabela propria. Confirmado na fatura 93872204, que traz
'QTY 7' de 6522586 e sete seriais (XWE42867, XWE42871, XWE42879...), numa
tabela 'Part Number | Serial Number' separada da tabela de itens.

O structurer expande a linha impressa em sete registros com quantidade 1 e
amount = unit_price, o que preserva a soma contra o total impresso.

Nao ha coluna de PIN: o cabecalho 'Pin Number' aparece nas CIVs de motor, mas
nenhum documento do corpus traz valor nela. Coluna que nunca se preenche e
pior que coluna ausente -- quando aparecer um exemplo, ela entra com evidencia.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoice_part_number_items",
        sa.Column("serial_number", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_invoice_part_number_items_serial_number",
        "invoice_part_number_items",
        ["serial_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_part_number_items_serial_number",
        table_name="invoice_part_number_items",
    )
    op.drop_column("invoice_part_number_items", "serial_number")
