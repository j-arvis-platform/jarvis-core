# Tenants — roadmap

État : 2026-04-18 (J2 du build V2)

## Principe

Un **tenant** = une entité business qui utilise J-ARVIS. Chaque tenant a son propre projet Supabase, ses credentials, son branding et ses modules actifs. Un tenant peut couvrir plusieurs verticaux (ex. ELEXITY 34 = PV + domo + bornes + clim + élec).

Nommage : `tenant-{slug-business}`. Le mot `core` est réservé à `jarvis-core`. Le slug identifie l'entreprise, pas un vertical métier. Détails : `.claude/docs/METHODOLOGIE.md`.

## Tenant 1 : `tenant-elexity34` — EN CONSTRUCTION

- **Entité :** ELEXITY 34 SASU (RGE QualiPV, Gignac 34150)
- **Build :** J1 à J4 du plan V2 (17 → 20 avril 2026)
- **Deadline go-live :** lundi 20 avril 2026, 18h
- **Modules actifs :**
  `module-photovoltaique`, `module-compta-france`, `module-rh-france`, `module-securite-france`, `module-site-web`, `module-marketing`
  (`module-domotique` à activer Q3 2026 pour la BU domotique)
- **Canaux :** WhatsApp Business (Axel), Telegram (`@Jarvis_hamid_bot`), Vapi (Axel voix), SMS Twilio, Email SMTP Gmail → OVH Email Pro post go-live
- **Supabase projet :** `tenant-elexity34` (EU West Frankfurt)
- **Statut credentials :** 29 récupérés de V1, 3 à créer (PISTE, Pappers, Koncile)

## Tenant 2 : `tenant-j-arvis` — APRÈS go-live ELEXITY 34

- **Entité :** J-ARVIS (future SASU, société dédiée à la vente SaaS conseil IA aux TPE/PME)
- **Démarrage :** semaine 2 post go-live ELEXITY 34 (à partir du 28 avril 2026)
- **Philosophie :** *dogfooding* — on utilise J-ARVIS pour vendre J-ARVIS.
  Preuve par l'usage : « regarde ce que mon propre J-ARVIS fait pour ma propre boîte ».
- **Périmètre attendu :**
  - Prospection B2B (leads IA conseil)
  - Site vitrine `j-arvis.ai` (WordPress ou alternative)
  - Commandes packs SaaS (Essentiel / Pro / Croissance)
  - Facturation clients + onboarding tenants
- **Modules actifs (prévisionnel) :**
  `module-marketing`, `module-site-web`, `module-compta-france`, `module-securite-france`, `module-rh-france` (+ un futur `module-saas-ops` pour gérer le cycle de vie tenants)
- **Email opérationnel :** `admin@j-arvis.ai` (OVH Email Pro, déjà actif)
- **Supabase projet :** `tenant-j-arvis` (à créer)

## Tenants futurs

Format : `tenant-{slug-business}`. Créés au fil des signatures clients J-ARVIS SaaS. Premières cibles envisagées :

- TPE PV via le réseau CAPEB
- Ambulanciers (vertical `module-ambulancier`)
- Restauration indépendante (`module-restauration`)
- BTP général (`module-btp-general`)

Chaque nouveau tenant suit la procédure `jarvis-cli tenant create <slug>` (CLI à développer) : création Supabase, génération `.env` vault, copie du template de config, seed des modules activés.

## Services mutualisés vs isolés

### Mutualisés (une seule instance au niveau plateforme)

- `ANTHROPIC_API_KEY` — facturation Anthropic centralisée, routage Haiku/Sonnet/Opus commun.
- `PENNYLANE_API_KEY`, `DOCUSEAL_API_KEY`, `INVOICE_NINJA_API_KEY` — tant qu'un seul compte Pennylane / Invoice Ninja dessert plusieurs tenants. Dès qu'un client exige son propre compte, il bascule en isolé.
- Les sources de MCPs open-source (clonés dans `external/`).

### Isolés par tenant (obligatoire)

- **Supabase** — 1 projet par tenant. RGPD + souveraineté données + argument commercial.
- **Credentials canaux** (WhatsApp token, Telegram bot, Vapi assistant, Twilio, SMTP). Chaque tenant a ses propres comptes et numéros.
- **Domaine / branding** (logo PWA, couleurs, wording).
- **Config modules** (`modules_actifs`, `personas_actives`, paramètres métier).

### Partagés optionnellement

- `GROQ_API_KEY`, `GMAPS_KEY` — usage transversal, facturation unique tant que la volumétrie reste faible.

## Checklist création d'un nouveau tenant

- [ ] Valider le nommage : `tenant-{slug}` disponible dans GitHub org `j-arvis-platform`
- [ ] Créer le projet Supabase dédié + appliquer schema standard (5 tables core)
- [ ] Copier `tenant-template/` → `tenant-configs/tenant-{slug}/`
- [ ] Remplir `config.yaml` (tenant identity, modules actifs, personas, canaux)
- [ ] Provisionner les credentials canaux propres au tenant (WhatsApp, Telegram, etc.)
- [ ] Stocker `.env` tenant (vault chiffré — Bitwarden post go-live)
- [ ] Déployer un service systemd / container dédié avec `JARVIS_TENANT_ID={slug}`
- [ ] Configurer monitoring Uptime Kuma + alertes Telegram admin
- [ ] Tester end-to-end sur `tenant-DEMO-{vertical}` avant bascule prod
