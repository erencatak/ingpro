// Placeholder content for screens whose backend does not exist yet (copied from design/mockup.html).
// Every view that reads this file shows an "Örnek veri" badge. Replace with API data in Faz 1.

export const SKILLS: [name: string, level: string, value: number][] = [
  ['Konuşma', 'A2', 1.55],
  ['Dinleme', 'A2+', 1.8],
  ['Kelime', 'A2+', 1.92],
  ['Dilbilgisi', 'A2', 1.6],
]

export const PLAN = [
  { title: 'Isınma tekrarları', sub: '12 kart · FSRS', dur: '3 dk', icon: 'check', state: 'done' },
  { title: 'Hedefli alıştırma', sub: 'Present perfect, artikeller · 6 soru', dur: '7 dk', icon: 'target', state: 'now' },
  { title: 'Sohbet: Restoran', sub: 'Alex garson, sen sipariş veriyorsun', dur: '12 dk', icon: 'headset', state: '' },
  { title: 'Kapanış', sub: 'Oturum özeti + 3 yeni kelime', dur: '2 dk', icon: 'flag', state: '' },
] as const

export type Exercise =
  | { type: 'mc'; kicker: string; title: string; prompt: string; options: string[]; answer: number; good: string; bad: string }
  | { type: 'order'; kicker: string; title: string; tr: string; words: string[]; answer: string; good: string; bad: string }
  | { type: 'cloze'; kicker: string; title: string; before: string; after: string; answer: string[]; hint: string; good: string; bad: string }

export const EXERCISES: Exercise[] = [
  { type: 'mc', kicker: 'Hata bankandan · present perfect', title: 'Boşluğa hangisi gelir?',
    prompt: "I ___ in this neighborhood since 2023, and I still love it.",
    options: ['am living', 'have been living', 'live', 'was living'], answer: 1,
    good: '“since 2023” geçmişten bugüne süren bir durumu anlatır: have been + -ing.',
    bad: 'have been living · “since” ile present perfect (continuous) kullanılır.' },
  { type: 'order', kicker: 'Yeni kelime · reluctant', title: 'Bu cümleyi İngilizceye çevir',
    tr: 'Arkadaşı yeni insanlarla tanışmaya isteksizdi.',
    words: ['Her', 'friend', 'was', 'reluctant', 'to', 'meet', 'new', 'people', 'reluctance', 'at'],
    answer: 'Her friend was reluctant to meet new people',
    good: '“reluctant to + fiil” kalıbı: bir şeyi yapmaya gönülsüz olmak.', bad: 'Her friend was reluctant to meet new people.' },
  { type: 'cloze', kicker: 'Hata bankandan · edatlar', title: 'Boşluğu doldur',
    before: 'We are meeting for dinner', after: 'Friday evening, after work.', answer: ['on'], hint: 'Günlerden önce hangi edat gelir?',
    good: 'Günlerle “on” kullanılır: on Friday, on Monday morning.', bad: 'on · günlerle “on”, saatlerle “at”, aylarla “in”.' },
  { type: 'mc', kicker: 'Tekrar · gündelik kelime', title: '“errand” ne demek?',
    prompt: 'I need to run a few errands before the shops close.',
    options: ['Tatil', 'Kısa iş/görev (alışveriş, postane gibi)', 'Randevu', 'Egzersiz'], answer: 1,
    good: 'errand = alışveriş, postane gibi kısa, günlük bir iş için dışarı çıkmak.', bad: 'Kısa iş/görev (alışveriş, postane gibi).' },
]

export interface Card { w: string; ipa: string; pos: string; tr: string; ex: [before: string, bold: string, after: string]; convo: string; src: string }
export const CARDS: Card[] = [
  { w: 'commute', ipa: '/kəˈmjuːt/', pos: 'verb', tr: 'işe/okula gidip gelmek',
    ex: ['I ', 'commute', ' by bus every morning.'], convo: '“I commute for almost an hour each day.”', src: 'Sen · 26 Eylül, serbest sohbet' },
  { w: 'reluctant', ipa: '/rɪˈlʌk.tənt/', pos: 'adjective', tr: 'isteksiz, gönülsüz',
    ex: ['She was ', 'reluctant', ' to try the spicy dish.'], convo: "“I'm a bit reluctant to order that.”", src: 'Alex · 26 Eylül, Restoran' },
  { w: 'errand', ipa: '/ˈer.ənd/', pos: 'noun', tr: 'kısa iş, görev (alışveriş, postane gibi)',
    ex: ['I have a few ', 'errands', ' to run this afternoon.'], convo: '“I ran a few errands after lunch, I think.”', src: 'Sen · 22 Eylül, serbest sohbet' },
  { w: 'figure out', ipa: '/ˈfɪɡ.ər aʊt/', pos: 'phrasal verb', tr: 'anlamak, çözmek, bir yolunu bulmak',
    ex: ["I can't ", 'figure out', ' which bus to take.'], convo: "“I didn't figure it out until later.”", src: 'Sen · 19 Eylül, serbest sohbet' },
]

