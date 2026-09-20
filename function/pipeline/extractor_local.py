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

Para remover tudo: veja docs/modo-local.md.

DOIS CAMINHOS, do barato para o caro
------------------------------------
1. PDF direto. O Docling usa a camada de texto quando existe. E rapido e sai
   perfeito em PDF nativo -- a fatura turca sai em 15 s com a tabela de itens
   em markdown, '7G-5837' e '6.398,88' intactos. E o caminho padrao.

2. Pagina renderizada como imagem. Usado so quando (1) devolve pouco texto.
   Medido no CIV, paginas 4-6:

       Docling pelo PDF .............    62 chars,  0 tabelas
       imagem, sem girar ............ 1.878 chars,  0 tabelas, ordem invertida
       imagem + 180 graus ........... 2.920 chars,  2 tabelas, ordem correta

   O caminho PDF do Docling perde essas paginas por completo, e nao e questao
   de resolucao: images_scale 1.0 e 2.0 dao os mesmos 62 chars.

SOBRE A ROTACAO -- limite conhecido
-----------------------------------
Girar a pagina nao muda o reconhecimento dos caracteres: o RapidOCR tem
classificador de angulo por linha e acerta as letras de qualquer jeito. Muda a
ORDEM de leitura e o layout. Numa pagina a 180 graus sai
'35.564,40 Invoice Amount Payable' em vez de 'Invoice Amount Payable 35.564,40',
e o modelo de tabela nao acha tabela nenhuma.

Medido na pagina 4 do CIV: sem girar 1.878 chars e 0 tabelas; girada 180 graus
2.920 chars e 2 tabelas, com a ordem certa.

