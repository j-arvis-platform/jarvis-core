# Plan de tests modulaires — semaine du 20 au 24 avril 2026

Objectif : valider chaque module critique **un par un** avant la bascule V1 → V2 prévue vendredi 24 avril 2026 (fin de journée).

Principe : un module par demi-journée, test réel côté ELEXITY, rollback possible à tout moment.

---

## Lundi 20/04 matin — Module compta / devis

**Périmètre :**
- Invoice Ninja : création devis + client via `/api/chat`.
- DocuSeal : envoi signature + callback webhook.
- Pennylane : création customer + list invoices (si MCP tools ajoutés).

**Scénario de test :**
> "Crée un devis pour un nouveau client M. Dupont, 6 kWc à Gignac, batterie 5 kWh, prix HT 12 500 €, TVA 20 %, envoie-le par email pour signature DocuSeal."

**Validations :**
- [ ] Contact + projet Supabase créés.
- [ ] Client Invoice Ninja créé avec bonnes coordonnées.
- [ ] Brouillon devis Invoice Ninja avec bonnes lignes + TVA.
- [ ] Email envoyé avec lien DocuSeal.
- [ ] Webhook DocuSeal reçu et statut mis à jour dans Supabase au moment de la signature.
- [ ] Relance J+7 programmée en tâche.

**À faire avant le test :**
- Ajouter tools Pennylane et DocuSeal dans `agent/tools/registry.py`.
- Tester webhook DocuSeal en local avec ngrok / Pipedream.

---

## Lundi 20/04 après-midi — Module RDV / agenda

**Périmètre :**
- Porter les tools V1 Calendar (`check_slots`, `book_appointment`, `find_appointment`, `cancel_appointment`, `reschedule_appointment`, `send_form`) sur V2.
- Utilisation par Léa (commercial) et Axel (voix).

**Scénario :**
> "Planifie une VT pour M. Dupont à Gignac, créneau mardi prochain 14h30, envoie-lui un SMS de confirmation avec le lien de formulaire coordonnées."

**Validations :**
- [ ] Créneau libre vérifié sur Google Calendar.
- [ ] Événement créé avec bon titre, adresse, durée 1 h.
- [ ] SMS envoyé au client avec lien formulaire.
- [ ] Tâche "VT Dupont" créée Supabase avec deadline mardi.
- [ ] Test annulation : `find_appointment` par téléphone → `cancel_appointment`.
- [ ] Test report : idem → `reschedule_appointment`.

**À faire avant :**
- Créer MCP `google-calendar` ou tools directs via `google-auth` + `googleapiclient`.
- Réutiliser `GOOGLE_CLIENT_ID/SECRET` du V1 (`youtube_credentials.json`) ou OAuth Twenty (`AUTH_GOOGLE_CLIENT_ID`).

---

## Mardi 21/04 matin — Module Vapi voix

**Périmètre :**
- Ajouter tools côté assistant Vapi Axel (via `client.update_assistant(tools=...)`) pour que pendant l'appel il puisse :
  - Créer un contact Supabase.
  - Vérifier une adresse dans la zone.
  - Créer une tâche VT.
  - Envoyer un SMS/WhatsApp formulaire.

**Scénario :**
- Appel test vers Axel depuis mobile.
- Simuler un prospect : nom, adresse, intérêt PV.
- Vérifier qu'Axel crée bien contact + tâche dans Supabase côté V2 (pas V1 Twenty).

**Validations :**
- [ ] Latence conversationnelle < 1 sec (sinon conversation casse).
- [ ] Contact Supabase créé pendant l'appel.
- [ ] Transcript récupérable via `client.get_call_transcript(call_id)`.
- [ ] Tâche VT Supabase avec lien vers contact.

**Risque :**
- Axel V1 est déjà outillé côté Twenty CRM. Il faut basculer ses tools vers Supabase V2 **ou** laisser V1 coexister et synchroniser Twenty → Supabase par cron.
- Décision produit : ne pas casser V1 tant que V2 pas validé.

---

## Mardi 21/04 après-midi — Module WhatsApp

