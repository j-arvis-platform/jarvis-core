# Analyse comparative — prompts V1 vs V2 (Axel / Lea)

**Date :** 2026-04-18 (post-J3 fix tools)
**Demande :** mesurer ce que V1 fait mieux qu'on a perdu en V2.
**Statut :** rapport pur. **Aucune modification appliquée**.

## Sources V1 récupérées

| Prompt | Localisation | Taille | Rôle |
|---|---|---|---|
| **Vapi voix (Axel téléphone)** | API Vapi assistant `9822c95d-ff7b-4311-a511-d959a6f19f08` | ~3 200 chars | Inbound voix (V1 actif en prod) |
| **Web messaging (Alex chat)** | `/home/ubuntu/backup_axel_20260406_150608/agent.py:37` | ~2 400 chars | Chat web V1 |
| **WhatsApp (Alex WhatsApp)** | même fichier `:105` | ~2 800 chars | WhatsApp V1 (chatbot prod actif) |

V1 a **3 prompts distincts par canal**, partageant les règles métier mais adaptés au format (voix orale, web markdown, WhatsApp court).

Note : `/home/ubuntu/lea/lea_telegram.py` n'a **pas** de prompt système conversationnel — c'est un Telegram dispatcher de commandes (`/relance`, `/nurturing`, `/rapport`). Léa V1 n'est pas un agent conversationnel, juste un script CRM.

## Source V2 actuelle

`modules/module-photovoltaique/skills/elexity-commercial/SKILL.md` — un skill unique pour le rôle commercial, persona Léa, ~5 000 chars (corps).

## Tableau comparatif

