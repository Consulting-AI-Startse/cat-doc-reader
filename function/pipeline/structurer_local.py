"""Structurer local, via OpenRouter. SO PARA DESENVOLVIMENTO.

Este arquivo NAO vai para o repo da Caterpillar nem para o Function App.
Existe para exercitar o prompt e o parsing com um LLM de verdade, sem depender
do Azure OpenAI da CAT nem da rede dela.

Nao ha dependencia nova: o pacote `openai` ja esta em requirements.txt por
causa do Azure, e o OpenRouter fala a mesma API. Por isso a classe inteira e
so a troca do cliente -- `structure()` vem herdado sem uma linha alterada, de
proposito. O que esta sendo testado tem de ser o prompt e o parsing de
producao, nao uma copia deles que pode divergir:

  _SYSTEM_PROMPT, _USER_TEMPLATE, _cat_invoice_numbers, _check_lines,
  _classify_part_number, _landed e _normalise sao os mesmos.

Como fica fora do deploy:
  - .funcignore exclui este modulo do zip;
  - build_structurer() so importa daqui quando USE_LOCAL_STRUCTURER=true, e
    essa setting nao existe no Function App;
  - a chave sai de OPENROUTER_API_KEY, no ambiente ou no .env.local, que o
    .gitignore ja cobre.

AVISO DE DADO: isto envia o texto do documento -- part numbers, precos e
condicoes comerciais de fornecedores da Caterpillar -- para uma API de
terceiros, que roteia para o provedor do modelo escolhido. Use so com o corpus
que ja esta na sua maquina e so com aval da StartSe. Ver docs/modo-local.md.

Para remover tudo: apague este arquivo, a linha do .funcignore, o bloco de
tres linhas em doc_worker.build_structurer() e as quatro settings
openrouter_*/use_local_structurer em shared/config.py.
"""
from __future__ import annotations

import logging

from pipeline.structurer import AzureOpenAIStructurer

logger = logging.getLogger("structurer_local")

# Montado em pedacos pelo mesmo motivo do _AOAI_SCOPE: filtros de email
# reescrevem URLs literais no codigo e corrompem o endereco.
_OPENROUTER_BASE = "https" + "://" + ".".join(["openrouter", "ai"]) + "/api/v1"

# response_format={"type":"json_object"} nao e suportado por todo modelo do
# OpenRouter. Estes sao os que sabemos que aceitam; para qualquer outro a
# classe avisa em vez de deixar o modelo devolver JSON malformado no meio da
# corrida. A lista e um alerta, nao uma trava.
_JSON_MODE_KNOWN_GOOD = (
    "openai/",
    "anthropic/",
    "google/gemini",
    "mistralai/",
)


class OpenRouterStructurer(AzureOpenAIStructurer):
    """Mesma logica do structurer de producao, apontando para o OpenRouter.

    Herda `structure()` inteiro. So o cliente e o nome do modelo mudam, que e
    exatamente o que a classe base usa: `self._client` e `self._deployment`.
    """

    def __init__(self, api_key: str, model: str, max_tokens: int = 16000) -> None:
        from openai import OpenAI

        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY nao configurada. Ponha no .env.local "
                "(ja ignorado pelo git) ou exporte no ambiente."
            )
        if not model:
            raise ValueError("OPENROUTER_MODEL nao configurado")

        if not model.startswith(_JSON_MODE_KNOWN_GOOD):
            logger.warning(
                "modelo '%s' nao esta na lista de modelos com modo JSON confirmado %s. "
                "Se o parsing falhar com JSONDecodeError, o motivo e provavelmente esse.",
                model,
                list(_JSON_MODE_KNOWN_GOOD),
            )

        self._deployment = model
        self._max_tokens = max_tokens
        self._client = OpenAI(base_url=_OPENROUTER_BASE, api_key=api_key)
        logger.info("structurer local via OpenRouter, modelo %s", model)
