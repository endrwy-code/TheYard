"""One-off commands, run by hand from PowerShell.

    python manage.py init-db
    python manage.py import imports\\The_Yard_Sign_Up_Responses.xlsx
    python manage.py make-secret
    python manage.py set-admin-password
    python manage.py set-staff-pin
    python manage.py set-gm-pin
    python manage.py backup
    python manage.py roster
    python manage.py void-claim maxi_muslim pastry "booth rehearsal"
    python manage.py generate-slots
    python manage.py cancel-group maxi_muslim "test booking"
    python manage.py set-public-url https://moonlight-dwelling-footpad.ngrok-free.dev
    python manage.py notify owner|on|off
    python manage.py notify-test maxi_muslim
    python manage.py outbox
"""

import getpass
import secrets
import sys
from pathlib import Path

import config
import db
from auth import hash_secret
from services import roster


def _say(msg=""):
    print(msg)


def _write_env(key, value):
    """Put KEY=value into .env, replacing the line if it is already there."""
    path = config.BASE_DIR / ".env"
    if not path.exists():
        example = config.BASE_DIR / ".env.example"
        path.write_text(example.read_text(encoding="utf-8") if example.exists() else "",
                        encoding="utf-8")
    lines = path.read_text(encoding="utf-8").splitlines()
    out, done = [], False
    for line in lines:
        if line.strip().startswith(f"{key}=") and not line.strip().startswith("#"):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------

def cmd_init_db(argv):
    existed = db.init_db()
    conn = db.connect()
    try:
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    finally:
        conn.close()
    _say("Database already up to date." if existed else "Database created.")
    _say(f"  {config.DB_PATH}")
    _say(f"  {len(tables)} tables: {', '.join(tables)}")
    return 0


def cmd_make_secret(argv):
    value = secrets.token_urlsafe(48)
    path = _write_env("FLASK_SECRET_KEY", value)
    _say(f"FLASK_SECRET_KEY written to {path}.")
    _say("You should see a long random line in .env. Nothing else to do.")
    return 0


def _set_secret(env_key, prompt, label, min_len):
    first = getpass.getpass(f"{prompt}: ")
    if len(first.strip()) < min_len:
        _say(f"Too short — {label} needs at least {min_len} characters. Nothing was changed.")
        return 1
    again = getpass.getpass("Type it again: ")
    if first != again:
        _say("Those two did not match. Nothing was changed.")
        return 1
    path = _write_env(env_key, hash_secret(first))
    _say(f"{label} saved to {path} as a hash.")
    _say(f"You should see {env_key}= followed by a long string starting with 'scrypt:' or 'pbkdf2:'.")
    return 0


def cmd_set_admin_password(argv):
    return _set_secret("ADMIN_PASSWORD_HASH", "New admin password", "The admin password", 8)


def cmd_set_staff_pin(argv):
    return _set_secret("STAFF_PIN_HASH", "New staff PIN", "The staff PIN", 4)


def cmd_set_gm_pin(argv):
    _say("The GM console shows the whole solution. Keep this PIN away from booth volunteers.")
    return _set_secret("GM_PIN_HASH", "New GM PIN", "The GM PIN", 4)


