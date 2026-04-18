# Claude Code Channels — évaluation pour J-ARVIS V2

**Date :** 2026-04-18 (J2 du build)
**Décision :** **SKIP pour V2**, backlog optionnel pour le confort dev d'Hamid.

## Ce qu'est réellement Claude Code Channels

Feature Anthropic lancée **mars 2026, research preview**. Ce que ça fait :

- **Bridge MCP Telegram / Discord / iMessage ↔ Claude Code**
- Permet de piloter *Claude Code lui-même* à distance depuis son téléphone (ex. "Claude, lance les tests sur la branche X" envoyé depuis Telegram)
- Claude Code s'exécute avec le flag `--channels` et devient un polling service qui écoute les messages entrants
- Les réponses sont renvoyées via le même canal messaging

Sources : docs.anthropic.com/en/docs/claude-code, anthropic.com/news, articles de presse (the-decoder, claudefa.st, medium.com/all-about-claude).

## Ce que le Build-Plan imaginait

Le plan original décrit CC Channels comme un **event bus interne** type publish/subscribe (channels `admin.notifications`, `business.events`, `ops.alerts`) entre l'agent J-ARVIS et ses intégrations. **Ce n'est pas ce que fait CC Channels.**

Le vrai nom de ce pattern serait : event bus, message broker, pub/sub, event stream. Pas Claude Code Channels.

## Pourquoi on skip pour V2

1. **Hors périmètre agent Jarvis** — CC Channels pilote Claude Code (l'outil de dev), pas le runtime de l'agent en production.
2. **Redondant côté communication** — on a déjà Telegram (envoi via `TelegramBot`), WhatsApp, Email, SMS et Vapi. Pour notifier Hamid, `JarvisAgent.notify_admin()` suffit largement.
3. **Research preview** — non-critique à mettre sur le chemin du go-live lundi.
4. **Pas de besoin multi-agent avéré en V2** — l'architecture V2 = 1 agent + personas narratives. Le besoin d'un event bus interne apparaît en V2.5 (3 agents) ou V3 (5-10 agents).

## Ce qu'on garde pour le besoin réel "events structurés"

Quand l'agent doit publier un événement structuré (nouveau prospect, devis créé, alerte SAV, etc.), le chemin naturel en V2 est :

- **Insert Supabase** dans une table dédiée (`audit_logs` existe déjà, ou créer `events` plus tard si besoin)
- **Subscription Supabase Realtime** côté PWA (écran Pulse en J4) pour rafraîchir les KPI en temps réel
- **Notifications humaines** via `JarvisAgent.notify_admin()` (Telegram) ou `send_email()` selon urgence

Aucune brique supplémentaire nécessaire pour V2.

## Backlog post go-live (optionnel, confort dev)

Si Hamid veut un jour piloter Claude Code depuis son mobile pendant qu'il est en déplacement :

- [ ] **Activer Claude Code Channels (bridge Telegram)** — permet d'envoyer des tâches de dev à Claude Code depuis Telegram, recevoir les réponses. Priorité LOW, purement confort dev.

## Changement au BUILD-PLAN

Étape 2.6 originellement intitulée "Claude Code Channels (1h)" → renommée **"2.6 Event stream (documentation + Supabase Realtime en J4)"**, et le gros du travail sur l'event stream passe à J4 avec la PWA.

Durée réelle 2.6 = ~15 min (doc + décision), gain de 45 min sur l'estimation initiale.
