from datetime import datetime, timedelta, timezone

import pytest

from ingpro.brain.service import BrainService
from ingpro.brain.store import Store
from ingpro.stats import build_stats, level_of

from test_brain import Clock, course

NOW = datetime(2026, 9, 29, 15, 0, tzinfo=timezone.utc)  # a Tuesday


@pytest.fixture
def brain():
    svc = BrainService(Store(":memory:"), None, Clock(NOW))
    svc.seed(course())
    return svc


def test_a_fresh_start_is_all_zero_and_measures_only_what_it_can(brain):
    s = build_stats(brain, NOW, timezone.utc)
    assert s["today"] == {"minutes": 0, "xp": 0} and s["streak"] == 0 and s["hours_total"] == 0
    assert s["level"] == "A1" and s["approved"] == [] and s["next_unit"]["unit"] == 1
    speaking, listening = s["skills"][0], s["skills"][1]
    assert speaking["value"] is None and listening["value"] is None  # nothing measures them yet: never guessed
    assert len(s["days"]) == 188 and s["days"][-1]["date"] == "2026-09-29" and len(s["curve"]) == 12
    assert [d["state"] for d in s["week"]] == ["", "today", "", "", "", "", ""]


def test_minutes_and_xp_land_on_the_local_day_and_build_the_streak(brain):
    st = brain.store
    st.log_session(NOW - timedelta(hours=1), NOW, 20 * 60, 5)
    st.log_session(NOW - timedelta(days=1, hours=1), NOW - timedelta(days=1), 12 * 60, 3)
    st.add_usage(NOW - timedelta(days=2), "c:01", "I have a car.", "i have a car", 1, 3, 0.9, None, [], None, None)
    s = build_stats(brain, NOW, timezone.utc)
    assert s["today"]["minutes"] == 20 and s["days"][-2]["minutes"] == 12
    assert s["days"][-3]["xp"] == 15  # 3 points x 5 xp, on the day it was spoken
    assert s["streak"] == 3 and s["hours_total"] == 0.5
    assert [d["state"] for d in s["week"]][:2] == ["on", "today"]  # Monday was active, Tuesday is today


def test_streak_survives_a_day_that_is_not_over_yet(brain):
    brain.store.log_session(NOW - timedelta(days=1, hours=1), NOW - timedelta(days=1), 600, 2)
    assert build_stats(brain, NOW, timezone.utc)["streak"] == 1  # nothing yet today, yesterday still counts


def test_grammar_level_grows_with_points_and_the_curve_is_history(brain):
    st = brain.store
    st.add_usage(NOW - timedelta(days=14), "c:01", "a", "a", 1, 3, 0.9, None, [], None, None)
    st.add_usage(NOW, "c:01", "b", "b", 1, 3, 0.9, None, [], None, None)
    s = build_stats(brain, NOW, timezone.utc)
    values = [p["value"] for p in s["curve"]]
    assert values == sorted(values) and values[-1] > values[-3] > 0  # 2 units A1-A2 need 60 points: 6 points = 2*6/60
    assert s["skills"][3]["value"] == values[-1] == 0.2


def test_level_bands():
    assert [level_of(v) for v in (0, 0.99, 1, 1.55, 2, 3.5, 4, 9)] == ["A1", "A1", "A2", "A2", "B1", "B2", "B2", "B2"]
