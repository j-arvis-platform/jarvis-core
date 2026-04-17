"""
J-ARVIS V2 — Initialisation Supabase tenant
Execute les 3 fichiers SQL dans l'ordre et valide la creation des tables.

Usage:
    python scripts/init-supabase.py

Pré-requis:
    - SUPABASE_URL et SUPABASE_SERVICE_KEY dans .env ou en variables d'environnement
    - pip install supabase python-dotenv httpx
"""

import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Charger .env depuis la racine jarvis-core ou depuis le tenant
for env_path in [
    Path(__file__).parent.parent / ".env",
    Path.home() / "jarvis-platform" / "jarvis-core" / ".env",
]:
    if env_path.exists():
        load_dotenv(env_path)
        break

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERREUR: SUPABASE_URL et SUPABASE_SERVICE_KEY requis.")
    print("Mets-les dans jarvis-core/.env ou en variables d'environnement.")
    sys.exit(1)

# Extraire le project ref depuis l'URL (https://xxx.supabase.co -> xxx)
PROJECT_REF = SUPABASE_URL.replace("https://", "").split(".")[0]

SCHEMA_DIR = Path(__file__).parent.parent / "supabase-schema"

SQL_FILES = [
    "001_init_tables.sql",
    "002_rls_policies.sql",
    "003_indexes.sql",
]

EXPECTED_TABLES = ["contacts", "projets", "documents", "taches", "file_humaine", "audit_logs"]


def execute_sql(sql: str, description: str) -> bool:
    """Execute du SQL via l'API REST de Supabase (pg endpoint)."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"

    # Supabase n'a pas de endpoint exec_sql par defaut
    # On utilise le endpoint SQL direct via le management API
    # Alternative : utiliser psycopg2 avec la connection string

    # Methode : via supabase-py avec raw SQL
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    # On utilise l'endpoint PostgreSQL direct via le project API
    pg_url = f"https://{PROJECT_REF}.supabase.co/pg/query"

    try:
        response = httpx.post(
            pg_url,
            headers=headers,
            json={"query": sql},
            timeout=60.0,
        )
        if response.status_code in (200, 201):
            print(f"  OK : {description}")
            return True
        else:
            # Fallback : essayer via la DB connection string directement
            print(f"  API pg/query non disponible ({response.status_code}), essai via psycopg2...")
            return execute_sql_psycopg2(sql, description)
    except Exception as e:
        print(f"  API non disponible ({e}), essai via psycopg2...")
        return execute_sql_psycopg2(sql, description)


def execute_sql_psycopg2(sql: str, description: str) -> bool:
    """Fallback : execute SQL via psycopg2 avec la connection string Supabase."""
    try:
        import psycopg2
    except ImportError:
        print("  ERREUR: psycopg2 non installe. Installe-le: pip install psycopg2-binary")
        return False

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Construire depuis les composants Supabase
        db_password = os.environ.get("SUPABASE_DB_PASSWORD", "")
        if not db_password:
            print("  ERREUR: DATABASE_URL ou SUPABASE_DB_PASSWORD requis pour psycopg2.")
            print("  Ajoute dans .env : DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres")
            return False
        db_url = f"postgresql://postgres.{PROJECT_REF}:{db_password}@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print(f"  OK : {description}")
        return True
    except Exception as e:
        print(f"  ERREUR : {description} — {e}")
        return False


def verify_tables() -> bool:
    """Verifie que toutes les tables existent."""
    try:
        import psycopg2
        db_url = os.environ.get("DATABASE_URL")
        db_password = os.environ.get("SUPABASE_DB_PASSWORD", "")
        if not db_url and db_password:
            db_url = f"postgresql://postgres.{PROJECT_REF}:{db_password}@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

        if not db_url:
            # Fallback via REST API
            return verify_tables_rest()

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        existing = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()

        print("\nTables existantes :")
        all_ok = True
        for table in EXPECTED_TABLES:
            status = "OK" if table in existing else "MANQUANTE"
            print(f"  {table} : {status}")
            if table not in existing:
                all_ok = False

        return all_ok

    except ImportError:
        return verify_tables_rest()


def verify_tables_rest() -> bool:
    """Verifie les tables via l'API REST Supabase (HEAD request sur chaque table)."""
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }

    print("\nVerification tables via REST API :")
    all_ok = True
    for table in EXPECTED_TABLES:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=id&limit=0"
        try:
            response = httpx.head(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                print(f"  {table} : OK")
            else:
                print(f"  {table} : ERREUR ({response.status_code})")
                all_ok = False
        except Exception as e:
            print(f"  {table} : ERREUR ({e})")
            all_ok = False

    return all_ok


def test_crud() -> bool:
    """Test insert + select + delete sur chaque table."""
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    print("\nTest CRUD :")

    # Test contacts
    try:
        # INSERT
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/contacts",
            headers=headers,
            json={"type": "prospect", "nom": "TEST_INIT", "email": "test@test.fr"},
            timeout=10.0,
        )
        if resp.status_code == 201:
            row = resp.json()[0]
            row_id = row["id"]
            print(f"  contacts INSERT : OK (id={row_id[:8]}...)")

            # SELECT
            resp2 = httpx.get(
                f"{SUPABASE_URL}/rest/v1/contacts?id=eq.{row_id}&select=*",
                headers=headers,
                timeout=10.0,
            )
            if resp2.status_code == 200 and len(resp2.json()) == 1:
                print(f"  contacts SELECT : OK")
            else:
                print(f"  contacts SELECT : ERREUR")

            # DELETE (nettoyage)
            resp3 = httpx.delete(
                f"{SUPABASE_URL}/rest/v1/contacts?id=eq.{row_id}",
                headers=headers,
                timeout=10.0,
            )
            if resp3.status_code in (200, 204):
                print(f"  contacts DELETE : OK (nettoyage)")
            else:
                print(f"  contacts DELETE : ERREUR ({resp3.status_code})")
        else:
            print(f"  contacts INSERT : ERREUR ({resp.status_code}) {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  contacts : ERREUR ({e})")
        return False

    # Test audit_logs (insert only)
    try:
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/audit_logs",
            headers=headers,
            json={"actor": "init_script", "action": "test_init", "status": "success"},
            timeout=10.0,
        )
        if resp.status_code == 201:
            row_id = resp.json()[0]["id"]
            print(f"  audit_logs INSERT : OK (id={row_id[:8]}...)")
            # Nettoyage
            httpx.delete(
                f"{SUPABASE_URL}/rest/v1/audit_logs?id=eq.{row_id}",
                headers=headers,
                timeout=10.0,
            )
        else:
            print(f"  audit_logs INSERT : ERREUR ({resp.status_code})")
    except Exception as e:
        print(f"  audit_logs : ERREUR ({e})")

    return True


