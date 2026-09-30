"""Generates content/grammar/sample.json: a 46-topic PLACEHOLDER curriculum (not the Yener book's table of contents)
so the roadmap screens can be designed at real scale. The book's real list goes into content/grammar/yener.json."""

import json
from pathlib import Path

T = [
    ("The Verb To Be", "Be Fiili", ["am / is / are", "Olumsuz ve soru cümleleri", "Kısa cevaplar"]),
    ("Subject Pronouns & Possessive Adjectives", "Özne Zamirleri ve İyelik Sıfatları", ["I, you, he, she, it, we, they", "my, your, his, her, its, our, their", "Zamir ve iyelik sıfatı farkı"]),
    ("Articles", "Tanımlıklar (a / an / the)", ["a ve an", "the ne zaman kullanılır", "Tanımlık kullanılmayan durumlar"]),
    ("Nouns: Countable & Uncountable", "Sayılabilir ve Sayılamayan İsimler", ["Sayılabilir isimler", "Sayılamayan isimler", "a piece of, a bottle of"]),
    ("Plural Nouns", "Çoğul İsimler", ["-s / -es ekleri", "Düzensiz çoğullar", "Yalnızca çoğul kullanılan isimler"]),
    ("This, That, These, Those", "İşaret Sıfatları ve Zamirleri", ["Yakın ve uzak işaret", "Tekil ve çoğul", "Soru ve kısa cevaplar"]),
    ("There is / There are", "Var / Yok Yapısı", ["Olumlu ve olumsuz", "Soru ve kısa cevap", "There is ile it is farkı"]),
    ("Have got / Has got", "Sahiplik", ["Olumlu, olumsuz, soru", "have ile have got farkı", "Sahiplik dışındaki kullanımlar"]),
    ("Present Simple Tense", "Geniş Zaman", ["Olumlu cümle ve üçüncü tekil -s", "do / does ile soru ve olumsuz", "Alışkanlık ve genel gerçekler", "Zaman ifadeleri"]),
    ("Adverbs of Frequency", "Sıklık Zarfları", ["always, usually, often", "sometimes, rarely, never", "Cümledeki yeri"]),
    ("Present Continuous Tense", "Şimdiki Zaman", ["-ing ekinin yazımı", "Olumlu, olumsuz, soru", "Şu anda ve yakın gelecek"]),
    ("Present Simple vs Continuous", "Geniş ve Şimdiki Zaman Farkı", ["Kalıcı ve geçici durumlar", "Durum fiilleri (stative verbs)", "Karışık alıştırma"]),
    ("Imperatives", "Emir Cümleleri", ["Olumlu ve olumsuz emir", "Let's ile öneri", "Kibar rica"]),
    ("Can, Could, Be able to", "Yeterlilik", ["can ile yetenek ve izin", "could ile geçmiş yetenek", "be able to"]),
    ("Prepositions of Place", "Yer Edatları", ["in, on, at", "under, between, next to", "Yön edatları"]),
    ("Prepositions of Time", "Zaman Edatları", ["in, on, at ile zaman", "for, since, during", "before, after, until"]),
    ("Question Words", "Soru Sözcükleri", ["what, who, where, when", "why, how, which", "Özne ve nesne soruları"]),
    ("Past Simple Tense", "Geçmiş Zaman", ["Düzenli fiiller -ed", "Düzensiz fiiller", "did ile soru ve olumsuz", "Geçmiş zaman ifadeleri"]),
    ("Past Continuous Tense", "Geçmişte Süren Eylem", ["was / were + -ing", "when ve while", "Past simple ile birlikte"]),
    ("Object Pronouns", "Nesne Zamirleri", ["me, you, him, her, it, us, them", "Fiilden sonra nesne zamiri", "Özne ve nesne zamiri karşılaştırma"]),
    ("Possessive Pronouns & Genitive", "İyelik Zamirleri ve 's", ["mine, yours, his, hers", "'s ve of ile aitlik", "Çift iyelik (a friend of mine)"]),
    ("Some, Any, No", "Belirsiz Nicelik Sözcükleri", ["some ve any", "no, none", "something, anything, nothing"]),
    ("Much, Many, A lot of", "Nicelik Sözcükleri", ["much ve many", "a lot of, lots of", "few, little, a few, a little"]),
    ("Comparatives", "Karşılaştırma Sıfatları", ["Kısa sıfatlar -er", "Uzun sıfatlar more", "as ... as ve than"]),
    ("Superlatives", "Üstünlük Derecesi", ["-est ve most", "Düzensiz sıfatlar", "the ... in / of"]),
    ("Adjectives & Adverbs", "Sıfatlar ve Zarflar", ["Sıfat sırası", "-ly ile zarf yapımı", "Düzensiz zarflar (fast, well)"]),
    ("Present Perfect Tense", "Yakın Geçmiş", ["have / has + V3", "for ve since", "ever, never, already, yet", "been ve gone farkı"]),
    ("Present Perfect vs Past Simple", "Yakın Geçmiş ve Geçmiş Zaman Farkı", ["Zaman belirteci var mı", "Şimdiyle bağlantı", "Karışık alıştırma"]),
    ("Present Perfect Continuous", "Süregelen Eylem", ["have been + -ing", "Süre vurgusu", "Present perfect ile farkı"]),
    ("Past Perfect Tense", "Geçmişin Geçmişi", ["had + V3", "before, after, by the time", "Past simple ile sıralama"]),
    ("Future: Will", "Gelecek Zaman (will)", ["Anlık karar ve söz", "Tahmin", "Olumsuz ve soru"]),
    ("Future: Be going to", "Planlı Gelecek", ["Plan ve niyet", "Kanıta dayalı tahmin", "will ile going to farkı"]),
    ("Future Continuous & Future Perfect", "İleri Gelecek Zamanlar", ["will be + -ing", "will have + V3", "Zaman ifadeleri"]),
    ("Modals of Obligation", "Zorunluluk Modalleri", ["must, have to", "mustn't ve don't have to", "should, ought to"]),
    ("Modals of Possibility", "Olasılık Modalleri", ["may, might, could", "must ve can't ile çıkarım", "Geçmiş çıkarım (must have)"]),
    ("Passive Voice", "Edilgen Çatı", ["be + V3", "Zamanlara göre edilgen", "by ile fail", "Edilgen soru ve olumsuz"]),
    ("Conditionals: Zero & First", "Koşul Cümleleri (0 ve 1)", ["If + present simple", "Zero conditional", "unless ve as long as"]),
    ("Conditionals: Second & Third", "Koşul Cümleleri (2 ve 3)", ["Second conditional", "Third conditional", "Karışık koşul cümleleri"]),
    ("Reported Speech", "Dolaylı Anlatım", ["Zaman kaymaları", "Dolaylı soru ve emir", "say ile tell farkı"]),
    ("Relative Clauses", "İlgi Cümlecikleri", ["who, which, that", "whose, where, when", "Tanımlayıcı ve tanımlayıcı olmayan"]),
    ("Gerunds & Infinitives", "-ing ve to + Fiil", ["Fiilden sonra -ing", "Fiilden sonra to + fiil", "Anlamı değişenler (stop, remember)"]),
    ("Phrasal Verbs", "Deyimsel Fiiller", ["Ayrılabilen ve ayrılamayan", "Sık kullanılan 30 phrasal verb", "Anlam tahmini"]),
    ("Conjunctions & Linking Words", "Bağlaçlar", ["and, but, or, so", "although, however, despite", "because, since, as"]),
    ("Question Tags", "Soru Ekleri", ["Olumlu ve olumsuz ek", "Özel durumlar (I am, let's)", "Tonlama"]),
    ("Wish & If only", "Dilek Cümleleri", ["wish + past simple", "wish + past perfect", "would ile şikâyet"]),
    ("Inversion & Emphasis", "Devrik Cümle ve Vurgu", ["Never, rarely, hardly", "Not only ... but also", "Cleft cümleler (It is ... that)"]),
]

assert len(T) == 46, len(T)
assert all(len(t[2]) >= 3 for t in T)
topics = [
    {"id": i + 1, "title": t, "tr": tr, "subtopics": [{"id": f"{i + 1}.{j + 1}", "title": s} for j, s in enumerate(subs)]}
    for i, (t, tr, subs) in enumerate(T)
]
out = {"source": "Örnek liste (Ebru Yener kitabından DEĞİL): 46 konu ve alt başlık yapısını görmek için taslak", "verified": False, "topics": topics}
path = Path(__file__).resolve().parents[1] / "content" / "grammar" / "sample.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
print(len(topics), "topics,", sum(len(t["subtopics"]) for t in topics), "subtopics")
