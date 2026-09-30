"""Pre-learning cards (konu anlatımı): content/grammar/lessons.json, one card per grammar unit.

One card feeds every part of the app: the pre-learning screen, the speaking engine (opener, target patterns,
correction style), the judge, and review (the one-line refresher). Each card carries the sources it was checked against;
a card without a usable source or with too much text is rejected instead of shown.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

MAX_READ_SECONDS = 60  # the screen is a 30 to 60 second read
FIELDS = ("unit", "title", "title_tr", "focus", "meaning", "when_to_use", "examples", "structure", "speaking_clue", "common_mistakes",
          "speaking_scenario", "target_patterns", "correction_guidance", "refresher", "sources")
_WORDS_PER_SECOND = 3.0  # about 180 words a minute, a comfortable reading pace


def read_seconds(card: dict) -> int:
    parts = [card["meaning"], *card["when_to_use"], *(f'{e["en"]} {e["tr"]}' for e in card["examples"]), *card["structure"], card["speaking_clue"],
             *(f'{m["wrong"]} {m["right"]} {m["why"]}' for m in card["common_mistakes"])]
    return round(sum(len(re.findall(r"\S+", p)) for p in parts) / _WORDS_PER_SECOND)


def problems(card: dict) -> list[str]:
    """What is wrong with a card, in words. An empty list means it may be shown."""
    out = [f"missing {f}" for f in FIELDS if not card.get(f)]
    if out:
        return out
    if not 1 <= len(card["examples"]) <= 2:
        out.append("needs 1-2 examples")
    if not 2 <= len(card["when_to_use"]) <= 4:
        out.append("needs 2-4 when_to_use lines")
    if not 1 <= len(card["common_mistakes"]) <= 3:
        out.append("needs 1-3 common mistakes")
    if any(not (m.get("wrong") and m.get("right") and m.get("why")) or m["wrong"].strip() == m["right"].strip() for m in card["common_mistakes"]):
        out.append("a common mistake needs distinct wrong / right and a reason")
    if any(not (e.get("en") and e.get("tr")) for e in card["examples"]):
        out.append("an example needs en and tr")
    if not all(s.get("name") and str(s.get("url", "")).startswith("https://") and s.get("checked") in ("page-read", "search-snippet") for s in card["sources"]):
        out.append("every source needs a name, an https url and how it was checked")
    if not any(s["checked"] == "page-read" for s in card["sources"]):
        if card.get("verified") != "medium":
            out.append("only snippet-checked sources: the card must be marked verified=medium")
    if not card["speaking_scenario"].get("opener"):
        out.append("speaking_scenario needs an opener")
    if read_seconds(card) > MAX_READ_SECONDS:
        out.append(f"too long to read ({read_seconds(card)} s)")
    return out


def load_lessons(content_dir: Path) -> dict[int, dict]:
    """unit -> card. Cards that fail `problems` are left out."""
    path = content_dir / "grammar" / "lessons.json"
    if not path.is_file():
        return {}
    cards = json.loads(path.read_text()).get("lessons", [])
    return {c["unit"]: c for c in cards if isinstance(c.get("unit"), int) and not problems(c)}


def prompt_rules(card: dict) -> str:
    """What the tutor needs from the card, as plain lines for the system prompt."""
    mistakes = "; ".join(f'"{m["wrong"]}" should be "{m["right"]}"' for m in card["common_mistakes"])
    return (
        f'- Lesson focus: {card["focus"]} The learner has just read a short card about it, so do not teach it again. Patterns to draw out: '
        f'{"; ".join(card["target_patterns"])}.\n'
        f"- Typical mistakes here: {mistakes}.\n"
        f'- Correcting: {card["correction_guidance"]}'
    )


def judge_hint(card: dict) -> str:
    patterns = "; ".join(card["target_patterns"])
    mistakes = "; ".join(f'"{m["wrong"]}" -> "{m["right"]}"' for m in card["common_mistakes"])
    return f"Structures that count as the target: {patterns}. Typical mistakes: {mistakes}."


def greeting_cue(card: dict | None) -> str | None:
    if not card:
        return None
    return (
        "(The conversation just started. The learner has read a short lesson card. Open with one short, friendly sentence and then ask this question in your own words, "
        f'easy to answer: "{card["speaking_scenario"]["opener"]}")'
    )
