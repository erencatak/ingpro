import os
from datetime import datetime, timedelta, timezone

import pytest

from ingpro.brain import rules
from ingpro.brain.seeds import seed_course
from ingpro.brain.service import BrainService, UnknownNeuron
from ingpro.brain.store import Store
from ingpro.brain.vault import USER_HEAD, Vault, safe_name

T0 = datetime(2026, 9, 27, 9, 0, tzinfo=timezone.utc)


def course(verified=False):
    def unit(n, title, tr, subs, page=10):
        return {"id": n, "title": title, "tr": tr, "page": page, "subtopics": [{"id": f"{n}.{i}", "title": t, **({"code": c} if c else {})} for i, (t, c) in enumerate(subs, 1)]}
    return {
        "source": "test", "verified": verified,
        "topics": [
            unit(1, "Articles", "Tanımlıklar", [("Indefinite Article", "1.A"), ("Definite Article", "1.B"), ("Exercises", None)]),
            unit(2, "Nouns", "İsimler", [("Countable / Uncountable Nouns", "2.A"), ("Plurals", "2.B")]),
        ],
    }


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


@pytest.fixture
def brain(tmp_path):
    clock = Clock()
    store = Store(":memory:")
    vault = Vault(tmp_path / "vault", store)
    svc = BrainService(store, vault, clock)
    svc.seed(course())
    svc.clock_ = clock
    return svc, clock, tmp_path / "vault"


# ---- rules ----------------------------------------------------------------------------------------------------

def test_stages_follow_consolidation_not_a_single_answer():
    m = rules.Memory()
    assert rules.stage_of(m) == "uyuyan" and rules.score_of(m, T0) == 0
    m, _ = rules.expose(m, T0)
    assert rules.stage_of(m) == "kodlama" and rules.score_of(m, T0) == 10
    m, o = rules.review(m, rules.GOOD, T0)
    assert o.stage_after == "kisa_sureli" and rules.score_of(m, T0) == 60  # one good answer cannot exceed the stage cap
    m, o = rules.review(m, rules.GOOD, T0 + timedelta(days=1))
    assert o.stage_after == "pekisme" and o.promoted and rules.score_of(m, T0 + timedelta(days=1)) == 85
    m, o = rules.review(m, rules.GOOD, T0 + timedelta(days=8))
    assert o.stage_after == "uzun_sureli" and rules.score_of(m, T0 + timedelta(days=8)) == 100


def test_same_day_repetition_does_not_consolidate():
    m = rules.Memory()
    for i in range(4):
        m, o = rules.review(m, rules.EASY, T0 + timedelta(minutes=10 * i))
    assert o.stage_after == "kisa_sureli"  # successes on one day only


def test_same_day_taps_freeze_the_fsrs_card_after_the_first():
    once, _ = rules.review(rules.Memory(), rules.EASY, T0)
    m = rules.Memory()
    for i in range(10):
        m, o = rules.review(m, rules.EASY, T0 + timedelta(minutes=10 * i))
    assert m.retrievals == 10 and o.stage_after == "kisa_sureli"  # attempts still tick, but a single day can't consolidate
    assert rules.stability(m) == pytest.approx(rules.stability(once))  # 10 same-day taps must look like 1 to FSRS
    assert m.card["due"] == once.card["due"]


def test_rereading_is_capped_below_retrieval():
    m = rules.Memory()
    for _ in range(10):
        m, _ = rules.expose(m, T0)
    assert rules.stage_of(m) == "kodlama" and rules.score_of(m, T0) == rules.EXPOSURE_CAP == 30


def test_forgetting_lowers_score_and_a_lapse_caps_it():
    m = rules.Memory()
    m, _ = rules.review(m, rules.GOOD, T0)
    m, _ = rules.review(m, rules.GOOD, T0 + timedelta(days=1))
    fresh = rules.score_of(m, T0 + timedelta(days=1))
    later = rules.score_of(m, T0 + timedelta(days=60))
    assert later < fresh
    m, _ = rules.review(m, rules.AGAIN, T0 + timedelta(days=60))
    assert rules.score_of(m, T0 + timedelta(days=60)) <= rules.LAPSE_CAP


def test_plasticity_falls_as_memory_consolidates():
    m = rules.Memory()
    assert rules.plasticity(m) == 1.0
    m, _ = rules.review(m, rules.GOOD, T0)
    assert rules.plasticity(m) == 1.0  # still short-term: fully plastic
    m, _ = rules.review(m, rules.GOOD, T0 + timedelta(days=1))
    assert rules.plasticity(m) == 0.6  # consolidating
    m, _ = rules.review(m, rules.GOOD, T0 + timedelta(days=8))
    assert rules.plasticity(m) == 0.3  # long-term: stable


def test_xp_rewards_consolidation_not_the_first_recall():
    m = rules.Memory()
    m, o = rules.review(m, rules.GOOD, T0)
    assert o.xp == rules.XP[rules.GOOD]
    m, o = rules.review(m, rules.GOOD, T0 + timedelta(days=1))
    assert o.xp == rules.XP[rules.GOOD] + rules.XP_CONSOLIDATION