def cmd_import(argv):
    assume_yes = "--yes" in argv
    argv = [a for a in argv if a != "--yes"]
    if not argv:
        _say("Which file? For example:")
        _say(r"  python manage.py import imports\The_Yard_Sign_Up_Responses.xlsx")
        return 1
    path = Path(argv[0])
    if not path.is_absolute():
        path = config.BASE_DIR / path
    if not path.exists():
        _say(f"No such file: {path}")
        _say(r"Put the Paperform export in the imports\ folder and try again.")
        return 1

    db.init_db()
    conn = db.connect()
    try:
        try:
            rows = roster.read_export(path)
        except ValueError as exc:
            _say(str(exc))
            return 1
        _say(f"Read {len(rows)} sign-ups from {path.name}.")
        result = roster.preview(conn, rows, path.name)
        c = result["counts"]
        _say("")
        _say(f"  {c['new']} new, {c['changed']} changed, {c['unchanged']} unchanged, "
             f"{c['missing']} missing, {c['no_receipt']} without a receipt")

        if result["missing"]:
            _say("")
            _say("  Missing from this file — they become inactive, nothing is deleted:")
            for m in result["missing"]:
                _say(f"    @{m['handle']}  {m['name']}")

        if result["problems"]:
            _say("")
            _say(f"  {len(result['problems'])} problem(s). NOTHING HAS BEEN WRITTEN:")
            for p in result["problems"]:
                _say(f"    row {p['row']}: {p['message']}")
            _say("")
            _say("  Fix them in Paperform, export again, and run this command again.")
            return 1

        if c["new"] == 0 and c["changed"] == 0 and c["missing"] == 0:
            _say("")
            _say("  Nothing to change — this file matches what is already in the database.")
            conn.execute("UPDATE import_runs SET committed_at=? WHERE id=?",
                         (db.utcnow(), result["run_id"]))
            return 0

        _say("")
        if assume_yes:
            _say("  --yes given, committing.")
        else:
            try:
                answer = input("  Commit these changes? Type yes to go ahead: ").strip().lower()
            except EOFError:
                answer = ""
            if answer != "yes":
                _say("  Nothing was written. (Run it again and type yes, "
                     "or add --yes to the command.)")
                return 0

        done = roster.commit(conn, result["run_id"], actor="manage.py")
        _say(f"Committed: {done['committed']} people."
             + (f" {done['inactive']} marked inactive." if done["inactive"] else ""))
        return 0
    finally:
        conn.close()


def cmd_roster(argv):
    """Show who is on the list right now."""
    db.init_db()
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT handle, name, status, payment_status, source, tg_user_id, pass_code "
            "FROM attendees ORDER BY status, handle"
        ).fetchall()
        if not rows:
            _say("Nobody on the list yet. Run: python manage.py import <file>")
            return 0
        _say(f"{len(rows)} people:")
        _say("")
        for r in rows:
            linked = "linked" if r["tg_user_id"] else "not opened"
            _say(f"  @{r['handle']:<24} {r['name']:<26} {r['status']:<9} "
                 f"{r['payment_status']:<10} {linked:<11} {r['pass_code'] or ''}")
        return 0
    finally:
        conn.close()


def cmd_void_claim(argv):
    """Undo one hand-over, e.g. after a booth rehearsal. Reason required; the
    row stays and the void is in the audit log (§9 rule 26)."""
    from services import claims
    if len(argv) < 3 or argv[1] not in claims.ITEMS:
        _say("Usage — the username, the item, then the reason in quotes:")
        _say(f'  python manage.py void-claim maxi_muslim {claims.ITEMS[0]} "booth rehearsal"')
        _say("  Items: " + ", ".join(claims.ITEMS))
        return 1
    handle = argv[0].strip().lstrip("@").lower()
    item, reason = argv[1], " ".join(argv[2:])
    db.init_db()
    conn = db.connect()
    try:
        row = conn.execute("SELECT id, name FROM attendees WHERE handle=?", (handle,)).fetchone()
        if row is None:
            _say(f"Nobody with the username @{handle}. Check it with: python manage.py roster")
            return 1
        try:
            done = claims.void_claim(conn, attendee_id=row["id"], item=item,
                                     reason=reason, by="manage.py")
        except claims.ClaimError as exc:
            _say(exc.message)
            return 1
        _say(f"Voided {item} for @{handle} ({row['name']}). They can collect it again.")
        _say(f"  claim {done['id']}, reason: {reason}")
        return 0
    finally:
        conn.close()


def cmd_backup(argv):
    db.init_db()
    conn = db.connect()
    try:
        keep = int(db.get_setting(conn, "backup_keep", 36))
    finally:
        conn.close()
    target = db.backup_now(keep=keep)
    _say(f"Backed up to {target}.")
    return 0


