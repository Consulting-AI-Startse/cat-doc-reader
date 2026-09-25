"""fornecedor sobe para a fatura e ganha chave de duplicata

A premissa do cliente pede sinalizar duplicata por (invoice + fornecedor), mas
'supplier' era coluna de invoice_part_number_items -- metade da chave morava um
nivel abaixo do que ela identifica. A tela ja contornava isso lendo
'line_items[0].supplier' e escrevendo o valor em todas as linhas de uma vez.

A condicao para subir o campo era "toda invoice tem um fornecedor so".
Conferida no CIV MRKU6295556, o documento mais dificil do corpus: 6 invoices de
6 fornecedores diferentes, cada uma com exatamente um fornecedor distinto --
inclusive a 26VX0515, que tem 3 linhas.

O backfill sobe o primeiro fornecedor nao vazio de cada fatura; o downgrade faz
o caminho inverso e copia o valor da fatura para todas as suas linhas. Nenhuma
das duas direcoes perde dado -- 'marcar, nunca descartar' vale para migracao
tambem.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-24

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("supplier", sa.Text(), nullable=True))
    op.add_column(
        "invoices", sa.Column("invoice_number_key", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "invoices", sa.Column("supplier_key", sa.String(length=128), nullable=True)
    )
    op.add_column("invoices", sa.Column("duplicate_of_id", sa.Uuid(), nullable=True))

    op.create_foreign_key(
        "fk_invoices_duplicate_of_id",
        "invoices",
        "invoices",
        ["duplicate_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_invoices_duplicate_of_id", "invoices", ["duplicate_of_id"])
    op.create_index(
        "ix_invoices_duplicate_key", "invoices", ["invoice_number_key", "supplier_key"]
    )

    # Sobe o fornecedor antes de derrubar a coluna de origem. DISTINCT ON pega
    # a primeira linha nao vazia por fatura; as chaves normalizadas ficam nulas
    # de proposito -- normalizar em SQL duplicaria a regra do shared/dedupe.py,
    # e documento reprocessado ou editado preenche a chave pelo caminho normal.
    op.execute(
        """
        UPDATE invoices AS inv
           SET supplier = src.supplier
          FROM (
                SELECT DISTINCT ON (invoice_id) invoice_id, supplier
                  FROM invoice_part_number_items
                 WHERE supplier IS NOT NULL AND btrim(supplier) <> ''
                 ORDER BY invoice_id, id
               ) AS src
         WHERE src.invoice_id = inv.id
        """
    )

    op.drop_column("invoice_part_number_items", "supplier")


def downgrade() -> None:
    op.add_column(
        "invoice_part_number_items", sa.Column("supplier", sa.Text(), nullable=True)
    )
    op.execute(
        """
        UPDATE invoice_part_number_items AS li
           SET supplier = inv.supplier
          FROM invoices AS inv
         WHERE inv.id = li.invoice_id AND inv.supplier IS NOT NULL
        """
    )

    op.drop_index("ix_invoices_duplicate_key", table_name="invoices")
    op.drop_index("ix_invoices_duplicate_of_id", table_name="invoices")
    op.drop_constraint("fk_invoices_duplicate_of_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "duplicate_of_id")
    op.drop_column("invoices", "supplier_key")
    op.drop_column("invoices", "invoice_number_key")
    op.drop_column("invoices", "supplier")
