"""Escape-room games and the jamming studio (§9 r15-20, r22).

Escape room: seats are per person, never per group, so a half-full game stays
open to anyone. A booking is one INSERT per person inside BEGIN IMMEDIATE;
seats are counted in the same transaction, and the `escape_one_per_person`
unique index refuses a second active booking for anyone.

Groups: the person who books is the owner, and must be in the game themselves.
They add friends by username, all or nothing. Only the owner adds or removes
people they added; anyone can leave their own seat. Every edit is an add or a
remove — nobody's name is ever changed in place — and edits stop at the
booking cutoff. `booked_by_id` on each row is who added that person.

Jamming studio: free. One booking holds the whole room for its slot (the
`jam_one_per_slot` unique index decides a race). Booking confirms at once.

A person's escape game and jam slots may not overlap, counting a
`WALK_MINUTES` buffer on each side of the game (§9 r18).
"""

import sqlite3
from datetime import datetime, timedelta, timezone

import auth
import config
import db
from auth import normalise_handle
from services import claims, notify
from services.claims import ClaimError

WALK_MINUTES = 5
FRIEND_WINDOW = 10 * 60
FRIEND_FAILS = auth.RateLimiter()
RETIRED = "retired"          # block_reason of a slot the schedule no longer has

ClaimError.STATUS.update({
    "SLOT_FULL": 409, "SLOT_CLOSED": 409, "SLOT_STARTED": 409, "SLOT_BLOCKED": 409,
    "INSTRUMENT_TAKEN": 409,
    "ALREADY_BOOKED": 409, "FRIEND_NOT_ELIGIBLE": 409, "FRIEND_ALREADY_BOOKED": 409,
    "LIMIT_REACHED": 409, "TIME_CONFLICT": 409, "NO_BOOKING": 404,
})


def _iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _dt(iso):
    return datetime.fromisoformat(iso)


def _settings(conn):
    s = db.get_settings(conn)
    return {
        "cutoff": int(s["booking_cutoff_minutes"]),
        "cancel": int(s["cancel_cutoff_minutes"]),
        "max_party": int(s["max_party"]),
        "fail_limit": int(s["friend_fail_limit"]),
        "jam_limit": int(s["jam_per_person"]),
        # How many the jam room holds — also the largest group, since the
        # booker's party can fill it (18 Sep).
        "jam_capacity": int(s.get("jam_capacity") or 15),
    }


