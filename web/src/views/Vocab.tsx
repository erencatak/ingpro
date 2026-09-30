import { useEffect, useState } from 'react'
import { DemoBadge } from '../components/DemoBadge'
import { Icon } from '../components/Icon'
import { CARDS, WORDS } from '../data/mock'

const RATES = [
  { key: 'again', label: 'Tekrar', next: '<10 dk', toast: 'Tekrar · 10 dk sonra' },
  { key: 'hard', label: 'Zor', next: '1 gün', toast: 'Zor · yarın' },
  { key: 'good', label: 'İyi', next: '3 gün', toast: 'İyi · 3 gün sonra' },
  { key: 'easy', label: 'Kolay', next: '8 gün', toast: 'Kolay · 8 gün sonra' },
] as const

const STATUS_PILL: Record<string, string> = { Biliniyor: 'pill-good', Öğreniliyor: 'pill-warn', 'Bugün tekrar': 'pill-brand', Yeni: '' }
// "genel" ve "daily" iki geniş deste: mesleğe özel kelime önerisi ileride ayrı bir AI destekli özellik olarak eklenecek.
const FILTERS = [['all', 'Tümü'], ['genel', 'Genel'], ['daily', 'Günlük'], ['convo', 'Sohbetten']] as const

export function Vocab() {
  const [ci, setCi] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [left, setLeft] = useState(14)
  const [toast, setToast] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>('all')
  const card = CARDS[ci % CARDS.length]

  const rate = (r: (typeof RATES)[number]) => {
    if (!flipped) return
    setToast(r.toast)
    if (r.key !== 'again') setLeft((l) => Math.max(0, l - 1))
    setFlipped(false)
    setTimeout(() => setCi((c) => c + 1), 250)
  }

  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 2000)
    return () => clearTimeout(id)
  }, [toast])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (/INPUT|TEXTAREA/.test((e.target as HTMLElement).tagName)) return
      if (e.code === 'Space' && (e.target as HTMLElement).tagName !== 'BUTTON') { e.preventDefault(); setFlipped((f) => !f) }
      if (['1', '2', '3', '4'].includes(e.key) && flipped) rate(RATES[Number(e.key) - 1])
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const q = query.trim().toLocaleLowerCase('tr')
  const rows = WORDS.filter(([w, m, deck, conv]) => (filter === 'all' || (filter === 'convo' ? conv : deck === filter)) && (!q || w.includes(q) || m.toLocaleLowerCase('tr').includes(q)))

  return (
    <section className="view" aria-labelledby="h-vocab">
      <div className="view-head">
        <div><h1 id="h-vocab">Kelimeler</h1><p>Genel ve Günlük desteleri</p></div>
        <DemoBadge />
      </div>
      <div className="tiles">
        <div className="tile"><div className="t-top"><i style={{ background: 'var(--mint)' }} />Yeni</div><strong className="num">10</strong><small>bugünkü limit</small></div>
        <div className="tile"><div className="t-top"><i style={{ background: 'var(--warn)' }} />Öğreniliyor</div><strong className="num">23</strong><small>kısa aralıkta</small></div>
        <div className="tile"><div className="t-top"><i style={{ background: 'var(--brand)' }} />Bugün tekrar</div><strong className="num">{left}</strong><small>~6 dk</small></div>
        <div className="tile"><div className="t-top"><i style={{ background: 'var(--good)' }} />Biliniyor</div><strong className="num">186</strong><small>+12 bu hafta</small></div>
      </div>
      <div className="vocab-grid">
        <div className="card review">
          <div className="review-head"><h2>Tekrar</h2><span className="pill pill-brand num">{left} kart kaldı</span></div>
          <button className={`flip ${flipped ? 'flipped' : ''}`} onClick={() => setFlipped((f) => !f)} aria-label="Kartı çevir">
            <span className="flip-in">
              <span className="face-card front">
                <span className="pill pill-brand">{card.pos}</span>
                <span className="word en">{card.w}</span>
                <span className="ipa">{card.ipa}</span>
                <span className="tap"><Icon name="vol" size="sm" />Çevirmek için dokun</span>
              </span>
              <span className="face-card back">
                <span className="eyebrow">{card.w} · {card.pos}</span>
                <span className="tr">{card.tr}</span>
                <span className="ex en">{card.ex[0]}<b>{card.ex[1]}</b>{card.ex[2]}</span>
                <span className="from-convo">
                  <span className="eyebrow"><Icon name="chat" size="sm" />Sohbetinden</span>
                  <span className="en" style={{ fontWeight: 600 }}>{card.convo}</span><br />
                  <span className="muted" style={{ fontSize: 12 }}>{card.src}</span>
                </span>
              </span>
            </span>
          </button>
          <div className="rates" aria-disabled={!flipped}>
            {RATES.map((r) => (
              <button key={r.key} className={`btn rate rate-${r.key}`} onClick={() => rate(r)}>{r.label}<small className="num">{r.next}</small></button>
            ))}
          </div>
          <p className="muted" style={{ fontSize: 13, textAlign: 'center' }}><kbd>Space</kbd> çevir · <kbd>1</kbd>–<kbd>4</kbd> puanla</p>
        </div>

        <div className="card">
          <div className="card-head"><h2>Tüm kelimeler</h2><span className="muted num" style={{ fontSize: 13 }}>{rows.length} / {WORDS.length}</span></div>
          <div className="search">
            <Icon name="search" />
            <label htmlFor="wSearch" className="sr">Kelime ara</label>
            <input id="wSearch" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ara: İngilizce veya Türkçe" autoComplete="off" />
          </div>
          <div className="filters">
            {FILTERS.map(([key, label]) => <button key={key} className="chip" aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}
          </div>
          <ul className="wlist">
            {rows.length ? rows.map(([w, m, deck, conv, status, nextReview]) => (
              <li key={w}>
                <span className="w en">{w}{conv ? <Icon name="chat" size="sm" style={{ color: 'var(--brand)', verticalAlign: -3, marginLeft: 6 }} /> : null}</span>
                <span className="m">{m}</span>
                <span className="st">
                  <span className={`pill ${STATUS_PILL[status]}`} style={{ padding: '3px 9px', fontSize: 11.5 }}>{status}</span>
                  <small>{deck === 'genel' ? 'Genel' : 'Günlük'} · {nextReview}</small>
                </span>
              </li>
            )) : <li className="empty" style={{ display: 'block' }}>“{query}” için sonuç yok. Sohbette kullanırsan otomatik eklenir.</li>}
          </ul>
        </div>
      </div>
      {toast && <div className="toast show" role="status">{toast}</div>}
    </section>
  )
}
