# DEPLOY — moving The Yard from a laptop + tunnel to a real server

For the developer helping the organiser. Everything here is what you need to
host it; `STATE.md` is the full handover if you want the why behind the code.

**The event is Thursday 24 September 2026, 3–10 PM (Singapore).** Aim to have
the server live and tested by the evening of the 23rd, and keep the laptop
setup as the fallback until the night is over.

---

## 1. What you are hosting

Two long-running Python processes and one SQLite file. No build step, no
Node at runtime, no external database.

| Process | Command | Notes |
|---|---|---|
| Web (Flask) | `waitress-serve --threads=24 --listen=127.0.0.1:5000 app:app` | Serves the Telegram Mini App (`/`), the staff console (`/admin`) and the API. Also runs the automatic backup thread. |
| Bot | `python bot.py` | Telegram **long polling**, outbound only, so it needs no port. Sends every queued message (bookings, reminders, the escape room's phone link). |

Hard constraints — each of these is load-bearing:

1. **Exactly one web process.** Rate limits, the console's live-update
   stream and the booking race protections assume one process with threads.
   waitress with threads is fine; gunicorn with several workers is not.
2. **Exactly one `bot.py` anywhere.** Telegram refuses a second poller for
   the same token (`Conflict` in the log). Stop the laptop's bot before
   starting the server's.
3. **The SQLite file needs a persistent disk.** `data/app.db` (WAL mode) is
   the whole state of the event: who paid, who collected what, every booking.
   Not an ephemeral container filesystem.
4. **HTTPS on a public domain.** Telegram Mini Apps only open `https://`
   URLs, and the console's session cookie is `Secure`.
5. **Never `python app.py` on the server.** That is the laptop's dev mode:
   Flask debug, with the auto-reloader and the interactive debugger.
6. **`/admin/api/live` is server-sent events.** The reverse proxy must not
   buffer it (Caddy is fine as below; nginx needs `proxy_buffering off`).

A small VPS is plenty (1 vCPU, 1 GB RAM): ~170 attendees, one evening.

---

## 2. What is not in the repository, and how to get it

The repo is **private** and must stay that way: it holds the escape room's
solution (`private/`, `ESCAPE_ROOM_FLOW.md`, `context/`) and attendees'
Telegram usernames in the tests. `.gitignore` keeps these out entirely:

| Missing piece | What it is | How you get it |
|---|---|---|
| `.env` | Bot token, Flask secret, password/PIN hashes, `PUBLIC_URL` | From the organiser over a private channel. Never commit it. `.env.example` lists the keys. |
| `data/app.db` | The live database | Copied at cutover (section 4), never earlier — it changes all the time. |
| `private/receipts/` | Saved payment screenshots | Copied at cutover with the database. Admin-only; may be empty. |
| `imports/`, `*.xlsx` | Paperform exports with names and emails | Not needed on the server. |
| `context/The_Yard_Sign_Up_Responses.xlsx` | The real sign-up export the tests run against | Only if you want to run `pytest` (section 5). |

---

## 3. Server setup (Ubuntu 24.04, Caddy, systemd)

Python 3.12 or newer (the laptop runs 3.14). Replace `yard.example.com`
with the real domain, pointed at the server with an A record first.

```bash
sudo apt update && sudo apt install -y python3-venv git caddy
sudo useradd --system --create-home --home-dir /srv/the-yard yard
sudo -u yard git clone <the private repo URL> /srv/the-yard/app
cd /srv/the-yard/app
sudo -u yard python3 -m venv venv
sudo -u yard venv/bin/pip install -r requirements.txt
```

Put the organiser's `.env` at `/srv/the-yard/app/.env` (owner `yard`, mode
600) and change one line in it:

```
PUBLIC_URL=https://yard.example.com
```

`/etc/systemd/system/yard-web.service`:

```ini
[Unit]
Description=The Yard - web
After=network.target

[Service]
User=yard
WorkingDirectory=/srv/the-yard/app
ExecStart=/srv/the-yard/app/venv/bin/waitress-serve --threads=24 --listen=127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/yard-bot.service`:

