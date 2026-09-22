#!/usr/bin/env bash
# The Yard — the one command Render runs for the service in render.yaml.
#
# waitress runs in the foreground so Render watches it and signals it directly.
# bot.py runs beside it because both processes open the same data/app.db, and a
# Render disk attaches to exactly one service. This is also the only copy of
# bot.py that may be running anywhere: Telegram refuses a second poller for the
# same token, so stop the laptop's bot before the first deploy.

set -euo pipefail

DISK="${DISK_MOUNT_PATH:-/var/yard}"

# The database, its backups and the payment screenshots all belong on the disk.
# DATA_DIR is a setting the app reads; RECEIPTS_DIR is not, so the checkout's
# private/receipts becomes a link into the disk before Flask is ever imported.
mkdir -p "$DISK/data" "$DISK/receipts"

if [ -L private/receipts ]; then
    :  # already linked by an earlier start in this container
elif [ -e private/receipts ]; then
    echo "render_start: private/receipts is a real folder in the checkout." >&2
    echo "  It is .gitignore'd and must be a link to $DISK/receipts, or every" >&2
    echo "  screenshot saved on the night is lost at the next deploy. Stopping." >&2
    exit 1
else
    ln -s "$DISK/receipts" private/receipts
fi

export DATA_DIR="${DATA_DIR:-$DISK/data}"

# Unset PUBLIC_URL means "use whatever address Render gave this service".
# Setting it in the dashboard (a custom domain) wins.
export PUBLIC_URL="${PUBLIC_URL:-${RENDER_EXTERNAL_URL:-}}"

# The bot: outbound only, no port. It sends everything the web process queues,
# so if it stops, bookings and reminders go quiet while the app looks fine —
# hence the restart loop rather than letting one crash end the evening.
if [ -n "${TELEGRAM_TOKEN:-}" ]; then
    (
        while true; do
            python -u bot.py || true
            echo "render_start: bot.py stopped; starting it again in 5s" >&2
            sleep 5
        done
    ) &
else
    echo "render_start: TELEGRAM_TOKEN is not set — the app runs, but no message goes out." >&2
fi

exec waitress-serve \
    --threads="${WEB_THREADS:-24}" \
    --listen="0.0.0.0:${PORT:-10000}" \
    app:app
