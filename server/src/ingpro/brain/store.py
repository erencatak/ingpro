"""SQLite storage of the brain (data/ingpro.db). Source of truth; the vault is only a projection of it."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .rules import Memory

SCHEMA = """
CREATE TABLE IF NOT EXISTS col (
    id TEXT PRIMARY KEY, num INTEGER NOT NULL, label TEXT NOT NULL, title TEXT NOT NULL, title_tr TEXT,
    page INTEGER, extra INTEGER NOT NULL DEFAULT 0, ord INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS neuron (
    id TEXT PRIMARY KEY, sub_id TEXT NOT NULL UNIQUE, col_id TEXT NOT NULL REFERENCES col(id), ord INTEGER NOT NULL,
    code TEXT, title TEXT NOT NULL, title_tr TEXT, kind TEXT,
    stage TEXT NOT NULL DEFAULT 'uyuyan', memory TEXT NOT NULL DEFAULT '{}', due_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS synapse (
    a TEXT NOT NULL, b TEXT NOT NULL, kind TEXT NOT NULL, weight REAL NOT NULL,
    co_activations INTEGER NOT NULL DEFAULT 0, reason TEXT, last_activated_at TEXT,
    PRIMARY KEY (a, b, kind)
);
CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, neuron_id TEXT NOT NULL, kind TEXT NOT NULL,
    rating INTEGER, source TEXT, xp INTEGER NOT NULL DEFAULT 0, session TEXT, confused_with TEXT,
    stage_before TEXT, stage_after TEXT
);
CREATE INDEX IF NOT EXISTS event_ts ON event(ts);
CREATE INDEX IF NOT EXISTS event_neuron ON event(neuron_id);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, col_id TEXT NOT NULL, text TEXT NOT NULL, text_key TEXT NOT NULL,
    rule INTEGER NOT NULL, points INTEGER NOT NULL, pron_conf REAL, grammar TEXT, new_words TEXT, feedback TEXT, session TEXT
);
CREATE INDEX IF NOT EXISTS usage_col ON usage(col_id);
CREATE TABLE IF NOT EXISTS vocab (
    lemma TEXT PRIMARY KEY, cefr TEXT, first_used_at TEXT NOT NULL, last_used_at TEXT NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0, seen INTEGER NOT NULL DEFAULT 0,
    vad_valence REAL, vad_arousal REAL, vad_dominance REAL
);
CREATE TABLE IF NOT EXISTS word_neuron (
    lemma TEXT PRIMARY KEY, cefr TEXT, valence REAL, arousal REAL, dominance REAL, vad_source TEXT, category TEXT,
    stage TEXT NOT NULL DEFAULT 'uyuyan', memory TEXT NOT NULL DEFAULT '{}', due_at TEXT, created_at TEXT NOT NULL, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS word_synapse (
    a TEXT NOT NULL, b TEXT NOT NULL, kind TEXT NOT NULL, weight REAL NOT NULL,
    co_activations INTEGER NOT NULL DEFAULT 0, last_activated_at TEXT,
    PRIMARY KEY (a, b, kind)
);
CREATE TABLE IF NOT EXISTS unit_state (col_id TEXT PRIMARY KEY, approved_at TEXT, points_at_approval INTEGER, band TEXT, required INTEGER);
CREATE TABLE IF NOT EXISTS session_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, ended_at TEXT NOT NULL, active_sec REAL NOT NULL, turns INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS session_log_start ON session_log(started_at);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vault_sync (path TEXT PRIMARY KEY, hash TEXT NOT NULL, synced_at TEXT NOT NULL);
"""


def pair(a: str, b: str) -> tuple[str, str]:
    """Synapses are undirected: always stored with the smaller id first."""
    return (a, b) if a <= b else (b, a)


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.commit()

    def close(self) -> None:
        with self.lock:
            self.db.close()

    # ---- columns and neurons ----
    def upsert_column(self, id: str, num: int, label: str, title: str, title_tr: str | None, page: int | None, extra: bool, ord: int) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO col(id,num,label,title,title_tr,page,extra,ord) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET num=excluded.num,label=excluded.label,title=excluded.title,title_tr=excluded.title_tr,"
                "page=excluded.page,extra=excluded.extra,ord=excluded.ord",
                (id, num, label, title, title_tr, page, int(extra), ord),
            )
            self.db.commit()

    def upsert_neuron(self, id: str, sub_id: str, col_id: str, ord: int, code: str | None, title: str, title_tr: str | None, kind: str | None) -> None:
        """Static description only: what the neuron is. Learned state is never touched here."""
        with self.lock:
            self.db.execute(
                "INSERT INTO neuron(id,sub_id,col_id,ord,code,title,title_tr,kind) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET sub_id=excluded.sub_id,col_id=excluded.col_id,ord=excluded.ord,code=excluded.code,"
                "title=excluded.title,title_tr=excluded.title_tr,kind=excluded.kind",
                (id, sub_id, col_id, ord, code, title, title_tr, kind),
            )
            self.db.commit()

    def columns(self) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM col ORDER BY extra, ord").fetchall()

    def neurons(self) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT n.* FROM neuron n JOIN col c ON c.id=n.col_id ORDER BY c.extra, c.ord, n.ord").fetchall()

    def neuron(self, id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.db.execute("SELECT * FROM neuron WHERE id=?", (id,)).fetchone()

    def neuron_by_sub(self, sub_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.db.execute("SELECT * FROM neuron WHERE sub_id=?", (sub_id,)).fetchone()

    @staticmethod
    def memory_of(row: sqlite3.Row) -> Memory:
        d = json.loads(row["memory"] or "{}")
        return Memory(**d) if d else Memory()

    def save_memory(self, id: str, memory: Memory, stage: str, due_at: str | None, now: datetime) -> None:
        with self.lock:
            self.db.execute(
                "UPDATE neuron SET memory=?, stage=?, due_at=?, updated_at=? WHERE id=?",
                (json.dumps(asdict(memory), ensure_ascii=False), stage, due_at, now.isoformat(), id),
            )
            self.db.commit()

    def set_stage(self, id: str, stage: str) -> None:
        with self.lock:
            self.db.execute("UPDATE neuron SET stage=? WHERE id=?", (stage, id))
            self.db.commit()

    # ---- synapses ----
    def synapses(self, neuron_id: str | None = None) -> list[sqlite3.Row]:
        with self.lock:
            if neuron_id is None:
                return self.db.execute("SELECT * FROM synapse ORDER BY weight DESC").fetchall()
            return self.db.execute("SELECT * FROM synapse WHERE a=? OR b=? ORDER BY weight DESC", (neuron_id, neuron_id)).fetchall()

    def synapse_between(self, x: str, y: str) -> list[sqlite3.Row]:
        a, b = pair(x, y)
        with self.lock:
            return self.db.execute("SELECT * FROM synapse WHERE a=? AND b=?", (a, b)).fetchall()

    def add_synapse_if_missing(self, x: str, y: str, kind: str, weight: float, reason: str | None) -> bool:
        a, b = pair(x, y)
        with self.lock:
            cur = self.db.execute("INSERT OR IGNORE INTO synapse(a,b,kind,weight,reason) VALUES(?,?,?,?,?)", (a, b, kind, weight, reason))
            self.db.commit()
            return cur.rowcount > 0

    def set_synapse(self, x: str, y: str, kind: str, weight: float, co_activations: int | None, when: datetime | None, reason: str | None = None) -> None:
        a, b = pair(x, y)
        with self.lock:
            self.db.execute(
                "INSERT INTO synapse(a,b,kind,weight,co_activations,reason,last_activated_at) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(a,b,kind) DO UPDATE SET weight=excluded.weight, "
                "co_activations=COALESCE(?, synapse.co_activations), last_activated_at=COALESCE(?, synapse.last_activated_at)",
                (a, b, kind, weight, co_activations or 0, reason, when.isoformat() if when else None, co_activations, when.isoformat() if when else None),
            )
            self.db.commit()

    def delete_synapse(self, a: str, b: str, kind: str) -> None:
        with self.lock:
            self.db.execute("DELETE FROM synapse WHERE a=? AND b=? AND kind=?", (a, b, kind))
            self.db.commit()

    # ---- events ----
    def add_event(self, ts: datetime, neuron_id: str, kind: str, rating: int | None, source: str, xp: int, session: str | None, confused_with: str | None,
                  stage_before: str | None = None, stage_after: str | None = None) -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO event(ts,neuron_id,kind,rating,source,xp,session,confused_with,stage_before,stage_after) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (ts.isoformat(), neuron_id, kind, rating, source, xp, session, confused_with, stage_before, stage_after),
            )
            self.db.commit()
            return int(cur.lastrowid)

    def recent_retrievals(self, since: datetime, exclude: str) -> list[sqlite3.Row]:
        """Latest successful retrieval per other neuron since `since`, newest first."""
        with self.lock:
            return self.db.execute(
                "SELECT neuron_id, MAX(ts) AS ts, rating FROM event WHERE kind='retrieval' AND rating>=2 AND ts>=? AND neuron_id<>? "
                "GROUP BY neuron_id ORDER BY ts DESC",
                (since.isoformat(), exclude),
            ).fetchall()

    def events_of(self, neuron_id: str, limit: int = 10) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM event WHERE neuron_id=? ORDER BY ts DESC LIMIT ?", (neuron_id, limit)).fetchall()

    def events_between(self, start: datetime, end: datetime) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM event WHERE ts>=? AND ts<? ORDER BY ts", (start.isoformat(), end.isoformat())).fetchall()

    def total_xp(self, xp_per_point: int = 0) -> int:
        with self.lock:
            xp = int(self.db.execute("SELECT COALESCE(SUM(xp),0) FROM event").fetchone()[0])
            pts = int(self.db.execute("SELECT COALESCE(SUM(points),0) FROM usage").fetchone()[0])
            return xp + pts * xp_per_point

    # ---- speaking points (usage) ----
    def add_usage(self, ts: datetime, col_id: str, text: str, text_key: str, rule: int, points: int, pron_conf: float | None,
                  grammar: str | None, new_words: list[str], feedback: str | None, session: str | None) -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO usage(ts,col_id,text,text_key,rule,points,pron_conf,grammar,new_words,feedback,session) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (ts.isoformat(), col_id, text, text_key, rule, points, pron_conf, grammar, json.dumps(new_words, ensure_ascii=False), feedback, session),
            )
            self.db.commit()
            return int(cur.lastrowid)

    def has_usage(self, col_id: str, text_key: str) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM usage WHERE col_id=? AND text_key=? AND rule<4", (col_id, text_key)).fetchone() is not None  # words-only rows never use up a sentence

    def usage_points(self, col_id: str | None = None):
        """Points of one unit, or {col_id: points} for all units."""
        with self.lock:
            if col_id is not None:
                return int(self.db.execute("SELECT COALESCE(SUM(points),0) FROM usage WHERE col_id=?", (col_id,)).fetchone()[0])
            return {r["col_id"]: int(r["p"]) for r in self.db.execute("SELECT col_id, SUM(points) AS p FROM usage GROUP BY col_id")}

    def usage_correct(self, col_id: str) -> int:
        """Sentences that used the target grammar correctly (rules 1 and 2)."""
        with self.lock:
            return int(self.db.execute("SELECT COUNT(*) FROM usage WHERE col_id=? AND rule IN (1,2)", (col_id,)).fetchone()[0])

    def recent_usages(self, col_id: str, limit: int = 10) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM usage WHERE col_id=? ORDER BY ts DESC, id DESC LIMIT ?", (col_id, limit)).fetchall()

    def usages_between(self, start: datetime, end: datetime) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM usage WHERE ts>=? AND ts<? ORDER BY ts, id", (start.isoformat(), end.isoformat())).fetchall()

    # ---- vocabulary ----
    def vocab_uses(self, lemmas: list[str]) -> dict[str, int]:
        if not lemmas:
            return {}
        with self.lock:
            marks = ",".join("?" * len(lemmas))
            return {r["lemma"]: r["uses"] for r in self.db.execute(f"SELECT lemma, uses FROM vocab WHERE lemma IN ({marks})", lemmas)}

    def vocab_cefr(self, lemmas: list[str]) -> dict[str, str]:
        """Cached CEFR of lemmas already classified by a past judgement, keyed by lemma: the judge does not need
        to spend an LLM call re-classifying a word once it has been seen before."""
        if not lemmas:
            return {}
        with self.lock:
            marks = ",".join("?" * len(lemmas))
            return {r["lemma"]: r["cefr"] for r in self.db.execute(f"SELECT lemma, cefr FROM vocab WHERE lemma IN ({marks})", lemmas)}

    def vocab_touch(self, lemma: str, cefr: str, now: datetime, correct_use: bool) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO vocab(lemma,cefr,first_used_at,last_used_at,uses,seen) VALUES(?,?,?,?,?,1) "
                "ON CONFLICT(lemma) DO UPDATE SET cefr=excluded.cefr, last_used_at=excluded.last_used_at, seen=seen+1, uses=uses+?",
                (lemma, cefr, now.isoformat(), now.isoformat(), int(correct_use), int(correct_use)),
            )
            self.db.commit()

    def vocab_all(self) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM vocab ORDER BY first_used_at, lemma").fetchall()

    def vocab_vad(self, lemmas: list[str]) -> dict[str, tuple[float, float, float]]:
        """LLM-derived VAD estimates cached from a past enrichment (vocab_set_vad), keyed by lemma: never
        re-asks the LLM for a word once it has been rated before, same economy as vocab_cefr."""
        if not lemmas:
            return {}
        with self.lock:
            marks = ",".join("?" * len(lemmas))
            rows = self.db.execute(
                f"SELECT lemma, vad_valence, vad_arousal, vad_dominance FROM vocab WHERE lemma IN ({marks}) AND vad_valence IS NOT NULL", lemmas
            )
            return {r["lemma"]: (r["vad_valence"], r["vad_arousal"], r["vad_dominance"]) for r in rows}

    def vocab_set_vad(self, lemma: str, valence: float, arousal: float, dominance: float) -> None:
        with self.lock:
            self.db.execute("UPDATE vocab SET vad_valence=?, vad_arousal=?, vad_dominance=? WHERE lemma=?", (valence, arousal, dominance, lemma))
            self.db.commit()

    # ---- word neurons (vocabulary brain) ----
    def word_neuron(self, lemma: str) -> sqlite3.Row | None:
        with self.lock:
            return self.db.execute("SELECT * FROM word_neuron WHERE lemma=?", (lemma,)).fetchone()

    def word_neurons(self) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM word_neuron ORDER BY created_at").fetchall()

    def word_neurons_in_category(self, category: str, exclude: str) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM word_neuron WHERE category=? AND lemma<>?", (category, exclude)).fetchall()

    def seed_word_neuron(self, lemma: str, cefr: str | None, vad: tuple[float, float, float] | None, vad_source: str | None,
                          category: str | None, now: datetime) -> None:
        """Creates the word's neuron row the first time it crosses the usage threshold. Idempotent: never
        touches learned state (memory/stage) if the word already has one."""
        valence, arousal, dominance = vad if vad else (None, None, None)
        with self.lock:
            self.db.execute(
                "INSERT INTO word_neuron(lemma,cefr,valence,arousal,dominance,vad_source,category,created_at) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(lemma) DO NOTHING",
                (lemma, cefr, valence, arousal, dominance, vad_source, category, now.isoformat()),
            )
            self.db.commit()

    def set_word_neuron_vad(self, lemma: str, valence: float, arousal: float, dominance: float, source: str) -> None:
        with self.lock:
            self.db.execute("UPDATE word_neuron SET valence=?, arousal=?, dominance=?, vad_source=? WHERE lemma=?", (valence, arousal, dominance, source, lemma))
            self.db.commit()

    @staticmethod
    def word_memory_of(row: sqlite3.Row) -> Memory:
        d = json.loads(row["memory"] or "{}")
        return Memory(**d) if d else Memory()

    def save_word_memory(self, lemma: str, memory: Memory, stage: str, due_at: str | None, now: datetime) -> None:
        with self.lock:
            self.db.execute(
                "UPDATE word_neuron SET memory=?, stage=?, due_at=?, updated_at=? WHERE lemma=?",
                (json.dumps(asdict(memory), ensure_ascii=False), stage, due_at, now.isoformat(), lemma),
            )
            self.db.commit()

    def word_synapses(self, lemma: str | None = None) -> list[sqlite3.Row]:
        with self.lock:
            if lemma is None:
                return self.db.execute("SELECT * FROM word_synapse ORDER BY weight DESC").fetchall()
            return self.db.execute("SELECT * FROM word_synapse WHERE a=? OR b=? ORDER BY weight DESC", (lemma, lemma)).fetchall()

    def word_synapse_between(self, x: str, y: str) -> list[sqlite3.Row]:
        a, b = pair(x, y)
        with self.lock:
            return self.db.execute("SELECT * FROM word_synapse WHERE a=? AND b=?", (a, b)).fetchall()

    def set_word_synapse(self, x: str, y: str, kind: str, weight: float, co_activations: int | None, when: datetime | None) -> None:
        a, b = pair(x, y)
        with self.lock:
            self.db.execute(
                "INSERT INTO word_synapse(a,b,kind,weight,co_activations,last_activated_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(a,b,kind) DO UPDATE SET weight=excluded.weight, "
                "co_activations=COALESCE(?, word_synapse.co_activations), last_activated_at=COALESCE(?, word_synapse.last_activated_at)",
                (a, b, kind, weight, co_activations or 0, when.isoformat() if when else None, co_activations, when.isoformat() if when else None),
            )
            self.db.commit()

    def delete_word_synapse(self, a: str, b: str, kind: str) -> None:
        with self.lock:
            self.db.execute("DELETE FROM word_synapse WHERE a=? AND b=? AND kind=?", (a, b, kind))
            self.db.commit()

    # ---- unit approval ----
    def unit_state(self, col_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.db.execute("SELECT * FROM unit_state WHERE col_id=?", (col_id,)).fetchone()

    def approved_units(self) -> dict[str, str]:
        with self.lock:
            return {r["col_id"]: r["approved_at"] for r in self.db.execute("SELECT col_id, approved_at FROM unit_state WHERE approved_at IS NOT NULL")}

    def approve_unit(self, col_id: str, when: datetime, points: int, band: str, required: int) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO unit_state(col_id,approved_at,points_at_approval,band,required) VALUES(?,?,?,?,?) "
                "ON CONFLICT(col_id) DO UPDATE SET approved_at=excluded.approved_at, points_at_approval=excluded.points_at_approval, band=excluded.band, required=excluded.required",
                (col_id, when.isoformat(), points, band, required),
            )
            self.db.commit()

    # ---- practice sessions (time on task) ----
    def log_session(self, started: datetime, ended: datetime, active_sec: float, turns: int) -> None:
        with self.lock:
            self.db.execute("INSERT INTO session_log(started_at,ended_at,active_sec,turns) VALUES(?,?,?,?)", (started.isoformat(), ended.isoformat(), active_sec, turns))
            self.db.commit()

    def sessions_since(self, start: datetime) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM session_log WHERE started_at>=? ORDER BY started_at", (start.isoformat(),)).fetchall()

    def total_session_seconds(self) -> float:
        with self.lock:
            return float(self.db.execute("SELECT COALESCE(SUM(active_sec),0) FROM session_log").fetchone()[0])

    def usage_history(self) -> list[sqlite3.Row]:
        """(ts, col_id, points) of every scored sentence, oldest first: the level curve is rebuilt from it."""
        with self.lock:
            return self.db.execute("SELECT ts, col_id, points FROM usage ORDER BY ts, id").fetchall()

    def xp_events_since(self, start: datetime) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT ts, xp FROM event WHERE ts>=? AND xp<>0", (start.isoformat(),)).fetchall()

    # ---- meta and vault bookkeeping ----
    def meta(self, key: str) -> str | None:
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.lock:
            self.db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
            self.db.commit()

    def vault_hash(self, path: str) -> str | None:
        with self.lock:
            row = self.db.execute("SELECT hash FROM vault_sync WHERE path=?", (path,)).fetchone()
            return row["hash"] if row else None

    def set_vault_hash(self, path: str, hash: str, now: datetime) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO vault_sync(path,hash,synced_at) VALUES(?,?,?) ON CONFLICT(path) DO UPDATE SET hash=excluded.hash,synced_at=excluded.synced_at",
                (path, hash, now.isoformat()),
            )
            self.db.commit()
