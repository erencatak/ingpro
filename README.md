# ingpro

Tamamen yerel çalışan, sesli bir İngilizce konuşma koçu. İlerlemeyi bir puan tablosunda değil, nörobilim
literatüründen (FSRS spaced repetition, Hebbian sinaps öğrenmesi, Complementary Learning Systems) esinlenen
gerçek bir **beyin modelinde** tutuyor — hem gramer hem kelime için ayrı ayrı — ve bu beyni uygulama içinde
canlı bir nöron ağı olarak gösteriyor.

## Ekran görüntüleri

| Bugün | Sohbet |
|---|---|
| ![Bugün](docs/screenshots/bugun.jpg) | ![Sohbet](docs/screenshots/sohbet.jpg) |

| Gramer | Kelime beyni |
|---|---|
| ![Gramer](docs/screenshots/gramer.jpg) | ![Kelime beyni](docs/screenshots/beyin.jpg) |

## Neden farklı

Çoğu dil öğrenme uygulaması "doğru/yanlış" sayar ve bir seviye barı doldurur. ingpro bunun yerine iki soruya
gerçek bir model kuruyor: *bu bilgi beyinde ne kadar kalıcı* ve *hangi bilgiler birbirine bağlı*. Puanı asla
LLM vermiyor — LLM sadece dili anlıyor, kararı deterministik kod veriyor. Ücretsiz: API anahtarı değil,
bilgisayarındaki Claude Code oturumunu kullanıyor.

## Özellikler

### Sesli sohbet
- Gerçek zamanlı, çift yönlü konuşma — WebSocket üzerinden cümle cümle akan TTS
- **İki dilli STT (Whisper):** Türkçe-İngilizce karışık konuşmayı ("bunu nasıl söylerim ingilizcede") anlayabiliyor —
  dil olasılığına göre yönlendirme, belirsiz durumlarda iki dilde de çözüp güven skoruna göre seçim
- **Tek ses, iki dil:** Chatterbox motoru tek bir klonlanmış sesle hem İngilizce hem Türkçe konuşuyor (4-bit
  kuantize, ayarlanabilir kalite/hız); alternatif olarak Kokoro (EN) + Piper/macOS Yelda (TR) ile daha hafif bir mod
- **Sıfırdan yazılmış perde-koruyucu hız değiştirme** (phase vocoder) — konuşma hızı değişirken ses tonu bozulmuyor
- Cümle içinde dil geçişi doğru telaffuz ediliyor (İngilizce cümle içindeki Türkçe alıntı, Türkçe okunuyor)
- **Filler/tepki sesleri:** "Hmm, I see." gibi kısa tepkiler bir kere seslendirilip önbelleğe alınıyor, LLM
  düşünürken anında çalınıyor — soru/ifade ayrımı yapıyor, selamlaşmalarda devreye girmiyor, her turda
  tetiklenmeyip doğal duruyor
- Basılı konuş ve otomatik dinleme (VAD) modları, konuşma sırasında araya girebilme (barge-in)
- WebSocket origin kontrolü — başka bir site mikrofonuna/Claude kotana erişemiyor

### Konuşma puanlama (tamamen deterministik)
- 4 kurallu puanlama: LLM sadece cümlenin doğru/yanlış olduğunu ve kelime seviyesini söylüyor, **puanı kod veriyor**
- LLM'e sormadan önce deterministik ön kontrol (konuşulmamış, yanlış dil, net olmayan telaffuz) — token tasarrufu
- Kelime "yenilik" eşiği, onaylanan ünite sayısına göre CEFR seviyesinde açılıyor

### Gramer beyni — nöron/sinaps hafıza sistemi
- Gerçek bir FSRS kütüphanesiyle aralıklı tekrar zamanlaması
- Hebbian sinapslar (birlikte hatırlanan konular bağlanır) + kitaptan gelen yapısal bağlar + karışıklık bağları
- Aynı gün tekrar tekrar test edip sistemi kandırmayı engelleyen "aynı gün dondurma" kuralı
- Karışıklık tespiti ve ilişkili konuları ayırt etme önerisi
- Gece uykusuna eşdeğer konsolidasyon: zayıflama, budama, tekrar kuyruğu, unutma riski tespiti
- 5 aşamalı bellek modeli (uyuyan → kodlama → kısa süreli → pekişme → uzun süreli)

### Kelime beyni — ayrı, daha basit ve bilimsel bir model
- Bir kelime, konuşmada 3 kez doğru kullanılınca kendi nöronuna kavuşuyor
- **2 aşamalı model** (Complementary Learning Systems literatürüne dayanıyor): hızlı tanıma → bir "uyku"
  geçişinden sonra kalıcı entegrasyon
- **Gerçek, yayınlanmış duygu verisi:** 13.915 İngilizce kelimenin insan puanlamasıyla valence/arousal/dominance
  skorları (Warriner, Kuperman & Brysbaert 2013); veri setinde olmayan kelimeler için LLM tahmini devreye giriyor
  ve bir daha sorulmuyor (kalıcı önbellek)
- İki ayrı sinaps türü: anlam ortaklığı (aynı konu grubu, statik) ve birlikte kullanım (aynı cümlede, Hebbian)
- Puanlama sistemine hiç karışmıyor — sadece ek bir bilgi katmanı