def test_hebbian_growth_is_bounded_and_needs_both_neurons_to_fire():
    w = 0.0
    for _ in range(50):
        w = rules.hebbian_step(w, 1.0, 1.0, 1.0, 1.0)
    assert 0.99 < w <= 1.0
    assert rules.hebbian_step(0.3, 0.0, 1.0, 1.0, 1.0) == 0.3  # one neuron silent: no learning
    assert rules.hebbian_step(0.0, 1, 1, 1, 1) > rules.hebbian_step(0.0, 1, 1, 0.25, 0.25)  # young synapses learn faster


def test_disuse_fades_learned_links_but_curated_ones_keep_a_floor():
    assert rules.decay_weight(0.5, "hebbian", 365) < 0.5 * 0.1
    assert rules.decay_weight(0.5, "structural", 10_000) == rules.FLOORS["structural"]
    assert rules.should_prune(0.01, "hebbian") and not rules.should_prune(0.01, "structural")


# ---- service --------------------------------------------------------------------------------------------------

def test_review_records_event_xp_and_snapshot(brain):
    svc, clock, _ = brain
    r = svc.review("1.1", rules.GOOD)
    assert r["stage"] == "kisa_sureli" and r["xp"] == rules.XP[rules.GOOD]
    snap = svc.snapshot()
    assert snap["xp"] == r["xp"] and snap["neurons"]["1.1"]["retrievals"] == 1
    assert "1.2" not in snap["neurons"]  # untouched neurons stay dormant
    with pytest.raises(UnknownNeuron):
        svc.review("9.9", 3)
    with pytest.raises(ValueError):
        svc.review("1.1", 7)


def test_recalling_together_wires_together(brain):
    svc, clock, _ = brain
    svc.review("1.1", rules.GOOD)
    clock.advance(minutes=5)
    svc.review("1.2", rules.GOOD)
    (syn,) = svc.store.synapse_between("g:1.1", "g:1.2")
    assert syn["kind"] == "hebbian" and syn["weight"] == pytest.approx(0.2) and syn["co_activations"] == 1
    clock.advance(minutes=5)
    svc.review("2.1", rules.GOOD)
    assert len(svc.store.synapses()) == 3  # 2.1 was linked with both earlier neurons
    clock.advance(minutes=45)  # a different sitting: outside the co-activation window
    svc.review("2.2", rules.GOOD)
    assert not svc.store.synapse_between("g:2.2", "g:1.1")


def test_a_failed_recall_does_not_wire(brain):
    svc, clock, _ = brain
    svc.review("1.1", rules.GOOD)
    clock.advance(minutes=2)
    svc.review("1.2", rules.AGAIN)
    assert not svc.store.synapse_between("g:1.1", "g:1.2")


def test_confusion_is_learned_and_relieved(brain):
    svc, clock, _ = brain
    r = svc.review("1.1", rules.AGAIN, confused_with="1.2")
    (syn,) = svc.store.synapse_between("g:1.1", "g:1.2")
    assert syn["kind"] == "confusion" and syn["weight"] == pytest.approx(rules.confusion_step(0.0))
    assert r["confusion_partners"][0]["sub_id"] == "1.2"
    before = syn["weight"]
    clock.advance(days=1)
    svc.review("1.1", rules.GOOD)
    clock.advance(minutes=3)
    svc.review("1.2", rules.GOOD)  # both recalled correctly in one sitting: the two are told apart
    rows = {r["kind"]: r for r in svc.store.synapse_between("g:1.1", "g:1.2")}
    assert rows["confusion"]["weight"] < before


def test_curated_synapses_only_for_the_verified_course():
    def two_units(verified):
        c = {"source": "x", "verified": verified, "topics": []}
        for n, sub in ((11, "Yapı"), (13, "Yapı")):
            c["topics"].append({"id": n, "title": f"U{n}", "page": 1, "subtopics": [{"id": f"{n}.1", "title": sub}]})
        return c

    s = Store(":memory:")
    assert seed_course(s, two_units(False))["synapses_new"] == 0
    s2 = Store(":memory:")
    seed_course(s2, two_units(True))
    (syn,) = s2.synapses()
    assert syn["kind"] == "confusion" and {syn["a"], syn["b"]} == {"g:11.1", "g:13.1"}


def test_seeding_again_keeps_what_was_learned(brain):
    svc, clock, _ = brain
    svc.review("1.1", rules.GOOD)
    svc.seed(course())
    assert svc.snapshot()["neurons"]["1.1"]["retrievals"] == 1


def test_consolidation_fades_unused_links_and_prunes_weak_ones(brain):
    svc, clock, _ = brain
    svc.review("1.1", rules.GOOD)
    clock.advance(minutes=2)
    svc.review("1.2", rules.GOOD)
    svc.consolidate()
    clock.advance(days=400)
    rep = svc.consolidate()
    assert rep["pruned"] and not svc.store.synapses()  # a year of disuse: the learned link is gone


