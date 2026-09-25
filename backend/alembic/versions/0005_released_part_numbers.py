"""lista de part numbers liberados e as regras de serial

A decisao do cliente e que a lista e a fonte da verdade: o que nao esta nela
nao e part number. Isso rebaixa o PART_NUMBER_RE a pre-filtro barato.

Medido na PN Liberados.xlsx real (206.769 linhas): a tabela ocupa 18 MB com
indices, carrega em 0,42 s por COPY, e a consulta de ~50 part numbers leva
0,43 ms de ida e volta, com Index Scan na PK.

A coluna requires_serial e derivada das regras em serial_rules, nao importada.
Recalcular a tabela inteira custa 0,81 s -- barato o bastante para rodar toda
vez que a regra mudar, e e o que deixa a consulta em tempo real ser um simples
teste de coluna.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "released_part_numbers",
        sa.Column("part_number", sa.String(length=32), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column(
            "requires_serial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("import_batch", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("part_number"),
    )
    # Indice parcial: as peças que exigem serial sao ~600 de 206 mil, entao o
    # indice cheio seria quase todo composto de 'false' que ninguem consulta.
    op.create_index(
        "ix_released_part_numbers_requires_serial",
        "released_part_numbers",
        ["requires_serial"],
        postgresql_where=sa.text("requires_serial"),
    )

    op.create_table(
        "serial_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "substrings",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "manual_part_numbers",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_serial_rules_singleton"),
    )
    # A linha unica nasce junto: sem ela a tela teria de tratar "ainda nao
    # existe" como caso separado de "esta vazia", que e a mesma coisa.
    op.execute("INSERT INTO serial_rules (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("serial_rules")
    op.drop_index(
        "ix_released_part_numbers_requires_serial", table_name="released_part_numbers"
    )
    op.drop_table("released_part_numbers")
