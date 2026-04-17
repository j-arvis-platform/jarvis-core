# jarvis-core v2.0

Moteur générique de la plateforme J-ARVIS — agents IA pour TPE/PME françaises.

## Architecture

```
jarvis-core/
├── agent/
│   ├���─ core/           # Config, Supabase client, utilitaires
│   ├── handlers/       # Points d'entrée agents (main, field, docs)
│   └── routing/        # Routage modèles Haiku/Sonnet/Opus
├── shared-skills/      # Skills réutilisables tous tenants
├── shared-mcps/        # MCPs réutilisables
├── pwa-template/       # PWA Preact 3 écrans
├── supabase-schema/    # Schéma BDD standard par tenant
├── prompts/            # Prompts système par version
├── cli/                # jarvis-cli (gestion tenants)
└── docs/               # Documentation
```

## Quickstart

```bash
cp .env.example .env
# Remplir les clés API dans .env
pip install -r requirements.txt
python -m agent.handlers.main
```

## Principes

- **1 agent, N personas** : Jarvis est unique, les personas sont du style UX
- **1 tenant = 1 Supabase** : isolation totale des données
- **Routage modèles** : Haiku (simple), Sonnet (standard), Opus (complexe)
- **Skills + MCPs** : pas de n8n, pas de Twenty CRM