Corrigir isso automaticamente exigiria uma conversao por orientacao, e cada
conversao do Docling nao devolve a memoria: com 7 GB, duas orientacoes por
pagina ja levam a OOM (testado a 150 e a 100 dpi). Por isso a sonda NAO foi
para o codigo. O efeito pratico e que pagina girada sai com o texto certo mas
fora de ordem e sem tabela -- o que ainda assim recupera os part numbers.
"""
from __future__ import annotations

import gc
import io
import logging
import math
from typing import Any

from pipeline.extractor import DocumentExtractor

logger = logging.getLogger("extractor_local")

# Abaixo disto o texto da pagina nao presta: ou o caminho PDF falhou, ou a
# pagina e imagem pura. O CIV inteiro pelo caminho PDF da ~133 chars/pagina;
# a fatura turca, que sai bem, da ~1800 numa pagina so.
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

    def __init__(
        self,
        *,
        force_full_page_ocr: bool = False,
        dpi: int = 150,
        fix_rotation: bool = True,
    ) -> None:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import (
                DocumentConverter,
                ImageFormatOption,
                PdfFormatOption,
            )
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

        self._dpi = dpi
        self._fix_rotation = fix_rotation
        self._orienter = None
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=options),
            }
        )

    # -- caminho 1: PDF direto -------------------------------------------------

    def _convert_pdf(self, content: bytes):
        from docling.datamodel.base_models import DocumentStream

        source = DocumentStream(name="upload.pdf", stream=io.BytesIO(content))
        return self._converter.convert(source)

    # -- caminho 2: pagina a pagina, como imagem -------------------------------

    def _convert_images(self, content: bytes, apenas: list[int] | None = None):
        """Renderiza as paginas pedidas e converte cada uma como imagem.

        Devolve (por_pagina, tabelas, paginas). Cada pagina vira uma conversao
        propria: e o preco de pular o caminho PDF do Docling.
        """
        import pypdfium2 as pdfium
        from docling.datamodel.base_models import DocumentStream

        pdf = pdfium.PdfDocument(io.BytesIO(content))
        alvo = apenas or list(range(1, len(pdf) + 1))
        por_pagina, tabelas, paginas = {}, [], []

        for numero in alvo:
            indice = numero - 1
            # render() ja aplica o /Rotate declarado no PDF; o que sobra e a
            # rotacao que veio queimada no bitmap do scan.
            bitmap = pdf[indice].render(scale=self._dpi / 72)
            graus = 0
            if self._fix_rotation:
                graus = self._rotacao_da_pagina(bitmap.to_numpy()[..., :3])
            imagem = bitmap.to_pil()
            if graus:
                imagem = imagem.rotate(graus, expand=True)
            del bitmap
            score, markdown, tabs = self._convert_image(imagem, numero)
            del imagem
            gc.collect()

            por_pagina[numero] = markdown
            tabelas.extend(tabs)
            paginas.append({
                "page_number": numero,
                "rotation_applied": graus,
                "chars": len(markdown),
                "tables": len(tabs),
            })
            logger.info(
                "pagina %d por imagem: girada %d, %d chars, %d tabelas",
                numero, graus, len(markdown), len(tabs),
            )

        return por_pagina, tabelas, paginas

    def _rotacao_da_pagina(self, img_np) -> int:
        """0 ou 180, pelo classificador de angulo do RapidOCR.

        O classificador existe para dizer se uma LINHA de texto esta invertida.
        Detecta as caixas de texto, recorta ate 25 e tira a maioria. Nao envolve
        o Docling, entao nao custa memoria: ~1 s por pagina.

        Medido contra os angulos do Document Intelligence nas 30 paginas do CIV
        que nao sao 90/270: 26 acertos, 0 erros, 5 sem texto. A separacao e
        limpa -- pagina de pe da fracao de invertidas entre 0.00 e 0.16, pagina
        virada entre 0.76 e 0.96.
        """
        if self._orienter is None:
            from rapidocr import EngineType, RapidOCR

            self._orienter = RapidOCR(params={
                "Det.engine_type": EngineType.TORCH,
                "Cls.engine_type": EngineType.TORCH,
                "Rec.engine_type": EngineType.TORCH,
            })
        import numpy as np

        try:
            boxes = self._orienter.text_det(img_np).boxes
        except Exception as exc:
            logger.warning("deteccao de orientacao falhou: %s", exc)
            return 0
        if boxes is None or len(boxes) == 0:
            return 0

        recortes = []
        for caixa in boxes[:25]:
            pts = np.array(caixa, dtype=np.float32)
            y0, y1 = int(pts[:, 1].min()), int(pts[:, 1].max())
            x0, x1 = int(pts[:, 0].min()), int(pts[:, 0].max())
            corte = img_np[y0:y1, x0:x1]
            if corte.size and corte.shape[0] > 6 and corte.shape[1] > 6:
                recortes.append(corte)
        if not recortes:
            return 0

        try:
            resultado = self._orienter.text_cls(recortes).cls_res
        except Exception as exc:
            logger.warning("classificador de angulo falhou: %s", exc)
            return 0
        invertidas = sum(1 for r in resultado if str(r[0]) == "180")
        return 180 if invertidas > len(resultado) / 2 else 0

    def _convert_image(self, imagem, numero: int):
        """(score, markdown, tabelas). Nao devolve o Document: segurar quatro
        deles, um por orientacao, estourava a memoria."""
        from docling.datamodel.base_models import DocumentStream

        buf = io.BytesIO()
        imagem.save(buf, format="PNG")
        buf.seek(0)
        try:
            doc = self._converter.convert(
                DocumentStream(name=f"p{numero}.png", stream=buf)
            ).document
        except Exception as exc:
            logger.warning("pagina %d falhou na conversao por imagem: %s", numero, exc)
            return -1.0, "", []
        markdown = doc.export_to_markdown()
        tabs = [_table_of(t, numero) for t in (doc.tables or [])]
        del doc
        # O sinal de orientacao certa e o LAYOUT, nao a confianca do OCR:
        # tabela encontrada vale muito mais que um punhado de caracteres.
        return len(tabs) * 1000 + len(markdown), markdown, tabs

    # -- contrato --------------------------------------------------------------

    def extract(self, content: bytes) -> dict[str, Any]:
        resultado = self._convert_pdf(content)
        texto = resultado.document.export_to_markdown()
        paginas, quality = _pages_and_quality(resultado, len(texto))
        total = quality["page_count"] or 1
        tabelas = _tables_of(resultado.document)
        quality["path"] = "pdf"

        # Fallback POR PAGINA, nao pelo documento. A media enganava: no CIV as
        # paginas 1 e 2 tem texto de verdade (913 e 1011 chars) e as outras 33
        # vem vazias, o que derruba a media para 133 e reprovaria o documento
        # inteiro -- inclusive as duas paginas boas.
        magras = [n for n, c in _chars_por_pagina(resultado.document, total).items()
                  if c < MIN_CHARS_PER_PAGE]
        if magras:
            logger.info(
                "caminho PDF deixou %d de %d paginas magras; refazendo por imagem: %s",
                len(magras), total, magras[:10],
            )
            por_pagina, tabelas_img, paginas_img = self._convert_images(content, magras)
            recuperado = [
                f"<!-- pagina {n} (OCR) -->\n\n{md}"
                for n, md in sorted(por_pagina.items()) if md.strip()
            ]
            if recuperado:
                texto = texto + "\n\n" + "\n\n".join(recuperado)
                tabelas = tabelas + tabelas_img
                paginas = paginas + paginas_img
                quality = dict(
                    quality,
                    path="pdf+image",
                    content_chars=len(texto),
                    chars_per_page=round(len(texto) / total, 1),
                    pages_recovered_by_image=len(recuperado),
                    rotations_applied={
                        p["page_number"]: p["rotation_applied"]
                        for p in paginas_img if p.get("rotation_applied")
                    },
                )

        if len(texto) < MIN_CHARS_PER_PAGE * total:
            raise LocalExtractionFailed(
                "Docling extraiu %d chars em %d pagina(s) (%.0f por pagina, minimo %d) "
                "mesmo apos o caminho por imagem. Scores: %s%s"
                % (
                    len(texto), total, len(texto) / total, MIN_CHARS_PER_PAGE,
                    quality.get("scores"),
                    "",
                )
            )

        logger.info(
            "docling (%s): %d paginas, %d chars, %d tabelas",
            quality["path"], total, len(texto), len(tabelas),
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
            "content": texto,
            "tables": tabelas,
            "pages": paginas,
            "low_confidence_words": [],
            "quality": quality,
        }


def _chars_por_pagina(document, total: int) -> dict[int, int]:
    """Quantos caracteres o caminho PDF achou em cada pagina.

    Vem da provenance dos itens de texto; pagina sem item nenhum conta zero.
    """
    contagem = {n: 0 for n in range(1, total + 1)}
    for item in (getattr(document, "texts", None) or []):
        texto = getattr(item, "text", "") or ""
        for prov in (getattr(item, "prov", None) or []):
            n = getattr(prov, "page_no", None)
            if n in contagem:
                contagem[n] += len(texto)
    return contagem


def _table_of(table, page_number: int | None = None) -> dict[str, Any]:
    """Mesma forma que a do Document Intelligence, para tables_summary funcionar."""
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
    if page_number is not None:
        paginas = [page_number]
    else:
        paginas = sorted({p.page_no for p in (getattr(table, "prov", None) or [])})
    return {
        "rows": getattr(data, "num_rows", None),
        "columns": getattr(data, "num_cols", None),
        "pages": paginas,
        "cells": cells,
    }


def _tables_of(document) -> list[dict[str, Any]]:
    return [_table_of(t) for t in (document.tables or [])]


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
