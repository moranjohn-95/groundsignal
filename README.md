# groundsignal
Planning intelligence platform for discovering local construction opportunities from Irish planning data.

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
