# Security configuration

This application is an admin-only Telegram Mini App. The most important
security objective is to stop unsolicited traffic at the edge, before it
reaches Uvicorn, SQLite, or the Telegram API. No single setting can guarantee
that all bot traffic is blocked; use all layers in this guide.

## Required traffic path

```text
Telegram Mini App
    -> Cloudflare proxy and WAF
    -> Caddy on ports 80/443
    -> Uvicorn on 127.0.0.1:8001
    -> FastAPI authentication
```

Do not expose Uvicorn directly. The public hostname is:

```text
https://internet.daramongkol.tech
```

## 1. Cloudflare edge protection

Put the DNS record for `internet.daramongkol.tech` behind the orange-cloud
Cloudflare proxy. Do not publish the server IP in DNS.

Use these settings in the Cloudflare dashboard:

### SSL/TLS

- Encryption mode: **Full (strict)**
- Always Use HTTPS: **On**
- Minimum TLS Version: **TLS 1.2**
- Automatic HTTPS Rewrites: **On**

Install the origin certificate on the server if using Full (strict). Do not
use Flexible mode.

### WAF managed rules

Enable the Cloudflare managed ruleset and OWASP Core Ruleset. Set the action to
**Managed Challenge** first, then move confirmed attack rules to **Block**.
Never disable the WAF globally to fix a single false positive.

### Bot protection

Enable the strongest bot protection available on the Cloudflare plan:

- Bot Fight Mode or Super Bot Fight Mode
- Browser Integrity Check
- Challenge Passage with a short duration
- Hotlink Protection if static assets are not embedded elsewhere

Telegram WebViews must remain able to load the page and JavaScript. If a
challenge blocks the Mini App, use a narrow skip rule for the application page
only, not a global bypass.

### Rate limiting rules

Create rate limiting rules with these starting values:

| Scope | Threshold | Action |
|---|---:|---|
| All requests to the hostname | 120 requests/minute/IP | Managed Challenge |
| `POST /api/*` | 20 requests/minute/IP | Block for 10 minutes |
| `PUT`, `DELETE` `/api/*` | 10 requests/minute/IP | Block for 10 minutes |
| `POST /api/report/trigger` | 3 requests/10 minutes/IP | Block for 1 hour |
| Requests to probe paths | 5 requests/minute/IP | Block |

Use a longer counting period for the report endpoint because every successful
request sends a real Telegram message. The application authentication remains
mandatory; a rate limit is not an authorization control.

If the Cloudflare plan cannot rate-limit by method, create separate hostname
rules for the API paths and set the action to Block or Managed Challenge.

### Firewall rules

Allow only:

- `GET /`
- `GET /app.js`
- `GET /api/*` from legitimate Mini App traffic after the challenge policy
- `POST`, `PUT`, and `DELETE /api/*` only when authenticated by the application

Block common automated probes:

```text
*/wp-admin*
*/wp-login.php
*/xmlrpc.php
*/.env*
*/.git/*
*/phpmyadmin*
*/server-status
```

## 2. Server firewall and origin protection

On the server, expose only SSH, HTTP, and HTTPS:

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 8001/tcp
ufw enable
ufw status verbose
```

The application must listen only on loopback:

```bash
ss -lntp
```

Expected application listener:

```text
127.0.0.1:8001
```

For stronger origin protection, configure the cloud provider firewall to allow
ports 80 and 443 only from the published Cloudflare IP ranges. Keep SSH
restricted to your fixed administrative IP or VPN whenever possible. Cloudflare
publishes its current ranges at <https://www.cloudflare.com/ips/>.

If Cloudflare is enabled but the origin remains reachable by IP, attackers can
bypass Cloudflare rate limits. Treat an exposed origin IP as a security
incident: rotate the server IP or restrict the provider firewall immediately.

## 3. Caddy configuration

The repository [Caddyfile](./Caddyfile) already:

- Serves the configured domain only
- Rejects common WordPress, Git, environment, and status probes
- Adds HSTS and browser security headers
- Proxies only to `127.0.0.1:8001`

Validate and reload it:

```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
```

Do not add a Caddy rate-limit plugin casually. Plugins change the server
binary and must be pinned, reviewed, and rebuilt during upgrades. Cloudflare
is the preferred edge rate limiter for this deployment.

## 4. systemd service isolation

The included [payment-tracker.service](./systemd/payment-tracker.service)
restricts the process with:

- No privilege escalation
- A private temporary directory
- No access to user home directories
- A read-only filesystem except for the SQLite data directory
- Restricted network families
- Memory and real-time execution restrictions

Install the hardened unit and verify it:

```bash
cp systemd/payment-tracker.service /etc/systemd/system/payment-tracker.service
systemctl daemon-reload
systemctl restart payment-tracker
systemctl status payment-tracker --no-pager
```

The service account must own the data directory:

```bash
chown -R paymenttracker:paymenttracker /opt/internet-payment-tracker/data
chmod 700 /opt/internet-payment-tracker/data
chmod 600 /opt/internet-payment-tracker/.env
```

## 5. Application authentication controls

Keep these production settings:

```ini
DEV_MODE=false
TIMEZONE=Asia/Phnom_Penh
PORT=8001
```

Every API endpoint requires the Telegram `initData` HMAC signature and the
configured `ADMIN_TELEGRAM_ID`. Never add a public health endpoint, API key in
the frontend, or unauthenticated report endpoint.

`DEV_MODE=true` bypasses authentication for local testing. It must never be
used on the public domain.

Rotate the Telegram bot token immediately if it appears in shell history,
logs, screenshots, source control, or a support request:

1. Generate a new token with BotFather.
2. Update `.env`.
3. Set file permissions back to `600`.
4. Restart the service.
5. Verify the Mini App and group report.

## 6. Resource and abuse controls

Monitor these commands during an attack:

```bash
journalctl -u payment-tracker -f
journalctl -u caddy -f
ss -s
df -h
free -h
```

Set log rotation at the host level. Do not allow request logs to fill the
disk. Keep only the retention period needed for incident investigation.

If the server is overloaded:

1. Enable Cloudflare **I'm Under Attack Mode** temporarily.
2. Tighten the API and report rate limits.
3. Temporarily disable the report trigger in the Cloudflare WAF.
4. Preserve SSH access from your administrative IP.
5. Check whether the origin IP is bypassing Cloudflare.

If the Telegram bot itself is being abused, rotate the bot token and review
the BotFather menu-button URL before restoring traffic.

## 7. Deployment verification checklist

Run after every deployment:

```bash
curl -I https://internet.daramongkol.tech/
curl -i https://internet.daramongkol.tech/api/tenants
curl -i https://internet.daramongkol.tech/wp-admin/
curl -i http://127.0.0.1:8001/
```

Expected results:

- HTTPS page: `200` or the normal static response
- API without Telegram authorization: `403`
- Probe path: `404`
- Local Uvicorn response: available only on the server
- Public `:8001`: unreachable

Test rate limits from a controlled administrative client only. Do not use
load-testing tools against the production endpoint without an explicit
maintenance window.

## 8. Emergency shutdown

If abuse is burning resources and Cloudflare controls are not taking effect:

```bash
ufw deny 80/tcp
ufw deny 443/tcp
systemctl stop payment-tracker
```

Keep SSH available. After the attack is contained, inspect Cloudflare
Security Events and service logs, restore only the required firewall rules, and
restart the service after correcting the edge policy.
