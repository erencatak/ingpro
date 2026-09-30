"""Turns the grammar course into neurons and gives them their first, curated synapses."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .rules import INITIAL_WEIGHT
from .store import Store

log = logging.getLogger("ingpro.brain")

Sel = str | int  # a subtopic of a unit: the book's code ("1.A") or its 1-based position (2)


@dataclass(frozen=True)
class SynapseSeed:
    unit_a: int
    sel_a: Sel
    unit_b: int
    sel_b: Sel
    kind: str  # structural: one idea builds on the other | confusion: learners often mix the two up
    reason: str


S, C = "structural", "confusion"
SEEDS: list[SynapseSeed] = [
    # nouns, articles, adjectives, adverbs, pronouns, prepositions
    SynapseSeed(1, "1.A", 2, "2.B", S, "a / an yalnızca sayılabilen tekil isimle kullanılır"),
    SynapseSeed(1, "1.C", 2, "2.B", S, "Sayılamayan ve çoğul isimlerde çoğu zaman tanımlık kullanılmaz"),
    SynapseSeed(2, "2.E", 6, "6.B", S, "İyelik: isimlerde 's, zamirlerde my / mine"),
    SynapseSeed(3, "3.D", 7, "7.F", S, "Aynı konu iki ünitede geçiyor: sıfat + edat"),
    SynapseSeed(4, "4.A", 5, "5.C", S, "-ly zarflar karşılaştırılırken more / most alır"),
    SynapseSeed(4, "4.C", 9, 1, S, "Sıklık zarfları geniş zamanla birlikte kullanılır"),
    SynapseSeed(4, "4.B", 7, "7.A", S, "Zaman zarfları ve zaman edatları aynı zaman ifadelerini paylaşır"),
    SynapseSeed(4, "4.D", 7, "7.B", S, "Yer zarfları ve yer edatları"),
    SynapseSeed(7, "7.G", 4, "4.D", C, "Edat mı zarf mı: in / inside, up / upstairs gibi çiftler karışır"),
    SynapseSeed(6, "6.D", 32, "32.B", S, "Soru zamirleri bilgi sorularını kurar"),
    SynapseSeed(32, "32.A", 33, 1, S, "Soru takıları evet / hayır sorusu mantığıyla cevaplanır"),
    # be, tenses
    SynapseSeed(8, 2, 10, 1, S, "am / is / are yardımcı fiili: Present Continuous yapısı"),
    SynapseSeed(8, 2, 12, 1, S, "was / were yardımcı fiili: Past Continuous yapısı"),
    SynapseSeed(8, 2, 37, "37.A", S, "Edilgen yapı be + V3'tür"),
    SynapseSeed(9, 1, 10, 1, C, "Geniş zaman ile şimdiki zaman sık karışır"),
    SynapseSeed(10, 2, 9, 1, S, "Continuous ile kullanılmayan fiiller geniş zamanda kalır"),
    SynapseSeed(11, 2, 46, "46.B", S, "Düzensiz fiillerin II. ve III. halleri"),
    SynapseSeed(11, 1, 12, 1, S, "Past Simple ile Past Continuous birlikte kullanılır (when / while)"),
    SynapseSeed(12, 3, 36, "36.A", S, "when / while zaman zarf cümleciklerini kurar"),
    SynapseSeed(11, 1, 13, 1, C, "\"went\" ile \"have gone\": bitmiş geçmiş ile şimdiye bağlı geçmiş"),
    SynapseSeed(13, 1, 14, 1, C, "Present Perfect ile Present Perfect Continuous"),
    SynapseSeed(14, 2, 13, 1, S, "İki zamanın farkını anlatan alt başlık"),
    SynapseSeed(13, 1, 15, 1, C, "have + V3 ile had + V3"),
    SynapseSeed(15, 2, 13, 1, S, "Present Perfect ile Past Perfect farkı"),
    SynapseSeed(15, 1, 16, 1, S, "had + V3 ile had been + -ing"),
    SynapseSeed(17, 3, 17, 1, C, "\"will\" ile \"be going to\""),
    SynapseSeed(18, 1, 19, 1, C, "will be doing ile will have done"),
    SynapseSeed(19, 2, 18, 1, S, "İki gelecek yapısının farkını anlatan alt başlık"),
    SynapseSeed(17, 1, 39, "39.A", S, "1. tip koşulda ana cümle will alır"),
    SynapseSeed(27, 1, 11, 1, S, "used to geçmiş alışkanlıkları anlatır, Past Simple ile yakın"),
    # modals
    SynapseSeed(22, 1, 23, 1, S, "can / could hem yeterlilik hem izin için kullanılır"),
    SynapseSeed(22, 2, 25, 1, S, "Olasılık ile çıkarım aynı kesinlik ölçeğinde (may, might, must)"),
    SynapseSeed(24, 1, 25, 1, C, "must: zorunluluk mu, çıkarım mı"),
    SynapseSeed(25, 2, 46, "46.B", S, "must have + V3 (III. hal)"),
    SynapseSeed(27, 1, 27, 4, C, "\"used to\" ile \"be used to\""),
    SynapseSeed(27, 4, 44, "44.A", S, "be used to + -ing"),
    SynapseSeed(29, 5, 30, "30.E", C, "Aynı sözcük iki anlamda: too (aşırı) ve too (de / da)"),
    SynapseSeed(29, 1, 29, 2, C, "very ile much / very much kullanımı"),
    # conditionals, passive, clauses, reported speech, non-finite forms
    SynapseSeed(39, "39.B", 40, "40.A", S, "Şimdiki gerçek dışı durum: if + past ile wish + past"),
    SynapseSeed(39, "39.C", 40, "40.A", S, "Geçmişe pişmanlık: if + had V3 ile wish + had V3"),
    SynapseSeed(39, "39.C", 15, 1, S, "3. tip koşulda had + V3 kullanılır"),
    SynapseSeed(40, "40.B", 39, "39.A", S, "unless, provided that gibi bağlaçlar koşul cümlesi kurar"),
    SynapseSeed(37, "37.A", 46, "46.B", S, "Edilgende III. hal (past participle)"),
    SynapseSeed(38, "38.A", 37, "37.A", S, "have / get something done edilgen yapıya benzer"),
    SynapseSeed(41, "41.B", 32, "32.B", C, "Dolaylı soruda düz cümle sırası, doğrudan soruda soru sırası"),
    SynapseSeed(43, "43.E", 41, "41.B", S, "Dolaylı anlatımda soru, isim cümleciği kurar"),
    SynapseSeed(43, "43.B", 22, 1, S, "Dolaylı anlatımda can → could gibi kip değişimleri"),
    SynapseSeed(43, "43.C", 4, "4.B", S, "Dolaylı anlatımda now → then gibi zaman zarfı değişimleri"),
    SynapseSeed(43, "43.A", 41, "41.A", S, "Aktarma fiillerinden sonra that cümleciği gelir"),
    SynapseSeed(42, "42.D", 46, "46.A", S, "İlgi cümleciği ortaç (-ing) ile kısaltılır"),
    SynapseSeed(42, "42.D", 46, "46.B", S, "İlgi cümleciği ortaç (III. hal) ile kısaltılır"),
    SynapseSeed(44, "44.A", 45, "45.A", C, "Fiilden sonra -ing mi, to + fiil mi"),
    SynapseSeed(44, "44.G", 45, "45.B", C, "Algı fiillerinden sonra -ing ile yalın mastar farklı anlam verir"),
    SynapseSeed(31, "31.C", 7, "7.A", S, "Saat ve tarihlerle at / on / in"),
    SynapseSeed(31, "31.B", 7, "7.A", S, "Tarihlerle on / in"),
]


def neuron_id(sub_id: str) -> str:
    return f"g:{sub_id}"


def _resolve(topics: dict[int, dict], unit: int, sel: Sel) -> str | None:
    topic = topics.get(unit)
    if not topic:
        return None
    subs = topic["subtopics"]
    if isinstance(sel, int):
        return neuron_id(subs[sel - 1]["id"]) if 0 < sel <= len(subs) else None
    return next((neuron_id(s["id"]) for s in subs if s.get("code") == sel), None)


def seed_course(store: Store, course: dict) -> dict[str, int]:
    """Idempotent: creates columns, neurons and curated synapses; never touches what was learned."""
    units = [t for t in course.get("topics", [])]
    extras = [t for t in course.get("extras", []) if t.get("roadmap")]
    n_neurons = 0
    for ord_, t in enumerate(units + extras):
        label = t.get("label") or f"{t['id']:02d}"
        is_extra = t in extras
        col_id = f"c:{label}"
        store.upsert_column(col_id, t["id"], label, t["title"], t.get("tr"), t.get("page"), is_extra, ord_)
        for i, s in enumerate(t["subtopics"], 1):
            store.upsert_neuron(neuron_id(s["id"]), s["id"], col_id, i, s.get("code"), s["title"], s.get("tr"), s.get("kind"))
            n_neurons += 1
    by_unit = {t["id"]: t for t in units}
    made = skipped = 0
    # The curated links are written against the book's unit numbers: only valid for the verified course
    for seed in SEEDS if course.get("verified") else []:
        a, b = _resolve(by_unit, seed.unit_a, seed.sel_a), _resolve(by_unit, seed.unit_b, seed.sel_b)
        if not a or not b:
            skipped += 1
            continue
        made += store.add_synapse_if_missing(a, b, seed.kind, INITIAL_WEIGHT[seed.kind], seed.reason)
    if skipped:
        log.warning("%d curated synapses could not be resolved against the course", skipped)
    return {"neurons": n_neurons, "columns": len(units) + len(extras), "synapses_new": made, "synapses_skipped": skipped}
