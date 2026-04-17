# Changelog — jarvis-core

## v2.0.0 (2026-04-17) — J1 Build Complete

### Added
- Structure initiale jarvis-core V2
- Agent principal avec personas narratives (main.py)
- Routage modeles Haiku/Sonnet/Opus (model_router.py)
- Client Supabase avec helpers query/insert/update
- Config loader tenant (YAML)
- Placeholders agents V2.5 (field.py, docs.py)
- .env.example avec toutes les variables necessaires
- requirements.txt

### Supabase Schema
- 6 tables core : contacts, projets, documents, taches, file_humaine, audit_logs
- RLS (Row-Level Security) sur toutes les tables
- 35 index de performance
- Auto-reference projets (ELX-2026-xxxx)
- Trigger updated_at automatique
- Champ marque multi-activite (solarstis, domotique, bornes_ve, etc.)

### MCPs valides
- Supabase REST API (service_role key)
- Invoice Ninja (API token, self-hosted V1)
- Pennylane V2 (API directe, pas Pipedream)
- DocuSeal (API token, self-hosted)
- Pappers : reporte (semaine prochaine)
- Koncile OCR : reporte (post go-live)

### Scripts
- scripts/init-supabase.py : init schema + validation + test CRUD
- scripts/test-agent-e2e.py : test agent + Supabase + Claude API
- scripts/test-mcps.py : test connexion tous MCPs
- scripts/test-integration-e2e.py : workflow complet prospect -> devis

### Tests valides
- Agent persona Lea : reponse chaleureuse, correcte metier
- E2E integration : 6 appels MCP, 4 rounds, 39s, 0.075 EUR
- Claude tool_use avec parallelisation automatique

### Architecture
- V1 abandonnee (10 agents + n8n + Twenty CRM)
- V2 = 1 agent Claude + skills + Supabase + MCPs
- Pennylane API directe V2 (pas Pipedream)
- VPS V2 dedie (51.38.38.226, user jarvis)
- GitHub org j-arvis-platform (7 repos)
