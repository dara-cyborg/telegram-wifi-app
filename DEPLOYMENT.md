# Deployment guide

This guide deploys the Internet Payment Tracker to an Ubuntu 24.04 DigitalOcean
Droplet behind Caddy with HTTPS.

## 1. Prerequisites

Prepare:

- An Ubuntu 24.04 server with a public IPv4 address
- A DNS `A` record such as `tracker.example.com` pointing to the server
- A Telegram bot token
- The Telegram group chat ID
- The administrator's Telegram user ID

The application must run with one Uvicorn worker. The scheduler is embedded in
the application and multiple workers would send duplicate daily reports.

## 2. Create the server

Connect as root:

```bash
ssh root@SERVER_IP
```

Install system packages and create a restricted application user:

```bash
apt update
apt upgrade -y
apt install -y python3 python3-venv python3-pip git sqlite3 caddy ufw

adduser --system --group --home /opt/internet-payment-tracker paymenttracker
mkdir -p /opt/internet-payment-tracker
chown -R paymenttracker:paymenttracker /opt/internet-payment-tracker
```

Set the server timezone:

```bash
timedatectl set-timezone Asia/Phnom_Penh
timedatectl status
```

Allow SSH and HTTPS, then enable the firewall:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

## 3. Install the application

Clone the repository as the application user:

```bash
sudo -u paymenttracker git clone \
  https://github.com/dara-cyborg/telegram-wifi-app.git \
  /opt/internet-payment-tracker
cd /opt/internet-payment-tracker
```

Create and activate the production virtual environment:

```bash
sudo -u paymenttracker python3 -m venv venv
sudo -u paymenttracker venv/bin/python -m pip install --upgrade pip
sudo -u paymenttracker venv/bin/pip install -r requirements.txt
sudo -u paymenttracker mkdir -p data
```

The virtual environment is mandatory. Do not install application packages with
the system-wide `pip`.

## 4. Configure secrets

Create the environment file:

```bash
sudo -u paymenttracker cp .env.example .env
sudo -u paymenttracker nano .env
```

Set real values:

```ini
TELEGRAM_BOT_TOKEN=123456789:real-token
TELEGRAM_GROUP_CHAT_ID=-1001234567890
ADMIN_TELEGRAM_ID=987654321
TIMEZONE=Asia/Phnom_Penh
DATABASE_PATH=/opt/internet-payment-tracker/data/tracker.db
DEV_MODE=false
PORT=8000
```

Protect the file:

```bash
chown paymenttracker:paymenttracker .env
chmod 600 .env
```

Never commit `.env` or paste the bot token into issue reports or logs.

## 5. Initialize and test the application

Initialize the database:

```bash
sudo -u paymenttracker venv/bin/python -c \
  "from app.database import initialize_database; initialize_database('/opt/internet-payment-tracker/data/tracker.db')"
```

Run the tests:

```bash
sudo -u paymenttracker venv/bin/python -m pytest -q
```

Run a temporary local check:

```bash
sudo -u paymenttracker venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 1
```

From a second SSH session:

```bash
curl -I http://127.0.0.1:8000/
```

Stop the temporary server with `Ctrl+C`.

## 6. Install the systemd service

Install the included service:

```bash
cp systemd/payment-tracker.service /etc/systemd/system/payment-tracker.service
systemctl daemon-reload
systemctl enable --now payment-tracker
systemctl status payment-tracker --no-pager
```

Inspect application logs:

```bash
journalctl -u payment-tracker -n 100 --no-pager
journalctl -u payment-tracker -f
```

## 7. Configure Caddy and HTTPS

Replace the placeholder hostname in the Caddy configuration:

```bash
sed 's/tracker.yourdomain.com/tracker.example.com/' \
  Caddyfile > /etc/caddy/Caddyfile
```

Validate and reload Caddy:

```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl enable --now caddy
systemctl reload caddy
systemctl status caddy --no-pager
```

Caddy obtains and renews the HTTPS certificate automatically. Verify the
public endpoint:

```bash
curl -I https://tracker.example.com/
```

Do not expose port `8000` publicly; Uvicorn must remain bound to
`127.0.0.1`.

## 8. Register the Telegram Mini App

In Telegram:

1. Open `@BotFather`.
2. Select the bot.
3. Open **Bot Settings** → **Menu Button**.
4. Set the Mini App URL to `https://tracker.example.com`.
5. Open the Mini App from the administrator account.

The app requires a valid Telegram `initData` signature and the configured
`ADMIN_TELEGRAM_ID`.

## 9. Verify production behavior

Check all of the following:

```bash
systemctl is-active payment-tracker
systemctl is-active caddy
curl -I https://tracker.example.com/
```

From the Mini App:

1. Create a test tenant.
2. Confirm its MAC address is displayed.
3. Mark the tenant as paid.
4. Confirm the next due date.
5. Trigger **Send Group Report**.
6. Confirm the Telegram group receives the report.

The scheduled report runs daily at `06:00` in `Asia/Phnom_Penh`.

## 10. Updates

Back up the database before updating:

```bash
sudo -u paymenttracker sqlite3 data/tracker.db \
  ".backup 'data/tracker-$(date +%Y%m%d-%H%M%S).db'"
```

Deploy a new version:

```bash
cd /opt/internet-payment-tracker
systemctl stop payment-tracker
sudo -u paymenttracker git pull --ff-only
sudo -u paymenttracker venv/bin/pip install -r requirements.txt
sudo -u paymenttracker venv/bin/python -m pytest -q
systemctl start payment-tracker
systemctl status payment-tracker --no-pager
```

If the test or startup check fails, leave the service stopped and inspect:

```bash
journalctl -u payment-tracker -n 200 --no-pager
```

## 11. Backups and recovery

Keep database backups outside the server. SQLite backups should be created with
the SQLite `.backup` command while the application is running:

```bash
sudo -u paymenttracker sqlite3 data/tracker.db \
  ".backup 'data/tracker-latest.db'"
```

Restore only while the service is stopped:

```bash
systemctl stop payment-tracker
sudo -u paymenttracker cp data/tracker-latest.db data/tracker.db
systemctl start payment-tracker
```

Confirm the service is healthy and verify tenant data through the Mini App
after a restore.

## 12. Common operations

Restart the application:

```bash
systemctl restart payment-tracker
```

Restart Caddy:

```bash
systemctl reload caddy
```

Check listening ports:

```bash
ss -tulpn
```

The expected public listeners are Caddy on ports `80` and `443`; Uvicorn
should listen only on `127.0.0.1:8000`.
