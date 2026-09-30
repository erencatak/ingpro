"""Learning rules. Pure functions, no I/O.

Ideas behind the rules (details and sources in the vault, İngilizce/Beyin/Kavramlar):
  retrieval practice (testing effect)  only an attempt to *recall* raises mastery a lot; re-reading is capped low
  spacing + forgetting curve           memory strength decays; FSRS schedules the next test (py-fsrs)
  memory consolidation                 durable stages need successes spread over several days, not one long session
  synaptic plasticity                  young neurons/synapses change fast, well-learned ones change slowly
  Hebbian learning                     things recalled together get linked more strongly
  LTD / pruning                        unused links fade, and very weak learned links are removed
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from fsrs import Card, Rating, Scheduler

# ---- stages -------------------------------------------------------------------------------------------------

STAGES = ("uyuyan", "kodlama", "kisa_sureli", "pekisme", "uzun_sureli")
STAGE_LABEL = {
    "uyuyan": "Uyuyan",
    "kodlama": "Kodlama",
    "kisa_sureli": "Kısa süreli bellek",
    "pekisme": "Pekişme",
    "uzun_sureli": "Uzun süreli bellek",
}
# The score (mastery, 0-100) can never exceed the cap of the stage: one lucky answer cannot look like durable knowledge.
STAGE_CAP = {"uyuyan": 0, "kodlama": 30, "kisa_sureli": 60, "pekisme": 85, "uzun_sureli": 100}

CONSOLIDATING_STABILITY = 3.0  # days of FSRS stability, and successes on >= 2 distinct days
LONG_TERM_STABILITY = 21.0  # days of stability, >= 3 successes on >= 3 distinct days
EXPOSURE_POINTS = 10  # re-reading gives this much score per read ...
EXPOSURE_CAP = STAGE_CAP["kodlama"]  # ... up to the "kodlama" cap
LAPSE_CAP = 20  # right after failing to recall, the score cannot exceed this

# ---- ratings ------------------------------------------------------------------------------------------------

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
RATING_LABEL = {AGAIN: "Hatırlayamadım", HARD: "Zor hatırladım", GOOD: "İyi hatırladım", EASY: "Kolay"}
ACTIVATION = {AGAIN: 0.0, HARD: 0.5, GOOD: 1.0, EASY: 1.0}  # how strongly the neuron "fired" in a retrieval
XP = {AGAIN: 2, HARD: 6, GOOD: 10, EASY: 12}  # effort counts a little even when it failed
XP_EXPOSURE = 1
XP_CONSOLIDATION = 25  # bonus for reaching a durable stage (pekisme, uzun_sureli), not for the first recall
DURABLE_STAGES = ("pekisme", "uzun_sureli")

# ---- synapses -----------------------------------------------------------------------------------------------

HEBB_ETA = 0.2  # base learning rate of a co-activation
HEBB_TAU_DAYS = 120.0  # time constant of decay by disuse (LTD)
PRUNE_BELOW = 0.03  # learned synapses weaker than this are removed
CONFUSION_STEP = 0.25  # a confusion error raises the confusion synapse by this fraction of the room left
CONFUSION_RELIEF = 0.10  # a successful joint retrieval lowers a confusion synapse by this fraction
FLOORS = {"structural": 0.10, "confusion": 0.10, "hebbian": 0.0}  # curated links never fully fade
INITIAL_WEIGHT = {"structural": 0.25, "confusion": 0.30, "hebbian": 0.0}
CO_ACTIVATION_WINDOW = timedelta(minutes=30)
MAX_PARTNERS = 6  # a new retrieval is linked with at most this many recent ones


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_scheduler() -> Scheduler:
    # No same-day learning steps: a subtopic is studied at a desk, the next test is scheduled in days.
    return Scheduler(desired_retention=0.9, learning_steps=(), relearning_steps=(), enable_fuzzing=False)


@dataclass
class Memory:
    """Everything the brain remembers about one neuron."""

    exposures: int = 0
    retrievals: int = 0
    successes: int = 0  # retrievals rated Hard / Good / Easy
    success_days: list[str] = field(default_factory=list)  # distinct UTC dates with a success
    last_rating: int | None = None
    card: dict | None = None  # FSRS card state
    last_event_at: str | None = None
    last_reviewed_on: str | None = None  # UTC date of the last review() that was allowed to move the FSRS card


@dataclass
class Outcome:
    stage_before: str
    stage_after: str
    promoted: bool
    interval_days: float
    due_at: str
    xp: int


def stability(m: Memory) -> float:
    return float(m.card["stability"]) if m.card and m.card.get("stability") else 0.0


def due_at(m: Memory) -> datetime | None:
    return datetime.fromisoformat(m.card["due"]) if m.card and m.card.get("due") else None


def retrievability(m: Memory, now: datetime, sched: Scheduler | None = None) -> float:
    """Probability of recalling the neuron right now (FSRS forgetting curve). 0 when it was never retrieved."""
    if not m.card:
        return 0.0
    return float(( sched or make_scheduler()).get_card_retrievability(Card.from_dict(m.card), current_datetime=now))


def stage_of(m: Memory) -> str:
    if m.exposures == 0 and m.retrievals == 0:
        return "uyuyan"
    if m.successes == 0:
        return "kodlama"
    days = len(m.success_days)
    s = stability(m)
    if s >= LONG_TERM_STABILITY and m.successes >= 3 and days >= 3:
        return "uzun_sureli"
    if s >= CONSOLIDATING_STABILITY and days >= 2:
        return "pekisme"
    return "kisa_sureli"


def score_of(m: Memory, now: datetime, sched: Scheduler | None = None) -> int:
    """Mastery 0-100: what fraction is recalled now, limited by how consolidated the memory is."""
    stage = stage_of(m)
    if stage == "uyuyan":
        return 0
    if stage == "kodlama":
        return min(EXPOSURE_CAP, EXPOSURE_POINTS * m.exposures)
    score = min(STAGE_CAP[stage], round(100 * retrievability(m, now, sched)))
    return min(score, LAPSE_CAP) if m.last_rating == AGAIN else score


PLASTICITY = {"uyuyan": 1.0, "kodlama": 1.0, "kisa_sureli": 1.0, "pekisme": 0.6, "uzun_sureli": 0.3}


def plasticity(m: Memory) -> float:
    """How easily the neuron's links change: fully plastic until consolidation starts, then increasingly stable."""
    return PLASTICITY[stage_of(m)]


