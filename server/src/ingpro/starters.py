"""Sentence-starter cheat sheet: content/grammar/starters.json.

Deterministic, rule-based selection — no LLM call per message, unlike the tutor and the judge. Alex's own reply
is scanned for topic keywords and a few cheap discourse-function cues (does it invite a past-tense answer? a
reason? a plan?...); starters are picked by tag overlap with those cues, the active scenario, and the learner's
vocabulary level (brain.usage.vocab_ceiling). Teaching the picker a new subject or cue is a data change (add a
keyword, add a starter to the JSON) — the scoring logic itself never needs to change.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import nlp
from .brain.usage import CEFR

FIELDS = ("id", "en", "tr", "level", "grammar", "topics", "functions", "scenarios")

# lemma -> topic tag. Extend freely: this is the only thing that needs touching to teach the picker a new subject.
TOPIC_KEYWORDS: dict[str, str] = {
    **dict.fromkeys(("work", "job", "office", "meeting", "career", "colleague", "boss", "project", "report", "business", "company", "resume", "salary", "interview"), "work"),
    **dict.fromkeys(("food", "restaurant", "eat", "order", "menu", "dish", "hungry", "meal", "breakfast", "lunch", "dinner", "coffee", "drink", "taste"), "food"),
    **dict.fromkeys(("travel", "flight", "airport", "luggage", "trip", "hotel", "vacation", "holiday", "passport", "ticket", "bag", "board", "gate", "fly"), "travel"),
    **dict.fromkeys(("computer", "laptop", "internet", "wifi", "password", "connect", "screen", "error", "software", "printer", "phone", "app", "network", "vpn"), "tech"),
    **dict.fromkeys(("feel", "tired", "happy", "sad", "excited", "nervous", "stressed", "worried", "glad", "angry", "bored"), "feelings"),
    **dict.fromkeys(("house", "home", "apartment", "room", "live", "kitchen", "garden", "neighbor"), "home"),
    **dict.fromkeys(("family", "friend", "parent", "sister", "brother", "wife", "husband", "child"), "people"),
    **dict.fromkeys(("weather", "rain", "sun", "snow", "cold", "hot", "warm", "wind", "cloud"), "weather"),
    **dict.fromkeys(("hobby", "weekend", "movie", "book", "music", "sport", "game", "gym", "run", "read", "play"), "hobbies"),
    **dict.fromkeys(("sick", "doctor", "hospital", "medicine", "headache", "sleep", "exercise"), "health"),
    **dict.fromkeys(("shop", "buy", "store", "price", "size", "clothes", "shoe"), "shopping"),
}

# a substring in Alex's (lowercased) message -> the discourse-function cue it invites. Extend freely.
FUNCTION_CUES: dict[str, tuple[str, ...]] = {
    "recount_past": ("yesterday", "this morning", "so far", "today", "last night", "last week"),
    "future_plan": ("weekend", "tomorrow", "tonight", "later", "plan", "going to", "next week"),
    "opinion": ("think", "feel", "prefer", "rather", "opinion"),
    "comparison": ("better", "worse", "than", "compare", "which one"),
    "reason": ("why",),
    "request_response": ("can you", "could you", "would you", "recommend", "what would"),
    "experience": ("ever", "before", "experience", "have you"),
}

LEVEL_INDEX = {level: i for i, level in enumerate(CEFR)}
SCENARIO_MISMATCH = float("-inf")


def load_starters(content_dir: Path) -> list[dict]:
    path = content_dir / "grammar" / "starters.json"
    if not path.is_file():
        return []
    items = json.loads(path.read_text()).get("starters", [])
    return [s for s in items if all(s.get(f) for f in FIELDS)]


def _topics_of(text: str) -> set[str]:
    return {TOPIC_KEYWORDS[t.lemma_.lower()] for t in nlp.doc(text) if t.lemma_.lower() in TOPIC_KEYWORDS}


def _functions_of(text: str) -> set[str]:
    low = text.lower()
    found = {fn for fn, cues in FUNCTION_CUES.items() if any(c in low for c in cues)}
    found.add("general_answer")  # a safety net: the candidate pool is never empty
    return found


def _score(s: dict, ctx_topics: set[str], ctx_functions: set[str], scenario: str, level_i: int, shown: set[str]) -> float:
    if "any" not in s["scenarios"] and scenario not in s["scenarios"]:
        return SCENARIO_MISMATCH
    points = 2.0 * len(ctx_topics & set(s["topics"])) + 3.0 * len(ctx_functions & set(s["functions"]))
    if scenario in s["scenarios"]:  # written for this exact role-play, not just "any": outweighs a merely-generic function match
        points += 4.0
    s_level = LEVEL_INDEX.get(s["level"], 0)
    points += 1.0 if s_level == level_i else (0.5 if s_level < level_i else -2.0)
    if s["id"] in shown:
        points -= 5.0  # deprioritized, not excluded: still better than showing nothing once the pool runs low
    return points


def pick(alex_text: str, scenario: str, level: str, content_dir: Path, shown: set[str] | None = None, n: int = 3) -> list[dict]:
    """Deterministic top-`n` starters for what Alex just said. `shown` is the caller's per-session memory of ids
    already suggested, so the same one is not repeated turn after turn while the context stays similar."""
    pool = load_starters(content_dir)
    if not pool:
        return []
    ctx_topics = _topics_of(alex_text)
    ctx_functions = _functions_of(alex_text)
    level_i = LEVEL_INDEX.get(level, 0)
    scored = [(_score(s, ctx_topics, ctx_functions, scenario, level_i, shown or set()), s) for s in pool]
    scored = [(sc, s) for sc, s in scored if sc != SCENARIO_MISMATCH]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [s for _, s in scored[:n]]
