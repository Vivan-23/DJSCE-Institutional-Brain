# Production deployment & operations

> The production runbook. **Production** = the tanish-lab homelab server serving https://djsce.tanishthar.com,
> with real CE faculty data. **Development** = your laptop (`docker compose up`, see [USAGE.md](USAGE.md)) with synthetic
> or snapshot data. Last verified: 2026-11-03.

## 1. Environments

| | Development (laptop) | Production (tanish-lab) |
|---|---|---|
| URL | http://localhost:3000 | https://djsce.tanishthar.com |
| Data | synthetic demo data, or a copied snapshot | **real** staff, timetables, tickets |
| Compose files | `docker-compose.yml` | `docker-compose.yml` + `deploy/prod/docker-compose.prod.yml` + homelab `compose.limits.yml` |
| `institution.yaml` | repo copy (demo members, `demo123`) | server's own copy, never overwritten by deploys |
| Registration / demo logins | on | off (`ALLOW_SELF_REGISTRATION=false`, `SHOW_DEMO_LOGINS=false`) |
| How code gets there | you edit it | push to the deploy branch, then a manual deploy (section 3) |

Rules:
- Build and test on the laptop. Never point dev tools, `ingest_institutional.py` or the evaluator at production.
- Every schema change needs an Alembic migration that works on existing rows. Startup runs `alembic upgrade head`
  on the real database.
- Production config changes go in `deploy/prod/` and ship through the pipeline. Don't hand-edit files on the server
  (the next deploy overwrites everything except `.env` and `institution.yaml`).
- Real data never goes into git. It moves only as snapshots in the private folder.

## 2. Topology

```
browser ─HTTPS─> Cloudflare (proxied) ─> tanish-lab edge Caddy (10.0.0.11:443) ─> 127.0.0.1:3000 frontend ─/api→ backend:8001
```
- Host: **tanish-lab** (Tanish's homelab node). Production since 2026-11-03; the Oracle VM is retired.
- The edge Caddy belongs to the homelab (`~/tanpi-infra`), not to this repo. The app's own `caddy` service from
  `deploy/prod/` must **not** run there (it would take 80/443). Routes, DNS and edge changes are made in the
  homelab infra, not here.
- 8 services run: postgres, redis, chromadb, neo4j, backend, celery_worker, celery_beat, frontend. Not run:
  `caddy`, `keepalive` (Oracle-only), Jenkins.
- All ports are loopback only: frontend 3000, backend 8001, chroma 8002, neo4j 7474/7687, postgres 5432, redis 6379.
- App dir: `~/djsce-brain` on tanish-lab. Memory caps live outside the repo in
  `~/tanpi-infra/hosts/tanish-lab/djsce-brain/compose.limits.yml`.
- Secrets and logins: the server's `.env` and the private `PASSWORDS.md` (outside the repo). Never paste them into chats or commits.

## 3. Deploying

Deploys are **manual** (Jenkins is retired). Push to the deploy branch (**`v2/faculty-workflow`**) on
github.com/Vivan-23/DJSCE-Institutional-Brain first, then:

1. Test on the laptop: `cd backend && python -m pytest -q`; `cd frontend && npm run lint && npx tsc --noEmit`.
2. On tanish-lab, dump the database:
   `docker compose exec -T postgres pg_dump -U djsce_brain_user -Fc djsce_brain_db > ~/backups/predeploy-<date>-<sha>.dump`.
3. Update `~/djsce-brain` to the pushed commit, keeping its `.env` and `institution.yaml`.
4. Rebuild with the three compose files, naming the services so `caddy` and `keepalive` stay off:
   ```bash
   cd ~/djsce-brain && docker compose -f docker-compose.yml -f deploy/prod/docker-compose.prod.yml \
     -f ~/tanpi-infra/hosts/tanish-lab/djsce-brain/compose.limits.yml up -d --build \
     postgres redis chromadb neo4j backend celery_worker celery_beat frontend
   ```
5. Check `curl -fsS http://127.0.0.1:8001/health` and https://djsce.tanishthar.com/.

The `Jenkinsfile` and `deploy/jenkins/` are kept for reference only; nothing runs them.

### Rollback
1. Check out the previous good commit in `~/djsce-brain` and repeat step 4.
2. If the bad deploy ran a migration that damaged data, stop `backend celery_worker celery_beat`, restore the
   pre-deploy dump with `pg_restore -U djsce_brain_user -d djsce_brain_db --clean --if-exists`, then repeat step 4.

## 4. Backups

- **Nightly** (cron 02:00 IST): `deploy/prod/backup.sh` stops the stack for 1–2 minutes and zips the Postgres,
  Neo4j and Chroma volumes into `~/backups/djsce-brain-snapshot-<stamp>.zip` (14 kept). The format matches
  `snapshot_export.ps1`, so `snapshot_restore.ps1` loads it onto a laptop.
- **Before every deploy**: Postgres dump (above).
- **Off the server**: not automated yet. Copy a snapshot to the laptop now and then with `scp`.
- `backup.sh` uses the three tanish-lab compose files and only stops/starts the 8 app services (never `caddy`/`keepalive`).
  Cron (host in UTC): `30 20 * * * ~/djsce-brain/deploy/prod/backup.sh >> ~/backups/backup.log 2>&1`.
  Installation on tanish-lab not yet confirmed.
- Restore on the server: stop the stack, then for each volume run the alpine `find -delete && tar xzf` step from
  `snapshot_restore.ps1` against `djsce-brain_<volume>`, then `docker compose up -d`.

## 5. Logs and health

- `cd ~/djsce-brain && docker compose logs -f --tail=100 backend` (also `celery_worker`, `frontend`).
- Docker rotates container logs (20 MB × 5 per container, `/etc/docker/daemon.json`).
- `docker compose ps`, `free -m`, `df -h /`.
- Uptime: add a free UptimeRobot check on https://djsce.tanishthar.com/ (email alert).
- OpenTelemetry/tracing: deliberately not used. One server and one API process; structured logs + uptime
  checks are enough. Revisit only if the app grows to multiple servers.

## 6. Oracle VM (retired 2026-11-03)

Production ran on an Oracle Always Free ARM VM from 2026-10-28 to 2026-11-03, with its own Caddy, the
`keepalive` service and Jenkins CI/CD. Those files stay in `deploy/prod/` and `deploy/jenkins/` for reference
but are not used on tanish-lab.

## 7. Never do this in production

- `docker compose down -v`, `docker volume prune`, or deleting `djsce-brain_*` volumes.
- Running `ingest_institutional.py`, the evaluator profile, or test suites against the live stack.
- Committing `.env`, `institution.yaml` from the VM, snapshots, dumps or anything from the private folder.
- Starting the app's `caddy` (it would take 80/443 from the homelab edge) or binding a port to a non-loopback address.

## 8. Rebuilding the server

1. Docker on the host; copy the code to `~/djsce-brain`; create `.env` from `deploy/prod/env.prod.example`;
   copy the production `institution.yaml`.
2. Restore the latest snapshot (section 4), then start the 8 services as in section 3, step 4.
3. Ask the homelab owner to route `djsce.tanishthar.com` → `127.0.0.1:3000` on the edge Caddy.
4. Cron for `deploy/prod/backup.sh` (section 4).
5. Cloudflare custom rules: the zone's "Block the scanners" rule (for the portfolio) blocks `/login`, among other paths.
   Rule #1 **"Allow DJSCE Brain"** (`http.host eq "djsce.tanishthar.com"` → Skip all remaining custom rules + rate
   limiting; managed rules stay on) must stay first, or faculty get "Sorry, you have been blocked".