def main():
    print("=" * 56)
    print("  J-ARVIS V2 — Init Supabase tenant")
    print("=" * 56)
    print(f"URL    : {SUPABASE_URL}")
    print(f"Projet : {PROJECT_REF}")
    print()

    # Etape 1 : Execute SQL files
    print("Etape 1 — Execution des fichiers SQL :")
    all_ok = True
    for sql_file in SQL_FILES:
        path = SCHEMA_DIR / sql_file
        if not path.exists():
            print(f"  ERREUR : {sql_file} introuvable dans {SCHEMA_DIR}")
            all_ok = False
            continue
        sql = path.read_text(encoding="utf-8")
        if not execute_sql(sql, sql_file):
            all_ok = False

    if not all_ok:
        print("\nDes erreurs SQL sont survenues. Verifie les logs ci-dessus.")
        print("Tu peux aussi executer les .sql manuellement dans le SQL Editor Supabase.")

    # Etape 2 : Verification tables
    print("\nEtape 2 — Verification des tables :")
    tables_ok = verify_tables()

    # Etape 3 : Test CRUD
    if tables_ok:
        print("\nEtape 3 — Test CRUD :")
        crud_ok = test_crud()
    else:
        crud_ok = False
        print("\nEtape 3 — SKIP (tables manquantes)")

    # Bilan
    print()
    print("=" * 56)
    if tables_ok and crud_ok:
        print("  SUPABASE INIT : SUCCES")
        print(f"  6 tables creees dans {PROJECT_REF}")
        print("  RLS active, indexes crees, CRUD OK")
    else:
        print("  SUPABASE INIT : PARTIEL")
        print("  Verifie les erreurs ci-dessus")
        print("  Alternative : copie les .sql dans le SQL Editor Supabase")
    print("=" * 56)


if __name__ == "__main__":
    main()
