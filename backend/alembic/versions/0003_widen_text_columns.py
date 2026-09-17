"""campos livres viram texto (incoterm, embalagem, partes envolvidas, moeda)

Descoberto num documento real: um incoterm veio como
"FCA ST QUENTIN FALLAVIER (INCOTERMS 2020)" -- 41 caracteres numa coluna de 16,
o que derrubou a gravacao da fatura inteira. Estes campos sao texto livre escrito
pelo fornecedor; qualquer limite que escolhermos e um palpite que algum
fornecedor vai estourar. Em Postgres, TEXT e VARCHAR(n) sao guardados igual --
o limite so acrescenta uma verificacao.

"currency" continua limitado porque 3 letras e uma regra de negocio, mas sobe
para 16: um documento traz ": CURRENCY : U. S . DOLLARS" por extenso.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TO_TEXT = [
    ("incoterm", 16),
    ("packaging", 128),
    ("country_of_origin", 128),
    ("exporter", 256),
    ("supplier", 256),
    ("manufacturer", 256),
]


def upgrade() -> None:
    for column, _ in _TO_TEXT:
        op.alter_column(
            "invoice_part_number_items",
            column,
            existing_type=sa.String(),
            type_=sa.Text(),
            existing_nullable=True,
        )
    op.alter_column(
        "invoices",
        "currency",
        existing_type=sa.String(length=3),
        type_=sa.String(length=16),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "invoices",
        "currency",
        existing_type=sa.String(length=16),
        type_=sa.String(length=3),
        existing_nullable=True,
        postgresql_using="left(currency, 3)",
    )
    for column, length in _TO_TEXT:
        op.alter_column(
            "invoice_part_number_items",
            column,
            existing_type=sa.Text(),
            type_=sa.String(length=length),
            existing_nullable=True,
            postgresql_using=f"left({column}, {length})",
        )