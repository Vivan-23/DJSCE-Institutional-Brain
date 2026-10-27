# Production deployment & operations

> The production runbook. **Production** = the Oracle VM serving https://djsce.tanishthar.com, with real
> CE faculty data. **Development** = your laptop (`docker compose up`, see [USAGE.md](USAGE.md)) with synthetic
> or snapshot data. Last verified: 2026-10-28.

## 1. Environments

| | Development (laptop) | Production (VM) |
|---|---|---|
| URL | http://localhost:3000 | https://djsce.tanishthar.com |
| Data | synthetic demo data, or a copied snapshot | **real** staff, timetables, tickets |
| Compose files | `docker-compose.yml` | `docker-compose.yml` + `deploy/prod/docker-compose.prod.yml` (via `COMPOSE_FILE` in `.env`) |
| `institution.yaml` | repo copy (demo members, `demo123`) | VM's own copy, never overwritten by deploys |
| Registration / demo logins | on | off (`ALLOW_SELF_REGISTRATION=false`, `SHOW_DEMO_LOGINS=false`) |
| How code gets there | you edit it | **only** by pushing to the deploy branch → Jenkins |

Rules:
- Build and test on the laptop. Never point dev tools, `ingest_institutional.py` or the evaluator at production.
- Every schema change needs an Alembic migration that works on existing rows. Startup runs `alembic upgrade head`
  on the real database.
- Production config changes go in `deploy/prod/` and ship through the pipeline. Don't hand-edit files on the VM
  (the next deploy overwrites everything except `.env` and `institution.yaml`).
- Real data never goes into git. It moves only as snapshots in the private folder.

## 2. Topology

```
browser ─HTTPS─> Cloudflare (proxied, SSL mode "Full") ─> VM :80/:443 Caddy (tls internal)
                                                            ├─ /github-webhook/* → Jenkins (djsce_jenkins:8080)
                                                            └─ everything else  → frontend:3000 ─/api→ backend:8001
```
- VM: Oracle Cloud Always Free, Ubuntu 24.04 **ARM64**, 2 OCPU / 12 GB, 4 GB swap, Mumbai. Public IP 132.226.190.80.
- Open ports: 22 (SSH), 80, 443. Every other container port is bound to 127.0.0.1 (`deploy/prod/docker-compose.prod.yml`).
- `/home/ubuntu/djsce-brain`: the app (deploy target; `REVISION` holds the deployed commit).
- `/home/ubuntu/jenkins`: Jenkins compose + `secrets/` (admin password, deploy key, webhook secret).
- `/home/ubuntu/backups`: nightly snapshots + pre-deploy dumps.
- Secrets and logins: the private `PASSWORDS.md` (outside the repo). Never paste them into chats or commits.

## 3. Deploying

Push to the deploy branch (**`v2/faculty-workflow`** for now) on github.com/Vivan-23/DJSCE-Institutional-Brain.
The GitHub webhook triggers the Jenkins job `djsce-brain-deploy` ([`Jenkinsfile`](../Jenkinsfile)):

1. Backend tests (pytest in the freshly built backend image).
2. Frontend `npm run lint` + `tsc --noEmit`.
3. Pre-deploy `pg_dump` → `~/backups/predeploy-<date>-<sha>.dump` (last 10 kept).
4. rsync the commit into the app dir (keeps `.env`, `institution.yaml`), `docker compose up -d --build`.
5. Health check on backend `/health` and the frontend.

If any step fails, nothing after it runs. If tests or a build fail, the old containers keep serving.
Jenkins UI: `ssh -i ~/.ssh/oracle_djsce -L 8080:127.0.0.1:8080 ubuntu@132.226.190.80` → http://localhost:8080.

### Rollback
1. `git revert <bad commit>` and push. Jenkins redeploys the previous code.
2. If the bad deploy ran a migration that damaged data, restore the pre-deploy dump:
   ```bash
   cd ~/djsce-brain && docker compose stop backend celery_worker celery_beat
   docker compose exec -T postgres pg_restore -U djsce_brain_user -d djsce_brain_db --clean --if-exists < ~/backups/predeploy-<...>.dump
   docker compose up -d
   ```

