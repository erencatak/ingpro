"""The brain's operations: record what the learner did, update neurons and synapses, consolidate, project to the vault."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from . import rules, usage, vad, word_rules, word_vad
from .seeds import seed_course
from .store import Store
from .vault import Vault as _Vault  # naming helpers only
from ..starters import TOPIC_KEYWORDS

log = logging.getLogger("ingpro.brain")
ISTANBUL = ZoneInfo("Europe/Istanbul")


class UnknownNeuron(KeyError):
    pass


class UnknownUnit(KeyError):
    pass


class BrainService:
    def __init__(self, store: Store, vault=None, clock: Callable[[], datetime] = rules.utcnow, content_dir=None, word_vad_model: str | None = None):
        self.store = store
        self.vault = vault  # brain.vault.Vault | None
        self.clock = clock
        self.sched = rules.make_scheduler()
        self.bands: dict[str, str] = {}  # column id -> CEFR band of the unit ("A1-A2" | "B1-B2" | "C1")
        self._vault_lock = threading.RLock()  # concurrent judgements must not write an older note over a newer one
        self.content_dir = content_dir  # for the word brain's VAD lookup (vad.py); None disables it gracefully
        self.word_vad_model = word_vad_model  # LLM fallback for words vad.py has no rating for; None disables it

    # ---- setup ----
    def seed(self, course: dict) -> dict:
        source = course.get("source", "")
        known = self.store.meta("course_source")
        if known and known != source:
            log.warning("The course changed (%r -> %r); neurons of both are kept", known, source)
        self.store.set_meta("course_source", source)
        result = seed_course(self.store, course)
        self.bands = {f"c:{t.get('label') or format(t['id'], '02d')}": t["band"] for t in course.get("topics", []) if t.get("band") in usage.REQUIRED}
        if course.get("verified") and len(self.bands) < len(course.get("topics", [])):
            log.warning("Some units have no CEFR band (content/grammar/levels.json): they default to %s", usage.DEFAULT_BAND)
        self.approve_pending()  # a lowered requirement approves the units that already reached it
        return result

    def approve_pending(self) -> list[str]:
        """Approval is evaluated when a sentence is scored; this also catches changes of a unit's band or requirement."""
        done = []
        with self.store.lock:
            now = self.clock()
            for c in self.store.columns():
                if c["extra"]:
                    continue
                info = self.unit_info(c["id"])
                if not info["approved"] and usage.is_approved(info["points"], info["required"], info["correct_uses"]):
                    self.store.approve_unit(c["id"], now, info["points"], info["band"], info["required"])
                    done.append(c["id"])
        return done

    # ---- views ----
    def view(self, row, now: datetime) -> dict:
        mem = self.store.memory_of(row)
        due = rules.due_at(mem)
        return {
            "id": row["id"], "sub_id": row["sub_id"], "col_id": row["col_id"], "code": row["code"], "title": row["title"], "title_tr": row["title_tr"],
            "kind": row["kind"], "stage": rules.stage_of(mem), "score": rules.score_of(mem, now, self.sched),
            "stability": round(rules.stability(mem), 2), "retrievability": round(rules.retrievability(mem, now, self.sched), 3),
            "retrievals": mem.retrievals, "exposures": mem.exposures, "successes": mem.successes,
            "due_at": due.isoformat() if due else None, "due": bool(due and due <= now), "last_event_at": mem.last_event_at,
        }

    def snapshot(self) -> dict:
        now = self.clock()
        self.consolidate_if_stale()
        neurons = {}
        due = 0
        for row in self.store.neurons():
            v = self.view(row, now)
            if v["stage"] == "uyuyan":
                continue
            neurons[v["sub_id"]] = {
                "score": v["score"], "stage": v["stage"], "attempts": v["retrievals"] + v["exposures"], "retrievals": v["retrievals"],
                "stability": v["stability"], "due_at": v["due_at"], "due": v["due"],
            }
            due += v["due"]
        return {"xp": self.store.total_xp(usage.XP_PER_POINT), "due_count": due, "neurons": neurons, "units": self.unit_progress(), "vocab_level": self.vocab_ceiling()}

    def unit_progress(self) -> dict[str, dict]:
        """Speaking points and approval of every one of the 46 units, keyed by the unit number."""
        points = self.store.usage_points()
        approved = self.store.approved_units()
        correct = {c["id"]: self.store.usage_correct(c["id"]) for c in self.store.columns() if not c["extra"]}
        out = {}
        for c in self.store.columns():
            if c["extra"]:
                continue
            band = self.bands.get(c["id"], usage.DEFAULT_BAND)
            out[str(c["num"])] = {
                "points": points.get(c["id"], 0), "required": usage.band_required(band), "band": band,
                "approved": c["id"] in approved, "approved_at": approved.get(c["id"]),
                "correct_uses": correct.get(c["id"], 0), "min_correct": usage.MIN_CORRECT_SENTENCES,
            }
        return out

    def vocab_ceiling(self) -> str:
        """Word level that currently counts as "new": opens up as units get approved."""
        return usage.vocab_ceiling(len(self.store.approved_units()))

    def unit_info(self, col_id: str) -> dict:
        band = self.bands.get(col_id, usage.DEFAULT_BAND)
        state = self.store.unit_state(col_id)
        return {"points": self.store.usage_points(col_id), "required": usage.band_required(band), "band": band,
                "approved": bool(state and state["approved_at"]), "approved_at": state["approved_at"] if state else None,
                "correct_uses": self.store.usage_correct(col_id), "min_correct": usage.MIN_CORRECT_SENTENCES,
                "vocab_level": self.vocab_ceiling()}

    # ---- events ----
    def review(self, sub_id: str, rating: int, source: str = "self_test", session: str | None = None, confused_with: str | None = None) -> dict:
        """A retrieval attempt (testing effect): the learner tried to recall the subtopic and rated how it went."""
        if rating not in rules.ACTIVATION:
            raise ValueError("rating must be 1-4")
        with self.store.lock:
            row = self.store.neuron_by_sub(sub_id)
            if row is None:
                raise UnknownNeuron(sub_id)
            now = self.clock()
            new, out = rules.review(self.store.memory_of(row), rating, now, self.sched)
            self.store.save_memory(row["id"], new, out.stage_after, out.due_at, now)
            conf = self.store.neuron_by_sub(confused_with) if confused_with else None
            self.store.add_event(now, row["id"], "retrieval", rating, source, out.xp, session, conf["id"] if conf else None, out.stage_before, out.stage_after)
            touched = {row["id"]} | self._co_activate(row["id"], new, rating, now)
            if rating == rules.AGAIN and conf is not None and conf["id"] != row["id"]:
                self._strengthen_confusion(row["id"], conf["id"], now)
                touched.add(conf["id"])
            partners = self._confusion_partners(row["id"]) if rating <= rules.HARD else []
            result = {
                "sub_id": sub_id, "score": rules.score_of(new, now, self.sched), "stage": out.stage_after, "stage_label": rules.STAGE_LABEL[out.stage_after],
                "promoted": out.promoted, "interval_days": round(out.interval_days, 1), "due_at": out.due_at, "xp": out.xp,
                "confusion_partners": partners,
            }
        self._project(touched, now)
        return result

    def expose(self, sub_id: str, source: str = "self_test", session: str | None = None) -> dict:
        """Re-reading without trying to recall: a small, capped effect."""
        with self.store.lock:
            row = self.store.neuron_by_sub(sub_id)
            if row is None:
                raise UnknownNeuron(sub_id)
            now = self.clock()
            new, out = rules.expose(self.store.memory_of(row), now)
            self.store.save_memory(row["id"], new, out.stage_after, out.due_at or None, now)
            self.store.add_event(now, row["id"], "exposure", None, source, out.xp, session, None, out.stage_before, out.stage_after)
            result = {"sub_id": sub_id, "score": rules.score_of(new, now, self.sched), "stage": out.stage_after, "stage_label": rules.STAGE_LABEL[out.stage_after], "xp": out.xp}
        self._project({row["id"]}, now)
        return result

    def unit_summary(self, unit: int) -> dict:
        col = next((c for c in self.store.columns() if c["num"] == unit and not c["extra"]), None)
        if col is None:
            raise UnknownUnit(unit)
        info = self.unit_info(col["id"])
        return {"unit": unit, **info, "unit_points": info["points"]}

    # ---- speaking points ----
    def record_usage(self, unit: int, judgement: usage.Judgement, speech: usage.Speech, text: str, session: str | None = None) -> dict:
        """Scores one spoken sentence about a unit with the four rules, updates vocabulary and approves the unit at its threshold."""
        with self.store.lock:
            col = next((c for c in self.store.columns() if c["num"] == unit and not c["extra"]), None)
            if col is None:
                raise UnknownUnit(unit)
            now = self.clock()
            key = usage.normalize(text)
            lemmas = [w.lemma for w in judgement.words if w.lemma]
            if not key:  # nothing but symbols: there is no sentence to score
                scored = usage.Scored(False, None, 0, "Cümle anlaşılamadı.")
            else:
                scored = usage.score(judgement, speech, self.store.vocab_uses(lemmas), duplicate=self.store.has_usage(col["id"], key), ceiling=self.vocab_ceiling())
            info = self.unit_info(col["id"])
            result = {
                "unit": unit, "valid": scored.valid, "rule": scored.rule, "points": scored.points, "reason": scored.reason,
                "new_words": scored.new_words, "feedback_tr": judgement.feedback_tr, "correction": judgement.correction,
                "unit_points": info["points"], "required": info["required"], "band": info["band"],
                "correct_uses": info["correct_uses"], "min_correct": info["min_correct"], "vocab_level": info["vocab_level"],
                "approved": info["approved"], "newly_approved": False, "spoken": speech.spoken,
            }
            if not scored.valid:
                return result
            self.store.add_usage(now, col["id"], text, key, scored.rule, scored.points, speech.pron_conf, judgement.grammar,
                                 scored.new_words, judgement.feedback_tr, session)
            for w in judgement.words:
                if w.lemma:
                    self.store.vocab_touch(w.lemma, w.cefr, now, correct_use=w.lemma in scored.used_words)
            touched_words, result["words_needing_vad"] = self._touch_word_brain(scored.used_words, now)
            info = self.unit_info(col["id"])
            if not info["approved"] and usage.is_approved(info["points"], info["required"], info["correct_uses"]):
                self.store.approve_unit(col["id"], now, info["points"], info["band"], info["required"])
                info = self.unit_info(col["id"])
                result["newly_approved"] = True
            result.update({"unit_points": info["points"], "correct_uses": info["correct_uses"], "approved": info["approved"]})
        self._project_unit(col["id"], now)
        self._project_words(set(touched_words), now)
        return result

    def _project_unit(self, col_id: str, now: datetime) -> None:
        if not self.vault:
            return
        try:
            with self._vault_lock:
                self.vault.sync_unit(col_id, self, now)
        except Exception:
            log.exception("Vault projection failed")

    # ---- synapses ----
    def _co_activate(self, nid: str, mem: rules.Memory, rating: int, now: datetime) -> set[str]:
        """Hebbian learning: neurons recalled in the same sitting get linked; a curated link grows, a new one is created."""
        act = rules.ACTIVATION[rating]
        if act <= 0:
            return set()
        touched: set[str] = set()
        for p in self.store.recent_retrievals(now - rules.CO_ACTIVATION_WINDOW, nid)[: rules.MAX_PARTNERS]:
            prow = self.store.neuron(p["neuron_id"])
            if prow is None:
                continue
            pmem = self.store.memory_of(prow)
            act_p = rules.ACTIVATION[p["rating"]]
            existing = {r["kind"]: r for r in self.store.synapse_between(nid, prow["id"])}
            if "confusion" in existing:  # recalled together and both right: the two are being told apart
                r = existing["confusion"]
                self.store.set_synapse(nid, prow["id"], "confusion", rules.confusion_relief(r["weight"]), r["co_activations"] + 1, now)
            target = existing.get("structural") or existing.get("hebbian")
            base = target["weight"] if target else 0.0
            kind = target["kind"] if target else "hebbian"
            w = rules.hebbian_step(base, act, act_p, rules.plasticity(mem), rules.plasticity(pmem))
            co = (target["co_activations"] if target else 0) + 1
            self.store.set_synapse(nid, prow["id"], kind, w, co, now, None if target else "Aynı oturumda birlikte hatırlandı")
            touched.add(prow["id"])
        return touched

    def _strengthen_confusion(self, a: str, b: str, now: datetime) -> None:
        rows = {r["kind"]: r for r in self.store.synapse_between(a, b)}
        r = rows.get("confusion")
        w = rules.confusion_step(r["weight"] if r else 0.0)
        self.store.set_synapse(a, b, "confusion", w, (r["co_activations"] if r else 0) + 1, now, None if r else "Hatırlama testinde karıştırıldı")

    def _confusion_partners(self, nid: str) -> list[dict]:
        out = []
        for r in self.store.synapses(nid):
            if r["kind"] != "confusion":
                continue
            other = self.store.neuron(r["b"] if r["a"] == nid else r["a"])
            if other:
                col = next(c for c in self.store.columns() if c["id"] == other["col_id"])
                out.append({"sub_id": other["sub_id"], "title": _Vault.shown_title(other, col), "weight": round(r["weight"], 2), "reason": r["reason"]})
        return out[:3]

    # ---- word brain (vocabulary) ----
    # Separate from the grammar neuron/synapse tables on purpose: a word has no "unit" to belong to, and its
    # memory model is deliberately simpler (2 stages, not 5 — see word_rules.py's module docstring for why).
    def _touch_word_brain(self, used_words: list[str], now: datetime) -> tuple[list[str], list[str]]:
        """A word graduates into its own neuron exactly when it stops being "new" for speaking-points purposes
        (usage.NEW_WORD_USES correct uses) — reusing that existing threshold rather than inventing a second one.
        Returns (touched lemmas, lemmas still needing an LLM VAD estimate — see word_vad.py, fetched by the
        caller in the background, never here: this method must stay fast and lock-friendly, no network calls)."""
        if not used_words:
            return [], []
        counts = self.store.vocab_uses(used_words)
        matured = [w for w in used_words if counts.get(w, 0) >= usage.NEW_WORD_USES]
        touched: set[str] = set(matured)
        needs_vad = []
        for lemma in matured:
            row = self.store.word_neuron(lemma)
            if row is None:
                needs, partners = self._seed_word_neuron(lemma, now)
                if needs:
                    needs_vad.append(lemma)
                touched.update(partners)
            elif row["vad_source"] is None:
                needs_vad.append(lemma)  # a past enrichment attempt may have failed or never run: retry
            self._review_word(lemma, now)
        self._co_activate_words(matured, now)  # only links words already in `matured` — nothing new to add to `touched`
        return list(touched), needs_vad

    def _seed_word_neuron(self, lemma: str, now: datetime) -> tuple[bool, list[str]]:
        """Returns (needs an LLM VAD estimate?, other lemmas newly linked to it — their own notes also changed)."""
        vad_table = vad.load_vad(self.content_dir) if self.content_dir else {}
        vad_scores = vad_table.get(lemma)
        source = "dataset" if vad_scores else None
        if vad_scores is None:
            cached = self.store.vocab_vad([lemma]).get(lemma)
            if cached:
                vad_scores, source = cached, "llm"
        category = TOPIC_KEYWORDS.get(lemma)
        cefr = self.store.vocab_cefr([lemma]).get(lemma)
        self.store.seed_word_neuron(lemma, cefr, vad_scores, source, category, now)
        partners = []
        if category:
            for other in self.store.word_neurons_in_category(category, exclude=lemma):
                self.store.set_word_synapse(lemma, other["lemma"], "semantic", word_rules.WORD_INITIAL_WEIGHT["semantic"], 0, None)
                partners.append(other["lemma"])
        return vad_scores is None, partners

    async def enrich_word_vad(self, lemmas: list[str]) -> None:
        """Background LLM fallback for words vad.py has no rating for — call after record_usage returns,
        never while holding store.lock (a network call must not block every other request on the DB)."""
        if not lemmas or not self.word_vad_model:
            return
        try:
            scores = await word_vad.fetch(lemmas, self.word_vad_model)
        except Exception:
            log.exception("Word VAD enrichment failed")
            return
        if scores:
            await asyncio.to_thread(self._save_word_vad, scores)

    def _save_word_vad(self, scores: dict[str, tuple[float, float, float]]) -> None:
        touched = set()
        with self.store.lock:
            for lemma, (v, a, d) in scores.items():
                self.store.vocab_set_vad(lemma, v, a, d)
                if self.store.word_neuron(lemma) is not None:
                    self.store.set_word_neuron_vad(lemma, v, a, d, "llm")
                    touched.add(lemma)
        self._project_words(touched, self.clock())

    def _project_words(self, lemmas: set[str], now: datetime) -> None:
        if not self.vault or not lemmas:
            return
        try:
            with self._vault_lock:
                self.vault.sync_word_touched(lemmas, self, now)
        except Exception:  # the vault is a view: never fail a learning event because of it
            log.exception("Word vault projection failed")

    def _review_word(self, lemma: str, now: datetime) -> None:
        row = self.store.word_neuron(lemma)
        if row is None:
            return
        last = self.store.meta("last_consolidation")
        new, out = word_rules.word_review(self.store.word_memory_of(row), now, datetime.fromisoformat(last) if last else None, self.sched)
        self.store.save_word_memory(lemma, new, out.stage_after, out.due_at, now)

    def _co_activate_words(self, lemmas: list[str], now: datetime) -> None:
        """Words correctly used together in the same sentence get a stronger link — same Hebbian mechanism as
        grammar's synapses, but the window is one sentence, not a 30-minute session (a tighter, cleaner signal)."""
        uniq = list(dict.fromkeys(lemmas))  # de-dupe, keep order: a repeated word must not link to itself
        for i, a in enumerate(uniq):
            for b in uniq[i + 1 :]:
                existing = self.store.word_synapse_between(a, b)
                row = next((r for r in existing if r["kind"] == "cooccurrence"), None)
                base = row["weight"] if row else word_rules.WORD_INITIAL_WEIGHT["cooccurrence"]
                w = rules.hebbian_step(base, 1.0, 1.0, 1.0, 1.0)  # every retrieval here is rated GOOD: activation is always 1.0
                self.store.set_word_synapse(a, b, "cooccurrence", w, (row["co_activations"] if row else 0) + 1, now)

    def word_network(self) -> dict:
        """The whole vocabulary brain as a graph for the app's neural view: neurons (words) and synapses."""
        last = self.store.meta("last_consolidation")
        last_dt = datetime.fromisoformat(last) if last else None
        nodes = []
        for row in self.store.word_neurons():
            mem = self.store.word_memory_of(row)
            stage = word_rules.word_stage_of(mem, last_dt)
            nodes.append({
                "id": row["lemma"], "cefr": row["cefr"], "category": row["category"], "stage": stage,
                "valence": row["valence"], "arousal": row["arousal"], "dominance": row["dominance"], "vad_source": row["vad_source"],
                "retrievals": mem.retrievals, "successes": mem.successes, "stability": round(rules.stability(mem), 2),
                "last_event_at": mem.last_event_at,
            })
        edges = [{"a": r["a"], "b": r["b"], "kind": r["kind"], "weight": round(r["weight"], 3), "co": r["co_activations"]} for r in self.store.word_synapses()]
        return {
            "nodes": nodes, "edges": edges,
            "stats": {
                "neurons": len(nodes), "synapses": len(edges),
                "integrated": sum(n["stage"] == "entegre" for n in nodes),
                "last_consolidation": last,
            },
        }

    def word_summary(self, lemma: str) -> dict | None:
        row = self.store.word_neuron(lemma)
        if row is None:
            return None
        mem = self.store.word_memory_of(row)
        last = self.store.meta("last_consolidation")
        stage = word_rules.word_stage_of(mem, datetime.fromisoformat(last) if last else None)
        return {
            "lemma": lemma, "cefr": row["cefr"], "category": row["category"],
            "valence": row["valence"], "arousal": row["arousal"], "dominance": row["dominance"], "vad_source": row["vad_source"],
            "stage": stage, "stage_label": word_rules.WORD_STAGE_LABEL[stage],
            "retrievals": mem.retrievals, "successes": mem.successes, "stability": round(rules.stability(mem), 2),
        }

    # ---- consolidation ("sleep") ----
    def consolidate_if_stale(self, max_age_hours: float = 20) -> dict | None:
        last = self.store.meta("last_consolidation")
        if last and self.clock() - datetime.fromisoformat(last) < timedelta(hours=max_age_hours):
            return None
        return self.consolidate()

    def consolidate(self) -> dict:
        """What sleep does for memory, in three steps: review the day, let unused links fade, plan the replay (next tests)."""
        with self.store.lock:
            now = self.clock()
            last = self.store.meta("last_consolidation")
            # No prior run: nothing has decayed yet, so the anchor must not be "now" (that would read every
            # synapse as freshly touched and silently skip its whole backlog of disuse on this first pass).
            prev = datetime.fromisoformat(last) if last else datetime.fromtimestamp(0, tz=timezone.utc)
            decayed = 0
            pruned: list[tuple[str, str]] = []
            for r in self.store.synapses():
                anchor = max(prev, datetime.fromisoformat(r["last_activated_at"])) if r["last_activated_at"] else None
                if anchor is None:
                    continue  # curated links that were never used keep their initial weight
                days = (now - anchor).total_seconds() / 86400
                if days <= 0.01:
                    continue
                w = rules.decay_weight(r["weight"], r["kind"], days)
                if rules.should_prune(w, r["kind"]):
                    self.store.delete_synapse(r["a"], r["b"], r["kind"])
                    pruned.append((r["a"], r["b"]))
                elif abs(w - r["weight"]) > 1e-6:
                    self.store.set_synapse(r["a"], r["b"], r["kind"], w, None, None)
                    decayed += 1
            word_decayed = word_pruned = 0
            for r in self.store.word_synapses():
                anchor = max(prev, datetime.fromisoformat(r["last_activated_at"])) if r["last_activated_at"] else None
                if anchor is None:
                    continue
                days = (now - anchor).total_seconds() / 86400
                if days <= 0.01:
                    continue
                w = word_rules.word_decay_weight(r["weight"], r["kind"], days)
                if word_rules.word_should_prune(w, r["kind"]):
                    self.store.delete_word_synapse(r["a"], r["b"], r["kind"])
                    word_pruned += 1
                elif abs(w - r["weight"]) > 1e-6:
                    self.store.set_word_synapse(r["a"], r["b"], r["kind"], w, None, None)
                    word_decayed += 1
            views = [self.view(row, now) for row in self.store.neurons()]
            day_start = now.astimezone(ISTANBUL).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            events = self.store.events_between(day_start, day_start + timedelta(days=1))
            promoted = [e for e in events if e["stage_before"] and e["stage_after"] and e["stage_before"] != e["stage_after"] and rules.STAGES.index(e["stage_after"]) > rules.STAGES.index(e["stage_before"])]
            active = [v for v in views if v["stage"] != "uyuyan" and v["retrievals"] > 0]
            at_risk = sorted((v for v in active if v["retrievability"] < 0.8), key=lambda v: v["retrievability"])[:15]
            due = sorted((v for v in active if v["due"]), key=lambda v: v["due_at"])
            self.store.set_meta("last_consolidation", now.isoformat())
            report = {
                "at": now.isoformat(), "decayed": decayed, "pruned": pruned, "at_risk": at_risk, "due": due, "promoted_events": [dict(e) for e in promoted],
                "active": len(active), "word_decayed": word_decayed, "word_pruned": word_pruned,
            }
        if self.vault:
            with self._vault_lock:
                self.vault.write_sleep_report(report, self)
            self._project(set(), now)
        return report

    # ---- vault ----
    def sync_vault(self) -> dict | None:
        if not self.vault:
            return None
        with self._vault_lock:
            return self.vault.sync_all(self)

    def _project(self, neuron_ids: set[str], now: datetime) -> None:
        if not self.vault:
            return
        try:
            with self._vault_lock:
                self.vault.sync_touched(neuron_ids, self, now)
        except Exception:  # the vault is a view: never fail a learning event because of it
            log.exception("Vault projection failed")
