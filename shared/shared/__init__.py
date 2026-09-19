"""Domínio compartilhado do CAT Document Reader.

Importado tanto pelo backend (FastAPI) quanto pela function (worker de IA):
- config: settings lidas do ambiente / .env
- db:     engine + fábrica de sessões SQLAlchemy
- models: tabelas (invoices, invoice_part_number_items, invoice_events)
- storage: cliente de Blob (Azurite local / Azure real, mesma interface)
"""
