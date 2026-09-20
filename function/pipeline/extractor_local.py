"""Extractor local, baseado em Docling. SO PARA DESENVOLVIMENTO.

Este arquivo NAO vai para o repo da Caterpillar nem para o Function App.
Existe para exercitar o structurer (prompt + parsing do LLM) com texto real de
documento, sem depender do Document Intelligence e sem gastar chamada paga.

Como fica fora do deploy:
  - a dependencia esta em requirements-local.txt, nunca em requirements.txt,
    que e o arquivo que o Oryx usa no build remoto;
  - .funcignore exclui este modulo e aquele requirements do zip;
  - build_extractor() so importa daqui quando USE_LOCAL_EXTRACTOR=true, e essa
    setting nao existe no Function App.

Para remover tudo: apague este arquivo, requirements-local.txt, as duas linhas
do .funcignore, o bloco de tres linhas em doc_worker.build_extractor() e a
setting use_local_extractor em shared/config.py.

LIMITES MEDIDOS (nao sao bugs, sao o motivo de isto ser so teste):
  - PDF nativo (com camada de texto): otimo. A fatura turca sai com a tabela
    de itens em markdown, part numbers 2+4 ('7G-5837') e decimais europeus
    intactos.
  - Pagina escaneada e DE PE: otimo. Nas paginas 1-3 do CIV o ocr_score deu
    0.997 e saiu 7 dos 8 part numbers.
  - Pagina escaneada e GIRADA: falha completa. Nas paginas 4-6 do CIV, que
    estao a -179.8 graus, o RapidOCR devolve vazio -- 62 caracteres e nenhum
    part number. O Document Intelligence rotaciona sozinho e nao perde nada;
    o Docling nao. Por isso existe a guarda de conteudo magro abaixo: melhor
    estourar do que entregar texto vazio para o LLM inventar em cima.
"""
from __future__ import annotations

import io
import logging
import math
from typing import Any

from pipeline.extractor import DocumentExtractor

logger = logging.getLogger("extractor_local")

# Abaixo disto o OCR quase certamente falhou (paginas giradas, PDF so imagem).
# O CIV inteiro, que o Docling nao consegue ler, da ~133 chars/pagina; a fatura
# turca, que ele le bem, da ~1800 numa pagina so.
MIN_CHARS_PER_PAGE = 150


