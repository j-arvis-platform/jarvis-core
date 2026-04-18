# Déploiement tenant-elexity34 sur VPS V2

**Statut 18/04/2026 :** LIVE à https://elexity34.j-arvis.ai

## Stack

- **VPS** : OVH 51.38.38.226, Ubuntu 25.04, user `jarvis`, Python 3.13, `uv`.
- **Backend** : FastAPI (`agent/server.py`) servi par `uvicorn`, systemd.
- **Frontend** : PWA Preact + Vite + Tailwind 4 (repo séparé `modules/module-pwa/`), buildée en `dist/`.
- **Reverse proxy** : nginx (HTTPS Let's Encrypt, renouvellement automatique).
- **DNS** : `elexity34.j-arvis.ai → 51.38.38.226` (A record OVH).

## Arborescence sur le VPS

```
/home/jarvis/jarvis-platform/
├── jarvis-core/          # clone depuis github.com/j-arvis-platform/jarvis-core
│   └── .venv/            # uv venv, deps depuis requirements.txt
├── modules/              # module-photovoltaique, module-pwa (copié via tar)
├── tenant-configs/
│   └── tenant-elexity34/.env   # credentials (gitignored)
└── pwa-dist/dist/        # artefact build PWA copié dans /var/www/elexity34-pwa/

/etc/systemd/system/jarvis-agent.service   # service uvicorn
/etc/nginx/sites-available/elexity34.conf  # reverse proxy + HTTPS
/etc/letsencrypt/live/elexity34.j-arvis.ai/*  # certbot
/var/www/elexity34-pwa/                    # PWA servie par nginx
```

## Commandes de déploiement (rappel)

### Première install

```bash
# Depuis le poste dev
git push origin main  # jarvis-core
tar --exclude=node_modules --exclude=dist -czf /tmp/modules.tgz modules/
tar -czf /tmp/tenant.tgz tenant-configs/tenant-elexity34
(cd modules/module-pwa && npm run build)
tar -czf /tmp/pwa-dist.tgz -C modules/module-pwa dist
scp -i ~/.ssh/jarvis_v2 /tmp/*.tgz jarvis@51.38.38.226:/tmp/

# Sur le VPS
ssh -i ~/.ssh/jarvis_v2 jarvis@51.38.38.226
cd ~/jarvis-platform
git clone https://github.com/j-arvis-platform/jarvis-core.git   # une seule fois
tar xzf /tmp/modules.tgz
tar xzf /tmp/tenant.tgz
mkdir -p pwa-dist && tar xzf /tmp/pwa-dist.tgz -C pwa-dist

# Venv + deps
cd jarvis-core
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install 'fastapi>=0.110.0' 'uvicorn[standard]>=0.27.0' aiosmtplib

# Systemd
sudo cp ~/jarvis-platform/deployments/tenant-elexity34/jarvis-agent.service \
    /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis-agent

# Nginx + certbot
sudo apt-get install -y nginx python3-certbot-nginx
sudo cp ~/jarvis-platform/deployments/tenant-elexity34/nginx.conf \
    /etc/nginx/sites-available/elexity34.conf
sudo ln -sf /etc/nginx/sites-available/elexity34.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx --non-interactive --agree-tos \
    --email contact@elexity34.fr -d elexity34.j-arvis.ai --redirect

# PWA
sudo mkdir -p /var/www/elexity34-pwa
sudo cp -r ~/jarvis-platform/pwa-dist/dist/* /var/www/elexity34-pwa/
sudo chown -R www-data:www-data /var/www/elexity34-pwa
```

### Mise à jour backend (jarvis-core)

```bash
ssh -i ~/.ssh/jarvis_v2 jarvis@51.38.38.226 '
  cd ~/jarvis-platform/jarvis-core &&
  git pull --ff-only origin main &&
  source .venv/bin/activate &&
  uv pip install -q -r requirements.txt &&
  sudo systemctl restart jarvis-agent
'
```

### Mise à jour PWA

```bash
# Local
(cd modules/module-pwa && npm run build)
tar -czf /tmp/pwa-dist.tgz -C modules/module-pwa dist
scp -i ~/.ssh/jarvis_v2 /tmp/pwa-dist.tgz jarvis@51.38.38.226:/tmp/

# VPS
ssh -i ~/.ssh/jarvis_v2 jarvis@51.38.38.226 '
  rm -rf ~/jarvis-platform/pwa-dist/dist &&
  tar xzf /tmp/pwa-dist.tgz -C ~/jarvis-platform/pwa-dist &&
  sudo cp -r ~/jarvis-platform/pwa-dist/dist/* /var/www/elexity34-pwa/
'
```

## Vérifications rapides

```bash
# Backend
curl -s https://elexity34.j-arvis.ai/api/health

# PWA
curl -s -I https://elexity34.j-arvis.ai/ | head -1

# Logs backend
ssh -i ~/.ssh/jarvis_v2 jarvis@51.38.38.226 'sudo journalctl -u jarvis-agent -f'

# Logs nginx
ssh -i ~/.ssh/jarvis_v2 jarvis@51.38.38.226 'sudo tail -f /var/log/nginx/access.log'
```

## PWA

Voir `modules/module-pwa/README.md`. 3 écrans : Pulse / Actions / Chat. Preact + Vite + Tailwind v4. Build ~20 KB JS + 17 KB CSS.

## Backend FastAPI

Expose sous `/api` :
- `GET /api/health` — statut Supabase + Jarvis + skills chargés
- `GET /api/kpis` — 4 KPIs Pulse + 3 alertes
- `GET /api/file-humaine` — items pending
- `POST /api/file-humaine/{id}/decide` — `{decision: approved|rejected|reported}`
- `POST /api/chat` — message utilisateur, skills auto-matchés, retour Jarvis

## Post go-live à faire

- [ ] Rate limiter nginx sur `/api/chat` (anti-abus : 10 req/min/IP).
- [ ] Secrets management : migrer `.env` vers Bitwarden ou vault chiffré systemd.
- [ ] Monitoring : Uptime Kuma sur `/api/health` + alertes Telegram.
- [ ] Logs centralisés (journald → loki/grafana post Q3).
- [ ] Backup Supabase automatique hebdomadaire.