**Périmètre :**
- Réception : brancher webhook Meta `https://elexity34.j-arvis.ai/api/whatsapp/webhook` (endpoint FastAPI à créer).
- Routage : incoming message → Jarvis V2 chat → response.
- Cohabitation V1/V2 : désactivation du webhook V1 AVANT activation V2.

**Scénario :**
- Envoyer message test au numéro Business +33 7 83 90 90 63 depuis Hamid.
- Vérifier que V2 reçoit bien et répond (pas V1).

**Validations :**
- [ ] Webhook Meta activé côté `elexity34.j-arvis.ai`.
- [ ] Signature HMAC validée côté serveur.
- [ ] Conversation V2 stockée dans Supabase `chat_messages` (table à créer).
- [ ] Réponse sortante via `send_whatsapp_message` tool.
- [ ] Pas de double traitement V1 + V2.

---

## Mercredi 22/04 — Module templates / email pro

**Périmètre :**
- Les 3 templates `modules/module-photovoltaique/skills/elexity-commercial/templates/`.
- Variables réelles injectées (`{prenom}`, `{numero_devis}`, `{creneau_1}`, etc.).
- Envoi via `send_email_gmail` tool avec `body_html`.

**Scénario :**
- Lea génère un email "bienvenue" pour un nouveau prospect.
- Lea génère un email "proposition VT" avec 3 créneaux.
- Lea génère un email "relance J+7" pour un devis.

**Validations :**
- [ ] Rendu HTML correct dans Gmail, Outlook, iOS Mail.
- [ ] Variables remplies sans placeholders orphelins.
- [ ] Signature Léa + mentions légales.
- [ ] Délivrabilité (check SpamAssassin via mail-tester.com — dépend backlog SPF/DKIM).

---

## Jeudi 23/04 — Site web `elexity34.fr`

**Périmètre :**
- Audit HTML/CSS (24 pages selon mémoire `project_site_html.md`).
- SEO rapide (title, meta, GA4, sitemap).
- Formulaire contact : vérifier qu'il pointe bien vers Jarvis V2 (`/api/chat` ou endpoint dédié).
- API kWc calculator + avis Google embedded.

**Validations :**
- [ ] Formulaire `contact@elexity34.fr` livré via SMTP Gmail.
- [ ] GA4 tracking OK.
- [ ] Mention **"tarif EDF OA 0,04 €/kWh"** (corriger les `0,13` obsolètes).
- [ ] Liens RGE + décennale MAAF cliquables et à jour.

---

## Vendredi 24/04 — Bascule V1 → V2 (si tous les modules OK)

**Séquence de bascule :**

1. 09h00 — dernier commit jarvis-core, tag `v2.1.0-elexity34`.
2. 09h30 — backup Supabase + export Twenty CRM V1 (sauvegarde décisions).
3. 10h00 — `ssh VPS V1 && sudo systemctl stop *-telegram.service` (extinction bots Telegram V1 Axel, Lea, etc.).
4. 10h30 — désactiver webhook WhatsApp V1 côté Meta.
5. 11h00 — activer webhook WhatsApp V2 (V2 reçoit tous les messages).
6. 11h30 — basculer le tenant Vapi vers tools V2 Supabase.
7. 12h00 — DNS `elexity34.fr` → vérifier que le formulaire pointe bien vers V2.
8. 14h00 — test trafic réel pendant 2 h.
9. 18h00 — GO LIVE officiel (ou rollback si anomalie).

**Rollback plan :**
- Re-démarrer les services V1 (`sudo systemctl start *-telegram.service`).
- Réactiver webhook Meta V1.
- Basculer Vapi tools vers V1.
- 5 minutes max.

---

## Critères GO / NO GO vendredi 18h

**GO si :**
- Modules 1-5 validés par au moins un test réel chacun.
- Aucun incident bloquant pendant la fenêtre trafic (14-18h).
- Hamid peut créer un devis en direct via chat V2 sans aucune intervention V1.

**NO GO si :**
- Un seul module critique n'est pas validé (compta, RDV, Vapi, WhatsApp, templates).
- Incident sur l'infra V2 pendant la fenêtre (500, timeout, data loss).
- Doute de Hamid sur la stabilité.

Dans ce cas : report bascule au lundi 27/04, V1 continue.
