"""Numbers for the Bugün and İlerleme screens, computed from what the learner really did (SQLite), nothing invented.

Levels use the same 0-4 scale as the UI's skill bars: 0-1 is A1, 1-2 is A2, 2-3 is B1, 3-4 is B2.
Speaking and listening are not measured by anything yet, so they are reported as missing rather than guessed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, tzinfo

from .brain import usage
from .brain.service import BrainService

DAILY_MINUTES_GOAL = 30
DAILY_XP_GOAL = 200
HOURS_GOAL = 400
HEAT_DAYS = 26 * 7 + 6  # the heatmap on Bugün: 26 Monday-first weeks, the first may start up to 6 days earlier
HISTORY_WEEKS = 12  # the level curve on İlerleme
LEVELS = ("A1", "A2", "B1", "B2")
# Words a learner has to know at each level to fill that level's segment. Rough, adapted from the sizes of common CEFR
# word lists (about 500 / 1000 / 2000 / 3500 cumulative); provisional like the rest of the vocabulary design.
VOCAB_SEGMENT = {"A1": 500, "A2": 500, "B1": 1000, "B2": 1500}


def level_of(value: float) -> str:
    return LEVELS[max(0, min(int(value), 3))]


def grammar_value(points_by_col: dict[str, int], brain: BrainService) -> float:
    """Share of the A1-A2 units' required points fills segments 0-2, share of the B1-B2 units' fills 2-4."""
    got: dict[str, int] = defaultdict(int)
    need: dict[str, int] = defaultdict(int)
    for c in brain.store.columns():
        if c["extra"]:
            continue
        band = brain.bands.get(c["id"], usage.DEFAULT_BAND)
        need[band] += usage.band_required(band)
        got[band] += min(points_by_col.get(c["id"], 0), usage.band_required(band))
    frac = lambda band: got[band] / need[band] if need[band] else 0.0  # noqa: E731
    return round(2 * frac("A1-A2") + 2 * frac("B1-B2"), 3)


def vocab_value(brain: BrainService) -> float:
    known: dict[str, int] = defaultdict(int)
    for r in brain.store.vocab_all():
        if r["uses"] >= usage.NEW_WORD_USES and r["cefr"] in VOCAB_SEGMENT:
            known[r["cefr"]] += 1
    return round(sum(min(known[lv] / size, 1.0) for lv, size in VOCAB_SEGMENT.items()), 3)


def build_stats(brain: BrainService, now: datetime, tz: tzinfo | None = None) -> dict:
    store = brain.store
    local = lambda iso: datetime.fromisoformat(iso).astimezone(tz).date()  # noqa: E731
    today = now.astimezone(tz).date()
    first = today - timedelta(days=HEAT_DAYS - 1)
    since = datetime.combine(first, datetime.min.time(), tzinfo=now.astimezone(tz).tzinfo).astimezone(now.tzinfo)

    minutes: dict[date, float] = defaultdict(float)
    for r in store.sessions_since(since):
        minutes[local(r["started_at"])] += r["active_sec"] / 60
    xp: dict[date, int] = defaultdict(int)
    for r in store.xp_events_since(since):
        xp[local(r["ts"])] += r["xp"]
    history = store.usage_history()
    for r in history:
        if local(r["ts"]) >= first:
            xp[local(r["ts"])] += r["points"] * usage.XP_PER_POINT

    days = [{"date": (first + timedelta(days=i)).isoformat(), "minutes": round(minutes[first + timedelta(days=i)], 1), "xp": xp[first + timedelta(days=i)]}
            for i in range(HEAT_DAYS)]
    active = lambda d: minutes[d] > 0 or xp[d] > 0  # noqa: E731
    streak, d = 0, today if active(today) else today - timedelta(days=1)
    while d >= first and active(d):
        streak, d = streak + 1, d - timedelta(days=1)

    # the week Monday-Sunday around today
    monday = today - timedelta(days=today.weekday())
    week = [{"date": (monday + timedelta(days=i)).isoformat(), "state": "today" if monday + timedelta(days=i) == today else ("on" if active(monday + timedelta(days=i)) else "")}
            for i in range(7)]

    # grammar level at the end of each of the last weeks, rebuilt from the scored sentences
    curve = []
    for w in range(HISTORY_WEEKS - 1, -1, -1):
        end = min(today, monday - timedelta(days=7 * w) + timedelta(days=6))
        pts: dict[str, int] = defaultdict(int)
        for r in history:
            if local(r["ts"]) <= end:
                pts[r["col_id"]] += r["points"]
        curve.append({"date": end.isoformat(), "value": grammar_value(pts, brain)})

    gv, vv = curve[-1]["value"], vocab_value(brain)
    skills = [
        {"name": "Konuşma", "value": None, "level": None},
        {"name": "Dinleme", "value": None, "level": None},
        {"name": "Kelime", "value": vv, "level": level_of(vv)},
        {"name": "Dilbilgisi", "value": gv, "level": level_of(gv)},
    ]

    progress = brain.unit_progress()
    titles = {c["num"]: c["title_tr"] or c["title"] for c in store.columns() if not c["extra"]}
    approved = sorted(({"unit": int(n), "title": titles.get(int(n), ""), "approved_at": u["approved_at"], "points": u["points"], "band": u["band"]}
                       for n, u in progress.items() if u["approved"]), key=lambda u: u["approved_at"], reverse=True)
    nxt = next(({"unit": int(n), "title": titles.get(int(n), ""), "points": u["points"], "required": u["required"]}
                for n, u in sorted(progress.items(), key=lambda kv: int(kv[0])) if not u["approved"]), None)
    snap = brain.snapshot()

    return {
        "today": {"minutes": round(minutes[today], 1), "xp": xp[today]},
        "goals": {"minutes": DAILY_MINUTES_GOAL, "xp": DAILY_XP_GOAL, "hours": HOURS_GOAL},
        "days": days, "week": week, "streak": streak,
        "hours_total": round(store.total_session_seconds() / 3600, 1),
        "skills": skills, "level": level_of(gv), "curve": curve,
        "approved": approved, "units_total": len(progress), "next_unit": nxt,
        "due_count": snap["due_count"], "xp_total": snap["xp"],
    }