```ini
[Unit]
Description=The Yard - Telegram bot
After=network.target yard-web.service

[Service]
User=yard
WorkingDirectory=/srv/the-yard/app
ExecStart=/srv/the-yard/app/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

`/etc/caddy/Caddyfile` (Caddy fetches the certificate by itself):

```
yard.example.com {
    reverse_proxy 127.0.0.1:5000 {
        flush_interval -1
    }
}
```

```bash
sudo systemctl daemon-reload
sudo systemctl reload caddy
sudo systemctl enable yard-web yard-bot   # enable only; do not start the bot yet
```

**Dry run before cutover** (safe while the laptop is still live): start only
the web process, which creates an empty database, and check the address.

```bash
sudo systemctl start yard-web
curl https://yard.example.com/healthz        # {"ok": true, "data": {"status": "up"}, ...}
sudo systemctl stop yard-web
sudo -u yard rm -f /srv/the-yard/app/data/app.db*   # throw the empty one away
```

---

## 4. Cutover (about 15 minutes, with the organiser)

Do these in order. Between steps 1 and 5 attendees can't open the app, so do
it at a quiet time.

1. **Organiser, on the laptop:** close the `app.py` (or waitress) window and
   the `bot.py` window. Closing the web process cleanly folds the WAL into
   `app.db`.
2. **Copy the state to the server.** From the laptop (PowerShell has `scp`):

   ```powershell
   cd C:\Users\endrw\my-mini-app
   scp data\app.db yard@yard.example.com:/srv/the-yard/app/data/
   scp -r private\receipts yard@yard.example.com:/srv/the-yard/app/private/
   ```

   If `data\app.db-wal` is not 0 bytes, the web process didn't close cleanly:
   copy `app.db-wal` too, alongside `app.db`.
3. **Server:** `sudo systemctl start yard-web yard-bot`, then
   `journalctl -u yard-bot -n 20` should show `Menu button points at
   https://yard.example.com` and `Bot started, polling`.
4. **BotFather:** update the bot's Mini App URL to `https://yard.example.com`
   (the organiser's Telegram account owns the bot). `bot.py` resets the chat
   menu button by itself; the Mini App URL is the one thing it can't set.
5. **Test from a phone on mobile data, wifi off:** open the bot, tap Open The
   Yard, and you should see the Start gate with the organiser's name. Then open
   `https://yard.example.com/admin` on a laptop and sign in; Overview should
   show the real headcount.

From here the server is the only copy that matters. **Never start the
laptop's `app.py` or `bot.py` again** unless you are rolling back: two copies
of the database drift apart silently.

**Rollback:** stop both services, copy `data/app.db` back to the laptop's
`data\` folder, and start the laptop setup as before (`scripts\start_event.ps1`,
ngrok or Tailscale Funnel), including the BotFather URL.

---

## 5. Day to day

- **Logs:** `journalctl -u yard-web -f` and `journalctl -u yard-bot -f`.
- **Backups:** the web process copies the database into `data/backups/`
  every 10 minutes (Settings → Access & safety). Copy that folder off the
  server after the event too.
- **Admin commands** run in the project folder as the `yard` user, e.g.
  `sudo -u yard venv/bin/python manage.py notify on` (switch messages on for
  everyone), `... manage.py outbox`, `... manage.py backup`.
- **Code updates:** `git pull`, then `sudo systemctl restart yard-web yard-bot`.
  A restart takes a second or two. The organiser changes prices, places,
  times and stock on the Settings screen, which needs no restart.
- **Tests** (optional): put the sign-up export at
  `context/The_Yard_Sign_Up_Responses.xlsx`, then `venv/bin/python -m pytest
  tests -q`, which should say `430 passed`. Without that file, the tests that
  import the real roster fail; that says nothing about the server.

---

## 6. Where things are

`README.md` is the file map and reading order; `STATE.md` has every decision
and why; `RUNBOOK.md` is the organiser's step-by-step for the laptop setup;
`HOW_IT_WORKS.md` explains the layers for a non-developer. The error codes
the app shows are in `RUNBOOK.md` near the end.