def cmd_fetch_receipts(argv):
    """Save our own copy of every Paperform payment screenshot.

    Paperform signs each link to expire 7 days after that person signed up,
    which for the current batch is before the event. Run this while they still
    work and the copies keep working on the day. Safe to run again: anyone
    already copied is skipped unless you pass --redo.
    """
    from services import receipts
    db.init_db()
    conn = db.connect()
    try:
        before = receipts.status(conn)
        if before["not_saved"] == 0:
            _say(f"All {before['saved']} receipt(s) are already saved. Nothing to do.")
            return 0
        _say(f"{before['not_saved']} receipt(s) to fetch. This takes a few seconds each.")
        out = receipts.archive(conn, "manage.py", redo="--redo" in argv)
        c = out["counts"]
        _say(f"Saved {c['saved']}, skipped {c['skipped']} (already had them), failed {c['failed']}.")
        for f in out["failed"]:
            _say(f"  FAILED @{f['handle']} ({f['name']}): {f['why']}")
        after = receipts.status(conn)
        if after["not_saved"]:
            _say(f"Still without a copy: {after['not_saved']}. "
                 + (f"The next link expires {after['next_expiry']}."
                    if after["next_expiry"] else
                    "Their links have already expired — check Paperform's dashboard."))
        else:
            _say("Every receipt now has a copy on this laptop.")
    finally:
        conn.close()
    return 0


def cmd_phone_images(argv):
    """Which of the phone's pictures are on this laptop, and which are not."""
    from services import game
    present = game.images_present()
    story = [n for n in game.STORY_IMAGES]
    filler = [n for n in game.FILLER_IMAGES]
    folder = config.PHONE_DIR / "assets"
    _say(f"Looking in {folder}")
    _say("")
    _say("The five that carry the story:")
    missing_story = []
    for n in story:
        _say(f"  [{'x' if present[n] else ' '}] {n}")
        if not present[n]:
            missing_story.append(n)
    have_filler = sum(1 for n in filler if present[n])
    _say("")
    _say(f"Ordinary camera-roll photos: {have_filler} of {len(filler)} "
         "(filler-01.jpg .. filler-17.jpg, all optional)")
    _say("")
    if missing_story:
        _say(f"STILL NEEDED: {len(missing_story)} of the 5 story pictures.")
        for n in missing_story:
            _say(f"  {n}")
        _say("Until they are here the game has no evidence to find. Anything")
        _say("missing shows as a plain grey tile, so you can still test.")
    else:
        _say("All five story pictures are here. The game has its evidence.")
    _say("")
    _say(f"Drop files into {folder} with exactly those names. Nothing needs")
    _say("rebuilding — add the file, reload the phone, it is there.")
    return 0


def cmd_generate_slots(argv):
    """Escape games and jam slots, from Settings. Safe to run again."""
    from services import bookings, notify
    db.init_db()
    conn = db.connect()
    try:
        done = bookings.generate_slots(conn)
        s = db.get_settings(conn)
    finally:
        conn.close()
    for room, label in (("escape", "Escape games"), ("jam", "Jam slots")):
        d = done[room]
        _say(f"{label}: {d['total']} in total ({d['new']} added, {d['removed']} removed).")
        if d["stuck"]:
            _say(f"  Still booked, so kept: {', '.join(d['stuck'])}. "
                 "Move those people, then run this again.")
        for o in d.get("over", []):
            _say(f"  OVER CAPACITY: {o['at']} now seats {o['capacity']} but "
                 f"{o['booked']} are booked. Move {o['booked'] - o['capacity']} of them.")
    # Read from Settings, so this line stays true when the times change.
    _say(f"Settings say escape games {notify.hhmm_text(s['first_game'])}-{notify.hhmm_text(s['last_game'])} "
         f"and jam slots {notify.hhmm_text(s['jam_first'])}-{notify.hhmm_text(s['jam_last'])}.")
    return 0