def _run(conn, fn, integrity=None):
    """fn() inside BEGIN IMMEDIATE. An IntegrityError becomes `integrity`."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        out = fn()
        conn.execute("COMMIT")
        return out
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        if integrity is None:
            raise
        raise integrity
    except BaseException:
        conn.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# Generating the schedule (manage.py generate-slots)
# ---------------------------------------------------------------------------

def _schedule(s):
    """{room: [(start, end)]} from the settings, in event-local time."""
    game = timedelta(minutes=int(s["game_minutes"]))
    jam = timedelta(minutes=int(s["jam_slot_minutes"]))
    plans = {
        "escape": (notify.event_local(s["first_game"]), notify.event_local(s["last_game"]),
                   game, game + timedelta(minutes=int(s["changeover_minutes"])), int(s["capacity"])),
        # The jam room holds a group now, not one booking (18 Sep).
        "jam": (notify.event_local(s["jam_first"]), notify.event_local(s["jam_last"]),
                jam, jam, int(s["jam_capacity"])),
    }
    out = {}
    for room, (t, last, length, step, cap) in plans.items():
        out[room] = []
        while t <= last:
            out[room].append((_iso(t), _iso(t + length), cap))
            t += step
    return out


def generate_slots(conn):
    """Make the slots table match the settings. New times are added; times the
    schedule no longer has are removed, or retired if someone ever booked
    them. A time with live bookings is left alone and reported."""
    report = {}
    for room, wanted in _schedule(db.get_settings(conn)).items():
        table = "escape_bookings" if room == "escape" else "jam_bookings"
        live = "('booked','checked_in')" if room == "escape" else "('confirmed')"
        keep = {start for start, _, _ in wanted}
        new = sum(conn.execute(
            "INSERT OR IGNORE INTO slots (room, starts_at, ends_at, capacity, price_cents) "
            "VALUES (?,?,?,?,0)", (room, start, end, cap)).rowcount for start, end, cap in wanted)
        over = []
        for start, end, cap in wanted:
            # Game length and seats follow Settings; a retired time that is
            # back in the schedule comes back.
            conn.execute("UPDATE slots SET ends_at=?, capacity=? WHERE room=? AND starts_at=?",
                         (end, cap, room, start))
            conn.execute("UPDATE slots SET is_blocked=0, block_reason=NULL "
                         "WHERE room=? AND starts_at=? AND block_reason=?", (room, start, RETIRED))
            # Lowering the seat count does not throw anyone out, so a game can
            # end up holding more people than it now allows. Nothing refuses a
            # booking that already exists, so without this the board quietly
            # reads "4 of 2" and the only person who would notice is whoever
            # counts heads at the door. Report it the way a stranded time is
            # reported, and let the caller decide.
            sl = conn.execute("SELECT id FROM slots WHERE room=? AND starts_at=?",
                              (room, start)).fetchone()
            if sl is not None:
                held = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE slot_id=? "  # noqa: S608
                                    f"AND status IN {live}", (sl["id"],)).fetchone()[0]
                if held > cap:
                    over.append({"at": claims.clock(start), "booked": held, "capacity": cap})
        removed, stuck = 0, []
        for sl in conn.execute("SELECT * FROM slots WHERE room=? AND COALESCE(block_reason,'') != ?",
                               (room, RETIRED)).fetchall():
            if sl["starts_at"] in keep:
                continue
            active = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE slot_id=? "  # noqa: S608
                                  f"AND status IN {live}", (sl["id"],)).fetchone()[0]
            if active:
                stuck.append(claims.clock(sl["starts_at"]))
                continue
            ever = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE slot_id=?",  # noqa: S608
                                (sl["id"],)).fetchone()[0]
            if ever:
                conn.execute("UPDATE slots SET is_blocked=1, block_reason=? WHERE id=?", (RETIRED, sl["id"]))
            else:
                conn.execute("DELETE FROM slots WHERE id=?", (sl["id"],))
            removed += 1
        total = conn.execute("SELECT COUNT(*) FROM slots WHERE room=? AND COALESCE(block_reason,'') != ?",
                             (room, RETIRED)).fetchone()[0]
        report[room] = {"new": new, "removed": removed, "total": total, "stuck": stuck,
                        "over": over}
        if new or removed:
            db.audit(conn, "system", f"{room.capitalize()} slots regenerated", actor_name="manage.py",
                     entity="slots", details=report[room])
    return report


def _slots(conn, room):
    return conn.execute("SELECT * FROM slots WHERE room=? AND COALESCE(block_reason,'') != ? "
                        "ORDER BY starts_at", (room, RETIRED)).fetchall()


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _taken(conn, slot_id):
    return conn.execute(
        "SELECT COUNT(*) FROM escape_bookings WHERE slot_id=? AND status IN ('booked','checked_in')",
        (slot_id,)).fetchone()[0]


def slot_status(slot, taken, now, cutoff):
    starts = _dt(slot["starts_at"])
    if slot["is_blocked"]:
        return "blocked"
    if now >= starts:
        return "started"
    if now >= starts - timedelta(minutes=cutoff):
        return "closed"
    if taken >= slot["capacity"]:
        return "full"
    return "open"


def active_booking(conn, attendee_id):
    return conn.execute(
        "SELECT b.*, s.starts_at, s.ends_at, s.capacity FROM escape_bookings b "
        "JOIN slots s ON s.id = b.slot_id "
        "WHERE b.attendee_id=? AND b.status IN ('booked','checked_in')", (attendee_id,)).fetchone()


def jam_bookings_of(conn, attendee_id):
    return conn.execute(
        "SELECT j.*, s.starts_at, s.ends_at FROM jam_bookings j JOIN slots s ON s.id = j.slot_id "
        "WHERE j.attendee_id=? AND j.status='confirmed' ORDER BY s.starts_at", (attendee_id,)).fetchall()


def board(conn, attendee_id, now):
    cfg = _settings(conn)
    mine = active_booking(conn, attendee_id)
    slots = []
    for sl in _slots(conn, "escape"):
        taken = _taken(conn, sl["id"])
        slots.append({"id": sl["id"], "starts_at": claims.local_iso(sl["starts_at"]),
                      "ends_at": claims.local_iso(sl["ends_at"]),
                      "seats_left": max(0, sl["capacity"] - taken),
                      "status": slot_status(sl, taken, now, cfg["cutoff"])})
    return {
        "capacity": int(db.get_setting(conn, "capacity")),
        "booking_cutoff_minutes": cfg["cutoff"],
        "cancel_cutoff_minutes": cfg["cancel"],
        "max_party": cfg["max_party"],
        "my_booking": {"ref": mine["ref_code"], "slot_id": mine["slot_id"],
                       } if mine else None,
        "slots": slots,
    }


def _party(conn, owner_id, slot_id):
    return conn.execute(
        "SELECT b.*, a.name, a.handle, a.tg_user_id, a.can_message FROM escape_bookings b "
        "JOIN attendees a ON a.id = b.attendee_id "
        "WHERE b.booked_by_id=? AND b.slot_id=? AND b.status IN ('booked','checked_in') "
        "ORDER BY (b.attendee_id = b.booked_by_id) DESC, b.id", (owner_id, slot_id)).fetchall()


def my_view(conn, attendee_id, now):
    """The escape_booking block of GET /api/me."""
    b = active_booking(conn, attendee_id)
    if b is None:
        return None
    cfg = _settings(conn)
    starts = _dt(b["starts_at"])
    edit_until = starts - timedelta(minutes=cfg["cutoff"])
    owner_id = b["booked_by_id"] or attendee_id
    owner = conn.execute("SELECT id, name, handle FROM attendees WHERE id=?", (owner_id,)).fetchone()
    i_own = owner_id == attendee_id
    leave_until = starts - timedelta(minutes=cfg["cancel"] if i_own else cfg["cutoff"])
    party = _party(conn, owner_id, b["slot_id"])
    open_edit = now < edit_until
    group = [{
        "name": p["name"], "handle": p["handle"],
        "me": p["attendee_id"] == attendee_id,
        "owner": p["attendee_id"] == owner_id,
        "removable": i_own and open_edit and p["attendee_id"] != attendee_id,
        "reachable": notify.reachable(p),
    } for p in party]
    if not any(g["me"] for g in group):
        # Your own row is always shown, even if your booker has since left.
        me = conn.execute("SELECT name, handle, tg_user_id, can_message FROM attendees WHERE id=?",
                          (attendee_id,)).fetchone()
        group.append({"name": me["name"], "handle": me["handle"], "me": True,
                      "owner": False, "removable": False, "reachable": notify.reachable(me)})
    return {
        "ref": b["ref_code"], "slot_id": b["slot_id"],
        "starts_at": claims.local_iso(b["starts_at"]), "ends_at": claims.local_iso(b["ends_at"]),
        "status": b["status"],
        "booked_by": {"name": owner["name"], "handle": owner["handle"], "me": i_own},
        "i_am_owner": i_own,
        "can_add": i_own and open_edit and len(party) < cfg["max_party"]
                   and _taken(conn, b["slot_id"]) < b["capacity"],
        "can_leave": now < leave_until,
        "locked": not open_edit,
        "edit_until": claims.local_iso(_iso(edit_until)),
        "leave_until": claims.local_iso(_iso(leave_until)),
        "max_party": cfg["max_party"],
        "group": group,
    }


def jam_board(conn, attendee_id, now):
    """The jam room's board: which instruments are free in each slot.

    Booked by instrument since 19 Sep, so a slot is never simply "taken". It
    has a free bass and a busy drum kit, and anyone may join a room somebody
    else started. `free` is what the board actually draws.
    """
    cfg = _settings(conn)
    seats = {}
    for r in conn.execute("SELECT slot_id, attendee_id, instrument FROM jam_bookings "
                          "WHERE status='confirmed'"):
        seats.setdefault(r["slot_id"], []).append(r)
    cap = int(cfg["jam_capacity"])
    slots = []
    for sl in _slots(conn, "jam"):
        here = seats.get(sl["id"], [])
        used = {r["instrument"] for r in here if r["instrument"]}
        status = slot_status(sl, len(here), now, cfg["cutoff"])
        if any(r["attendee_id"] == attendee_id for r in here):
            status = "mine"
        slots.append({
            "id": sl["id"], "starts_at": claims.local_iso(sl["starts_at"]),
            "ends_at": claims.local_iso(sl["ends_at"]), "status": status,
            "booked": len(here), "capacity": cap,
            "seats_left": max(0, cap - len(here)),
            "free": [k for k in config.INSTRUMENT_KEYS if k not in used],
            "mine_instrument": next((r["instrument"] for r in here
                                     if r["attendee_id"] == attendee_id), None),
        })
    return {"per_person_limit": cfg["jam_limit"], "capacity": cap,
            "booking_cutoff_minutes": cfg["cutoff"],
            "instruments": [{"key": k, "label": v} for k, v in config.INSTRUMENTS],
            "mine": len(jam_bookings_of(conn, attendee_id)), "slots": slots}


def my_jam(conn, attendee_id, now):
    """The jam_bookings block of GET /api/me.

    Carries the whole room, not only the people this person brought: anyone
    may join a slot, so "who else is in there and on what" is the thing
    somebody actually wants to see before they turn up.
    """
    cfg = _settings(conn)
    out = []
    for j in jam_bookings_of(conn, attendee_id):
        owner_id = j["booked_by_id"] or j["attendee_id"]
        i_own = owner_id == attendee_id
        room = conn.execute(
            "SELECT j.*, a.handle, a.name FROM jam_bookings j JOIN attendees a ON a.id=j.attendee_id "
            "WHERE j.slot_id=? AND j.status='confirmed' ORDER BY j.created_at, j.id",
            (j["slot_id"],)).fetchall()
        owner = next((p for p in room if p["attendee_id"] == owner_id), None)
        open_until = _dt(j["starts_at"]) - timedelta(minutes=cfg["cutoff"])
        used = {p["instrument"] for p in room if p["instrument"]}
        out.append({
            "ref": j["ref_code"], "slot_id": j["slot_id"],
            "starts_at": claims.local_iso(j["starts_at"]),
            "ends_at": claims.local_iso(j["ends_at"]),
            "status": j["status"],
            "instrument": j["instrument"],
            "instrument_label": config.INSTRUMENT_LABELS.get(j["instrument"], ""),
            "i_am_owner": i_own,
            "booked_by": {"name": owner["name"], "handle": owner["handle"],
                          "me": i_own} if owner else None,
            # Everyone in the room, mine or not, each with their instrument.
            "line_up": [{"name": p["name"], "handle": p["handle"],
                         "me": p["attendee_id"] == attendee_id,
                         "mine_to_remove": i_own and (p["booked_by_id"] == attendee_id)
                                           and p["attendee_id"] != attendee_id,
                         "instrument": p["instrument"],
                         "instrument_label": config.INSTRUMENT_LABELS.get(p["instrument"], "")}
                        for p in room],
            "free": [{"key": k, "label": v} for k, v in config.INSTRUMENTS if k not in used],
            "capacity": int(cfg["jam_capacity"]),
            "can_add": i_own and now < open_until and len(used) < int(cfg["jam_capacity"]),
            "can_leave": (not i_own) and now < open_until,
            "can_cancel": i_own and now < _dt(j["starts_at"]),
            "edit_until": claims.local_iso(_iso(open_until)),
        })
    return out


def admin_board(conn, now):
    cfg = _settings(conn)
    games, seats = [], 0
    for sl in _slots(conn, "escape"):
        rows = conn.execute(
            "SELECT status FROM escape_bookings WHERE slot_id=? AND status IN ('booked','checked_in')",
            (sl["id"],)).fetchall()
        booked = len(rows)
        seats += booked
        starts, ends = _dt(sl["starts_at"]), _dt(sl["ends_at"])
        games.append({
            "id": sl["id"], "starts_at": claims.local_iso(sl["starts_at"]),
            "ends_at": claims.local_iso(sl["ends_at"]), "capacity": sl["capacity"],
            "booked": booked, "checked_in": sum(r["status"] == "checked_in" for r in rows),
            "blocked": bool(sl["is_blocked"]), "running": starts <= now < ends, "done": now >= ends,
            "closed": starts - timedelta(minutes=cfg["cutoff"]) <= now < starts,
        })
    # The jam room takes a group now, so a slot has a booker and a party
    # rather than one name (18 Sep). Staff need the booker's name to find the
    # group at the door, and the count to know how many to expect.
    jam = []
    jam_seats = 0
    for sl in _slots(conn, "jam"):
        rows = conn.execute(
            "SELECT j.ref_code, j.attendee_id, j.booked_by_id, a.handle "
            "FROM jam_bookings j JOIN attendees a ON a.id=j.attendee_id "
            "WHERE j.slot_id=? AND j.status='confirmed' ORDER BY j.created_at, j.id",
            (sl["id"],)).fetchall()
        jam_seats += len(rows)
        owner = next((r for r in rows if (r["booked_by_id"] or r["attendee_id"]) == r["attendee_id"]),
                     rows[0] if rows else None)
        starts = _dt(sl["starts_at"])
        jam.append({"id": sl["id"], "starts_at": claims.local_iso(sl["starts_at"]),
                    "ends_at": claims.local_iso(sl["ends_at"]), "blocked": bool(sl["is_blocked"]),
                    "status": "past" if now >= starts else "booked" if rows else "open",
                    "capacity": sl["capacity"], "booked": len(rows),
                    "who": "@" + owner["handle"] if owner else "",
                    "party": ["@" + r["handle"] for r in rows],
                    "ref": owner["ref_code"] if owner else ""})
    return {"escape": games, "jam": jam, "seats_taken": seats,
            "seats_total": sum(g["capacity"] for g in games),
            "jam_seats_taken": jam_seats,
            "jam_seats_total": sum(j["capacity"] for j in jam)}


def lookup_view(conn, attendee_id):
    b = active_booking(conn, attendee_id)
    if b is None:
        return None
    # Staff at the door need the half before the game starts.
    return {"ref": b["ref_code"], "starts_at": claims.local_iso(b["starts_at"])}


def person_bookings(conn, attendee_id):
    """The person page's Bookings panel."""
    out = []
    b = active_booking(conn, attendee_id)
    if b is not None:
        owner_id = b["booked_by_id"] or attendee_id
        by = None
        if owner_id != attendee_id:
            o = conn.execute("SELECT handle, name FROM attendees WHERE id=?", (owner_id,)).fetchone()
            by = "@" + o["handle"] if o["handle"] else o["name"]
        out.append({"kind": "escape", "ref": b["ref_code"], "starts_at": claims.local_iso(b["starts_at"]),
                    "status": b["status"], "booked_by": by})
    for j in jam_bookings_of(conn, attendee_id):
        # Who booked it, same as the escape row: a jam slot is a group now,
        # and an admin looking at one person needs to know whose slot it is
        # before they cancel or move anything.
        owner_id = j["booked_by_id"] or attendee_id
        by = None
        if owner_id != attendee_id:
            o = conn.execute("SELECT handle, name FROM attendees WHERE id=?", (owner_id,)).fetchone()
            by = "@" + o["handle"] if o["handle"] else o["name"]
        out.append({"kind": "jam", "ref": j["ref_code"], "starts_at": claims.local_iso(j["starts_at"]),
                    "status": j["status"], "booked_by": by})
    return out


