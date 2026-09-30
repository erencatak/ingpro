"""Word-memory rules. Pure functions, no I/O. Reuses rules.py's generic Memory/FSRS/Hebbian machinery —
none of it is grammar-specific — but words get their own, simpler 2-stage model instead of the 5-stage one.

Why 2 stages, not 5: a word's path to being genuinely known has two well-evidenced phases (Complementary
Learning Systems: Davis & Gaskell 2009), not grammar's five. A new word is bound quickly ("hizli_tanima" —
fast, hippocampal-style familiarization, reachable after a single successful recall). It only becomes a real
lexical competitor — reliably usable, not just recognizable — after it has survived at least one offline
consolidation pass ("entegre"). Practically: the same `consolidate()` sweep that already runs for the grammar
brain (service.py) also anchors this gate, via `store.meta("last_consolidation")`.

Every retrieval here comes from one source: a correctly-used, clearly-spoken word in conversation (the judge
already gates on spoken + clear pronunciation before a lemma ever reaches this module — see brain/judge.py,
usage.precheck). There is no self-rated 1-4 dial for words yet, so every such retrieval is rated GOOD (rules.GOOD):
a plain, defensible "yes, recalled it correctly", not an invented guess at how easy it felt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from . import rules
from .rules import Memory

WORD_STAGES = ("uyuyan", "hizli_tanima", "entegre")
WORD_STAGE_LABEL = {"uyuyan": "Uyuyan", "hizli_tanima": "Hızlı tanıma", "entegre": "Entegre"}

# Two synapse kinds, both distinct from grammar's structural/confusion/hebbian:
#   semantic       static, precomputed from shared TOPIC_KEYWORDS category — not activity-based
#   cooccurrence   dynamic, Hebbian-style: strengthens when two words are both used correctly in the same sentence
WORD_INITIAL_WEIGHT = {"semantic": 0.20, "cooccurrence": 0.0}
WORD_FLOORS = {"semantic": 0.05, "cooccurrence": 0.0}

WORD_XP_RETRIEVAL = 5  # flat: every retrieval here is rated GOOD (see module docstring), no per-rating ladder needed
WORD_XP_INTEGRATION = 15  # bonus the first time a word reaches "entegre" (mirrors grammar's consolidation bonus)


@dataclass
class WordOutcome:
    stage_before: str
    stage_after: str
    promoted: bool
    due_at: str
    xp: int


def word_stage_of(m: Memory, last_consolidation: datetime | None) -> str:
    if m.exposures == 0 and m.retrievals == 0:
        return "uyuyan"
    if m.successes == 0:
        return "hizli_tanima"
    survived_a_sleep = last_consolidation is not None and m.last_event_at is not None and last_consolidation.isoformat() > m.last_event_at
    return "entegre" if survived_a_sleep else "hizli_tanima"


def word_decay_weight(weight: float, kind: str, days_idle: float) -> float:
    faded = weight * math.exp(-max(days_idle, 0.0) / rules.HEBB_TAU_DAYS)
    return max(WORD_FLOORS.get(kind, 0.0), faded)


def word_should_prune(weight: float, kind: str) -> bool:
    return kind == "cooccurrence" and weight < rules.PRUNE_BELOW


def word_review(m: Memory, now: datetime, last_consolidation: datetime | None, sched=None) -> tuple[Memory, WordOutcome]:
    """One correctly-used, clearly-spoken occurrence of the word. Reuses rules.review()'s FSRS-card update (that
    part is generic, not stage-system-specific) but replaces its 5-stage before/after/promoted/xp with the
    2-stage reading — `entegre` cannot be reached here, only by a `consolidate()` pass that runs later; see
    word_stage_of."""
    sched = sched or rules.make_scheduler()
    before = word_stage_of(m, last_consolidation)
    new, _discarded = rules.review(m, rules.GOOD, now, sched)
    after = word_stage_of(new, last_consolidation)
    promoted = after == "entegre" and before != "entegre"
    xp = WORD_XP_RETRIEVAL + (WORD_XP_INTEGRATION if promoted else 0)
    return new, WordOutcome(before, after, promoted, new.card["due"] if new.card else "", xp)