### Canlı nöron ağı görselleştirmesi (Beyin sekmesi)
- Canvas tabanlı fizik simülasyonu: kelimeler anlam gruplarına göre kendi "kortikal bölgelerinde" kümeleniyor
- Bir kelimeye tıklayınca "ateşleniyor", sinyal bağlı olduğu kelimelere yayılıyor — beynin **yayılan aktivasyon**
  dediği şeyin görsel karşılığı
- İki renk modu: duygu (valence'e göre mavi→pembe) ve anlam grubu
- Sürüklenebilir nöronlar, arada kendiliğinden ateşlenen rastgele aktivite
- Henüz veri yokken elle hazırlanmış bir örnek ağ gösteriyor

### Senaryolar
- Serbest sohbet, iş görüşmesi (pozisyonu sen belirliyorsun), restoran
- **Serbest metinle senaryo oluşturma:** "hayvanat bahçesinde bekçiyle konuşma" gibi bir açıklamayı AI'a
  yapılandırılmış bir rol-yapma senaryosuna çeviriyor

### Konu anlatımı (pre-learning kartları)
- Her gramer ünitesi için 30-60 saniyelik, kaynak gösterilen bir anlatım kartı
- Sıkı doğrulama: kaynağı olmayan, kelime sınırını aşan veya eksik alanı olan kart hiç gösterilmiyor
- Kart, Alex'in konuşma açılışını ve düzeltme tarzını da yönlendiriyor

### Cümle kalıpları
- Deterministik, LLM'siz bir öneri sistemi — Alex'in son cevabındaki konu/işlev ipuçlarına göre boşluklu
  cümle kalıpları öneriyor ("I worked ___ at ___.")

### İlerleme takibi
- Gerçek konuşma puanlarından hesaplanan haftalık CEFR eğrisi, günlük pratik dakikası, seri (streak), ısı haritası
- **Dürüst:** Konuşma/dinleme henüz ölçülmüyorsa "Ölçülmedi" diyor, uydurmuyor

### Obsidian entegrasyonu (isteğe bağlı)
- Hem gramer hem kelime beyni, kendi Markdown notları olarak bir Obsidian vault'una yansıtılıyor
- Tek yönlü (DB → not): sen bir nota "## Notlarım" altına bir şey yazarsan, her yenilemede korunuyor
- Atomik dosya yazımı, değişmeyen notlar yeniden yazılmıyor (hash kontrolü)

## Mimari

- **Backend:** FastAPI + SQLite, WebSocket üzerinden ses akışı
- **Frontend:** React + TypeScript + Vite
- **LLM:** Claude Code CLI (`claude login` ile), API anahtarı yok — kim çalıştırırsa kendi aboneliği harcanır
- **Ses:** mlx-whisper (STT), Chatterbox / Kokoro + Piper (TTS) — Apple'ın MLX framework'üne dayanıyor
- **Test:** 130+ testle kapsanan backend (`pytest`)

## Gereksinimler

- **Apple Silicon Mac (M1/M2/M3/M4).** Ses motorları MLX'e dayanıyor — Intel Mac, Windows ve Linux'ta çalışmaz.
- [`uv`](https://docs.astral.sh/uv/) (Python 3.12 paket yöneticisi)
- Node.js + npm
- **Claude Code CLI, kurulu ve giriş yapılmış** (`claude login`)

## Kurulum

```bash
./scripts/setup.sh
```

Bağımlılıkları kurar, `.env`'i `.env.example`'dan oluşturur, ses modellerini (~2 GB) ve kelime beyninin
duygu veri setini indirir.

## Çalıştırma

```bash
./scripts/dev.sh      # ön planda, Ctrl+C ikisini de durdurur
# veya
./scripts/start.sh    # arka planda başlatır, hemen döner
./scripts/stop.sh      # arka planda çalışanı durdurur
```

Backend `:8765`, web arayüzü `:5173`'te açılır.

## Ayarlar

Tüm ayarlar isteğe bağlı; varsayılanlar `server/src/ingpro/config.py`'de. Öne çıkanlar (tam liste `.env.example`'da):

| Ayar | Ne işe yarar |
|---|---|
| `INGPRO_TTS_ENGINE` | `chatterbox` (tek klon ses) veya `classic` (Kokoro + Piper, daha hafif) |
| `INGPRO_STT_MODEL` | Whisper model boyutu — doğruluk/hız dengesi |
| `INGPRO_VOICE_REF` | Alex'in sesini klonlayacağın kendi ses kaydın |
| `INGPRO_PROFILE_PATH` | Öğrenci hakkında serbest metin notlar (tutor'a bağlam verir) |
| `INGPRO_TUTOR_MODEL` / `INGPRO_JUDGE_MODEL` | Konuşma ve puanlama için kullanılan model |
| `INGPRO_VAULT_DIR` | Obsidian vault yolu — boşsa entegrasyon kapalı |
| `INGPRO_FILLERS` | Anında sesli tepkiler açık/kapalı |

## Notlar

- Kitap tabanlı gramer içeriği (`content/grammar/yener.json`) ve kelime beyninin duygu veri seti
  (`content/vocab/warriner_vad.csv`) telif/lisans nedeniyle bu repoda yok; `setup.sh` bunları senin için indirir.

## Lisans

MIT — bkz. [LICENSE](LICENSE). Kelime beyninin duygu verileri ayrı bir lisansla (Warriner, Kuperman & Brysbaert 2013,
CC BY-NC-ND) geliyor ve repoya dahil değil; kaynağı uygulama içinde Beyin sekmesinde belirtiliyor.