# ---------------------------------------------------------------------------
# Time clashes (§9 r18)
# ---------------------------------------------------------------------------

def _busy_escape(conn, attendee_id):
    """(start, end) of this person's game, walking buffer included, or None."""
    b = active_booking(conn, attendee_id)
    if b is None:
        return None
    walk = timedelta(minutes=WALK_MINUTES)
    return _dt(b["starts_at"]) - walk, _dt(b["ends_at"]) + walk


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _escape_clashes(conn, attendee_id, slot):
    walk = timedelta(minutes=WALK_MINUTES)
    start, end = _dt(slot["starts_at"]) - walk, _dt(slot["ends_at"]) + walk
    return any(_overlaps(start, end, _dt(j["starts_at"]), _dt(j["ends_at"]))
               for j in jam_bookings_of(conn, attendee_id))


# ---------------------------------------------------------------------------
# Writing — escape room
# ---------------------------------------------------------------------------

def _person(conn, attendee_id):
    return conn.execute("SELECT * FROM attendees WHERE id=?", (attendee_id,)).fetchone()


def _check_open(slot, taken, now, cfg, adding, what="game"):
    status = slot_status(slot, taken, now, cfg["cutoff"])
    if status == "blocked":
        raise ClaimError("SLOT_BLOCKED", f"That {what} is not running.")
    if status == "started":
        raise ClaimError("SLOT_STARTED", f"That {what} has already started.")
    if status == "closed":
        raise ClaimError("SLOT_CLOSED", f"Booking has closed for that {what}.")
    if taken + adding > slot["capacity"]:
        left = max(0, slot["capacity"] - taken)
        raise ClaimError("SLOT_FULL",
                         f"Only {left} seat{'s' if left != 1 else ''} left in that {what}."
                         if left else f"That {what} is full.", seats_left=left)


