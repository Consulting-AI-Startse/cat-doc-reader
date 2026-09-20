from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env.local vem depois e tem precedencia sobre .env: e onde ficam segredos
    # de desenvolvimento que nao podem existir em nenhum ambiente da CAT, como a
    # chave do OpenRouter. Ja esta coberto pelo .gitignore (.env.*).
    # Variavel de ambiente continua vencendo os dois.
    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), extra="ignore")

    database_url: str = "postgresql+psycopg://invoice:invoice@localhost:5432/documentreader"
    db_use_entra_token: bool = False

    azure_storage_connection_string: str = (
        "DefaultEndpointsProtocol=http;"
        "AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq"
        "/K1SZFPTOtr/KBHBeksoGMGw==;"
        "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    )
    azure_storage_account_url: str = ""
    blob_container_name: str = "invoices"

    use_real_services: bool = False

    # Extractor local de desenvolvimento (Docling). Nao existe como app setting
    # no Function App -- e deliberado, ver docs/modo-local.md. Tem
    # precedencia sobre use_real_services na escolha do extractor, e so do
    # extractor: com os dois ligados roda Docling + Azure OpenAI de verdade,
    # que e o combo para testar o parsing do LLM sem gastar Doc Intelligence.
    use_local_extractor: bool = False
    local_extractor_force_ocr: bool = False
    # DPI do fallback por imagem, quando o caminho PDF do Docling nao le a pagina.
    local_extractor_dpi: int = 150

    # Structurer local de desenvolvimento (OpenRouter). Mesma logica: tem
    # precedencia sobre use_real_services e decide so o structurer. A chave sai
    # do ambiente ou do .env.local, nunca do .env versionavel.
    use_local_structurer: bool = False
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4.1"
    openrouter_max_tokens: int = 16000
    azure_docintel_endpoint: str = ""
    azure_docintel_key: str = ""
    azure_docintel_high_res: bool = True
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    # O deployment publicado e gpt-4.1. O default so entra em cena se a app
    # setting sumir -- e ja aconteceu num run de infraestrutura. Deixar 'gpt-4o'
    # aqui fazia o codigo cair calado num deployment que nem existe no recurso.
    azure_openai_deployment: str = "gpt-4.1"
    azure_openai_api_version: str = "2024-10-21"

    function_url: str = ""
    function_key: str = ""

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
