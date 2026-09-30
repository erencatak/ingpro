from datetime import timedelta

import pytest

from ingpro.brain import usage, vad, word_rules, word_vad
from ingpro.brain.service import BrainService
from ingpro.brain.store import Store
from ingpro.brain.vault import Vault
from ingpro.config import settings

from test_brain import T0, Clock, course


def make(content_dir=None, word_vad_model=None, vault_path=None):
    store = Store(":memory:")
    clock = Clock()
    vault = Vault(vault_path, store) if vault_path else None
    svc = BrainService(store, vault, clock, content_dir=content_dir, word_vad_model=word_vad_model)
    svc.seed(course())
    return svc, store, clock


def judgement(*lemmas, grammar="correct"):
    return usage.Judgement(is_sentence=True, grammar=grammar, words=tuple(usage.Word(l, "A1") for l in lemmas))


def spoken():
    return usage.Speech(spoken=True, lang="en", pron_conf=0.9, weak_share=0.0)


# ---- word_rules (pure) ------------------------------------------------------------------------------------------


def test_word_stage_starts_dormant_then_fast_recognition_after_one_success():
    m = word_rules.Memory()
    assert word_rules.word_stage_of(m, None) == "uyuyan"
    new, out = word_rules.word_review(m, T0, None)
    assert out.stage_before == "uyuyan" and out.stage_after == "hizli_tanima"
    assert word_rules.word_stage_of(new, None) == "hizli_tanima"


def test_word_cannot_become_integrated_without_a_sleep_pass_after_it():
    m, _ = word_rules.word_review(word_rules.Memory(), T0, None)
    # a "consolidation" that happened BEFORE this review does not count: the gate is "since the last touch"
    assert word_rules.word_stage_of(m, T0 - timedelta(hours=1)) == "hizli_tanima"
    # one that happens AFTER does
    assert word_rules.word_stage_of(m, T0 + timedelta(hours=1)) == "entegre"


def test_word_review_never_promotes_within_the_same_call():
    """A correct spoken use always lands in hizli_tanima immediately — entegre can only be read later,
    once a real consolidate() pass has happened after it (see word_stage_of)."""
    m, out = word_rules.word_review(word_rules.Memory(), T0, T0 - timedelta(days=1))
    assert out.stage_after == "hizli_tanima" and not out.promoted


# ---- vad.py (real dataset) --------------------------------------------------------------------------------------


def test_vad_dataset_loads_and_rates_a_clearly_positive_word_above_a_clearly_negative_one():
    table = vad.load_vad(settings.content_dir)
    assert len(table) > 10000  # the full Warriner set, not a stub
    assert "love" in table and "murder" in table
    love_v, murder_v = table["love"][0], table["murder"][0]
    assert love_v > murder_v
    for lemma in ("love", "murder"):
        v, a, d = table[lemma]
        assert 1.0 <= v <= 9.0 and 1.0 <= a <= 9.0 and 1.0 <= d <= 9.0


def test_vad_dataset_missing_for_an_unknown_word():
    table = vad.load_vad(settings.content_dir)
    assert "xyznotarealword" not in table


# ---- BrainService integration -----------------------------------------------------------------------------------


def test_a_word_only_enters_the_brain_after_crossing_the_new_word_threshold():
    svc, store, clock = make()
    for i in range(usage.NEW_WORD_USES - 1):
        svc.record_usage(1, judgement("happy"), spoken(), f"sentence {i} happy")
    assert store.word_neuron("happy") is None  # below threshold: still just a vocab counter
    svc.record_usage(1, judgement("happy"), spoken(), "I feel happy now")
    assert store.word_neuron("happy") is not None  # threshold reached: neuron created


def test_word_neuron_is_enriched_with_vad_and_category_from_the_real_dataset():
    svc, store, clock = make(content_dir=settings.content_dir)
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"sentence {i} happy")
    row = store.word_neuron("happy")
    assert row["vad_source"] == "dataset" and row["valence"] is not None
    assert row["category"] == "feelings"  # from starters.TOPIC_KEYWORDS


def test_word_neuron_without_vad_coverage_degrades_gracefully():
    svc, store, clock = make(content_dir=None)  # no VAD lookup at all
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"sentence {i} happy")
    row = store.word_neuron("happy")
    assert row is not None and row["vad_source"] is None and row["valence"] is None