def _resolve_friends(conn, owner, handles, cfg, room_for, slot):
    """Normalise, de-duplicate and check friends. Raises before anything is written."""
    wanted, seen = [], set()
    for raw in handles or []:
        h = normalise_handle(raw)
        if h and h not in seen and h != owner["handle"]:
            seen.add(h)
            wanted.append(h)
    if len(wanted) > room_for:
        raise ClaimError("LIMIT_REACHED",
                         f"A group can be at most {cfg['max_party']} people, including you."
                         + (f" You can add {room_for} more." if room_for > 0 else ""))
    if not wanted:
        return []
    key = f"friends:{owner['id']}"
    if not FRIEND_FAILS.allowed(key, cfg["fail_limit"], FRIEND_WINDOW):
        raise ClaimError("RATE_LIMITED", "Too many usernames that didn't work. Wait a few minutes.")
    rows = {r["handle"]: r for r in conn.execute(
        f"SELECT * FROM attendees WHERE handle IN ({','.join('?' * len(wanted))})", wanted)}
    bad = [h for h in wanted if h not in rows or rows[h]["status"] != "active"]
    if bad:
        FRIEND_FAILS.hit(key, FRIEND_WINDOW)
        raise ClaimError("FRIEND_NOT_ELIGIBLE",
                         "Not on The Yard's list: " + ", ".join("@" + h for h in bad)
                         + ". Nobody was booked.", handles=bad)
    busy = [h for h in wanted if active_booking(conn, rows[h]["id"]) is not None]
    if busy:
        raise ClaimError("FRIEND_ALREADY_BOOKED",
                         "Already in a game: " + ", ".join("@" + h for h in busy)
                         + ". They can leave theirs first. Nobody was booked.", handles=busy)
    clash = [h for h in wanted if _escape_clashes(conn, rows[h]["id"], slot)]
    if clash:
        raise ClaimError("TIME_CONFLICT",
                         "That game clashes with a jam slot booked by " + ", ".join("@" + h for h in clash)
                         + ". Nobody was booked.", handles=clash)
    return [rows[h] for h in wanted]


def _insert(conn, slot_id, attendee_id, owner_id, now):
    """One seat. Returns (ref, booking id)."""
    ref = db.new_code(conn, "escape_bookings", "ref_code", length=4, group="ESC")
    cur = conn.execute(
        "INSERT INTO escape_bookings (slot_id, attendee_id, booked_by_id, ref_code, status, created_at) "
        "VALUES (?,?,?,?,'booked',?)", (slot_id, attendee_id, owner_id, ref, _iso(now)))
    return ref, cur.lastrowid


def _seat_friends(conn, owner, friends, slot, cfg, now):
    """Insert each friend's seat, tell them, and log it."""
    lock = _dt(slot["starts_at"]) - timedelta(minutes=cfg["cutoff"])
    for f in friends:
        _, booking_id = _insert(conn, slot["id"], f["id"], owner["id"], now)
        notify.queue(conn, f["id"], "friend_added",
                     notify.text_friend_added(notify.who(owner), slot["starts_at"], _iso(lock),
                                              notify.place(conn, "escape")),
                     go=notify.GO_TICKET, dedupe_key=f"friend_added:{booking_id}",
                     expires_at=_dt(slot["starts_at"]), now=now)
        db.audit(conn, "attendee", "Added to an escape game", actor_name=notify.who(owner),
                 entity="attendee", entity_id=f["id"], details={"by": owner["id"], "slot_id": slot["id"]})


def book(conn, attendee_id, slot_id, friends, now):
    """Book yourself, plus any friends, all or nothing."""
    cfg = _settings(conn)
    me = _person(conn, attendee_id)
    try:
        slot_id = int(slot_id)
    except (TypeError, ValueError):
        raise ClaimError("VALIDATION_FAILED", "Pick a game.")

    def run():
        slot = conn.execute("SELECT * FROM slots WHERE id=? AND room='escape'", (slot_id,)).fetchone()
        if slot is None:
            raise ClaimError("VALIDATION_FAILED", "No such game.")
        if active_booking(conn, attendee_id):
            raise ClaimError("ALREADY_BOOKED", "You already have a game. Cancel it first to move.")
        if _escape_clashes(conn, attendee_id, slot):
            raise ClaimError("TIME_CONFLICT", "That game clashes with your jam slot.")
        people = _resolve_friends(conn, me, friends, cfg, cfg["max_party"] - 1, slot)
        _check_open(slot, _taken(conn, slot_id), now, cfg, 1 + len(people))
        ref, booking_id = _insert(conn, slot_id, attendee_id, attendee_id, now)
        _seat_friends(conn, me, people, slot, cfg, now)
        handles = [p["handle"] for p in people]
        notify.queue(conn, attendee_id, "escape_booked",
                     notify.text_booked(slot["starts_at"], ref, ["@" + h for h in handles],
                                        notify.place(conn, "escape")),
                     go=notify.GO_TICKET, dedupe_key=f"escape_booked:{booking_id}", now=now)
        db.audit(conn, "attendee", "Escape game booked", actor_name=notify.who(me),
                 entity="attendee", entity_id=attendee_id,
                 details={"ref": ref, "slot_id": slot_id, "starts_at": slot["starts_at"], "friends": handles})
        return {"ref": ref, "slot_id": slot_id, "starts_at": claims.local_iso(slot["starts_at"]),
                "friends": handles}

    return _run(conn, run, ClaimError(
        "FRIEND_ALREADY_BOOKED", "Someone in that group booked another game a moment ago. Nobody was booked."))


