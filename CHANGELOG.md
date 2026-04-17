# Changelog — jarvis-core

## v2.0 (2026-04-17)

### Added
- Structure initiale jarvis-core V2
- Agent principal avec personas narratives (main.py)
- Routage modèles Haiku/Sonnet/Opus (model_router.py)
- Client Supabase avec helpers query/insert/update
- Config loader tenant (YAML)
- Placeholders agents V2.5 (field.py, docs.py)
- .env.example avec toutes les variables nécessaires
- requirements.txt

### Architecture
- Décision : V1 abandonnée (10 agents + n8n + Twenty)
- V2 = 1 agent Claude + skills + Supabase + MCPs
- Pennylane via Pipedream (repo melvynx introuvable)