def cmd_cancel_group(argv):
    """Take someone's whole escape group off its game, without messaging anyone."""
    from datetime import datetime, timezone
    from services import bookings, claims
    if len(argv) < 2:
        _say("Usage — the booker's username, then a reason in quotes:")
        _say('  python manage.py cancel-group maxi_muslim "test booking"')
        return 1
    db.init_db()
    conn = db.connect()
    try:
        try:
            gone = bookings.cancel_group_as_admin(
                conn, argv[0], f"manage.py ({' '.join(argv[1:])})", datetime.now(timezone.utc))
        except claims.ClaimError as exc:
            _say(exc.message)
            return 1
    finally:
        conn.close()
    if not gone:
        _say(f"@{argv[0].lstrip('@')} has no group booked. Nothing changed.")
        return 0
    _say(f"Cancelled {len(gone)} seat(s): {', '.join(gone)}. Nobody was messaged.")
    return 0


def cmd_set_public_url(argv):
    if not argv or not argv[0].startswith("https://"):
        _say("Give the tunnel address, starting with https://, for example:")
        _say("  python manage.py set-public-url https://moonlight-dwelling-footpad.ngrok-free.dev")
        return 1
    url = argv[0].strip().rstrip("/")
    path = _write_env("PUBLIC_URL", url)
    _say(f"PUBLIC_URL={url} written to {path}.")
    _say("Now restart app.py and bot.py (Ctrl+C, then start them again).")
    return 0


def cmd_notify(argv):
    """Who the bot may message: owner (test accounts only), on, or off."""
    from services import notify
    db.init_db()
    conn = db.connect()
    try:
        if not argv:
            mode = db.get_setting(conn, "notify_mode", "owner")
            _say(f"Messages are: {mode}")
            _say("  python manage.py notify owner   only always-allowed test accounts (safe for testing)")
            _say("  python manage.py notify on      everyone on the list")
            _say("  python manage.py notify off     nobody")
            return 0
        mode = argv[0].lower()
        if mode not in notify.MODES:
            _say("Use one of: owner, on, off.")
            return 1
        before = db.get_setting(conn, "notify_mode", "owner")
        db.set_setting(conn, "notify_mode", mode, by="manage.py")
        db.audit(conn, "admin", "Bot messages switched", actor_name="manage.py",
                 entity="settings", entity_id="notify_mode",
                 details={"before": before, "after": mode})
        _say(f"Messages switched from {before} to {mode}. bot.py picks this up by itself.")
        if mode == "on":
            _say("Real attendees will now get reminders and group messages.")
        return 0
    finally:
        conn.close()