def add_friends(conn, owner_id, handles, now):
    cfg = _settings(conn)
    owner = _person(conn, owner_id)

    def run():
        mine = active_booking(conn, owner_id)
        if mine is None:
            raise ClaimError("NO_BOOKING", "Book a game for yourself first.")
        if (mine["booked_by_id"] or owner_id) != owner_id:
            raise ClaimError("FORBIDDEN", "Only the person who booked this group can add people. "
                                          "Ask them, or book your own game.")
        slot = conn.execute("SELECT * FROM slots WHERE id=?", (mine["slot_id"],)).fetchone()
        room = cfg["max_party"] - len(_party(conn, owner_id, slot["id"]))
        people = _resolve_friends(conn, owner, handles, cfg, room, slot)
        if not people:
            raise ClaimError("VALIDATION_FAILED", "Type at least one username.")
        _check_open(slot, _taken(conn, slot["id"]), now, cfg, len(people))
        _seat_friends(conn, owner, people, slot, cfg, now)
        return {"added": [p["handle"] for p in people]}

    return _run(conn, run, ClaimError(
        "FRIEND_ALREADY_BOOKED", "One of them booked another game a moment ago. Nobody was added."))


def _cancel_seat(conn, b, now):
    """Cancel one seat. True if they were never told they had it."""
    conn.execute("UPDATE escape_bookings SET status='cancelled', cancelled_at=? WHERE id=?",
                 (_iso(now), b["id"]))
    withdrawn = notify.withdraw(conn, f"friend_added:{b['id']}")
    return withdrawn


def remove_friend(conn, owner_id, handle, now):
    """The owner takes someone they added off their game."""
    cfg = _settings(conn)
    owner = _person(conn, owner_id)
    h = normalise_handle(handle)

    def run():
        b = conn.execute(
            "SELECT b.*, s.starts_at FROM escape_bookings b JOIN slots s ON s.id=b.slot_id "
            "JOIN attendees a ON a.id=b.attendee_id "
            "WHERE a.handle=? AND b.booked_by_id=? AND b.attendee_id != ? "
            "AND b.status IN ('booked','checked_in')", (h, owner_id, owner_id)).fetchone()
        if b is None:
            raise ClaimError("FORBIDDEN", "You can only remove people you added yourself.")
        if now >= _dt(b["starts_at"]) - timedelta(minutes=cfg["cutoff"]):
            raise ClaimError("SLOT_CLOSED", "The group is locked now. See the game master.")
        if b["status"] == "checked_in":
            raise ClaimError("SLOT_CLOSED", "They're already checked in. See the game master.")
        # Someone who never heard they were added doesn't need to hear they were removed.
        if not _cancel_seat(conn, b, now):
            notify.queue(conn, b["attendee_id"], "friend_removed",
                         notify.text_friend_removed(notify.who(owner), b["starts_at"]),
                         go=notify.GO_HOME, expires_at=_dt(b["starts_at"]), now=now)
        db.audit(conn, "attendee", "Removed from an escape game", actor_name=notify.who(owner),
                 entity="attendee", entity_id=b["attendee_id"], details={"ref": b["ref_code"], "by": owner_id})
        return {"removed": h}

    return _run(conn, run)


def cancel(conn, attendee_id, ref, now):
    """Cancel your own seat. If someone else added you, this is 'leave'."""
    cfg = _settings(conn)
    me = _person(conn, attendee_id)

    def run():
        b = conn.execute(
            "SELECT b.*, s.starts_at FROM escape_bookings b JOIN slots s ON s.id=b.slot_id "
            "WHERE b.ref_code=? AND b.attendee_id=? AND b.status IN ('booked','checked_in')",
            (str(ref or "").upper(), attendee_id)).fetchone()
        if b is None:
            raise ClaimError("NO_BOOKING", "That isn't one of your bookings.")
        owner_id = b["booked_by_id"] or attendee_id
        own = owner_id == attendee_id
        minutes = cfg["cancel"] if own else cfg["cutoff"]
        if now >= _dt(b["starts_at"]) - timedelta(minutes=minutes):
            raise ClaimError("SLOT_CLOSED",
                             f"Too late to {'cancel' if own else 'leave'} — "
                             f"that closes {minutes} minutes before the game. See the game master.")
        if b["status"] == "checked_in":
            raise ClaimError("SLOT_CLOSED", "You're already checked in. See the game master.")
        _cancel_seat(conn, b, now)
        if not own:
            notify.queue(conn, owner_id, "member_left",
                         notify.text_member_left(notify.who(me), b["starts_at"]),
                         go=notify.GO_TICKET, expires_at=_dt(b["starts_at"]), now=now)
        db.audit(conn, "attendee", "Escape booking cancelled" if own else "Left an escape game",
                 actor_name=notify.who(me), entity="attendee", entity_id=attendee_id,
                 details={"ref": b["ref_code"], "slot_id": b["slot_id"]})
        return {"cancelled": True, "left": not own}

    return _run(conn, run)


