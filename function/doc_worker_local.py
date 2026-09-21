"""Builders de desenvolvimento local do pipeline.

Existe para manter o `doc_worker.py` **identico nos dois repos**. Antes os
blocos de modo local moravam la dentro, e por isso o arquivo divergia do repo da
Caterpillar em ~24 linhas -- nenhum `git diff` dele aplicava la, o que ja custou
uma leva inteira de espelhamento.

Mesmo padrao de `pipeline/extractor_local.py` e `structurer_local.py`: nunca vai
para o Function App. Tres barreiras independentes garantem isso -- o
`.funcignore` exclui este arquivo do zip, a dependencia do Docling so esta em
`requirements-local.txt`, e as settings `USE_LOCAL_*` nao existem la.

Cada builder devolve `None` quando a setting correspondente esta desligada, e ai
o `doc_worker` segue para o caminho de producao.
"""

from __future__ import annotations

from shared.config import settings


def build_extractor():
    """Docling no lugar do Document Intelligence.

    Vem ANTES do use_real_services de proposito: o uso que importa e Docling +
    Azure OpenAI de verdade, para testar o parsing do LLM com texto real sem
    gastar Document Intelligence.
    """
    if not settings.use_local_extractor:
        return None

    from pipeline.extractor_local import DoclingExtractor

    return DoclingExtractor(
        force_full_page_ocr=settings.local_extractor_force_ocr,
        dpi=settings.local_extractor_dpi,
        fix_rotation=settings.local_extractor_fix_rotation,
    )


def build_structurer():
    """OpenRouter no lugar do Azure OpenAI. Decide so o structurer."""
    if not settings.use_local_structurer:
        return None

    from pipeline.structurer_local import OpenRouterStructurer

    return OpenRouterStructurer(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        max_tokens=settings.openrouter_max_tokens,
    )
