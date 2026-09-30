"""One-way projection of the brain into the Obsidian vault: DB -> Markdown (ADR-008, ADR-011).

Layout, all under <vault_dir>/Beyin/ (vault_dir is the "İngilizce" project folder; nothing outside it is ever written):
  Neokorteks/Gramer/<kolon>/    one note per neuron (subtopic) and one per column (unit)   long-term knowledge
  Neokorteks/Kelimeler/         Kelime-Listesi.md (all vocab, simple tracker) + one note per word-neuron
  Hipokampus/                   Bugun.md, Tekrar-Kuyrugu.md, Uyku/<date>.md               today, replay queue, sleep reports
  Sinapslar/                    Sinaps-Agi.md, Karisiklik-Haritasi.md                     strongest grammar links, confusion map
                                 Kelime-Sinaps-Agi.md                                      strongest word links — its own network, never mixed with grammar's
Hand-written notes (00-Beyin-Haritasi.md, Kavramlar/) are never touched. Every generated note keeps its "## Notlarım"
section: text the learner writes there survives every refresh.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import rules, usage, word_rules
from .store import Store

log = logging.getLogger("ingpro.brain")
TZ = ZoneInfo("Europe/Istanbul")
START, END = "<!-- ingpro:start -->", "<!-- ingpro:end -->"
USER_HEAD = "## Notlarım"
KIND_LABEL = {"structural": "yapısal", "confusion": "karışıklık", "hebbian": "Hebb (birlikte hatırlandı)"}
WORD_KIND_LABEL = {"semantic": "anlam ortaklığı", "cooccurrence": "birlikte kullanma (Hebb)"}
EVENT_LABEL = {"retrieval": "Hatırlama testi", "exposure": "Okuma (test etmeden)"}
BOOK = "Ebru Yener, *Systematic English Grammar*"


def safe_name(s: str) -> str:
    """A string that is safe as an Obsidian note / folder name."""
    s = re.sub(r'[\\/:*?"<>|#^\[\]]+', " - ", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?:\s*-\s*){2,}", " - ", s).strip(" .-")
    return s[:90].rstrip(" .-")


def yaml_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]"
    return json.dumps(str(v), ensure_ascii=False)


def cell(text: str) -> str:
    """Spoken text goes into a table: it must not be able to break the table or the generated block."""
    return re.sub(r"[|#<>\[\]\n\r]+", " ", text).strip()[:200]


def local(iso: str | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    return datetime.fromisoformat(iso).astimezone(TZ).strftime(fmt) if iso else "—"


class Vault:
    def __init__(self, root: Path | str, store: Store):
        self.base = (Path(root) / "Beyin").resolve()
        self.store = store

    # ---- naming ----
    def col_label(self, col) -> str:
        return col["label"]

    @staticmethod
    def shown_title(n, col) -> str:
        """Short titles ("Yapı", "Must", "Exercises") say nothing without their unit: prefix them with it."""
        return f"{col['title']} · {n['title']}" if len(n["title"]) <= 14 else n["title"]

    def neuron_name(self, n, col) -> str:
        return safe_name(f"N{col['label']}.{n['ord']} {self.shown_title(n, col)}")

    def col_name(self, col) -> str:
        return safe_name(f"K{col['label']} {col['title']}")

    def col_dir(self, col) -> Path:
        return self.base / "Neokorteks" / "Gramer" / safe_name(f"{col['label']} - {col['title']}")

    def neuron_path(self, n, col) -> Path:
        return self.col_dir(col) / f"{self.neuron_name(n, col)}.md"

    def col_path(self, col) -> Path:
        return self.col_dir(col) / f"{self.col_name(col)}.md"

    def link(self, n, col) -> str:
        label = f"{n['code'] or col['label'] + '.' + str(n['ord'])} {self.shown_title(n, col)}"
        return f"[[{self.neuron_name(n, col)}|{label.replace('|', '/')}]]"

    # ---- word naming: a separate namespace from grammar's neurons, never mixed ----
    def word_dir(self) -> Path:
        return self.base / "Neokorteks" / "Kelimeler"

    def word_path(self, lemma: str) -> Path:
        return self.word_dir() / f"{safe_name(lemma)}.md"

    def word_link(self, lemma: str) -> str:
        return f"[[{safe_name(lemma)}|{lemma}]]"

    # ---- writing ----
    def _inside(self, path: Path) -> Path:
        resolved = path.resolve()
        if self.base != resolved and self.base not in resolved.parents:
            raise ValueError(f"refusing to write outside the brain folder: {path}")
        return resolved

    def write_managed(self, path: Path, frontmatter: dict, title: str, block: str, now: datetime) -> bool:
        """Writes a generated note. Returns True when the file changed. Keeps the learner's own notes."""
        path = self._inside(path)
        rel = str(path.relative_to(self.base))
        fm = "---\n" + "".join(f"{k}: {yaml_value(v)}\n" for k, v in frontmatter.items()) + "---\n"
        generated = f"{fm}\n# {title}\n\n{START}\n{block.strip()}\n{END}\n"
        digest = hashlib.sha256(generated.encode()).hexdigest()
        existing = path.read_text() if path.exists() else None
        if existing is not None and START not in existing:
            log.warning("Skipping %s: it exists and is not managed by ingpro", rel)
            return False
        if existing is not None and self.store.vault_hash(rel) == digest:
            return False
        user = "\n\n"
        if existing and USER_HEAD in existing:
            user = existing.split(USER_HEAD, 1)[1]
        content = f"{generated}\n{USER_HEAD}{user}"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".ingpro-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.replace(tmp, path)  # atomic: Obsidian never sees half a file
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        self.store.set_vault_hash(rel, digest, now)
        return True

    # ---- neuron and column notes ----
    def _neighbors(self, nid: str) -> list[dict]:
        out = []
        for r in self.store.synapses(nid):
            other = self.store.neuron(r["b"] if r["a"] == nid else r["a"])
            if other is None:
                continue
            col = self._cols[other["col_id"]]
            out.append({"row": r, "other": other, "col": col})
        return out

    def sync_neuron(self, nid: str, service, now: datetime) -> bool:
        row = self.store.neuron(nid)
        col = self._cols[row["col_id"]]
        v = service.view(row, now)
        neighbors = self._neighbors(nid)
        syn_lines = ["| Komşu nöron | Tür | Ağırlık | Neden |", "|---|---|---|---|"]
        for nb in neighbors[:12]:
            r = nb["row"]
            syn_lines.append(f"| {self.link(nb['other'], nb['col'])} | {KIND_LABEL[r['kind']]} | {r['weight']:.2f} | {(r['reason'] or '—').replace('|', '/')} |")
        if not neighbors:
            syn_lines = ["_Henüz sinaps yok. Bu nöron başka nöronlarla birlikte hatırlandıkça bağlar oluşur._"]
        events = self.store.events_of(nid, 10)
        ev_lines = []
        for e in events:
            what = EVENT_LABEL.get(e["kind"], e["kind"])
            grade = f" · {rules.RATING_LABEL[e['rating']]}" if e["rating"] else ""
            ev_lines.append(f"- {local(e['ts'])} · {what}{grade} · +{e['xp']} XP")
        stage_label = rules.STAGE_LABEL[v["stage"]]
        block = "\n".join([
            f"> **Aşama:** {stage_label} · **Güç:** %{v['score']} · **Kararlılık:** {v['stability']} gün · **Sonraki tekrar:** {local(v['due_at'], '%Y-%m-%d')}",
            "",
            "## Kimlik",
            f"- Kaynak: {BOOK}" + (f" · {row['code']}" if row["code"] else "") + (f" · Kitap s. {col['page']}" if col["page"] else ""),
            f"- Kolon: [[{self.col_name(col)}|{col['label']} {col['title']}]]",
            *([f"- Türkçe: {row['title_tr']}"] if row["title_tr"] else []),
            "",
            "## Sinapslar",
            *syn_lines,
            "",
            "## Hatırlama geçmişi",
            *(ev_lines or ["_Henüz yok._"]),
        ])
        fm = {
            "tags": ["noron", "gramer", f"asama/{v['stage'].replace('_', '-')}"], "noron": row["sub_id"], "kolon": col["label"],
            "kaynak_kodu": row["code"] or "", "sayfa": col["page"], "asama": v["stage"], "guc": v["score"], "kararlilik_gun": v["stability"],
            "hatirlama": v["retrievals"], "okuma": v["exposures"], "basari": v["successes"],
            "son_olay": local(v["last_event_at"]) if v["last_event_at"] else "", "sonraki_tekrar": local(v["due_at"], "%Y-%m-%d") if v["due_at"] else "",
        }
        title = f"{row['code'] or col['label'] + '.' + str(row['ord'])} {self.shown_title(row, col)}" + (f" · {row['title_tr']}" if row["title_tr"] else "")
        return self.write_managed(self.neuron_path(row, col), fm, title, block, now)

    def sync_column(self, col_id: str, service, now: datetime) -> bool:
        col = self._cols[col_id]
        rows = [n for n in self.store.neurons() if n["col_id"] == col_id]
        views = [service.view(n, now) for n in rows]
        mastery = round(sum(v["score"] for v in views) / len(views)) if views else 0
        lines = ["| Nöron | Aşama | Güç | Sonraki tekrar |", "|---|---|---|---|"]
        for n, v in zip(rows, views):
            lines.append(f"| {self.link(n, col)} | {rules.STAGE_LABEL[v['stage']]} | %{v['score']} | {local(v['due_at'], '%Y-%m-%d')} |")
        cross = []
        for n in rows:
            for nb in self._neighbors(n["id"]):
                if nb["other"]["col_id"] != col_id and nb["row"]["weight"] >= 0.2:
                    cross.append(f"- {self.link(n, col)} ↔ {self.link(nb['other'], nb['col'])} · {KIND_LABEL[nb['row']['kind']]} · {nb['row']['weight']:.2f}" + (f" · {nb['row']['reason']}" if nb["row"]["reason"] else ""))
        fm = {"tags": ["kolon", "gramer"], "kolon": col["label"], "sayfa": col["page"], "noron_sayisi": len(rows), "hakimiyet": mastery}
        head = f"> **Hakimiyet (bellek):** %{mastery} · **{len(rows)} nöron**"
        speaking: list[str] = []
        if not col["extra"]:
            info = service.unit_info(col_id)
            need = max(0, info["min_correct"] - info["correct_uses"])
            state = ("**ONAYLI ✔**" + (f" ({local(info['approved_at'], '%Y-%m-%d')})" if info["approved_at"] else "")) if info["approved"] else (
                f"puan tamam, onay için doğru gramerli {need} cümle daha gerek" if info["points"] >= info["required"] else "onay bekliyor")
            head += f" · **Konuşma puanı:** {info['points']} / {info['required']} ({info['band']}) · {state}"
            fm.update({"seviye": info["band"], "puan": info["points"], "gereken_puan": info["required"], "dogru_cumle": info["correct_uses"], "onayli": info["approved"]})
            recent = self.store.recent_usages(col_id, 10)
            speaking = [
                "",
                "## Konuşma puanları",
                f"Onay için {info['required']} puan ve konunun gramerini doğru kullandığın en az {info['min_correct']} cümle gerekir ({info['band']} seviyesi; şu an {info['correct_uses']} doğru cümle). Kurallar: [[03-Konusma-Puanlari]]",
                "",
                *(["| Zaman | Cümle | Kural | Puan |", "|---|---|---|---|"] + [f"| {local(u['ts'])} | {cell(u['text'])} | {u['rule']} | {u['points']} |" for u in recent] if recent else ["_Henüz puanlanmış konuşma yok. Konu sayfasındaki \"Alex'le çalış\" ile başla._"]),
            ]
        block = "\n".join([
            head,
            "",
            "## Nöronlar",
            *lines,
            "",
            "## Kolonlar arası bağlantılar",
            *(cross or ["_Bu kolonun diğer kolonlarla belirgin bir sinapsı yok._"]),
            *speaking,
        ])
        title = f"Kolon {col['label']} · {col['title']}" + (f" · {col['title_tr']}" if col["title_tr"] else "")
        return self.write_managed(self.col_path(col), fm, title, block, now)

    # ---- hippocampus and synapse indexes ----
    def sync_hippocampus(self, service, now: datetime) -> None:
        local_now = now.astimezone(TZ)
        start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        events = self.store.events_between(start, start + timedelta(days=1))
        by_id = {n["id"]: n for n in self.store.neurons()}
        lines = ["| Saat | Nöron | Olay | XP |", "|---|---|---|---|"]
        for e in events:
            n = by_id[e["neuron_id"]]
            what = EVENT_LABEL.get(e["kind"], e["kind"]) + (f" · {rules.RATING_LABEL[e['rating']]}" if e["rating"] else "")
            lines.append(f"| {local(e['ts'], '%H:%M')} | {self.link(n, self._cols[n['col_id']])} | {what} | +{e['xp']} |")
        retr = sum(e["kind"] == "retrieval" for e in events)
        usages = self.store.usages_between(start, start + timedelta(days=1))
        cols = self._cols
        ulines = ["| Saat | Ünite | Cümle | Kural | Puan |", "|---|---|---|---|---|"] + [
            f"| {local(u['ts'], '%H:%M')} | [[{self.col_name(cols[u['col_id']])}|{cols[u['col_id']]['label']}]] | {cell(u['text'])} | {u['rule']} | {u['points']} |" for u in usages
        ]
        xp_total = sum(e["xp"] for e in events) + sum(u["points"] for u in usages) * usage.XP_PER_POINT
        block = "\n".join([
            f"> **{local_now:%Y-%m-%d}** · {retr} hatırlama testi · {len(events) - retr} okuma · {sum(u['points'] for u in usages)} konuşma puanı · {xp_total} XP",
            "",
            "Hipokampus yeni bilgiyi geçici olarak tutar; tekrarlar ve uyku (konsolidasyon) bunu neokortekse taşır. Bugün dokunduğun nöronlar:",
            "",
            *(lines if events else ["_Bugün henüz bir hatırlama testi yapılmadı._"]),
            "",
            "## Konuşma puanları",
            *(ulines if usages else ["_Bugün puanlanmış konuşma yok._"]),
        ])
        self.write_managed(self.base / "Hipokampus" / "Bugun.md", {"tags": ["hipokampus", "gunluk"], "tarih": f"{local_now:%Y-%m-%d}", "hatirlama": retr, "konusma_puani": sum(u["points"] for u in usages), "xp": xp_total}, "Bugün", block, now)

        views = [service.view(n, now) for n in self.store.neurons()]
        queue = sorted((v for v in views if v["retrievals"] > 0 and v["due_at"]), key=lambda v: v["due_at"])
        limit = now + timedelta(days=7)
        now_list = [v for v in queue if v["due"]]
        soon = [v for v in queue if not v["due"] and datetime.fromisoformat(v["due_at"]) <= limit]

        def rows(vs):
            out = ["| Nöron | Güç | Hatırlanma ihtimali | Zamanı |", "|---|---|---|---|"]
            for v in vs:
                n = by_id[v["id"]]
                out.append(f"| {self.link(n, self._cols[n['col_id']])} | %{v['score']} | %{round(v['retrievability'] * 100)} | {local(v['due_at'])} |")
            return out

        block = "\n".join([
            f"> **{len(now_list)} nöronun tekrar zamanı geldi** · {len(soon)} tanesi bu hafta",
            "",
            "Tekrar = hatırlama testi: önce kitabı kapat, hatırlamaya çalış, sonra dürüstçe değerlendir. Yalnızca tekrar okumak gücü %30'un üstüne çıkarmaz.",
            "",
            "## Şimdi",
            *(rows(now_list) if now_list else ["_Zamanı gelen nöron yok._"]),
            "",
            "## Bu hafta",
            *(rows(soon) if soon else ["_Bu hafta planlı tekrar yok._"]),
        ])
        self.write_managed(self.base / "Hipokampus" / "Tekrar-Kuyrugu.md", {"tags": ["hipokampus", "tekrar"], "zamani_gelen": len(now_list), "bu_hafta": len(soon)}, "Tekrar kuyruğu", block, now)

    def sync_synapse_indexes(self, now: datetime) -> None:
        all_syn = self.store.synapses()
        by_id = {n["id"]: n for n in self.store.neurons()}

        def line(r):
            a, b = by_id[r["a"]], by_id[r["b"]]
            return f"| {self.link(a, self._cols[a['col_id']])} | {self.link(b, self._cols[b['col_id']])} | {KIND_LABEL[r['kind']]} | {r['weight']:.2f} | {r['co_activations']} | {(r['reason'] or '—').replace('|', '/')} |"

        head = ["| Nöron A | Nöron B | Tür | Ağırlık | Ortak etkinleşme | Neden |", "|---|---|---|---|---|---|"]
        strongest = [r for r in all_syn if r["weight"] >= 0.2][:60]
        block = "\n".join([
            f"> **{len(all_syn)} sinaps** · {sum(r['kind'] == 'hebbian' for r in all_syn)} tanesi senin çalışmandan doğdu (Hebb), {sum(r['kind'] == 'structural' for r in all_syn)} yapısal, {sum(r['kind'] == 'confusion' for r in all_syn)} karışıklık",
            "",
            "Sinaps = iki nöron arasındaki bağ. Birlikte hatırlanan nöronların bağı güçlenir (Hebb), kullanılmayanlar zamanla zayıflar, çok zayıflayan Hebb bağları budanır.",
            "",
            *head, *(line(r) for r in strongest),
        ])
        self.write_managed(self.base / "Sinapslar" / "Sinaps-Agi.md", {"tags": ["sinaps"], "sinaps_sayisi": len(all_syn)}, "Sinaps ağı", block, now)
        conf = [r for r in all_syn if r["kind"] == "confusion"]
        block = "\n".join([
            f"> **{len(conf)} karışıklık bağı.** Ağırlık yüksekse bu iki konu sık karışıyor; ayrım için ikisini aynı oturumda, iç içe test etmek en iyisi (serpiştirme).",
            "",
            *head, *(line(r) for r in conf),
        ])
        self.write_managed(self.base / "Sinapslar" / "Karisiklik-Haritasi.md", {"tags": ["sinaps", "karisiklik"], "baglanti": len(conf)}, "Karışıklık haritası", block, now)

    def sync_words(self, now: datetime, ceiling: str = "A1") -> None:
        words = self.store.vocab_all()

        def status(w) -> str:
            word = usage.Word(w["lemma"], w["cefr"] or "A1")
            if usage.is_new_word(word, w["uses"], ceiling):
                return "yeni"
            return "bilinen" if w["uses"] >= usage.NEW_WORD_USES else "üst seviye (henüz açılmadı)"

        lines = ["| Kelime | Seviye | İlk kullanım | Doğru kullanım | Durum |", "|---|---|---|---|---|"]
        for w in words:
            lines.append(f"| {w['lemma']} | {w['cefr'] or '—'} | {local(w['first_used_at'], '%Y-%m-%d')} | {w['uses']} | {status(w)} |")
        unlock = " → ".join(f"{lvl} ({n} onaylı konu)" for lvl, n in usage.VOCAB_UNLOCK)
        block = "\n".join([
            f"> **{len(words)} kelime** · {sum(status(w) == 'yeni' for w in words)} tanesi hâlâ yeni · **açık kelime seviyesi: {ceiling}**",
            "",
            f"Konuşurken kullandığın içerik kelimeleri. Bir kelime, açık seviyeye (şu an **{ceiling}**) kadar olan ve {usage.NEW_WORD_USES} kez **doğru gramerle** kullanmadığın kelimeyse \"yeni\" sayılır ve konuşma puanında 3. kuralı açar. Üst seviye kelimeler kullanılabilir ama yeni sayılmaz; seviyeler ilerledikçe açılır: {unlock}. Kurallar: [[03-Konusma-Puanlari]].",
            "",
            *(lines if words else ["_Henüz kelime yok._"]),
        ])
        self.write_managed(self.base / "Neokorteks" / "Kelimeler" / "Kelime-Listesi.md", {"tags": ["kelime", "neokorteks"], "kelime_sayisi": len(words), "acik_seviye": ceiling}, "Kelime listesi", block, now)

    # ---- word neurons (vocabulary brain) — its own small network, kept apart from grammar's ----
    def sync_word_neuron(self, lemma: str, service, now: datetime) -> bool:
        row = self.store.word_neuron(lemma)
        if row is None:
            return False
        summary = service.word_summary(lemma)
        neighbors = self.store.word_synapses(lemma)
        syn_lines = ["| Komşu kelime | Tür | Ağırlık |", "|---|---|---|"]
        for r in neighbors[:12]:
            other = r["b"] if r["a"] == lemma else r["a"]
            syn_lines.append(f"| {self.word_link(other)} | {WORD_KIND_LABEL[r['kind']]} | {r['weight']:.2f} |")
        if not neighbors:
            syn_lines = ["_Henüz bağlantısı yok. Aynı anlam grubundaki ya da aynı cümlede birlikte kullandığın kelimelerle bağ kurulur._"]
        if row["valence"] is not None:
            source_note = "insan verisi (Warriner ve ark. 2013)" if row["vad_source"] == "dataset" else "model tahmini"
            vad_line = f"- Duygu (hoşluk / yoğunluk / kontrol, 1-9): {row['valence']:.1f} / {row['arousal']:.1f} / {row['dominance']:.1f} · kaynak: {source_note}"
        else:
            vad_line = "- Duygu skoru henüz yok"
        block = "\n".join([
            f"> **Aşama:** {word_rules.WORD_STAGE_LABEL[summary['stage']]} · **Kararlılık:** {summary['stability']} gün · **Doğru hatırlama:** {summary['successes']}/{summary['retrievals']}",
            "",
            "## Kimlik",
            f"- Seviye (CEFR): {row['cefr'] or '—'}",
            f"- Anlam grubu: {row['category'] or '—'}",
            vad_line,
            "",
            "## Bağlantılar",
            *syn_lines,
        ])
        fm = {
            "tags": ["kelime", "neokorteks", f"asama/{summary['stage'].replace('_', '-')}"],
            "kelime": lemma, "cefr": row["cefr"] or "", "anlam_grubu": row["category"] or "",
            "valence": row["valence"], "arousal": row["arousal"], "dominance": row["dominance"], "duygu_kaynagi": row["vad_source"] or "",
            "asama": summary["stage"], "kararlilik_gun": summary["stability"],
        }
        return self.write_managed(self.word_path(lemma), fm, lemma, block, now)

    def sync_word_synapse_index(self, now: datetime) -> None:
        all_syn = self.store.word_synapses()

        def line(r):
            return f"| {self.word_link(r['a'])} | {self.word_link(r['b'])} | {WORD_KIND_LABEL[r['kind']]} | {r['weight']:.2f} | {r['co_activations']} |"

        head = ["| Kelime A | Kelime B | Tür | Ağırlık | Birlikte kullanım |", "|---|---|---|---|---|"]
        strongest = [r for r in all_syn if r["weight"] >= 0.1][:60]
        block = "\n".join([
            f"> **{len(all_syn)} kelime bağlantısı** · {sum(r['kind'] == 'cooccurrence' for r in all_syn)} birlikte-kullanım (Hebb), {sum(r['kind'] == 'semantic' for r in all_syn)} anlam ortaklığı",
            "",
            "Kelimelerin kendi sinaps ağı — gramerin sinaps ağından ayrı. Anlam ortaklığı aynı konu grubundaki kelimeler arasında baştan kurulur; "
            "birlikte-kullanım bağı ise aynı cümlede doğru kullanılan kelimeler arasında zamanla güçlenir.",
            "",
            *head, *(line(r) for r in strongest),
        ])
        self.write_managed(self.base / "Sinapslar" / "Kelime-Sinaps-Agi.md", {"tags": ["sinaps", "kelime"], "sinaps_sayisi": len(all_syn)}, "Kelime sinaps ağı", block, now)

    def sync_word_touched(self, lemmas: set[str], service, now: datetime) -> None:
        for lemma in lemmas:
            self.sync_word_neuron(lemma, service, now)
        if lemmas:
            self.sync_word_synapse_index(now)

    def sync_unit(self, col_id: str, service, now: datetime) -> None:
        """After a scored sentence: the unit note, today's note and the word list change."""
        self._ensure_cols()
        self.sync_column(col_id, service, now)
        self.sync_hippocampus(service, now)
        self.sync_words(now, service.vocab_ceiling())

    def write_sleep_report(self, report: dict, service) -> None:
        now = datetime.fromisoformat(report["at"])
        by_id = {n["id"]: n for n in self.store.neurons()}
        self._ensure_cols()

        def nlink(nid):
            n = by_id[nid]
            return self.link(n, self._cols[n["col_id"]])

        promoted = [f"- {nlink(e['neuron_id'])}: {rules.STAGE_LABEL[e['stage_before']]} → **{rules.STAGE_LABEL[e['stage_after']]}**" for e in report["promoted_events"]]
        risk = [f"- {nlink(v['id'])} · hatırlanma ihtimali %{round(v['retrievability'] * 100)} · güç %{v['score']}" for v in report["at_risk"]]
        pruned = [f"- {nlink(a)} ↔ {nlink(b)}" for a, b in report["pruned"]]
        block = "\n".join([
            f"> {len(report['due'])} nöron tekrar bekliyor · {report['decayed']} sinaps zayıfladı · {len(report['pruned'])} sinaps budandı · {report['active']} aktif nöron",
            "",
            "Uykuda beyin günü tekrar oynatır, önemli bağları sabitler, kullanılmayanları zayıflatır. Bu not aynı işin uygulamadaki karşılığıdır.",
            "",
            "## Bugün terfi eden nöronlar",
            *(promoted or ["_Bugün aşama atlayan nöron olmadı._"]),
            "",
            "## Unutma riski taşıyanlar",
            *(risk or ["_Hatırlanma ihtimali %80'in altına düşen nöron yok._"]),
            "",
            "## Budanan sinapslar",
            *(pruned or ["_Budanan sinaps yok._"]),
        ])
        day = now.astimezone(TZ).strftime("%Y-%m-%d")
        self.write_managed(self.base / "Hipokampus" / "Uyku" / f"{day}.md", {"tags": ["hipokampus", "uyku"], "tarih": day, "tekrar_bekleyen": len(report["due"]), "budanan": len(report["pruned"])}, f"Uyku raporu {day}", block, now)

    # ---- orchestration ----
    def _ensure_cols(self) -> None:
        self._cols = {c["id"]: c for c in self.store.columns()}

    def sync_touched(self, neuron_ids: set[str], service, now: datetime) -> None:
        self._ensure_cols()
        cols = set()
        for nid in neuron_ids:
            self.sync_neuron(nid, service, now)
            cols.add(self.store.neuron(nid)["col_id"])
        for c in cols:
            self.sync_column(c, service, now)
        self.sync_hippocampus(service, now)
        self.sync_synapse_indexes(now)

    def sync_all(self, service) -> dict:
        now = service.clock()
        self._ensure_cols()
        written = 0
        for n in self.store.neurons():
            written += self.sync_neuron(n["id"], service, now)
        for c in self._cols:
            written += self.sync_column(c, service, now)
        self.sync_hippocampus(service, now)
        self.sync_synapse_indexes(now)
        self.sync_words(now, service.vocab_ceiling())
        word_rows = self.store.word_neurons()
        for row in word_rows:
            written += self.sync_word_neuron(row["lemma"], service, now)
        self.sync_word_synapse_index(now)
        return {"neurons": len(self.store.neurons()), "written": written, "words": len(word_rows)}
