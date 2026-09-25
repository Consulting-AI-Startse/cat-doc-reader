import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from shared.models import Base  # o schema vem do domínio compartilhado

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL vem do ambiente. O default bate com o docker-compose local, então
# `alembic upgrade head` funciona sem config extra em dev.
db_url = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://invoice:invoice@localhost:5432/documentreader"
)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # NAO injete o token do Entra aqui, por mais que pareca faltar.
    #
    # O shared/db.py tem um listener 'do_connect' que poe o token da Managed
    # Identity como senha. Copiar isso para ca parece consertar a assimetria e
    # QUEBRA a migracao na CAT: a MI tem so SELECT/INSERT/UPDATE/DELETE (secao
    # 2.4 do DEPLOY.md), entao 'ALTER TABLE' devolve
    # 'must be owner of table invoices'. Dono das tabelas e o grupo admin do
    # Entra, que foi quem rodou o db-setup-v2.sql.
    #
    # A ausencia e o que faz a migracao ser possivel: sem listener, o libpq
    # usa o PGPASSWORD do ambiente, e e por ali que entra o token do
    # administrador. Medido em 25/09 aplicando a 0004 em producao.
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