## 4. Backups

- **Nightly** (cron 02:00 IST): `deploy/prod/backup.sh` stops the stack for 1–2 minutes and zips the Postgres,
  Neo4j and Chroma volumes into `~/backups/djsce-brain-snapshot-<stamp>.zip` (14 kept). The format matches
  `snapshot_export.ps1`, so `snapshot_restore.ps1` loads it onto a laptop.
- **Before every deploy**: Postgres dump (above).
- **Off the VM**: not automated yet. Copy a snapshot to the laptop now and then:
  `scp -i ~/.ssh/oracle_djsce ubuntu@132.226.190.80:backups/djsce-brain-snapshot-<stamp>.zip .`
  An Oracle Object Storage copy is planned.
- Restore on the VM: stop the stack, then for each volume run the alpine `find -delete && tar xzf` step from
  `snapshot_restore.ps1` against `djsce-brain_<volume>`, then `docker compose up -d`.

## 5. Logs and health

- `cd ~/djsce-brain && docker compose logs -f --tail=100 backend` (also `celery_worker`, `frontend`, `caddy`).
- Docker rotates container logs (20 MB × 5 per container, `/etc/docker/daemon.json`).
- `docker compose ps`, `free -m`, `df -h /`.
- Uptime: add a free UptimeRobot check on https://djsce.tanishthar.com/ (email alert).
- OpenTelemetry/tracing: deliberately not used. One server and one API process; structured logs + uptime
  checks are enough. Revisit only if the app grows to multiple servers.

## 6. Oracle Always Free notes

- Always Free VMs run indefinitely, but Oracle **stops** ones that stay under 20% CPU, network and memory
  for 7 days. The `keepalive` service holds ~2 GB of memory to stay above that line. Remove it once the
  account is upgraded to Pay-As-You-Go (no idle reclamation; Always Free usage stays free; budget alert set at $1).
- Don't resize above the Always Free A1 cap (check Governance → Limits). Stopping the VM gives back its
  capacity, and Mumbai has been out of A1 capacity before.

## 7. Never do this in production

- `docker compose down -v`, `docker volume prune`, or deleting `djsce-brain_*` volumes.
- Running `ingest_institutional.py`, the evaluator profile, or test suites against the live stack.
- Committing `.env`, `institution.yaml` from the VM, snapshots, dumps or anything from the private folder.
- Opening database ports in the Oracle security list.

## 8. First-time server setup (for rebuilding the VM)

1. Ubuntu 24.04 A1 VM; open TCP 80/443 in the security list; on the VM: `iptables -I INPUT 5 -p tcp --dport 80/443 -j ACCEPT`
   (+ `netfilter-persistent save`).
2. Install Docker (`curl -fsSL https://get.docker.com | sudo sh`), add 4 GB swap, set log rotation in `/etc/docker/daemon.json`.
3. Copy the code to `~/djsce-brain`; create `.env` from `deploy/prod/env.prod.example`; copy production `institution.yaml`.
4. Restore the latest snapshot (section 4), then `docker compose up -d --build`.
5. Jenkins: copy `deploy/jenkins/*` to `~/jenkins`, generate `secrets/{deploy_key,admin_password,webhook_secret}`,
   write `DOCKER_GID=<docker group id>` to `~/jenkins/.env`, `docker compose up -d --build`. Add the deploy key
   (read-only) and the webhook (`https://djsce.tanishthar.com/github-webhook/`, JSON, push events, secret) on GitHub.
6. Cron: `30 20 * * * /home/ubuntu/djsce-brain/deploy/prod/backup.sh >> /home/ubuntu/backups/backup.log 2>&1` (UTC).
7. DNS: Cloudflare A record `djsce` → VM IP, proxied, SSL mode Full.
8. Cloudflare custom rules: the zone's "Block the scanners" rule (for the portfolio) blocks `/login`, among other paths.
   Rule #1 **"Allow DJSCE Brain"** (`http.host eq "djsce.tanishthar.com"` → Skip all remaining custom rules + rate
   limiting; managed rules stay on) must stay first, or faculty get "Sorry, you have been blocked".