def cmd_notify_test(argv):
    """Send one of every message to a test account, straight away."""
    from datetime import timedelta
    from services import claims, notify
    if not argv:
        _say("Whose Telegram? For example:  python manage.py notify-test maxi_muslim")
        return 1
    handle = argv[0].strip().lstrip("@").lower()
    db.init_db()
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM attendees WHERE handle=?", (handle,)).fetchone()
        if row is None:
            _say(f"Nobody with the username @{handle}.")
            return 1
        if not row["tg_user_id"]:
            _say(f"@{handle} has never opened The Yard or the bot, so there is no chat to send to.")
            _say("Open the bot in Telegram and tap Start first.")
            return 1
        now = notify.utc_now()
        at = db.utcnow()
        lock = (now + timedelta(minutes=25)).isoformat()
        samples = [
            ("escape_booked", notify.text_booked(at, "ESC-TEST", ["@heidily"]), notify.GO_TICKET),
            ("jam_booked", notify.text_jam_booked(at, at, "JAM-TEST",
                                                  [("maxi_muslim", "bass"), ("heidily", "drums")]),
             notify.GO_BOOKINGS),
            ("friend_added", notify.text_friend_added("@maxi_muslim", at, lock), notify.GO_TICKET),
            ("friend_removed", notify.text_friend_removed("@maxi_muslim", at), notify.GO_HOME),
            ("member_left", notify.text_member_left("@heidily", at), notify.GO_TICKET),
            # The jam room became a group booking on 18 Sep and brought four
            # messages with it. They belong here so the organiser can read
            # every message the bot can send, in one pass.
            ("jam_friend_added", notify.text_jam_friend_added("@maxi_muslim", at, at, "drums"),
             notify.GO_BOOKINGS),
            ("jam_removed", notify.text_jam_removed("@maxi_muslim"), notify.GO_BOOKINGS),
            ("jam_friend_left", notify.text_jam_friend_left("@heidily", at), notify.GO_BOOKINGS),
            ("jam_cancelled", notify.text_jam_cancelled_by_owner("@maxi_muslim", at),
             notify.GO_BOOKINGS),
            ("escape_reminder", notify.text_reminder(at, 10), notify.GO_TICKET),
            # The only way to the escape-room phone (22 Sep). Its button says
            # "Open the phone"; with no game running it opens to "Locked".
            ("phone_open", notify.text_phone(lock), notify.GO_PHONE),
            ("jam_reminder", notify.text_jam_reminder(at, 10), notify.GO_BOOKINGS),
            ("payment_verified", notify.text_payment_verified(), notify.GO_FOOD),
            ("payment_rejected", notify.text_payment_rejected("the amount shown is $5, not $12"),
             notify.GO_HOME),
            ("doors_open", notify.text_doors(notify.hhmm_text(db.get_setting(conn, "doors_open")),
                                             notify.hhmm_text(db.get_setting(conn, "doors_close")),
                                             db.get_setting(conn, "venue")),
             notify.GO_HOME),
            ("last_call", notify.text_last_call(claims.ITEMS[:1], "10:00 PM"), notify.GO_FOOD),
        ]
        for kind, text, go in samples:
            notify.queue(conn, row["id"], "test_" + kind, "[TEST] " + text, go=go, now=now)
        counts = notify.deliver(conn, notify.bot_api_send, now=now, limit=50)
        _say(f"Sent {counts.get('sent', 0)} of {len(samples)} sample messages to @{handle}.")
        if counts.get("suppressed"):
            _say("Some were held back: messages are in 'owner' mode and this is not a test "
                 "account. Only use real people's usernames once 'notify on' is set.")
        if counts.get("failed") or counts.get("retry"):
            _say("Some failed. Has this account pressed Start in the bot? "
                 "Run: python manage.py outbox")
        return 0
    finally:
        conn.close()


def cmd_outbox(argv):
    """The last 20 bot messages and what happened to each."""
    db.init_db()
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT n.created_at, n.kind, n.status, n.last_error, a.handle FROM notifications n "
            "JOIN attendees a ON a.id=n.attendee_id ORDER BY n.id DESC LIMIT 20").fetchall()
        _say(f"Messages are: {db.get_setting(conn, 'notify_mode', 'owner')}")
        if not rows:
            _say("No messages yet.")
            return 0
        for r in rows:
            _say(f"  {r['created_at'][:19]}  @{r['handle']:<20} {r['kind']:<22} {r['status']:<10} "
                 f"{r['last_error'] or ''}")
        _say("")
        _say("sent = delivered · queued = waiting for bot.py · suppressed = held back by "
             "the notify setting · skipped = they never opened the bot · expired = too late to "
             "be useful · withdrawn = the booking was cancelled before it went · "
             "failed = Telegram refused (often: they never pressed Start)")
        return 0
    finally:
        conn.close()


COMMANDS = {
    "init-db": cmd_init_db,
    "import": cmd_import,
    "roster": cmd_roster,
    "make-secret": cmd_make_secret,
    "set-admin-password": cmd_set_admin_password,
    "set-staff-pin": cmd_set_staff_pin,
    "set-gm-pin": cmd_set_gm_pin,
    "backup": cmd_backup,
    "fetch-receipts": cmd_fetch_receipts,
    "phone-images": cmd_phone_images,
    "void-claim": cmd_void_claim,
    "generate-slots": cmd_generate_slots,
    "cancel-group": cmd_cancel_group,
    "set-public-url": cmd_set_public_url,
    "notify": cmd_notify,
    "notify-test": cmd_notify_test,
    "outbox": cmd_outbox,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        _say("Commands:")
        for name in COMMANDS:
            _say(f"  python manage.py {name}")
        return 0
    cmd = COMMANDS.get(argv[0])
    if cmd is None:
        _say(f"No command called {argv[0]!r}. Run 'python manage.py help'.")
        return 1
    return cmd(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
