"""Duplicata contra Postgres de verdade -- quem decide e a consulta, nao a regex.

Precisa de banco: e o unico dos tres check_*.py que precisa. Roda com o schema
ja migrado (alembic upgrade head) e usa DATABASE_URL.

    DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/documentreader \
        python check_dedupe.py

Apaga TODOS os documentos do banco que apontar. Aponte para uma base de teste.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.models import Document, DocumentStatus, Invoice
from shared.dedupe import find_original, normalise_invoice_number, normalise_supplier

URL = os.environ.get("DATABASE_URL")
if not URL:
    sys.exit("DATABASE_URL nao definida -- este check precisa de banco")
engine = create_engine(URL)

falhas = []


def check(label, got, expected):
    ok = got == expected
    print(("  OK   " if ok else "  FALHA") + f" {label:<46} -> {got!r}   esperado {expected!r}")
    if not ok:
        falhas.append(label)


def grava(db, nome_doc, numero, fornecedor):
    """Mesmo caminho do doc_worker: chaves, flush, busca, marca."""
    doc = Document(status=DocumentStatus.extracted, source_filename=nome_doc)
    db.add(doc)
    inv = Invoice(
        invoice_number=numero,
        supplier=fornecedor,
        invoice_number_key=normalise_invoice_number(numero),
        supplier_key=normalise_supplier(fornecedor),
    )
    doc.invoices.append(inv)
    db.flush()
    original = find_original(
        db,
        invoice_number_key=inv.invoice_number_key,
        supplier_key=inv.supplier_key,
        exclude_invoice_id=inv.id,
    )
    if original is not None:
        inv.duplicate_of_id = original.id
    db.commit()
    return inv


with Session(engine) as db:
    for inv in db.query(Invoice).all():
        inv.duplicate_of_id = None
    db.commit()
    db.query(Document).delete()
    db.commit()

    print("=== a primeira entrada nunca e marcada ===")
    a = grava(db, "doc-a.pdf", "739 /01", "TECNORD s.r.l.")
    check("original", a.duplicate_of_id, None)

    print("=== a copia e marcada, mesmo escrita diferente ===")
    b = grava(db, "doc-b.pdf", "739/01", "TECNORD S.R.L")
    check("copia aponta para a original", b.duplicate_of_id, a.id)

    print("=== a terceira aponta para a PRIMEIRA, nao para a segunda ===")
    c = grava(db, "doc-c.pdf", "739 - 01", "Tecnord SRL")
    check("cadeia fica plana", c.duplicate_of_id, a.id)

    print("=== mesmo numero, outro fornecedor: nao e duplicata ===")
    d = grava(db, "doc-d.pdf", "739 /01", "Groeneveld-BEKA GmbH")
    check("fornecedor diferente", d.duplicate_of_id, None)

    print("=== outro numero, mesmo fornecedor: nao e duplicata ===")
    e = grava(db, "doc-e.pdf", "26VX0515", "TECNORD s.r.l.")
    check("numero diferente", e.duplicate_of_id, None)

    print("=== sem numero: nao casa por ausencia ===")
    f1 = grava(db, "doc-f.pdf", None, "ROTOTECH S.P.A.")
    f2 = grava(db, "doc-g.pdf", None, "ROTOTECH S.P.A.")
    check("duas sem numero nao sao duplicatas", f2.duplicate_of_id, None)

    print("=== sem fornecedor: idem ===")
    g1 = grava(db, "doc-h.pdf", "AB-100", None)
    g2 = grava(db, "doc-i.pdf", "AB-100", None)
    check("duas sem fornecedor nao sao duplicatas", g2.duplicate_of_id, None)

    print("=== duas faturas repetidas DENTRO do mesmo documento ===")
    doc = Document(status=DocumentStatus.extracted, source_filename="civ.pdf")
    db.add(doc)
    marcadas = []
    for numero, fornecedor in [("VE 3246", "Dana Graziano S.r.l."),
                               ("VE3246", "DANA GRAZIANO SRL")]:
        inv = Invoice(
            invoice_number=numero, supplier=fornecedor,
            invoice_number_key=normalise_invoice_number(numero),
            supplier_key=normalise_supplier(fornecedor),
        )
        doc.invoices.append(inv)
        db.flush()
        orig = find_original(
            db, invoice_number_key=inv.invoice_number_key,
            supplier_key=inv.supplier_key, exclude_invoice_id=inv.id,
        )
        if orig is not None:
            inv.duplicate_of_id = orig.id
        marcadas.append(inv)
    db.commit()
    check("a 1a do documento nao e marcada", marcadas[0].duplicate_of_id, None)
    check("a 2a do documento e marcada", marcadas[1].duplicate_of_id, marcadas[0].id)

    print("=== reprocessar o MESMO documento nao o torna duplicata de si ===")
    doc_r = db.get(Document, a.document_id)
    doc_r.invoices.clear()
    inv = Invoice(
        invoice_number="739 /01", supplier="TECNORD s.r.l.",
        invoice_number_key=normalise_invoice_number("739 /01"),
        supplier_key=normalise_supplier("TECNORD s.r.l."),
    )
    doc_r.invoices.append(inv)
    db.flush()
    orig = find_original(
        db, invoice_number_key=inv.invoice_number_key,
        supplier_key=inv.supplier_key, exclude_invoice_id=inv.id,
    )
    # b e c apontavam para a invoice apagada; o ON DELETE SET NULL as libera, e
    # a mais antiga delas vira a nova referencia. O documento reprocessado passa
    # a ser a copia -- correto: ele deixou de ser o primeiro a registrar a chave.
    check("encontra uma referencia viva", orig is not None, True)
    check("a referencia nao e ele mesmo", orig.id != inv.id if orig else False, True)
    db.rollback()

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): {falhas}")
    sys.exit(1)
print("tudo certo")