def test_the_very_first_consolidation_still_decays_pre_existing_stale_synapses(brain):
    svc, clock, _ = brain
    svc.review("1.1", rules.GOOD)
    clock.advance(minutes=2)
    svc.review("1.2", rules.GOOD)  # wires g:1.1 <-> g:1.2 (hebbian)
    clock.advance(days=400)  # note: consolidate() has never run yet, so "last_consolidation" meta is unset
    rep = svc.consolidate()
    assert rep["pruned"] and not svc.store.synapses()  # must not silently skip the whole backlog on a cold start


def test_consolidation_runs_at_most_once_a_day(brain):
    svc, clock, _ = brain
    assert svc.consolidate_if_stale() is not None
    clock.advance(hours=3)
    assert svc.consolidate_if_stale() is None
    clock.advance(hours=24)
    assert svc.consolidate_if_stale() is not None


# ---- vault ----------------------------------------------------------------------------------------------------

def test_vault_projection_and_the_learners_own_notes_survive(brain):
    svc, clock, root = brain
    svc.review("1.1", rules.GOOD)
    note = next((root / "Beyin" / "Neokorteks").rglob("N01.1 *.md"))
    assert note.name.startswith("N01.1 Indefinite Article")
    text = note.read_text()
    assert "asama: \"kisa_sureli\"" in text and "guc: 60" in text and "## Hatırlama geçmişi" in text
    note.write_text(text.replace(USER_HEAD + "\n\n", USER_HEAD + "\n\nBenim notum: a/an sesli harften önce.\n"))
    clock.advance(days=1)
    svc.review("1.1", rules.GOOD)
    again = note.read_text()
    assert "Benim notum: a/an sesli harften önce." in again and "asama: \"pekisme\"" in again
    assert (root / "Beyin" / "Hipokampus" / "Bugun.md").exists() and (root / "Beyin" / "Sinapslar" / "Sinaps-Agi.md").exists()
    assert (root / "Beyin" / "Neokorteks" / "Gramer" / "01 - Articles" / "K01 Articles.md").exists()


def test_unchanged_notes_are_not_rewritten(brain):
    svc, clock, root = brain
    svc.review("1.1", rules.GOOD)
    note = next((root / "Beyin" / "Neokorteks").rglob("N01.1 *.md"))
    before = note.stat().st_mtime_ns
    svc.vault.sync_all(svc)
    svc.vault.sync_all(svc)
    assert note.stat().st_mtime_ns == before


def test_a_file_the_app_does_not_manage_is_left_alone(brain):
    svc, clock, root = brain
    svc.vault._ensure_cols()
    n = svc.store.neuron("g:1.1")
    path = svc.vault.neuron_path(n, svc.vault._cols[n["col_id"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# my own note, not from ingpro\n")
    svc.review("1.1", rules.GOOD)
    assert path.read_text() == "# my own note, not from ingpro\n"


def test_the_app_never_writes_outside_the_brain_folder(brain):
    svc, clock, root = brain
    with pytest.raises(ValueError):
        svc.vault.write_managed(root / "Mimari" / "x.md", {}, "x", "x", clock())
    with pytest.raises(ValueError):
        svc.vault.write_managed(root / "Beyin" / ".." / "00-Index.md", {}, "x", "x", clock())


def test_note_names_are_obsidian_safe():
    assert safe_name("Both / Either / Neither: Each? #1 [x]") == "Both - Either - Neither - Each - 1 - x"
    assert "/" not in safe_name("a/b") and len(safe_name("x" * 300)) <= 90


def test_short_titles_carry_their_unit_in_the_name(brain):
    svc, clock, root = brain
    svc.review("1.3", rules.GOOD)  # "Exercises"
    assert any(p.name == "N01.3 Articles · Exercises.md" for p in (root / "Beyin").rglob("*.md"))


# ---- HTTP API -------------------------------------------------------------------------------------------------

def test_brain_endpoints(brain):
    from fastapi.testclient import TestClient

    import ingpro.main as main

    svc, clock, root = brain
    main.brain = svc
    client = TestClient(main.app)  # no lifespan: the speech models are not loaded
    first = client.get("/api/brain/progress").json()
    assert (first["xp"], first["due_count"], first["neurons"]) == (0, 0, {})
    assert first["units"]["1"] == {"points": 0, "required": 30, "band": "A1-A2", "approved": False, "approved_at": None, "correct_uses": 0, "min_correct": 3}
    r = client.post("/api/brain/review", json={"sub_id": "1.1", "rating": 3})
    assert r.status_code == 200 and r.json()["stage"] == "kisa_sureli"
    assert client.get("/api/brain/progress").json()["neurons"]["1.1"]["score"] == 60
    assert client.post("/api/brain/review", json={"sub_id": "1.1", "rating": 9}).status_code == 422
    assert client.post("/api/brain/review", json={"sub_id": "nope", "rating": 3}).status_code == 404
    assert client.post("/api/brain/expose", json={"sub_id": "1.2"}).json()["score"] == 10
    assert client.post("/api/brain/consolidate").status_code == 200
