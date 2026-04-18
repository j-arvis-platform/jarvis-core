# Backlog post go-live

Items identifiés pendant le build V2, à traiter après go-live (lundi 20 avril 18h).

## Infrastructure

- [ ] **Migration SMTP Gmail → Infomaniak**
  V1 tourne actuellement sur Gmail App Password (`smtp.gmail.com:587`, compte `contact@elexity34.fr`). Migration prévue vers Infomaniak (`mail.infomaniak.com:465`) pour cohérence hébergement et fiabilité délivrabilité. Pas urgent tant que Gmail ne rate limit pas.
  **Note 18/04 :** décision revue — viser plutôt OVH Email Pro (cf item suivant).

- [ ] **Migration email `contact@elexity34.fr` : Google Workspace → OVH Email Pro**
  - **Raison :** économie (6 €/mois → 1,49 €/mois), souveraineté FR (argument commercial J-ARVIS SaaS).
  - **Procédure :**
    1. Créer `contact@elexity34.fr` sur OVH Email Pro (ou ajouter `elexity34.fr` aux domaines gérés).
    2. Migrer la boîte existante (IMAP migration tool).
    3. Changer les DNS MX records.
    4. Tester envoi / réception pendant 7 jours.
    5. Résilier Workspace.
  - **Timing :** après stabilisation V2 (J+14 à J+30).
  - **Note :** futurs clients J-ARVIS SaaS → proposer Email Pro OVH dans le pack (argument souveraineté).

- [ ] **Suppression clé Anthropic V1**
  Deux `ANTHROPIC_API_KEY` actives : V1 (`sk-ant***yKgAA`, utilisée par tous les services V1) et V2 (`sk-ant***8pwAA`, dans `tenant-elexity34/.env`). Supprimer V1 dans le dashboard Anthropic une fois VPS V1 décommissionné (semaine du 22 avril).

- [ ] **Rotation mot de passe OpenSolar**
  `OPENSOLAR_PASSWORD` récupéré en clair depuis VPS V1 pendant l'audit. Rotation recommandée + stockage Bitwarden + génération d'un token API dédié plutôt que login email/password.

## Sécurité

- [ ] **Migration credentials vers Bitwarden**
  Tous les `.env` locaux actuels (build V2) à migrer dans Bitwarden vault. UX terminal Bitwarden à retester (bloquant reporté au pré-build).

- [ ] **Audit complet VPS V1 avant décommissionnement**
  Avant de couper VPS V1, vérifier qu'aucun service n'est oublié (cf. `external/v1-rescue/secrets/raw-vps-v1-audit.txt` : 42 services systemd + 12 containers Docker).

## MCPs différés

- [ ] `PAPPERS_API_KEY` — inscription pappers.fr/api
- [ ] `KONCILE_API_KEY` — inscription koncile.com (OCR factures)