// [word, meaning, deck, fromConversation, status, next review]
export const WORDS: [string, string, 'genel' | 'daily', 0 | 1, string, string][] = [
  ['commute', 'işe/okula gidip gelmek', 'daily', 1, 'Öğreniliyor', 'bugün'],
  ['reluctant', 'isteksiz, gönülsüz', 'genel', 1, 'Öğreniliyor', 'bugün'],
  ['errand', 'kısa iş, görev', 'daily', 1, 'Biliniyor', '8 gün'],
  ['workout', 'antrenman, egzersiz', 'daily', 0, 'Öğreniliyor', 'yarın'],
  ['figure out', 'anlamak, çözmek', 'genel', 1, 'Bugün tekrar', 'bugün'],
  ['appointment', 'randevu', 'daily', 0, 'Biliniyor', '21 gün'],
  ['postpone', 'ertelemek', 'genel', 0, 'Yeni', '—'],
  ['meanwhile', 'bu arada', 'genel', 1, 'Biliniyor', '14 gün'],
  ['grocery', 'market alışverişi', 'daily', 0, 'Yeni', '—'],
  ['straightforward', 'basit, anlaşılır', 'genel', 0, 'Öğreniliyor', '2 gün'],
  ['leftovers', 'artan yemek', 'daily', 1, 'Bugün tekrar', 'bugün'],
  ['look forward to', 'dört gözle beklemek', 'genel', 0, 'Biliniyor', '30 gün'],
  ['neighborhood', 'mahalle', 'daily', 0, 'Yeni', '—'],
  ['apparently', 'görünüşe göre', 'genel', 1, 'Öğreniliyor', 'yarın'],
]

export const ERRORS = [
  { t: 'Artikeller (a / an / the)', code: 'grammar/article', n: 23, trend: -18, weeks: [7, 6, 6, 5, 4, 4, 3], o: 'I took bus this morning and it was late.', c: ['I took ', 'the', ' bus this morning and it was late.'], note: 'Türkçede artikel yok, bu yüzden en sık hatan bu. Belirli, bilinen bir şeyden bahsederken “the” gerekir.', close: 0 },
  { t: 'Present perfect', code: 'grammar/present_perfect', n: 17, trend: 12, weeks: [1, 2, 2, 3, 3, 4, 5], o: 'I live here since 2023.', c: ['I ', 'have lived', ' here since 2023.'], note: '“since / for” ile geçmişte başlayıp hâlâ süren durumlar present perfect ister.', close: 0 },
  { t: 'Edatlar (in / on / at)', code: 'grammar/preposition', n: 14, trend: -5, weeks: [3, 2, 3, 2, 2, 2, 2], o: 'The dinner is in Friday at the evening.', c: ['The dinner is ', 'on', ' Friday ', 'in', ' the evening.'], note: 'Günler → on, günün bölümleri → in, saatler → at.', close: 1 },
  { t: 'Soru cümlesinde sıra', code: 'word_order/question', n: 9, trend: -30, weeks: [3, 2, 2, 1, 1, 0, 0], o: "Why you didn't call your friend?", c: ['Why ', "didn't you", ' call your friend?'], note: 'Soru kelimesinden sonra yardımcı fiil öne gelir: Why + did + you…', close: 2 },
  { t: '“be” + fiil', code: 'grammar/be_plus_verb', n: 6, trend: -40, weeks: [2, 2, 1, 1, 0, 0, 0], o: 'I am agree, it sounds fun.', c: ['I ', 'agree', ', it sounds fun.'], note: 'agree, want, need gibi fiillerin önüne “am / is / are” gelmez.', close: 2 },
  { t: 'Yalancı eş anlamlılar', code: 'vocab/false_friend', n: 4, trend: 0, weeks: [0, 1, 0, 1, 1, 0, 1], o: 'Our new neighbor is very sympathetic.', c: ['Our new neighbor is very ', 'friendly', '.'], note: '“sympathetic” = anlayışlı, halden anlayan. “Sempatik” için friendly / likeable.', close: 1 },
]

export const CAN_DO = [
  { ok: true, text: 'İşimi ve günlük rutinimi anlatabilirim.', note: 'Kanıt: 12 Eylül, serbest sohbet', lv: 'A2' },
  { ok: true, text: 'Bir restoranda sipariş verip isteklerimi belirtebilirim.', note: 'Kanıt: 26 Eylül, Restoran', lv: 'A2+' },
  { ok: false, text: 'Bir arkadaşıma adım adım yol tarifi verebilirim.', note: '2 / 3 sohbette görüldü', lv: 'B1' },
  { ok: false, text: 'Geçmiş bir deneyimi ayrıntılı anlatabilirim.', note: 'Present perfect / past simple ayrımı gerekli', lv: 'B1' },
  { ok: false, text: 'İş görüşmesinde fikrimi gerekçesiyle savunabilirim.', note: 'Henüz denenmedi', lv: 'B1' },
  { ok: false, text: 'Yavaş konuşulan bir sohbeti takip edebilirim.', note: 'Dinleme alıştırmalarında %64', lv: 'B1' },
]

export const CEFR_POINTS = [1.3, 1.34, 1.36, 1.42, 1.45, 1.44, 1.52, 1.58, 1.6, 1.66, 1.7, 1.74]
export const CEFR_LABELS = ['6 Tem', '', '20 Tem', '', '3 Ağu', '', '17 Ağu', '', '31 Ağu', '', '14 Eyl', '26 Eyl']
export const DAILY_MINUTES = [34, 22, 41, 30, 0, 18, 45, 0, 34, 36, 31, 52, 38, 18]
export const DAILY_LABELS = ['13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26']