def test_two_words_in_the_same_category_get_a_semantic_synapse():
    svc, store, clock = make()
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("sad"), spoken(), f"t{i} sad")
    rows = store.word_synapse_between("happy", "sad")
    assert any(r["kind"] == "semantic" for r in rows)  # both tagged "feelings" in starters.TOPIC_KEYWORDS


def test_two_words_used_correctly_in_the_same_sentence_get_a_cooccurrence_synapse():
    svc, store, clock = make()
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    for i in range(usage.NEW_WORD_USES - 1):
        svc.record_usage(1, judgement("tired"), spoken(), f"t{i} tired")
    before = store.word_synapse_between("happy", "tired")
    assert not any(r["kind"] == "cooccurrence" for r in before)
    svc.record_usage(1, judgement("happy", "tired"), spoken(), "I am happy but tired")  # crosses tired's threshold too
    after = store.word_synapse_between("happy", "tired")
    coacts = next(r for r in after if r["kind"] == "cooccurrence")
    assert coacts["weight"] > 0


def test_consolidate_promotes_a_word_to_entegre_after_a_sleep_pass():
    svc, store, clock = make()
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    assert svc.word_summary("happy")["stage"] == "hizli_tanima"
    clock.advance(hours=25)
    svc.consolidate()
    assert svc.word_summary("happy")["stage"] == "entegre"


def test_consolidate_decays_an_unused_cooccurrence_link():
    svc, store, clock = make()
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    for i in range(usage.NEW_WORD_USES - 1):
        svc.record_usage(1, judgement("tired"), spoken(), f"t{i} tired")
    svc.record_usage(1, judgement("happy", "tired"), spoken(), "I am happy but tired")
    before = next(r["weight"] for r in store.word_synapse_between("happy", "tired") if r["kind"] == "cooccurrence")
    clock.advance(days=30)
    svc.consolidate()
    after = next(r["weight"] for r in store.word_synapse_between("happy", "tired") if r["kind"] == "cooccurrence")
    assert after < before


def test_speaking_points_are_unaffected_by_the_word_brain():
    """The word brain is purely additive: it must not change unit points, approval, or the grammar judge's rule."""
    svc, store, clock = make()
    result = svc.record_usage(1, judgement("happy", grammar="correct"), spoken(), "I am happy")
    assert result["rule"] in (1, 2) and result["points"] > 0  # unchanged speaking-points path


# ---- LLM VAD fallback (word_vad.py + BrainService.enrich_word_vad) -----------------------------------------------


def test_troubleshoot_has_no_dataset_coverage():
    """Sanity check the fallback tests actually exercise the fallback path, against the real dataset."""
    assert "troubleshoot" not in vad.load_vad(settings.content_dir)


def test_word_vad_clean_strips_everything_but_letters_and_hyphen_apostrophe():
    assert word_vad.clean("  Troubleshoot!! ") == "troubleshoot"
    assert word_vad.clean("well-known") == "well-known"
    assert word_vad.clean("<script>") == "script"


@pytest.mark.asyncio
async def test_word_vad_fetch_parses_and_range_checks_the_llm_response(monkeypatch):
    from ingpro.agents.provider import TokenUsage

    async def fake_complete_once(system, prompt, model):
        return '{"troubleshoot": {"v": 5.5, "a": 6.0, "d": 7.0}, "junk": {"v": 99, "a": 1, "d": 1}}', TokenUsage(5, 5)

    monkeypatch.setattr(word_vad, "complete_once", fake_complete_once)
    result = await word_vad.fetch(["troubleshoot"], "model")
    assert result == {"troubleshoot": (5.5, 6.0, 7.0)}  # "junk" is out of range (v=99) and must be dropped


def test_a_word_missing_from_the_dataset_is_flagged_for_llm_enrichment():
    svc, store, clock = make(content_dir=settings.content_dir)
    result = None
    for i in range(usage.NEW_WORD_USES):
        result = svc.record_usage(1, judgement("troubleshoot"), spoken(), f"s{i} troubleshoot")
    assert result["words_needing_vad"] == ["troubleshoot"]
    row = store.word_neuron("troubleshoot")
    assert row["vad_source"] is None  # neuron exists already (does not wait on the LLM), just unenriched yet


