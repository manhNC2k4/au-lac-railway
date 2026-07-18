# Deployment Guide — CI/CD to VPS

Pipeline: push to `main` → GitHub Actions builds backend + frontend images → pushes to GHCR → SSHes into the VPS → `git pull` + `docker compose pull/up`. Nginx on the VPS (already installed) reverse-proxies two subdomains to the containers.

## One-time VPS setup

Docker + Nginx are assumed already installed (`docker compose version`, `nginx -v`). Also install certbot: `apt install certbot python3-certbot-nginx`.

1. Clone the repo onto the VPS, e.g. `git clone <repo-url> /opt/aulac-railway`.
2. `cd /opt/aulac-railway && cp .env.prod.example .env` and fill in real `POSTGRES_PASSWORD`, `GHCR_OWNER` (your GitHub org/user, lowercase), `GHCR_REPO`.
3. If the GHCR packages are **private**, log in once so the VPS can pull: `echo <PAT-with-read:packages> | docker login ghcr.io -u <github-user> --password-stdin`. Simplest alternative: after the first push, make the two packages public in GitHub → Packages settings, then skip this step entirely.
4. Nginx sites — copy `deploy/nginx/app.conf.example` → `/etc/nginx/sites-available/app.<your-domain>` and `deploy/nginx/api.conf.example` → `/etc/nginx/sites-available/api.<your-domain>`, replacing the placeholder `server_name`. Symlink both into `sites-enabled`, then:
   ```bash
   nginx -t && systemctl reload nginx
   certbot --nginx -d app.<your-domain> -d api.<your-domain>
   ```
   Point both subdomains' DNS A records at the VPS IP before running certbot.
5. First deploy: `docker compose -f docker-compose.prod.yml --env-file .env pull && docker compose -f docker-compose.prod.yml --env-file .env up -d`.

## GitHub repo secrets

Set under Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `VPS_HOST` | VPS IP or hostname |
| `VPS_USER` | SSH user (e.g. `deploy`) |
| `VPS_PASSWORD` | SSH password for `VPS_USER` |
| `VPS_PORT` | SSH port, optional, defaults to 22 |
| `VPS_APP_DIR` | absolute path of the repo clone on the VPS, e.g. `/opt/aulac-railway` |

`GITHUB_TOKEN` (built-in, no setup) is used to push images to GHCR from the workflow — it doesn't need adding.

## What the workflow does (`.github/workflows/deploy.yml`)

1. `build-push`: builds `backend/Dockerfile` and `web/Dockerfile`, pushes `ghcr.io/<owner>/aulac-railway-{backend,frontend}:latest` and `:<short-sha>`.
2. `deploy`: SSHes in, `git pull --ff-only` (picks up compose/nginx/migration changes), `docker compose pull` + `up -d --remove-orphans`, prunes dangling images.

Flyway migrations run automatically on `up` via the `flyway` service before `backend` starts (same as local dev).

## Rollback

`IMAGE_TAG` in the VPS `.env` defaults to `latest`. To pin a known-good build: set `IMAGE_TAG=<short-sha>` in `.env`, then `docker compose -f docker-compose.prod.yml up -d`.