def cancel_group_as_admin(conn, handle, by, now):
    """Take a booker's whole group off their game, quietly (e.g. after a test).
    Nobody is messaged, and queued 'you were added' messages are withdrawn."""
    owner = conn.execute("SELECT * FROM attendees WHERE handle=?", (normalise_handle(handle),)).fetchone()
    if owner is None:
        raise ClaimError("NOT_FOUND", f"Nobody with the username @{normalise_handle(handle)}.")

    def run():
        rows = conn.execute(
            "SELECT b.*, a.handle FROM escape_bookings b JOIN attendees a ON a.id=b.attendee_id "
            "WHERE b.booked_by_id=? AND b.status IN ('booked','checked_in')", (owner["id"],)).fetchall()
        for b in rows:
            _cancel_seat(conn, b, now)
            notify.withdraw(conn, f"escape_booked:{b['id']}")
            db.audit(conn, "admin", "Escape booking cancelled by admin", actor_name=by,
                     entity="attendee", entity_id=b["attendee_id"],
                     details={"ref": b["ref_code"], "group_of": owner["handle"]})
        # The jam room is a group booking too now, and a test leaves seats
        # there just as readily. Clearing only the escape game would leave
        # half the test behind for somebody to find on the night.
        jams = conn.execute(
            "SELECT j.*, a.handle FROM jam_bookings j JOIN attendees a ON a.id=j.attendee_id "
            "WHERE COALESCE(j.booked_by_id, j.attendee_id)=? AND j.status='confirmed'",
            (owner["id"],)).fetchall()
        for j in jams:
            conn.execute("UPDATE jam_bookings SET status='cancelled', cancelled_at=? WHERE id=?",
                         (_iso(now), j["id"]))
            notify.withdraw(conn, f"jam_friend_added:{j['id']}")
            notify.withdraw(conn, f"jam_booked:{j['id']}")
            db.audit(conn, "admin", "Jam booking cancelled by admin", actor_name=by,
                     entity="attendee", entity_id=j["attendee_id"],
                     details={"ref": j["ref_code"], "group_of": owner["handle"]})
        return ["@" + b["handle"] for b in rows] + ["@" + j["handle"] + " (jam)" for j in jams]

    return _run(conn, run)


# ---------------------------------------------------------------------------
# Writing — jamming studio (free)
# ---------------------------------------------------------------------------

def _jam_party(conn, owner_id, slot_id):
    """Everyone the owner has in this jam slot, themselves included."""
    return conn.execute(
        "SELECT j.*, a.handle, a.name FROM jam_bookings j JOIN attendees a ON a.id=j.attendee_id "
        "WHERE j.slot_id=? AND j.status='confirmed' AND COALESCE(j.booked_by_id, j.attendee_id)=? "
        "ORDER BY j.created_at, j.id", (slot_id, owner_id)).fetchall()


def _instrument(raw):
    key = str(raw or "").strip().lower()
    if key not in config.INSTRUMENT_KEYS:
        raise ClaimError("VALIDATION_FAILED", "Pick an instrument.")
    return key


def _jam_blocked(conn, attendee_id, slot, cfg):
    """Why this person cannot take a seat in this jam slot, or None.

    Two reasons, and both must be checked for *every* friend, not just the
    booker: their own jam allowance, and a clash with their escape game. The
    second is the one people forget — a friend added to a jam slot may have a
    game of their own at that time, and only the server knows.
    """
    if len(jam_bookings_of(conn, attendee_id)) >= cfg["jam_limit"]:
        n = cfg["jam_limit"]
        return ("LIMIT_REACHED",
                f"can already hold {n} jam slot{'s' if n != 1 else ''}")
    game = _busy_escape(conn, attendee_id)
    if game and _overlaps(game[0], game[1], _dt(slot["starts_at"]), _dt(slot["ends_at"])):
        return ("TIME_CONFLICT", "has an escape game at that time")
    return None


def _resolve_jam_friends(conn, owner, players, cfg, room_for, slot):
    """Check the friends a booker is bringing, and the instrument each will play.

    `players` is a list of {handle, instrument}. All-or-nothing, like the
    escape room: nobody gets a seat until every name *and* every instrument is
    right. A half-booked group is worse than none, because the booker has no
    way of telling who made it in.
    """
    wanted, want_inst, seen = [], {}, set()
    for p in players or []:
        h = normalise_handle((p or {}).get("handle"))
        if not h or h in seen or h == owner["handle"]:
            continue
        seen.add(h)
        wanted.append(h)
        want_inst[h] = _instrument((p or {}).get("instrument"))
    # Nothing to check if they are booking alone. The order matters: in a
    # full room `room_for` goes negative, and testing the limit first made a
    # solo booking fail with "there are only five instruments" instead of
    # naming the instrument that was gone.
    if not wanted:
        return []
    if len(wanted) > room_for:
        raise ClaimError("LIMIT_REACHED",
                         f"There are only {len(config.INSTRUMENTS)} instruments in the room."
                         + (f" You can add {room_for} more." if room_for > 0 else ""))
    # Two friends cannot be handed the same instrument, and neither can a
    # friend and somebody already in the room. The index would catch it, but
    # a name is a better answer than a constraint violation.
    doubled = [i for i in set(want_inst.values())
               if list(want_inst.values()).count(i) > 1]
    if doubled:
        raise ClaimError("VALIDATION_FAILED",
                         "Two people can't play the "
                         + config.INSTRUMENT_LABELS[doubled[0]].lower()
                         + ". Nobody was booked.")
    key = f"jamfriends:{owner['id']}"
    if not FRIEND_FAILS.allowed(key, cfg["fail_limit"], FRIEND_WINDOW):
        raise ClaimError("RATE_LIMITED", "Too many usernames that didn't work. Wait a few minutes.")
    rows = {r["handle"]: r for r in conn.execute(
        f"SELECT * FROM attendees WHERE handle IN ({','.join('?' * len(wanted))})", wanted)}
    bad = [h for h in wanted if h not in rows or rows[h]["status"] != "active"]
    if bad:
        FRIEND_FAILS.hit(key, FRIEND_WINDOW)
        raise ClaimError("FRIEND_NOT_ELIGIBLE",
                         "Not on The Yard's list: " + ", ".join("@" + h for h in bad)
                         + ". Nobody was booked.", handles=bad)
    already = [h for h in wanted
               if any(r["attendee_id"] == rows[h]["id"] for r in _jam_seats(conn, slot["id"]))]
    if already:
        raise ClaimError("FRIEND_ALREADY_BOOKED",
                         "Already in this slot: " + ", ".join("@" + h for h in already)
                         + ". Nobody was booked.", handles=already)
    stuck = {}
    for h in wanted:
        why = _jam_blocked(conn, rows[h]["id"], slot, cfg)
        if why:
            stuck.setdefault(why[0], []).append((h, why[1]))
    if stuck:
        code, pairs = next(iter(stuck.items()))
        names = ", ".join(f"@{h} {reason}" for h, reason in pairs)
        raise ClaimError(code, f"{names}. Nobody was booked.",
                         handles=[h for h, _ in pairs])
    # Carry each person's instrument alongside their row, so the caller does
    # not have to pair the two lists back up and risk getting it wrong.
    out = []
    for h in wanted:
        row = dict(rows[h])
        row["_instrument"] = want_inst[h]
        out.append(row)
    return out