@pytest.mark.asyncio
async def test_enrich_word_vad_fills_in_the_neuron_and_caches_for_next_time(monkeypatch):
    from ingpro.agents.provider import TokenUsage

    async def fake_complete_once(system, prompt, model):
        return '{"troubleshoot": {"v": 5.5, "a": 6.0, "d": 7.0}}', TokenUsage(5, 5)

    monkeypatch.setattr(word_vad, "complete_once", fake_complete_once)
    svc, store, clock = make(content_dir=settings.content_dir, word_vad_model="fake-model")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("troubleshoot"), spoken(), f"s{i} troubleshoot")
    await svc.enrich_word_vad(["troubleshoot"])
    row = store.word_neuron("troubleshoot")
    assert row["vad_source"] == "llm" and row["valence"] == 5.5
    assert store.vocab_vad(["troubleshoot"])["troubleshoot"] == (5.5, 6.0, 7.0)  # cached for future words too


@pytest.mark.asyncio
async def test_enrich_word_vad_is_a_noop_without_a_configured_model():
    svc, store, clock = make(content_dir=settings.content_dir, word_vad_model=None)
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("troubleshoot"), spoken(), f"s{i} troubleshoot")
    await svc.enrich_word_vad(["troubleshoot"])  # must not raise even though nothing will happen
    assert store.word_neuron("troubleshoot")["vad_source"] is None


# ---- Obsidian projection (vault.py) — its own folder, never mixed with grammar's -------------------------------


def test_a_matured_word_gets_its_own_note_under_neokorteks_kelimeler(tmp_path):
    svc, store, clock = make(vault_path=tmp_path / "vault")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    note = tmp_path / "vault" / "Beyin" / "Neokorteks" / "Kelimeler" / "happy.md"
    assert note.is_file()
    text = note.read_text()
    assert "Hızlı tanıma" in text and "Anlam grubu" in text


def test_word_note_lands_in_kelimeler_not_in_gramer(tmp_path):
    svc, store, clock = make(vault_path=tmp_path / "vault")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    gramer_dir = tmp_path / "vault" / "Beyin" / "Neokorteks" / "Gramer"
    assert not any(p.name == "happy.md" for p in gramer_dir.rglob("*.md"))


def test_word_synapses_land_in_their_own_sinapslar_file(tmp_path):
    svc, store, clock = make(vault_path=tmp_path / "vault")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("sad"), spoken(), f"t{i} sad")
    word_net = tmp_path / "vault" / "Beyin" / "Sinapslar" / "Kelime-Sinaps-Agi.md"
    grammar_net = tmp_path / "vault" / "Beyin" / "Sinapslar" / "Sinaps-Agi.md"
    assert word_net.is_file()
    assert "happy" in word_net.read_text() and "anlam ortaklığı" in word_net.read_text()
    if grammar_net.is_file():
        assert "happy" not in grammar_net.read_text()  # the two synapse networks never mix in the same file


@pytest.mark.asyncio
async def test_llm_enriched_vad_updates_the_word_note(tmp_path, monkeypatch):
    from ingpro.agents.provider import TokenUsage

    async def fake_complete_once(system, prompt, model):
        return '{"troubleshoot": {"v": 5.5, "a": 6.0, "d": 7.0}}', TokenUsage(5, 5)

    monkeypatch.setattr(word_vad, "complete_once", fake_complete_once)
    svc, store, clock = make(content_dir=settings.content_dir, word_vad_model="fake-model", vault_path=tmp_path / "vault")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("troubleshoot"), spoken(), f"s{i} troubleshoot")
    note = tmp_path / "vault" / "Beyin" / "Neokorteks" / "Kelimeler" / "troubleshoot.md"
    assert "Duygu skoru henüz yok" in note.read_text()
    await svc.enrich_word_vad(["troubleshoot"])
    assert "5.5" in note.read_text() and "model tahmini" in note.read_text()


def test_word_network_exposes_neurons_and_synapses_for_the_app_view():
    svc, store, clock = make()
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("sad"), spoken(), f"t{i} sad")
    net = svc.word_network()
    assert {n["id"] for n in net["nodes"]} == {"happy", "sad"}
    assert any(e["kind"] == "semantic" for e in net["edges"])
    assert net["stats"]["neurons"] == 2 and net["stats"]["integrated"] == 0


def test_sync_all_writes_every_word_neuron_too(tmp_path):
    svc, store, clock = make(vault_path=tmp_path / "vault")
    for i in range(usage.NEW_WORD_USES):
        svc.record_usage(1, judgement("happy"), spoken(), f"s{i} happy")
    report = svc.vault.sync_all(svc)
    assert report["words"] == 1