def _clean(value) -> float | None:
    """Docling devolve nan quando nem tentou pontuar aquela dimensao."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else round(v, 4)


class LocalExtractionFailed(RuntimeError):
    """Docling devolveu pouco ou nenhum texto. Ver o docstring do modulo."""


class DoclingExtractor(DocumentExtractor):
    """Converte o PDF em markdown localmente, no formato que o structurer espera.

    Devolve as mesmas chaves que o extractor do Document Intelligence, com duas
    ausencias assumidas: nao existe confianca por palavra nem span por palavra,
    porque o Docling so pontua por pagina. Ou seja, a confianca por campo que o
    structurer calcula a partir dos spans nao funciona neste modo.
    """

    MODEL_ID = "docling"

    def __init__(self, *, force_full_page_ocr: bool = False) -> None:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise ImportError(
                "USE_LOCAL_EXTRACTOR=true mas o docling nao esta instalado. "
                "Rode: uv pip install -r function/requirements-local.txt"
            ) from exc

        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        # force_full_page_ocr ignora a camada de texto e OCRa a pagina inteira.
        # Ajuda em PDF com camada de texto ruim e atrapalha quando ela e boa.
        options.ocr_options.force_full_page_ocr = force_full_page_ocr

        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
        self._stream_cls = self._document_stream_cls()

    @staticmethod
    def _document_stream_cls():
        from docling.datamodel.base_models import DocumentStream

        return DocumentStream

    def extract(self, content: bytes) -> dict[str, Any]:
        source = self._stream_cls(name="upload.pdf", stream=io.BytesIO(content))
        result = self._converter.convert(source)
        document = result.document

        text = document.export_to_markdown()
        pages, quality = _pages_and_quality(result, len(text))
        page_count = quality["page_count"] or 1

        if len(text) < MIN_CHARS_PER_PAGE * page_count:
            raise LocalExtractionFailed(
                "Docling extraiu %d chars em %d pagina(s) (%.0f por pagina, minimo %d). "
                "Provavel pagina girada ou so imagem -- o Docling nao rotaciona. "
                "Scores: %s"
                % (
                    len(text),
                    page_count,
                    len(text) / page_count,
                    MIN_CHARS_PER_PAGE,
                    quality["scores"],
                )
            )

        logger.info(
            "docling: %d paginas, %d chars, %d tabelas, scores %s",
            page_count,
            len(text),
            len(document.tables or []),
            quality["scores"],
        )

        return {
            "model": self.MODEL_ID,
            # Sem confianca comparavel a do Document Intelligence: o Docling
            # pontua por pagina, nao por campo. Deixar None evita que um score
            # de OCR seja lido como confianca de extracao la no _normalise.
            "confidence": None,
            # O Docling nao tem modelo de invoice, entao nao ha pre-pass. O
            # structurer trata lista vazia normalmente.
            "invoices": [],
            "content": text,
            "tables": _tables_of(document),
            "pages": pages,
            "low_confidence_words": [],
            "quality": quality,
        }


def _tables_of(document) -> list[dict[str, Any]]:
    """Mesma forma que a do Document Intelligence, para tables_summary funcionar."""
    out = []
    for table in (document.tables or []):
        data = getattr(table, "data", None)
        cells = []
        for cell in (getattr(data, "table_cells", None) or []):
            cells.append({
                "row": getattr(cell, "start_row_offset_idx", None),
                "col": getattr(cell, "start_col_offset_idx", None),
                "row_span": getattr(cell, "row_span", None) or 1,
                "col_span": getattr(cell, "col_span", None) or 1,
                "kind": "columnHeader" if getattr(cell, "column_header", False) else "content",
                "content": getattr(cell, "text", None),
                "spans": [],
            })
        out.append({
            "rows": getattr(data, "num_rows", None),
            "columns": getattr(data, "num_cols", None),
            "pages": sorted({p.page_no for p in (getattr(table, "prov", None) or [])}),
            "cells": cells,
        })
    return out


def _pages_and_quality(result, text_length: int) -> tuple[list[dict], dict]:
    """Resumo por pagina a partir dos scores do Docling.

    Nao ha contagem de palavras nem confianca por palavra aqui -- o que o
    Docling da e layout/ocr/table/parse por pagina, numa escala que nao e a
    mesma do Document Intelligence. As chaves seguem separadas de proposito,
    para ninguem comparar os dois numeros como se fossem a mesma coisa.
    """
    report = getattr(result, "confidence", None)
    per_page = getattr(report, "pages", None) or {}

    pages = []
    for page_no in sorted(per_page):
        scores = per_page[page_no]
        pages.append({
            "page_number": page_no,
            "layout_score": _clean(getattr(scores, "layout_score", None)),
            "ocr_score": _clean(getattr(scores, "ocr_score", None)),
            "table_score": _clean(getattr(scores, "table_score", None)),
            "parse_score": _clean(getattr(scores, "parse_score", None)),
        })

    page_count = len(getattr(result, "pages", None) or []) or len(pages)
    quality = {
        "source": "docling",
        "page_count": page_count,
        "content_chars": text_length,
        "chars_per_page": round(text_length / page_count, 1) if page_count else None,
        "scores": {
            "layout": _clean(getattr(report, "layout_score", None)),
            "ocr": _clean(getattr(report, "ocr_score", None)),
            "table": _clean(getattr(report, "table_score", None)),
            "parse": _clean(getattr(report, "parse_score", None)),
        },
        # Deixado explicito para nao parecer omissao: o modo local nao alimenta
        # a confianca por campo, que depende de span e confianca por palavra.
        "word_confidence_available": False,
    }
    return pages, quality
