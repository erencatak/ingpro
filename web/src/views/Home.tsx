import { useEffect, useMemo, useRef, useState } from 'react'
import { Icon } from '../components/Icon'
import type { ViewId } from '../components/useRoute'
import { useStats, type Stats } from '../data/useStats'

const WEEK_DAYS = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
const nf = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 1 })

const MONTHS = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']

// 26 Monday-first weeks ending this week; the days come from the server (minutes practised per day)
function useHeatmap(stats: Stats | null) {
  return useMemo(() => {
    const minutesOf = new Map((stats?.days ?? []).map((d) => [d.date, d.minutes]))
    const today = new Date()
    const end = new Date(today)
    end.setDate(today.getDate() + ((7 - today.getDay()) % 7)) // upcoming Sunday
    const weeks = 26
    const start = new Date(end)
    start.setDate(end.getDate() - weeks * 7 + 1)
    const cells: { level: number; label: string; hidden: boolean; today: boolean }[] = []
    const months: { col: number; name: string }[] = []
    for (let i = 0; i < weeks * 7; i++) {
      const d = new Date(start)
      d.setDate(start.getDate() + i)
      const age = Math.round((today.getTime() - d.getTime()) / 864e5)
      if (age < 0) { cells.push({ level: 0, label: '', hidden: true, today: false }); continue }
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      const mins = Math.round(minutesOf.get(key) ?? 0)
      const level = mins === 0 ? 0 : mins < 15 ? 1 : mins < 30 ? 2 : mins < 45 ? 3 : 4
      cells.push({ level, label: `${d.getDate()} ${MONTHS[d.getMonth()]}: ${mins ? `${mins} dk` : 'pratik yok'}`, hidden: false, today: age === 0 })
      if (i % 7 === 0 && d.getDate() <= 7) months.push({ col: i / 7 + 1, name: MONTHS[d.getMonth()] })
    }
    return { cells, months }
  }, [stats])
}

type Step = { title: string; sub: string; dur: string; icon: string; state: 'done' | 'now' | '' }

/** Today's plan from what is really due: reviews, the next unapproved unit, then the daily speaking goal. */
function planOf(st: Stats): Step[] {
  const reviews: Step = st.due_count > 0
    ? { title: 'Tekrar zamanı gelen konular', sub: `${st.due_count} konu · aralıklı tekrar`, dur: '~3 dk', icon: 'check', state: 'now' }
    : { title: 'Tekrarlar', sub: 'Zamanı gelen konu yok', dur: '', icon: 'check', state: 'done' }
  const unit: Step = st.next_unit
    ? { title: `Ünite ${st.next_unit.unit} · ${st.next_unit.title}`, sub: `${st.next_unit.points} / ${st.next_unit.required} konuşma puanı`, dur: '~10 dk', icon: 'target', state: st.due_count > 0 ? '' : 'now' }
    : { title: 'Tüm üniteler onaylandı', sub: 'Serbest sohbetle pekiştir', dur: '', icon: 'target', state: 'done' }
  const goalMet = st.today.minutes >= st.goals.minutes
  const talk: Step = { title: 'Günlük konuşma hedefi', sub: `Bugün ${nf.format(st.today.minutes)} / ${st.goals.minutes} dk`, dur: `${st.goals.minutes} dk`, icon: 'headset', state: goalMet ? 'done' : '' }
  return [reviews, unit, talk]
}