| Domaine | V1 (Axel) | V2 (Lea — skill actuel) | Verdict |
|---|---|---|---|
| **Identité** | "Alex, assistant commercial d'ELEXITY 34" | "Lea, persona Lea de J-ARVIS" | V1 plus net commercialement. V2 a un overhead "persona narrative". |
| **Tutoiement / vouvoiement** | **VOUVOIEMENT STRICT** ("vous", règle TRES IMPORTANT) | Mixte / non explicite | ⚠️ V2 manque cette règle dure. |
| **Style par canal** | 3 prompts (voix orale, chat web, WhatsApp court) avec contraintes spécifiques (pas de markdown WhatsApp, phrases courtes voix, etc.) | 1 prompt unique sans variation canal | ⚠️ V2 envoie du markdown sur WhatsApp si on n'y prend pas garde. |
| **Confidentialité numéros** | "Ne JAMAIS dire le 07 83 90 90 63", rediriger vers `contact@elexity34.fr` | Indique le numéro de Léa dans templates email | ⚠️ Régression V2. |
| **Prix au téléphone** | "JAMAIS de prix exact, même fourchette" + reformulation toute prête | "Pas de prix ferme sans VT" | V2 OK mais moins ferme. V1 plus opérationnel. |
| **Zone d'intervention** | Vapi : "tout le sud + au-delà, jamais mentionner distance". Web/WhatsApp : "150 km principal + 4-5 h étendue" | "150 km strict + refus poli + recommandation confrère" | ⚠️ V1 vend plus large. V2 décide de refuser net. À arbitrer côté business. |
| **TVA 5,5 % / Certisolis** | **ABSENT** | Détail complet 3 conditions cumulatives | ✅ V2 mieux (V1 ne traitait pas finement). |
| **Tarif EDF OA 2026 (0,04 €/kWh)** | Absent | "Corriger gentiment si client dit 0,13" | ✅ V2 mieux. |
| **Curieux / démarcheurs / fournisseurs** | "Si appel pas projet solaire : redirige email, pas de transfert, pas de message" | Non explicite | ⚠️ V2 vulnérable au prompt-injection / dispersion. |
| **Anti-déni concurrence** | "Ne JAMAIS dénigrer la concurrence" | Absent | ⚠️ V2 manque garde-fou. |
| **Honnêteté IA** | "Oui je suis un assistant IA. Ça permet à ELEXITY 34 de réduire ses coûts et de répercuter les économies sur le devis" | Absent | ⚠️ V2 manque la réponse standardisée. |
| **MaPrimeRénov'** | "Ne JAMAIS promettre MaPrimeRénov pour PV pur" | "Pas d'aide directe PV seul" | ✅ Égalité, V2 correct. |
| **Outils / RDV** | check_slots, book_appointment, find_appointment, cancel_appointment, reschedule_appointment, send_form, enrich_crm, create_sav_ticket | Tools V2 : supabase_create_*, ninja_*, send_email/sms/whatsapp/telegram | V2 plus large métier (Supabase + facturation), V1 plus profond RDV (Calendar + form). |
| **SAV** | "Collecter info, créer ticket, JAMAIS de RDV SAV, callback humain" | Absent | ⚠️ V2 ne couvre pas le SAV. |
| **Maillage agents internes** | "Notre équipe prend le relais" — ne JAMAIS mentionner Adam/Lea/Hugo au client | "Personas narratives" mais pas exposées au client en V2 actuelle | ✅ Égalité (philosophie identique, V1 explicite). |
| **Format date 2026** | "Toujours année 2026, ne JAMAIS demander confirmation année" | Implicite via system prompt date du jour | V1 plus explicite, utile. |
| **Sortie de conversation** | "Remerciement chaleureux, pas d'insistance, porte ouverte" | Absent | ⚠️ V2 manque cette gentillesse codée. |
| **Détail métier (panneaux, onduleurs, batteries)** | Absent | Catalogue stock + EMS compatibles + détail Certisolis | ✅ V2 nettement mieux. |
| **Pricing fourchettes (interne)** | Absent | `pricing-pv-2026.md` reference détaillée | ✅ V2 mieux (mais c'est interne, pas dans le prompt client). |
| **Argumentaire vente / objections** | Absent du prompt, présent comme savoir implicite | `argumentaire-vente.md` + `objections-types.md` | ✅ V2 mieux structuré. |

## Ce que V1 fait mieux et qu'on a perdu

1. **Vouvoiement strict** (règle dure, pas une suggestion).
2. **3 prompts par canal** (voix / chat / WhatsApp) avec contraintes de format adaptées (pas de markdown sur WhatsApp, phrases courtes voix, une question à la fois).
3. **Confidentialité numéros perso** : ne pas exposer `+33 7 83 90 90 63`.
4. **Garde-fous prompt-injection** : démarcheurs, fournisseurs, hors-sujet → email seulement, pas de prise de message.
5. **Honnêteté IA standardisée** : phrase prête à l'emploi.
6. **Anti-dénigrement concurrence** explicite.
7. **Workflow RDV outillé** : check_slots, book, find, cancel, reschedule, send_form (formulaire WhatsApp pour confirmer coords).
8. **SAV** : ticket auto + callback humain, jamais de RDV SAV.
9. **Sortie conversation gracieuse** : remerciement, porte ouverte, pas d'insistance.
10. **Année 2026 par défaut** : pas demander à confirmer.

## Ce que V2 fait mieux et qu'on doit garder

1. **TVA 5,5 % / 20 % détaillée** avec 3 conditions cumulatives + stock actuel.
2. **Tarif EDF OA 2026 (0,04 €/kWh)** + correction d'erreurs web.
3. **Catalogue stock concret** (DMEGC, DualSun, Trina, Huawei, APsystems, Tesla, MyLight…).
4. **Pricing fourchettes interne** (`pricing-pv-2026.md`) — base saine pour le devis.
5. **Argumentaire commercial structuré** (`argumentaire-vente.md`) + **objections-types**.
6. **Workflow CRM Supabase** (contacts / projets / tâches / file_humaine).
7. **Intégration Invoice Ninja + DocuSeal** (création client, brouillon devis, signature).
8. **Documentation lisible** (sections, exemples, references chargeables à la demande).

## Ce qui manque dans V2 et doit être ajouté

### Critique (impact prod immédiat)

- **Vouvoiement strict** : règle dure dans le SKILL.md.
- **Confidentialité du numéro perso 07 83 90 90 63** : ne jamais l'exposer côté client, rediriger vers `contact@elexity34.fr` ou le numéro Business Twilio `+33 9 39 24 50 20`.
- **Garde-fous démarcheurs / fournisseurs / hors-sujet** : redirection email systématique.
- **Anti-dénigrement concurrence** : règle explicite.
- **Honnêteté IA** : phrase standard prête à l'emploi.

### Important (UX et délivrabilité)

- **Variations par canal** : règles spécifiques pour Telegram/email/SMS/WhatsApp/voix dans le SKILL ou un nouveau `references/canal-rules.md`.
  - Email : markdown OK, sujet précis, signature.
  - SMS : ≤ 160 chars, pas d'URL longue, pas de markdown.
  - WhatsApp : phrases courtes, pas de markdown, 1 question à la fois.
  - Voix (futur si on porte Axel sur V2) : pas de listes à puces, oral pur.
- **Sortie de conversation chaleureuse** : pattern de remerciement.
- **Année 2026 par défaut** dans dates relatives.

### À discuter (décision business)

- **Zone d'intervention** : V1 voix dit "tout le sud + au-delà", V1 WhatsApp dit "150 km principal + jusqu'à 4-5 h étendue". V2 dit "150 km strict, refus net". Quel discours retient-on ? Implication directe sur le pipeline commercial.
- **SAV** : ajouter un skill dédié `pv-sav` ou inclure les règles SAV dans `elexity-terrain-pv` ?
- **Workflow RDV** : porter `check_slots / book_appointment / find_appointment / cancel / reschedule / send_form` comme tools V2 (équivalent du V1 vapi_webhook).

## 3 options possibles

### Option A — `elexity-commercial` actuel + injection des règles V1 manquantes

Ajouter une section "Règles absolues V1" dans le SKILL.md (vouvoiement strict, confidentialité, garde-fous, honnêteté IA, anti-dénigrement). Garder la structure V2.
**Coût** : 30 min. **Risque** : faible.

### Option B — Refonte hybride : SKILL.md "v2.1" qui prend les meilleurs morceaux V1 + V2

Réécrire le SKILL.md autour du squelette V1 (canal-aware, garde-fous explicites) en injectant les apports V2 (TVA détaillée, tarif EDF, catalogue, pricing). Ajouter des sections par canal.
**Coût** : 1 h 30. **Risque** : moyen (changement de structure).

### Option C — Garder V2 tel quel, ajouter un skill séparé `elexity-canaux` + `elexity-securite`

Garder `elexity-commercial` pour le métier, ajouter :
- `elexity-canaux` : règles de format par canal (email / WhatsApp / SMS / voix).
- `elexity-securite` : confidentialité numéros, garde-fous démarcheurs, anti-injection.
Le matcher injecte les 2-3 skills pertinents selon le contexte.
**Coût** : 1 h. **Risque** : faible (modulaire, V2-native).

## Recommandation

**Option A pour aujourd'hui (15-30 min)** + **Option C planifiée pour la semaine 1 post go-live (1 h)**.

Justification :
- Option A bouche les trous critiques (vouvoiement, confidentialité, garde-fous IA) sans toucher la structure V2.
- Option C ajoute la modularité canal/sécurité sans tout réécrire, et profite de la cohabitation V1/V2 (V1 absorbe les conversations entrantes en attendant).
- Option B est tentante mais le ROI est faible vs Option A+C.

**Décision attendue de toi avant toute modification.**
