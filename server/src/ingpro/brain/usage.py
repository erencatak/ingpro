"""Speaking points: how well the learner USES a grammar topic in real spoken sentences, and when a topic is approved.

The four rules (one scored spoken sentence, always about one target topic):
  1. target grammar used correctly + a NEW word + clear spoken pronunciation ........ 3 points
  2. target grammar used correctly + a known word + clear spoken pronunciation ....... 2 points
  3. target grammar missing or wrong + a word + clear spoken pronunciation ........... 1 point
  4. speaking with words only (no sentence) ......................................... 0 points

A topic is approved (finished) when its points reach the requirement of its level:
  A1-A2 topic 30 points, B1-B2 topic 60 points, C1 topic 90 points.

Validity conditions (what does NOT count, decided before any rule is applied):
  - not spoken (typed) ............ pronunciation is part of every rule, so typed messages earn nothing
  - not English ................... Turkish speech earns nothing
  - unclear pronunciation ......... recognizer confidence below PRONUNCIATION_OK
  - the same sentence again ....... a sentence scores once per topic
Approval also needs a few sentences that really used the target grammar (MIN_CORRECT_SENTENCES): a unit cannot be finished
with off-topic sentences that only earn rule 3.
Pure functions, no I/O.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

BANDS = ("A1-A2", "B1-B2", "C1")
REQUIRED = {"A1-A2": 30, "B1-B2": 60, "C1": 90}
DEFAULT_BAND = "A1-A2"

RULE_POINTS = {1: 3, 2: 2, 3: 1, 4: 0}
RULE_LABEL = {
    1: "Kural doğru + yeni kelime + net telaffuz",
    2: "Kural doğru + bilinen kelime + net telaffuz",
    3: "Kural eksik ya da hatalı + kelime + net telaffuz",
    4: "Yalnızca kelimelerle konuşma",
}

PRONUNCIATION_OK = 0.6  # mean word confidence of the speech recognizer; a rough proxy, see the vault note Beyin/03-Konusma-Puanlari
WEAK_WORD = 0.4  # a word recognized with less confidence than this is "weak" ...
MAX_WEAK_SHARE = 0.3  # ... and a sentence with more than this share of weak words is not clear (a good mean can hide garbage words)
MIN_CORRECT_SENTENCES = 3  # a unit needs this many sentences with correct target grammar (rules 1 and 2), whatever its points; 0 turns the guard off
NEW_WORD_USES = 3  # a word stays "new" until it was used correctly in speech this many times
# Vocabulary opens up with progress: only words up to the unlocked level count as "new". The learner knows very few words
# today, so it starts at the very bottom (A1) and stays at the lower bounds; higher levels open as units get approved.
# Provisional numbers: the vocabulary side gets its own design later. Capped at B2 (TOEFL level).
VOCAB_UNLOCK = (("A1", 0), ("A2", 5), ("B1", 15), ("B2", 30))  # (level, approved units needed)
CEFR = ("A1", "A2", "B1", "B2", "C1", "C2")
XP_PER_POINT = 5


@dataclass(frozen=True)
class Word:
    lemma: str
    cefr: str = "A1"


@dataclass(frozen=True)
class Judgement:
    """What the language judge (an LLM) decided about one sentence."""

    is_sentence: bool
    grammar: str  # "correct" | "incorrect" | "absent"  (about the target topic)
    words: tuple[Word, ...] = ()
    feedback_tr: str = ""
    correction: str | None = None


@dataclass(frozen=True)
class Speech:
    """How the sentence was produced."""

    spoken: bool
    lang: str
    pron_conf: float | None  # mean recognizer confidence of the words; None when there is none (typed, or nothing recognized)
    weak_share: float = 0.0  # share of words the recognizer was unsure about


@dataclass
class Scored:
    valid: bool
    rule: int | None
    points: int
    reason: str
    new_words: list[str] = field(default_factory=list)
    used_words: list[str] = field(default_factory=list)  # content words that count as a correct use (rules 1 and 2)


def normalize(text: str) -> str:
    """Key of a sentence for the "same sentence" rule: case, punctuation, curly apostrophes and Unicode forms do not matter."""
    t = unicodedata.normalize("NFKC", text).lower().replace("’", "'").replace("‘", "'")
    return " ".join(re.findall(r"[^\W_]+(?:'[^\W_]+)*", t))


def is_approved(points: int, required: int, correct_sentences: int) -> bool:
    return points >= required and correct_sentences >= MIN_CORRECT_SENTENCES


def band_required(band: str | None) -> int:
    return REQUIRED.get(band or DEFAULT_BAND, REQUIRED[DEFAULT_BAND])


def precheck(speech: Speech) -> str | None:
    """Validity conditions that need no language judge. Returns the reason the sentence is not valid, or None."""
    if not speech.spoken:
        return "Yazılı mesaj puan vermez: telaffuz her kuralın parçası, sesli söylemelisin."
    if speech.lang != "en":
        return "Türkçe konuşma puan vermez."
    # No confidence at all (nothing recognized) is not clear speech: it must not pass by default
    if speech.pron_conf is None or math.isnan(speech.pron_conf) or speech.pron_conf < PRONUNCIATION_OK or speech.weak_share > MAX_WEAK_SHARE:
        return "Telaffuz net anlaşılmadı, aynı cümleyi tekrar dene."
    return None


def vocab_ceiling(approved_units: int) -> str:
    """The highest word level that counts as "new" for a learner with this many approved units."""
    return [level for level, needed in VOCAB_UNLOCK if approved_units >= needed][-1]


def is_new_word(word: Word, uses: int, ceiling: str = "A1") -> bool:
    """A word not yet used correctly NEW_WORD_USES times, at or below the unlocked vocabulary level.
    Harder words are still fine to use (and count for the grammar), they just do not open rule 1 yet."""
    level = CEFR.index(word.cefr if word.cefr in CEFR else "A1")
    return level <= CEFR.index(ceiling if ceiling in CEFR else "A1") and uses < NEW_WORD_USES


def score(judgement: Judgement, speech: Speech, word_uses: dict[str, int], duplicate: bool = False, ceiling: str = "A1") -> Scored:
    """Applies the validity conditions and then the four rules."""
    bad = precheck(speech)
    if bad:
        return Scored(False, None, 0, bad)
    if duplicate:
        return Scored(False, None, 0, "Bu cümle bu konuda zaten puanlandı, farklı bir cümle kur.")
    if not judgement.is_sentence:
        return Scored(True, 4, RULE_POINTS[4], RULE_LABEL[4])
    content = [w for w in judgement.words if w.lemma]
    if judgement.grammar == "correct":
        new = [w.lemma for w in content if is_new_word(w, word_uses.get(w.lemma, 0), ceiling)]
        rule = 1 if new else 2
        return Scored(True, rule, RULE_POINTS[rule], RULE_LABEL[rule], new, [w.lemma for w in content])
    return Scored(True, 3, RULE_POINTS[3], RULE_LABEL[3])
