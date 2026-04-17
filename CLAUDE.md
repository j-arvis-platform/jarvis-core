# CLAUDE.md — jarvis-core

Ce repo est le moteur générique de J-ARVIS. Aucun code spécifique tenant ici.

## Règles
- Ne JAMAIS mettre de données client dans ce repo
- Ne JAMAIS hardcoder un tenant_id
- Tout doit fonctionner pour n'importe quel tenant via config.yaml
- Les skills métier sont dans modules/, pas ici
- shared-skills/ = skills génériques réutilisables par tous

## Structure agent
- `agent/handlers/main.py` : point d'entrée unique V2
- `agent/routing/model_router.py` : Haiku/Sonnet/Opus selon complexité
- `agent/core/config.py` : charge config tenant
- `agent/core/supabase_client.py` : helpers BDD

## Test rapide
```bash
JARVIS_TENANT_ID=elexity34 python -m agent.handlers.main
```
