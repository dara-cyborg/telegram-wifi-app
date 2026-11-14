# Updating the production app

Use this guide whenever a new version of the Telegram Mini App is ready. The
commands assume the deployment documented in [DEPLOYMENT.md](./DEPLOYMENT.md):

- Repository: `/opt/internet-payment-tracker`
- Service: `payment-tracker`
- Application user: `paymenttracker`
- Database: `/opt/internet-payment-tracker/data/tracker.db`

## 1. Connect and check the current service

Connect to the server and confirm the application is healthy before making
changes:

```bash
ssh root@SERVER_IP
systemctl is-active payment-tracker
systemctl status payment-tracker --no-pager
```

Do not continue if the service is already unhealthy. Check the logs first:

```bash
journalctl -u payment-tracker -n 200 --no-pager
```

## 2. Create a backup

The scheduled backup script should already be installed at
`/usr/local/sbin/backup-telegram-order-bot`. Run it manually before every
update:

```bash
/usr/local/sbin/backup-telegram-order-bot
ls -lh /opt/backups/telegram-order-bot/
```

The script uses SQLite's `.backup` command, keeps backups for 14 days, and
stores them outside the application directory. Do not continue unless a new
backup file was created successfully.

## 3. Pull and validate the update

Stop the service so the application is not serving code while dependencies are
being changed:

```bash
cd /opt/internet-payment-tracker
systemctl stop payment-tracker
sudo -u paymenttracker git pull --ff-only
sudo -u paymenttracker venv/bin/pip install -r requirements.txt
sudo -u paymenttracker venv/bin/python -m pytest -q
```

If `git pull`, dependency installation, or the tests fail, do not start the
service. Inspect the error, restore the previous revision if needed, and keep
the service stopped until the problem is resolved.

## 4. Start and verify the update

```bash
systemctl start payment-tracker
systemctl status payment-tracker --no-pager
systemctl is-active payment-tracker
curl -I https://internet.daramongkol.tech/
journalctl -u payment-tracker -n 100 --no-pager
```

Then verify the Mini App manually:

1. Sign in with the administrator Telegram account.
2. Confirm existing tenants and payment status are present.
3. Open a tenant and confirm its MAC address and due date.
4. If appropriate, send a test group report and confirm it arrives.

## 5. Roll back a failed update

If the new version fails after it starts, stop the service and restore the
previous Git revision. Replace `PREVIOUS_COMMIT` with the commit shown by
`git log` before the update:

```bash
cd /opt/internet-payment-tracker
systemctl stop payment-tracker
sudo -u paymenttracker git switch --detach PREVIOUS_COMMIT
sudo -u paymenttracker venv/bin/pip install -r requirements.txt
sudo -u paymenttracker venv/bin/python -m pytest -q
systemctl start payment-tracker
systemctl status payment-tracker --no-pager
```

Only restore the database when data is damaged or missing. Stop the service
first, copy the selected backup into the database path, and then start and
verify the service:

```bash
systemctl stop payment-tracker
sudo -u paymenttracker cp \
  /opt/backups/telegram-order-bot/orders-YYYYMMDD-HHMMSS.db \
  /opt/internet-payment-tracker/data/tracker.db
systemctl start payment-tracker
systemctl status payment-tracker --no-pager
```

## 6. Configure scheduled backups once

Install the repository's backup script and make it executable:

```bash
mkdir -p /opt/backups/telegram-order-bot
cp /opt/internet-payment-tracker/scripts/backup-telegram-order-bot \
  /usr/local/sbin/backup-telegram-order-bot
chmod 700 /usr/local/sbin/backup-telegram-order-bot
```

Add the daily cron job with `crontab -e`:

```cron
15 2 * * * /usr/local/sbin/backup-telegram-order-bot
```

Test it immediately:

```bash
/usr/local/sbin/backup-telegram-order-bot
ls -lh /opt/backups/telegram-order-bot/
```

Backups on the same server do not protect against disk loss. Periodically
copy the backup directory to a separate, access-controlled server or storage
location.