def _jam_seats(conn, slot_id):
    return conn.execute(
        "SELECT * FROM jam_bookings WHERE slot_id=? AND status='confirmed'", (slot_id,)).fetchall()


def book_jam(conn, attendee_id, slot_id, instrument, friends, now):
    """Take an instrument in a jam slot, and bring whoever you like.

    Booked by **instrument** since 19 Sep. Before that it was the whole room,
    briefly for one person and then for one group. The instrument is what is
    actually scarce — there is one bass — so that is what a booking claims,
    and five people who do not know each other each on their own instrument
    is a jam rather than the awkward silence the earlier rule was avoiding.

    So a slot is never "taken": it has a free keyboard and a busy drum kit,
    and anyone may walk into a room somebody else started.
    """
    cfg = _settings(conn)
    me = _person(conn, attendee_id)
    try:
        slot_id = int(slot_id)
    except (TypeError, ValueError):
        raise ClaimError("VALIDATION_FAILED", "Pick a slot.")
    mine_inst = _instrument(instrument)

    def run():
        slot = conn.execute("SELECT * FROM slots WHERE id=? AND room='jam'", (slot_id,)).fetchone()
        if slot is None:
            raise ClaimError("VALIDATION_FAILED", "No such slot.")
        seated = _jam_seats(conn, slot_id)
        taken = len(seated)
        room_for = int(cfg["jam_capacity"]) - taken - 1
        people = _resolve_jam_friends(conn, me, friends, cfg, room_for, slot)
        wanted = {mine_inst: me["handle"]}
        for p in people:
            wanted[p["_instrument"]] = p["handle"]
        if len(wanted) != 1 + len(people):
            raise ClaimError("VALIDATION_FAILED",
                             "Two of you picked the same instrument. Nobody was booked.")
        clash = [i for i in wanted if any(r["instrument"] == i for r in seated)]
        if clash:
            names = ", ".join(config.INSTRUMENT_LABELS[i].lower() for i in clash)
            raise ClaimError("INSTRUMENT_TAKEN",
                             f"Someone already has the {names} in that slot. "
                             "Pick another, or another time. Nobody was booked.",
                             instruments=clash)
        _check_open(slot, taken, now, cfg, 1 + len(people), what="slot")
        mine = _jam_blocked(conn, attendee_id, slot, cfg)
        if mine:
            raise ClaimError(mine[0],
                             "You can hold "
                             f"{cfg['jam_limit']} jam slot{'s' if cfg['jam_limit'] != 1 else ''} "
                             "at a time. Cancel yours to pick another."
                             if mine[0] == "LIMIT_REACHED" else
                             "That slot clashes with your escape-room game "
                             "(including 5 minutes to walk over).")
        ref = db.new_code(conn, "jam_bookings", "ref_code", length=4, group="JAM")
        cur = conn.execute(
            "INSERT INTO jam_bookings (slot_id, attendee_id, booked_by_id, instrument, ref_code, "
            "price_cents, status, created_at) VALUES (?,?,?,?,?,0,'confirmed',?)",
            (slot_id, attendee_id, attendee_id, mine_inst, ref, _iso(now)))
        _seat_jam_friends(conn, me, people, slot, cfg, now)
        handles = [p["handle"] for p in people]
        line_up = [(me["handle"], mine_inst)] + [(p["handle"], p["_instrument"]) for p in people]
        notify.queue(conn, attendee_id, "jam_booked",
                     notify.text_jam_booked(slot["starts_at"], slot["ends_at"], ref, line_up,
                                            notify.place(conn, "jam")),
                     go=notify.GO_BOOKINGS, dedupe_key=f"jam_booked:{cur.lastrowid}", now=now)
        db.audit(conn, "attendee", "Jam slot booked", actor_name=notify.who(me), entity="attendee",
                 entity_id=attendee_id,
                 details={"ref": ref, "slot_id": slot_id, "starts_at": slot["starts_at"],
                          "friends": handles})
        return {"ref": ref, "slot_id": slot_id, "starts_at": claims.local_iso(slot["starts_at"]),
                "ends_at": claims.local_iso(slot["ends_at"]), "friends": handles}

    return _run(conn, run, ClaimError("SLOT_FULL", "Someone booked that slot a moment ago."))


def _seat_jam_friends(conn, owner, friends, slot, cfg, now):
    """An instrument each, a message each, and a line in the log each."""
    for f in friends:
        ref = db.new_code(conn, "jam_bookings", "ref_code", length=4, group="JAM")
        cur = conn.execute(
            "INSERT INTO jam_bookings (slot_id, attendee_id, booked_by_id, instrument, ref_code, "
            "price_cents, status, created_at) VALUES (?,?,?,?,?,0,'confirmed',?)",
            (slot["id"], f["id"], owner["id"], f["_instrument"], ref, _iso(now)))
        notify.queue(conn, f["id"], "jam_friend_added",
                     notify.text_jam_friend_added(notify.who(owner), slot["starts_at"],
                                                  slot["ends_at"], f["_instrument"],
                                                  notify.place(conn, "jam")),
                     go=notify.GO_BOOKINGS, dedupe_key=f"jam_friend_added:{cur.lastrowid}",
                     expires_at=_dt(slot["starts_at"]), now=now)
        db.audit(conn, "attendee", "Added to a jam slot", actor_name=notify.who(owner),
                 entity="attendee", entity_id=f["id"],
                 details={"by": owner["id"], "slot_id": slot["id"]})


def add_jam_friends(conn, owner_id, ref, players, now):
    """The booker adds more players, each on a named instrument."""
    cfg = _settings(conn)
    owner = _person(conn, owner_id)

    def run():
        mine = conn.execute(
            "SELECT j.*, s.starts_at FROM jam_bookings j JOIN slots s ON s.id=j.slot_id "
            "WHERE j.ref_code=? AND j.attendee_id=? AND j.status='confirmed'",
            (str(ref or "").upper(), owner_id)).fetchone()
        if mine is None:
            raise ClaimError("NO_BOOKING", "That isn't one of your bookings.")
        if (mine["booked_by_id"] or owner_id) != owner_id:
            raise ClaimError("FORBIDDEN", "Only the person who booked this slot can add people. "
                                          "Ask them, or book your own.")
        slot = conn.execute("SELECT * FROM slots WHERE id=?", (mine["slot_id"],)).fetchone()
        seated = _jam_seats(conn, slot["id"])
        taken = len(seated)
        people = _resolve_jam_friends(conn, owner, players, cfg,
                                      int(cfg["jam_capacity"]) - taken, slot)
        if not people:
            raise ClaimError("VALIDATION_FAILED", "Type at least one username.")
        clash = [p["_instrument"] for p in people
                 if any(r["instrument"] == p["_instrument"] for r in seated)]
        if clash:
            names = ", ".join(config.INSTRUMENT_LABELS[i].lower() for i in clash)
            raise ClaimError("INSTRUMENT_TAKEN",
                             f"Someone already has the {names} in that slot. Nobody was added.",
                             instruments=clash)
        _check_open(slot, taken, now, cfg, len(people), what="slot")
        _seat_jam_friends(conn, owner, people, slot, cfg, now)
        return {"added": [p["handle"] for p in people]}

    return _run(conn, run, ClaimError(
        "INSTRUMENT_TAKEN", "Someone took that instrument a moment ago. Nobody was added."))


