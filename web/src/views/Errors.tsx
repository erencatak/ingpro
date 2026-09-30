import { DemoBadge } from '../components/DemoBadge'
import { Icon } from '../components/Icon'
import type { ViewId } from '../components/useRoute'
import { ERRORS } from '../data/mock'

function Spark({ values }: { values: number[] }) {
  const w = 120, h = 36, max = Math.max(...values, 1), bw = 12
  const gap = (w - bw * values.length) / (values.length - 1)
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      {values.map((v, i) => {
        const bh = Math.max(3, (v / max) * (h - 2))
        return <rect key={i} x={i * (bw + gap)} y={h - bh} width={bw} height={bh} rx={3} fill={i === values.length - 1 ? 'var(--brand)' : 'var(--surface-3)'} />
      })}
    </svg>
  )
}

export function Errors({ go }: { go: (v: ViewId) => void }) {
  return (
    <section className="view" aria-labelledby="h-errors">
      <div className="view-head">
        <div><h1 id="h-errors">Hata bankası</h1><p>Sohbetlerinden yakalanan hatalar. Aynı hatayı 3 farklı gün doğru yapınca kapanır.</p></div>
        <DemoBadge />
      </div>
      <div className="err-list">
        {ERRORS.map((e) => (
          <article key={e.code} className="card err">
            <div className="err-top">
              <div><h3>{e.t}</h3><code>{e.code}</code></div>
              {e.trend < 0 ? <span className="pill pill-good"><Icon name="down" size="sm" />%{-e.trend} azaldı</span>
                : e.trend > 0 ? <span className="pill pill-bad"><Icon name="up" size="sm" />%{e.trend} arttı</span>
                : <span className="pill">Sabit</span>}
            </div>
            <div className="err-freq">
              <div><strong className="num">{e.n}</strong><small>kez · son 30 gün</small></div>
              <Spark values={e.weeks} />
            </div>
            <div className="pair en">
              <span className="o"><span className="tag">✕</span><s>{e.o}</s></span>
              <span className="c"><span className="tag">✓</span><span>{e.c.map((part, i) => (i % 2 ? <u key={i}>{part}</u> : part))}</span></span>
            </div>
            <p className="err-note">{e.note}</p>
            <div className="err-foot">
              <span className="close-dots" title="Kapanması için 3 farklı gün doğru kullanım">
                {[0, 1, 2].map((i) => <i key={i} className={i < e.close ? 'on' : ''} />)} {e.close}/3 gün doğru
              </span>
              <button className="btn btn-sm" onClick={() => go('practice')}>Bunu çalış</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
