# Telegram V1/V2 — Stratégie de cohabitation

**Contexte :** VPS V1 (51.91.123.127) tourne encore en production pendant le build V2 et pendant la première semaine post go-live. Le bot `@Jarvis_hamid_bot` (token `8387035104:...`) est partagé entre les deux environnements.

## Le conflit

L'API Bot Telegram expose `getUpdates(offset, limit, timeout)` pour le **polling**. Chaque appel **consomme** les updates : une fois lus par un process, ils ne reviennent pas. Si V1 et V2 appellent `getUpdates` en parallèle sur le même token, les messages entrants sont distribués au hasard entre les deux — l'un ou l'autre rate la moitié des messages.

Même problème avec les webhooks : un seul URL webhook peut être enregistré par bot. `setWebhook` côté V2 écraserait celui de V1 (et inversement).

## Règle en vigueur pendant le build V2 + semaine 1 post go-live

| Direction | V1 | V2 |
|---|---|---|
| **Envoi** (`sendMessage`, `sendPhoto`, etc.) | ✅ actif | ✅ actif — autorisé tout de suite |
| **Réception** (`getUpdates` / webhook) | ✅ actif | ❌ **INTERDIT** |

L'envoi est *stateless* côté API : aucun conflit possible entre plusieurs émetteurs sur le même token.

La réception doit rester côté V1 tant que V1 tourne.

## Transition prévue

1. **J4 lundi 20/04 18h** — GO LIVE V2
2. **Semaine 1 (21-25/04)** — V1 et V2 cohabitent, V2 en envoi seul
3. **Début semaine 2 (28/04)** — extinction V1 :
   - Stopper tous les `*-telegram.service` systemd sur VPS V1
   - Vérifier : aucun `getUpdates` en cours depuis V1
4. **Après extinction V1** — activation réception V2 :
   - Choix polling ou webhook (à décider selon charge)
   - Si webhook : `setWebhook` côté V2 une fois
   - Si polling : lancer le service `jarvis-telegram-poller` sur VPS V2

## Implémentation côté V2

- `agent/integrations/telegram.py` expose `get_updates()` **mais le wrapper ne doit pas être appelé en boucle** tant que V1 tourne.
- Ajouter un flag env `TELEGRAM_RECEIVE_ENABLED=false` par défaut. Le flipper à `true` uniquement après extinction V1.
- Aucun service systemd / cron de polling Telegram ne doit être activé sur VPS V2 avant l'étape 3 ci-dessus.

## Checklist d'activation réception V2 (à faire semaine 2)

- [ ] VPS V1 : `sudo systemctl stop *-telegram.service && sudo systemctl disable *-telegram.service`
- [ ] V1 : `docker stop jarvis` (container bot principal V1)
- [ ] Vérifier `curl https://api.telegram.org/bot{TOKEN}/getUpdates` retourne vide plusieurs fois de suite
- [ ] V2 : `TELEGRAM_RECEIVE_ENABLED=true` dans tenant-elexity34/.env
- [ ] V2 : démarrer le service de réception (polling ou webhook selon choix)
- [ ] Test end-to-end : envoyer un message au bot, vérifier qu'il atterrit bien dans V2
