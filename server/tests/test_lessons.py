import copy
import json

import pytest

from ingpro import lessons
from ingpro.brain.judge import SYSTEM
from ingpro.config import settings
from ingpro.main import build_system_prompt, topic_focus

CARDS = json.loads((settings.content_dir / "grammar" / "lessons.json").read_text())["lessons"]
YENER = settings.content_dir / "grammar" / "yener.json"


def test_every_unit_has_a_valid_card():
    assert [c["unit"] for c in CARDS] == list(range(1, 47))
    assert {c["unit"]: lessons.problems(c) for c in CARDS if lessons.problems(c)} == {}


def test_cards_read_in_under_a_minute():
    assert max(lessons.read_seconds(c) for c in CARDS) <= lessons.MAX_READ_SECONDS


@pytest.mark.skipif(not YENER.is_file(), reason="the book's table of contents is not in this checkout")
def test_titles_match_the_book():
    topics = {t["id"]: t["title"] for t in json.loads(YENER.read_text())["topics"]}
    assert {c["unit"]: c["title"] for c in CARDS} == topics


def test_every_source_has_a_url_and_snippet_only_cards_are_marked_medium():
    for c in CARDS:
        assert all(s["url"].startswith("https://") for s in c["sources"])
        if not any(s["checked"] == "page-read" for s in c["sources"]):
            assert c["verified"] == "medium", c["unit"]


def test_every_mistake_is_really_different_and_examples_are_capped():
    for c in CARDS:
        assert 1 <= len(c["examples"]) <= 2
        assert all(m["wrong"] != m["right"] for m in c["common_mistakes"])


@pytest.mark.parametrize("field,value", [
    ("examples", []), ("examples", [{"en": "a", "tr": "b"}] * 3), ("sources", []),
    ("sources", [{"name": "x", "url": "http://x", "checked": "page-read"}]),
    ("common_mistakes", [{"wrong": "same", "right": "same", "why": "x"}]),
    ("meaning", ""), ("speaking_scenario", {"opener": ""}),
])
def test_bad_cards_are_rejected(field, value):
    card = copy.deepcopy(CARDS[0])
    card[field] = value
    assert lessons.problems(card)


def test_too_long_card_is_rejected():
    card = copy.deepcopy(CARDS[0])
    card["meaning"] = "word " * 300
    assert any("too long" in p for p in lessons.problems(card))


def test_snippet_only_card_must_admit_it():
    card = copy.deepcopy(CARDS[0])
    card["sources"] = [{**s, "checked": "search-snippet"} for s in card["sources"]]
    card["verified"] = "high"
    assert lessons.problems(card)


def test_load_skips_broken_cards(tmp_path):
    (tmp_path / "grammar").mkdir()
    broken = copy.deepcopy(CARDS[1])
    broken["sources"] = []
    (tmp_path / "grammar" / "lessons.json").write_text(json.dumps({"lessons": [CARDS[0], broken]}))
    assert list(lessons.load_lessons(tmp_path)) == [1]
    assert lessons.load_lessons(tmp_path / "nowhere") == {}


@pytest.mark.skipif(not YENER.is_file(), reason="needs the book's table of contents")
def test_topic_session_gets_the_lesson_in_prompt_greeting_and_judge():
    topic = topic_focus(1)
    assert topic["lesson"]["unit"] == 1
    prompt = build_system_prompt("free", "flow", topic)
    assert "Almost. Say:" in prompt and "{lesson_rules}" not in prompt
    assert "an + noun that starts with a vowel sound" in prompt
    assert CARDS[0]["speaking_scenario"]["opener"] in lessons.greeting_cue(topic["lesson"])
    assert lessons.greeting_cue(None) is None
    hint = lessons.judge_hint(topic["lesson"])
    assert "I have apple." in hint
    assert "{hint}" in SYSTEM


def test_session_without_a_card_still_builds():
    topic = {"id": 99, "title": "T", "tr": "T", "subtopics": [{"id": "99.1", "title": "s"}]}
    assert "Lesson focus" not in build_system_prompt("free", "flow", topic)