export function Home({ go }: { go: (v: ViewId) => void }) {
  const { stats, error } = useStats()
  const { cells, months } = useHeatmap(stats)
  const [animated, setAnimated] = useState(false)
  const heatScroll = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const id = requestAnimationFrame(() => setAnimated(true))
    if (heatScroll.current) heatScroll.current.scrollLeft = heatScroll.current.scrollWidth
    return () => cancelAnimationFrame(id)
  }, [])

  const st = stats
  const minutes = st?.today.minutes ?? 0
  const xp = st?.today.xp ?? 0
  const goalMin = st?.goals.minutes ?? 30
  const goalXp = st?.goals.xp ?? 200
  const plan = st ? planOf(st) : []
  const startPractice = () => {
    if (st?.next_unit) location.hash = `sohbet?topic=${st.next_unit.unit}`
    else go('chat')
  }
  const dateLabel = new Date().toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <section className="view" aria-labelledby="h-home">
      <div className="hello">
        <div>
          <p className="eyebrow">{dateLabel}</p>
          <h1 id="h-home">Merhaba!</h1>
          <p>Bugün Alex'le sohbet ederek başla, hatalarından ve kelimelerinden kişisel alıştırmalar çıkacak.</p>
        </div>
        <div className="stat-pills">
          {error && <span className="pill pill-bad">Sunucuya ulaşılamadı</span>}
          <span className="stat-pill"><span style={{ color: 'var(--brand)' }}>{st?.level ?? '–'}</span> <small>→ B2</small></span>
        </div>
      </div>

      <div className="home-grid">
        <article className="card plan">
          <div className="plan-top">
            <div>
              <p className="eyebrow">Bugünün planı</p>
              <h2>{st?.next_unit ? `Sıradaki: ${st.next_unit.title}` : 'Serbest pratik'}</h2>
              <p>Tekrar zamanı gelenlere, sıradaki üniteye ve günlük hedefine göre derlendi.</p>
            </div>
            <span className="pill pill-good num">{plan.filter((p) => p.state === 'done').length} / {plan.length} bitti</span>
          </div>
          <ol className="steps">
            {plan.map((s) => (
              <li key={s.title} className={`step ${s.state}`}>
                <span className="step-ic"><Icon name={s.icon as never} /></span>
                <div><h3>{s.title}</h3><p>{s.sub}</p></div>
                <span className="dur num">{s.dur}</span>
              </li>
            ))}
          </ol>
          <div className="plan-cta">
            <button className="btn btn-lg" onClick={startPractice}>
              <Icon name="play" size="lg" style={{ fill: 'currentColor', stroke: 'none' }} />{st?.next_unit ? `Ünite ${st.next_unit.unit} ile konuş` : 'Sohbete başla'}
            </button>
            <p>Plan önerir, zorlamaz. İstersen doğrudan <a href="#sohbet">serbest sohbete</a> da geçebilirsin.</p>
          </div>
        </article>

        <div className="side-stack">
          <article className="card">
            <div className="card-head"><h2>Günlük hedef</h2><span className="pill num">{goalMin} dk · {goalXp} XP</span></div>
            <div className="goal">
              <div className="ring-wrap" role="img" aria-label={`Bugün ${nf.format(minutes)} / ${goalMin} dakika, ${xp} / ${goalXp} XP`}>
                <svg viewBox="0 0 132 132">
                  <circle className="track" cx="66" cy="66" r="58" strokeWidth="12" />
                  <circle className="ring-a" cx="66" cy="66" r="58" strokeWidth="12" strokeDasharray="364.4" strokeDashoffset={animated ? 364.4 * (1 - Math.min(minutes / goalMin, 1)) : 364.4} />
                  <circle className="track" cx="66" cy="66" r="40" strokeWidth="10" />
                  <circle className="ring-b" cx="66" cy="66" r="40" strokeWidth="10" strokeDasharray="251.3" strokeDashoffset={animated ? 251.3 * (1 - Math.min(xp / goalXp, 1)) : 251.3} />
                </svg>
                <div className="ring-center"><strong className="num">{nf.format(minutes)}</strong><span>/ {goalMin} dk</span></div>
              </div>
              <div className="goal-legend">
                <div className="legend-row"><i style={{ background: 'var(--brand)' }} /><span><b className="num">{nf.format(minutes)}</b> / {goalMin} dk pratik</span></div>
                <div className="legend-row"><i style={{ background: 'var(--xp)' }} /><span><b className="num">{xp}</b> / {goalXp} XP</span></div>
              </div>
            </div>
          </article>
          <article className="card">
            <div className="card-head"><h2>Bu hafta</h2><span className={`pill ${st && st.streak > 0 ? 'pill-warn' : ''} num`}>{st?.streak ?? 0} gün seri</span></div>
            <div className="week">
              {WEEK_DAYS.map((d, i) => {
                const s = st?.week[i]?.state ?? ''
                return (
                <div key={d} className={`day ${s}`}>
                  <span className="dot">
                    {s === 'on' && <Icon name="check" size="sm" style={{ strokeWidth: 3 }} />}
                    {s === 'today' && <Icon name="flame-o" size="sm" style={{ fill: 'currentColor', stroke: 'none' }} />}
                  </span>
                  {d}
                </div>
                )
              })}
            </div>
          </article>
        </div>
      </div>

      <div className="row-2">
        <article className="card">
          <div className="card-head"><h2>Aktivite</h2><span className="muted num" style={{ fontSize: 13 }}>Son 26 hafta</span></div>
          <div className="heat-wrap">
            <div className="heat-days" aria-hidden="true"><span>Pzt</span><span /><span>Çar</span><span /><span>Cum</span><span /><span>Paz</span></div>
            <div className="heat-scroll" ref={heatScroll}>
              <div className="heat-months">{months.map((m) => <span key={m.col} style={{ gridColumn: m.col }}>{m.name}</span>)}</div>
              <div className="heat" role="img" aria-label="Son 26 haftanın günlük pratik yoğunluğu">
                {cells.map((c, i) => (
                  <i key={i} data-l={c.level || undefined} className={c.today ? 'today' : undefined} style={c.hidden ? { visibility: 'hidden' } : undefined} title={c.label} />
                ))}
              </div>
            </div>
          </div>
          <div className="heat-foot">
            <span className="heat-scale">Az {[0, 1, 2, 3, 4].map((l) => <i key={l} style={{ background: `var(--heat-${l})` }} />)} Çok</span>
          </div>
        </article>
        <article className="card">
          <div className="card-head"><h2>Beceriler</h2><span className="pill pill-brand">Hedef B2</span></div>
          <div className="skills">
            {(st?.skills ?? []).map(({ name, level, value }) => (
              <div key={name}>
                <div className="skill-top"><span>{name}</span><span className="lvl" title={level ? undefined : 'Bu beceri henüz ölçülmüyor'}>{level ?? 'Ölçülmedi'}</span></div>
                <div className="cefr-track" role="img" aria-label={level ? `${name}: ${level}, hedef B2` : `${name}: henüz ölçülmüyor`}>
                  <span /><span /><span /><span />
                  <i className="cefr-fill" style={{ width: animated && value !== null ? `${(value / 4) * 100}%` : 0 }} />
                </div>
                <div className="cefr-labels"><span>A1</span><span>A2</span><span>B1</span><span>B2</span></div>
              </div>
            ))}
          </div>
          <div className="hours">
            <div className="hours-num"><strong className="num">{nf.format(st?.hours_total ?? 0)}</strong><span>/ {st?.goals.hours ?? 400} saat</span></div>
            <div className="bar"><i style={{ width: `${Math.min(((st?.hours_total ?? 0) / (st?.goals.hours ?? 400)) * 100, 100)}%` }} /></div>
          </div>
        </article>
      </div>
    </section>
  )
}