def remove_jam_friend(conn, owner_id, ref, handle, now):
    """The booker takes someone they added back off the slot."""
    owner = _person(conn, owner_id)
    h = normalise_handle(handle)

    def run():
        row = conn.execute(
            "SELECT j.*, s.starts_at FROM jam_bookings j JOIN slots s ON s.id=j.slot_id "
            "JOIN attendees a ON a.id=j.attendee_id "
            "WHERE a.handle=? AND j.booked_by_id=? AND j.attendee_id != ? AND j.status='confirmed'",
            (h, owner_id, owner_id)).fetchone()
        if row is None:
            raise ClaimError("FORBIDDEN", "You can only remove people you added yourself.")
        if now >= _dt(row["starts_at"]):
            raise ClaimError("SLOT_STARTED", "That slot has already started.")
        _cancel_jam_seat(conn, row, now, told=notify.who(owner))
        db.audit(conn, "attendee", "Removed from a jam slot", actor_name=notify.who(owner),
                 entity="attendee", entity_id=row["attendee_id"],
                 details={"slot_id": row["slot_id"]})
        return {"removed": h}

    return _run(conn, run)


def _cancel_jam_seat(conn, row, now, told=None):
    """Cancel one seat. `told` names whoever did it, when it was not them."""
    conn.execute("UPDATE jam_bookings SET status='cancelled', cancelled_at=? WHERE id=?",
                 (_iso(now), row["id"]))
    # If they were never told they had the seat, take the message back rather
    # than sending "you're booked" followed by "actually you're not".
    withdrawn = notify.withdraw(conn, f"jam_friend_added:{row['id']}")
    if told and not withdrawn:
        notify.queue(conn, row["attendee_id"], "jam_removed",
                     notify.text_jam_removed(told), go=notify.GO_BOOKINGS,
                     dedupe_key=f"jam_removed:{row['id']}", now=now)
    return withdrawn


def leave_jam(conn, attendee_id, ref, now):
    """Somebody who was added to a slot gives up their own seat."""
    me = _person(conn, attendee_id)

    def run():
        row = conn.execute(
            "SELECT j.*, s.starts_at FROM jam_bookings j JOIN slots s ON s.id=j.slot_id "
            "WHERE j.ref_code=? AND j.attendee_id=? AND j.status='confirmed'",
            (str(ref or "").upper(), attendee_id)).fetchone()
        if row is None:
            raise ClaimError("NO_BOOKING", "That isn't one of your bookings.")
        if now >= _dt(row["starts_at"]):
            raise ClaimError("SLOT_STARTED", "That slot has already started.")
        owner_id = row["booked_by_id"] or attendee_id
        conn.execute("UPDATE jam_bookings SET status='cancelled', cancelled_at=? WHERE id=?",
                     (_iso(now), row["id"]))
        notify.withdraw(conn, f"jam_friend_added:{row['id']}")
        if owner_id != attendee_id:
            notify.queue(conn, owner_id, "jam_friend_left",
                         notify.text_jam_friend_left(notify.who(me), row["starts_at"]),
                         go=notify.GO_BOOKINGS, dedupe_key=f"jam_friend_left:{row['id']}", now=now)
        db.audit(conn, "attendee", "Left a jam slot", actor_name=notify.who(me),
                 entity="attendee", entity_id=attendee_id, details={"slot_id": row["slot_id"]})
        return {"left": True}

    return _run(conn, run)


def cancel_jam(conn, attendee_id, ref, now):
    """Cancel a jam booking.

    The booker cancels the whole group — the room was theirs for that slot and
    the others are only there because of them. Anyone else gives up their own
    seat instead, which is `leave_jam`. The app shows whichever of the two
    buttons applies, so the refusal below is a safety net rather than
    something a person should ever meet.
    """
    me = _person(conn, attendee_id)

    def run():
        j = conn.execute(
            "SELECT j.*, s.starts_at, s.ends_at FROM jam_bookings j JOIN slots s ON s.id=j.slot_id "
            "WHERE j.ref_code=? AND j.attendee_id=? AND j.status='confirmed'",
            (str(ref or "").upper(), attendee_id)).fetchone()
        if j is None:
            raise ClaimError("NO_BOOKING", "That isn't one of your bookings.")
        if now >= _dt(j["starts_at"]):
            raise ClaimError("SLOT_STARTED", "That slot has already started.")
        owner_id = j["booked_by_id"] or attendee_id
        if owner_id != attendee_id:
            raise ClaimError("FORBIDDEN",
                             "That slot was booked by someone else. You can leave it instead.")
        party = _jam_party(conn, attendee_id, j["slot_id"])
        for row in party:
            if row["attendee_id"] == attendee_id:
                conn.execute("UPDATE jam_bookings SET status='cancelled', cancelled_at=? WHERE id=?",
                             (_iso(now), row["id"]))
                continue
            # A cancelled group is not the same as being removed from one, so
            # it gets its own wording rather than "X took you off".
            if not notify.withdraw(conn, f"jam_friend_added:{row['id']}"):
                notify.queue(conn, row["attendee_id"], "jam_cancelled",
                             notify.text_jam_cancelled_by_owner(notify.who(me), j["starts_at"]),
                             go=notify.GO_BOOKINGS, dedupe_key=f"jam_cancelled:{row['id']}", now=now)
            conn.execute("UPDATE jam_bookings SET status='cancelled', cancelled_at=? WHERE id=?",
                         (_iso(now), row["id"]))
        db.audit(conn, "attendee", "Jam slot cancelled", actor_name=notify.who(me), entity="attendee",
                 entity_id=attendee_id,
                 details={"ref": j["ref_code"], "slot_id": j["slot_id"], "seats": len(party)})
        return {"cancelled": True, "seats": len(party)}

    return _run(conn, run)
