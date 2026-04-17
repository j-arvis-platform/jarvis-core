"""
J-ARVIS V2 — Test de connexion de tous les MCPs/APIs
Execute chaque test independamment, skip si cle manquante.
"""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent.parent / ".env")

results = []


def test_mcp(name, func):
    print(f"\n{'='*50}")
    print(f"  MCP: {name}")
    print(f"{'='*50}")
    start = time.time()
    try:
        status, detail = func()
        ms = int((time.time() - start) * 1000)
        print(f"  Status  : {status}")
        print(f"  Detail  : {detail}")
        print(f"  Latence : {ms}ms")
        results.append((name, status, detail, ms))
    except Exception as e:
        ms = int((time.time() - start) * 1000)
        err = str(e).encode("ascii", errors="replace").decode("ascii")
        print(f"  ERREUR  : {err}")
        results.append((name, "KO", err[:100], ms))


# ── 1. Supabase REST API ──
def test_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key or "A_REMPLIR" in key:
        return "SKIP", "Credentials manquants"

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    resp = httpx.get(f"{url}/rest/v1/contacts?select=id&limit=0", headers=headers, timeout=10)
    if resp.status_code == 200:
        return "OK", f"REST API operationnelle (projet {url.split('//')[1].split('.')[0][:8]}...)"
    return "KO", f"HTTP {resp.status_code}"


# ── 2. Invoice Ninja ──
def test_invoice_ninja():
    url = os.environ.get("INVOICE_NINJA_URL", "")
    token = os.environ.get("INVOICE_NINJA_TOKEN", "")
    if not url or not token or "A_REMPLIR" in token:
        return "SKIP", "Credentials manquants"

    headers = {"X-Api-Token": token, "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}
    resp = httpx.get(f"{url}/api/v1/ping", headers=headers, timeout=10)
    data = resp.json()
    company = data.get("company_name", "?")

    resp2 = httpx.get(f"{url}/api/v1/invoices?per_page=1", headers=headers, timeout=10)
    total_inv = resp2.json().get("meta", {}).get("pagination", {}).get("total", 0)

    resp3 = httpx.get(f"{url}/api/v1/clients?per_page=1", headers=headers, timeout=10)
    total_cli = resp3.json().get("meta", {}).get("pagination", {}).get("total", 0)

    return "OK", f"{company} — {total_inv} factures, {total_cli} clients"


# ── 3. Pennylane (API directe V2) ──
def test_pennylane():
    key = os.environ.get("PENNYLANE_API_KEY", "")
    url = os.environ.get("PENNYLANE_URL", "https://app.pennylane.com/api/external/v2")
    if not key or "A_REMPLIR" in key:
        return "SKIP", "API key manquante"

    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    resp = httpx.get(f"{url}/customer_invoices?per_page=1", headers=headers, timeout=10)
    if resp.status_code == 200:
        resp2 = httpx.get(f"{url}/suppliers?per_page=1", headers=headers, timeout=10)
        return "OK", f"API V2 operationnelle (invoices + suppliers)"
    return "KO", f"HTTP {resp.status_code}"


# ── 4. DocuSeal ──
def test_docuseal():
    url = os.environ.get("DOCUSEAL_URL", "")
    key = os.environ.get("DOCUSEAL_API_KEY", "")
    if not key or "A_REMPLIR" in key:
        return "SKIP", "API key manquante — recuperer dans DocuSeal Settings > API"

    headers = {"X-Auth-Token": key, "Accept": "application/json"}
    resp = httpx.get(f"{url}/api/templates", headers=headers, timeout=10)
    if resp.status_code == 200:
        templates = resp.json()
        count = len(templates) if isinstance(templates, list) else "?"
        return "OK", f"{count} templates"
    return "KO", f"HTTP {resp.status_code}"


# ── 5. Pappers ──
def test_pappers():
    key = os.environ.get("PAPPERS_API_KEY", "")
    if not key or "A_REMPLIR" in key:
        return "SKIP", "API key manquante — creer compte sur pappers.fr/api"

    resp = httpx.get(
        f"https://api.pappers.fr/v2/entreprise?api_token={key}&siret=94006873700011",
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        nom = data.get("nom_entreprise", "?")
        return "OK", f"Trouve: {nom}"
    return "KO", f"HTTP {resp.status_code} - {resp.text[:100]}"


# ── 6. Koncile OCR ──
def test_koncile():
    key = os.environ.get("KONCILE_API_KEY", "")
    if not key or "A_REMPLIR" in key:
        return "SKIP", "API key manquante — creer compte sur koncile.com"
    # Koncile health check
    resp = httpx.get("https://api.koncile.com/health", headers={"Authorization": f"Bearer {key}"}, timeout=10)
    return ("OK" if resp.status_code == 200 else "KO"), f"HTTP {resp.status_code}"


# ── Run all tests ──
if __name__ == "__main__":
    print("\n" + "#" * 50)
    print("  J-ARVIS V2 — Test MCPs / APIs")
    print("#" * 50)

    test_mcp("Supabase", test_supabase)
    test_mcp("Invoice Ninja", test_invoice_ninja)
    test_mcp("Pennylane (Pipedream)", test_pennylane)
    test_mcp("DocuSeal", test_docuseal)
    test_mcp("Pappers", test_pappers)
    test_mcp("Koncile OCR", test_koncile)

    # Summary
    print("\n" + "=" * 50)
    print("  BILAN MCPs")
    print("=" * 50)
    for name, status, detail, ms in results:
        icon = {"OK": "[OK]", "KO": "[KO]", "SKIP": "[--]"}.get(status, "[??]")
        print(f"  {icon} {name:25s} {detail[:50]}")

    ok = sum(1 for _, s, _, _ in results if s == "OK")
    skip = sum(1 for _, s, _, _ in results if s == "SKIP")
    ko = sum(1 for _, s, _, _ in results if s == "KO")
    print(f"\n  Total: {ok} OK / {skip} a configurer / {ko} KO")
