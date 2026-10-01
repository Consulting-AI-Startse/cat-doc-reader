"""confianca por campo

A confianca do documento era a auto-reportada pelo modelo -- o extractor usa
prebuilt-layout, que nao devolve 'documents', entao o pre-passe vinha nulo e
sobrava so o numero do GPT. Um documento ja voltou com 0.95 e quatro defeitos.

Agora cada campo ganha nota do OCR. Medido no CIV (52 campos, rodadas de 10/09
e 01/10): marca exatamente os dois defeitos reais do documento, '26-2100870' /
'26-2I00870' e 'QIPPO1280' / 'QIPP01280', e nenhum campo bom.

A nota por campo vai em JSONB, na linha e no cabecalho da invoice. Os
agregados ficam em coluna na invoice porque o relatorio por fornecedor agrupa
por eles; recalcula-los do JSONB a cada consulta seria varrer todas as linhas.

Sem backfill: o indice de palavras vive so em memoria durante a extracao, e as
invoices antigas nao tem como ser pontuadas. Ficam nulas, e o relatorio as
conta como "sem dado".

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("field_confidence", JSONB(), nullable=True))
    op.add_column("invoices", sa.Column("min_field_confidence", sa.Float(), nullable=True))
    op.add_column("invoices", sa.Column("mean_field_confidence", sa.Float(), nullable=True))
    op.add_column("invoices", sa.Column("flagged_fields", sa.Integer(), nullable=True))
    op.add_column("invoices", sa.Column("corrected_fields", sa.Integer(), nullable=True))
    op.add_column(
        "invoice_part_number_items",
        sa.Column("field_confidence", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoice_part_number_items", "field_confidence")
    op.drop_column("invoices", "corrected_fields")
    op.drop_column("invoices", "flagged_fields")
    op.drop_column("invoices", "mean_field_confidence")
    op.drop_column("invoices", "min_field_confidence")
    op.drop_column("invoices", "field_confidence")
