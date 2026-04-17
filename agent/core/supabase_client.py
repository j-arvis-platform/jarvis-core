"""Client Supabase — 1 instance par tenant, jamais mutualisé."""

import os

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_clients: dict[str, Client] = {}


def get_supabase(tenant_id: str | None = None) -> Client:
    """Retourne le client Supabase pour un tenant donné.

    En V2 simple (1 tenant), utilise les variables d'env directement.
    En multi-tenant, les clés sont dans tenant-{id}/.env.
    """
    cache_key = tenant_id or "default"

    if cache_key not in _clients:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _clients[cache_key] = create_client(url, key)

    return _clients[cache_key]


def query_table(table: str, filters: dict | None = None, tenant_id: str | None = None):
    """Query helper — select avec filtres optionnels."""
    client = get_supabase(tenant_id)
    query = client.table(table).select("*")

    if filters:
        for col, val in filters.items():
            query = query.eq(col, val)

    return query.execute()


def insert_row(table: str, data: dict, tenant_id: str | None = None):
    """Insert une ligne dans une table."""
    client = get_supabase(tenant_id)
    return client.table(table).insert(data).execute()


def update_row(table: str, row_id: str, data: dict, tenant_id: str | None = None):
    """Update une ligne par son id."""
    client = get_supabase(tenant_id)
    return client.table(table).update(data).eq("id", row_id).execute()
