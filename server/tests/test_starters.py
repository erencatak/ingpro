import json

from ingpro import starters
from ingpro.config import settings

REAL = json.loads((settings.content_dir / "grammar" / "starters.json").read_text())["starters"]
ALL_SCENARIOS = {"any", "free", "interview", "restaurant", "custom"}
ALL_FUNCTIONS = set(starters.FUNCTION_CUES) | {"general_answer", "ability", "description_present"}


def test_every_starter_is_well_formed():
    ids = [s["id"] for s in REAL]
    assert len(ids) == len(set(ids)), "duplicate starter id"
    for s in REAL:
        assert all(s.get(f) for f in starters.FIELDS), s["id"]
        assert s["en"].count("___") >= 1, s["id"]
        assert s["level"] in starters.LEVEL_INDEX, s["id"]
        assert set(s["scenarios"]) <= ALL_SCENARIOS, s["id"]
        assert set(s["functions"]) <= ALL_FUNCTIONS, s["id"]


def test_load_starters_drops_a_malformed_entry(tmp_path):
    good = REAL[0]
    (tmp_path / "grammar").mkdir()
    (tmp_path / "grammar" / "starters.json").write_text(json.dumps({"starters": [good, {"id": "missing_fields"}]}))
    assert [s["id"] for s in starters.load_starters(tmp_path)] == [good["id"]]


def test_load_starters_is_empty_without_a_file(tmp_path):
    assert starters.load_starters(tmp_path) == []


# ---- pick(): pure scoring logic, against a small fixed pool ------------------------------------------------------

POOL = [
    {"id": "work_past", "en": "I worked ___.", "tr": "-", "level": "A2", "grammar": "past simple", "topics": ["work"], "functions": ["recount_past"], "scenarios": ["any"]},
    {"id": "food_order", "en": "I would like ___.", "tr": "-", "level": "A1", "grammar": "would like", "topics": ["food"], "functions": ["request_response"], "scenarios": ["restaurant"]},
    {"id": "hard_relative", "en": "___ is someone who ___.", "tr": "-", "level": "B1", "grammar": "relative clause", "topics": ["people"], "functions": ["description_present"], "scenarios": ["any"]},
    {"id": "fallback_a", "en": "___, because ___.", "tr": "-", "level": "A1", "grammar": "because", "topics": ["general"], "functions": ["general_answer"], "scenarios": ["any"]},
    {"id": "fallback_b", "en": "___, and then ___.", "tr": "-", "level": "A1", "grammar": "sequence", "topics": ["general"], "functions": ["general_answer"], "scenarios": ["any"]},
]


def pick(text, scenario="free", level="A2", shown=None, n=3):
    ctx_topics = starters._topics_of(text)
    ctx_functions = starters._functions_of(text)
    level_i = starters.LEVEL_INDEX.get(level, 0)
    scored = [(starters._score(s, ctx_topics, ctx_functions, scenario, level_i, shown or set()), s) for s in POOL]
    scored = [(sc, s) for sc, s in scored if sc != starters.SCENARIO_MISMATCH]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [s for _, s in scored[:n]]


def test_a_past_tense_work_question_surfaces_the_matching_starter_first():
    top = pick("What kept you so busy at work yesterday?")
    assert top[0]["id"] == "work_past"


def test_scenario_restricted_starters_never_leak_into_another_scenario():
    top = pick("What would you like to order?", scenario="free")
    assert all(s["id"] != "food_order" for s in top)
    top = pick("What would you like to order?", scenario="restaurant")
    assert top[0]["id"] == "food_order"


def test_a_scenario_specific_starter_still_surfaces_before_any_keyword_appears():
    """A restaurant greeting with no food word yet ("table for one tonight?") should still lean toward
    restaurant content, not just the generic fallback pool — the role-play itself is a strong enough signal."""
    top = pick("Welcome in, table for one tonight?", scenario="restaurant", n=1)
    assert top[0]["id"] == "food_order"


def test_a_scenario_specific_starter_beats_a_generic_function_match_from_another_topic():
    """"Table for one today?" also hits the recount_past cue ("today"), which work_past (scenario "any") is
    tagged for — the restaurant-specific starter must still win, not lose a tie to an unrelated topic."""
    top = pick("Table for one today, sir?", scenario="restaurant", n=1)
    assert top[0]["id"] == "food_order"


def test_a_harder_than_level_starter_is_deprioritized_not_excluded():
    # nothing in the pool matches this text's context, so it's a pure level contest between the A1 fallbacks and the B1 one
    top = pick("Tell me about your city.", level="A1", n=5)
    assert top[0]["level"] != "B1" and "hard_relative" in [s["id"] for s in top]  # present, just not first


def test_shown_ids_are_deprioritized_so_the_cheat_sheet_rotates():
    first = pick("I don't know what to say.", n=1)
    again = pick("I don't know what to say.", shown={first[0]["id"]}, n=1)
    assert again[0]["id"] != first[0]["id"]


def test_the_general_fallback_pool_is_never_empty():
    assert len(pick("...", scenario="custom", n=3)) == 3
