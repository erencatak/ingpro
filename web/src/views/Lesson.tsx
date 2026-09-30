import { Icon } from '../components/Icon'
import { markLessonSeen, useLesson, type GrammarTopic } from '../grammar/data'

const SOURCE_STATE = { 'page-read': 'sayfa okundu', 'search-snippet': 'arama özetinden' } as const

/** Pre-learning card: what the structure means, when to use it, one clue for speaking. Then straight to talking. */
export function Lesson({ topic, back }: { topic: GrammarTopic; back: () => void }) {
  const { card, loading } = useLesson(topic.id)
  const start = () => {
    markLessonSeen(topic.id)
    location.hash = `sohbet?topic=${topic.id}`
  }

  return (
    <div className="gr lesson">
      <div className="gr-crumbs">
        <button className="btn btn-ghost btn-sm" onClick={back}>← Konuya dön</button>
        <span className="muted num">Konu anlatımı</span>
      </div>

      {loading && <p className="muted" role="status">Konu anlatımı yükleniyor…</p>}
      {!loading && !card && (
        <article className="card">
          <p>Bu konu için doğrulanmış bir anlatım kartı yok. Yine de Alex'le konuşarak çalışabilirsin.</p>
          <div className="gr-actions"><button className="btn" onClick={start}>Konuşmaya başla<Icon name="send" /></button></div>
        </article>
      )}

      {card && (
        <>
          <article className="card lesson-head">
            <div className="gr-pills">
              <span className="pill pill-brand">≈ {Math.max(20, Math.round(card.read_seconds / 5) * 5)} sn okuma</span>
              {card.verified === 'medium' && <span className="pill pill-warn" title="Kaynak sayfası açılamadı, arama özetleriyle kontrol edildi">Orta güven</span>}
            </div>
            <h2>{card.title}</h2>
            <p className="muted tr">{card.title_tr}</p>
            <p className="lesson-focus">{card.focus}</p>
          </article>

          <article className="card lesson-sec">
            <h3>Ne demek?</h3>
            <p className="lesson-big">{card.meaning}</p>
          </article>

          <article className="card lesson-sec">
            <h3>Ne zaman kullanılır?</h3>
            <ul>{card.when_to_use.map((w) => <li key={w}>{w}</li>)}</ul>
          </article>

          <article className="card lesson-sec">
            <h3>Örnek</h3>
            <ul className="lesson-ex">
              {card.examples.map((e) => (
                <li key={e.en}><b lang="en">{e.en}</b><span className="muted">{e.tr}</span></li>
              ))}
            </ul>
          </article>

          <article className="card lesson-sec">
            <h3>Temel yapı</h3>
            <ul className="lesson-struct">{card.structure.map((x) => <li key={x} lang="en"><code>{x}</code></li>)}</ul>
          </article>

          <article className="card lesson-clue" aria-label="Konuşurken ipucu">
            <Icon name="bulb" />
            <div>
              <h3>Konuşurken ipucu</h3>
              <p>{card.speaking_clue}</p>
            </div>
          </article>

          <article className="card lesson-sec">
            <h3>Sık yapılan hata</h3>
            <ul className="lesson-mist">
              {card.common_mistakes.map((m) => (
                <li key={m.wrong}>
                  <span className="bad" lang="en">✗ {m.wrong}</span>
                  <span className="good" lang="en">✓ {m.right}</span>
                  <small className="muted">{m.why}</small>
                </li>
              ))}
            </ul>
          </article>

          <article className="card lesson-go">
            <div>
              <h3>Şimdi konuşalım</h3>
              <p className="muted">{card.speaking_scenario.note}</p>
              <p lang="en" className="lesson-opener">“{card.speaking_scenario.opener}”</p>
            </div>
            <button className="btn" onClick={start}>Konuşmaya başla<Icon name="send" /></button>
          </article>

          <details className="lesson-src">
            <summary>Kaynaklar ({card.sources.length}) · kontrol: {card.checked_on}</summary>
            <ul>
              {card.sources.map((s) => (
                <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.name}</a> <span className="muted">({SOURCE_STATE[s.checked]})</span></li>
              ))}
            </ul>
            <p className="muted">Cümleler ve açıklamalar bu kaynaklardaki kurallara göre yazıldı. Kaynaklarda desteği olmayan bir şey eklenmedi.</p>
          </details>
        </>
      )}
    </div>
  )
}