# ---- events -------------------------------------------------------------------------------------------------


def review(m: Memory, rating: int, now: datetime, sched: Scheduler | None = None) -> tuple[Memory, Outcome]:
    """One retrieval attempt (the testing effect): try to recall, then rate honestly."""
    sched = sched or make_scheduler()
    before = stage_of(m)
    today = now.astimezone(timezone.utc).date().isoformat()
    card = Card.from_dict(m.card) if m.card else Card()
    if m.last_reviewed_on != today:
        # FSRS stability may only advance once per calendar day: without this, repeated same-day taps (e.g.
        # several EASY ratings in one sitting) keep growing stability on their own, letting the multi-day
        # consolidation requirement be reached in far fewer real days than intended.
        card, _ = sched.review_card(card, Rating(rating), review_datetime=now)
    days = list(m.success_days)
    success = rating >= HARD
    if success and today not in days:
        days.append(today)
    new = replace(
        m,
        retrievals=m.retrievals + 1,
        successes=m.successes + (1 if success else 0),
        success_days=days,
        last_rating=rating,
        card=card.to_dict(),
        last_reviewed_on=today,
        last_event_at=now.isoformat(),
    )
    after = stage_of(new)
    promoted = STAGES.index(after) > STAGES.index(before)
    interval = (card.due - now).total_seconds() / 86400
    xp = XP[rating] + (XP_CONSOLIDATION if promoted and after in DURABLE_STAGES else 0)
    return new, Outcome(before, after, promoted, interval, card.due.isoformat(), xp)


def expose(m: Memory, now: datetime) -> tuple[Memory, Outcome]:
    """Re-reading / listening without trying to recall: it helps a little, up to a low cap."""
    before = stage_of(m)
    new = replace(m, exposures=m.exposures + 1, last_event_at=now.isoformat())
    after = stage_of(new)
    return new, Outcome(before, after, STAGES.index(after) > STAGES.index(before), 0.0, m.card["due"] if m.card else "", XP_EXPOSURE)


# ---- synapses -----------------------------------------------------------------------------------------------


def hebbian_step(weight: float, act_a: float, act_b: float, plast_a: float, plast_b: float) -> float:
    """Neurons that are recalled together get linked: growth is proportional to both activations, bounded by 1."""
    delta = HEBB_ETA * (plast_a + plast_b) / 2.0 * act_a * act_b * (1.0 - weight)
    return min(1.0, weight + delta)


def confusion_step(weight: float) -> float:
    return min(1.0, weight + CONFUSION_STEP * (1.0 - weight))


def confusion_relief(weight: float) -> float:
    return max(FLOORS["confusion"], weight * (1.0 - CONFUSION_RELIEF))


def decay_weight(weight: float, kind: str, days_idle: float) -> float:
    """Long-term depression by disuse: exponential fade towards the floor of the synapse kind."""
    faded = weight * math.exp(-max(days_idle, 0.0) / HEBB_TAU_DAYS)
    return max(FLOORS.get(kind, 0.0), faded)


def should_prune(weight: float, kind: str) -> bool:
    return kind == "hebbian" and weight < PRUNE_BELOW
