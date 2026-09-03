# groundsignal
Planning intelligence platform for discovering local construction opportunities from Irish planning data.

## Production Nginx and privacy-safe logging

Nginx is the production reverse proxy and static frontend server on EC2. Its
version-controlled configuration is in `deploy/nginx/`. The custom
`siteforecaster_safe` access-log format records the request method and `$uri`
path, but intentionally excludes query strings and referrers. This minimises
retention of user-entered location searches and coordinates. Uvicorn access
logging is disabled separately; Nginx error logging remains available.

### Install or update the Nginx configuration

From `/home/ubuntu/groundsignal` after deploying this repository revision:

```bash
sudo install -D -m 0644 deploy/nginx/siteforecaster-safe-logging.conf \
  /etc/nginx/conf.d/siteforecaster-safe-logging.conf
sudo install -D -m 0644 deploy/nginx/siteforecaster.conf \
  /etc/nginx/sites-available/siteforecaster
sudo ln -sfn /etc/nginx/sites-available/siteforecaster \
  /etc/nginx/sites-enabled/siteforecaster

sudo nginx -t
# Reload only after nginx -t succeeds.
sudo systemctl reload nginx
```

The live SSL certificate and private-key files referenced by this configuration
are managed separately. Never commit certificate or key material to this
repository.

## Production planning-data sync

Planning applications are stored locally in PostgreSQL. The initial full import
is a separate operation; ongoing production freshness uses inclusive rolling
`ReceivedDate` windows. Existing applications are updated and missing ones are
inserted by source object ID, so repeating a window is safe and idempotent.

- The recent, near-real-time sync runs every 15 minutes with a 7-day window.
- A 90-day reconciliation runs daily at 03:15 UTC.
- `ETL_DATE` is deliberately not used as an incremental watermark because the
  source batch-refreshes older records.

Both jobs run inside the existing Docker Compose `api` container and are
scheduled by systemd timers on the Ubuntu EC2 host. The 7-day timer has been
verified in production with a successful `status=0` run.

### Install the systemd timers

From `/home/ubuntu/groundsignal` after deploying this repository revision:

```bash
sudo cp deploy/systemd/siteforecaster-planning-sync.service /etc/systemd/system/
sudo cp deploy/systemd/siteforecaster-planning-sync.timer /etc/systemd/system/
sudo cp deploy/systemd/siteforecaster-planning-reconcile.service /etc/systemd/system/
sudo cp deploy/systemd/siteforecaster-planning-reconcile.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now siteforecaster-planning-sync.timer
sudo systemctl enable --now siteforecaster-planning-reconcile.timer
```

### Verify and operate

```bash
systemctl list-timers --all | grep siteforecaster
systemctl status siteforecaster-planning-sync.timer --no-pager
systemctl status siteforecaster-planning-reconcile.timer --no-pager
journalctl -u siteforecaster-planning-sync.service -n 50 --no-pager
journalctl -u siteforecaster-planning-reconcile.service -n 50 --no-pager
```

For a manual recent sync, the default window is 7 days:

```bash
docker compose exec -T api python -m backend.app.commands.planning_sync
docker compose exec -T api python -m backend.app.commands.planning_sync --days 90
```
