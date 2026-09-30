import { Icon } from '../components/Icon'
import { useStats, type Stats } from '../data/useStats'

const MONTHS = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
const LEVELS = ['A1', 'A2', 'B1', 'B2']
const shortDate = (iso: string) => { const [, m, d] = iso.split('-').map(Number); return `${d} ${MONTHS[m - 1]}` }

function CefrChart({ curve }: { curve: Stats['curve'] }) {
  const W = 640, H = 280, L = 40, R = 40, T = 14, B = 30
  const top = Math.min(4, Math.max(2, Math.ceil(Math.max(...curve.map((p) => p.value)) + 0.25))) // zoom in while the learner is near the bottom
  const x = (i: number) => L + (i * (W - L - R)) / Math.max(curve.length - 1, 1)
  const y = (v: number) => T + ((top - v) / top) * (H - T - B)
  const d = curve.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join('')
  const last = curve.at(-1)!
  const lastX = x(curve.length - 1), lastY = y(last.value)
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Dilbilgisi seviyesi son ${curve.length} haftada: şu an ${LEVELS[Math.min(Math.floor(last.value), 3)]}`}>
      <defs>
        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--brand)" stopOpacity=".28" /><stop offset="1" stopColor="var(--brand)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {LEVELS.slice(0, top).map((n, i) => (
        <g key={n}>
          <rect className={i % 2 ? 'band-alt' : 'band'} x={L} y={y(i + 1)} width={W - L - R} height={y(i) - y(i + 1)} rx={6} />
          <text className="band-lbl" x={L - 10} y={(y(i) + y(i + 1)) / 2 + 4} textAnchor="end">{n}</text>
        </g>
      ))}
      <path className="area" d={`${d}L${lastX},${y(0)}L${x(0)},${y(0)}Z`} />
      <path className="line" d={d} />
      {curve.map((p, i) => (i % 2 === (curve.length - 1) % 2) && <text key={p.date} x={x(i)} y={H - 8} textAnchor="middle">{shortDate(p.date)}</text>)}
      {curve.map((p, i) => {
        const end = i === curve.length - 1
        return <circle key={p.date} className={end ? 'pt-end' : 'pt'} cx={x(i)} cy={y(p.value)} r={end ? 7 : 4}><title>{`${shortDate(p.date)}: ${LEVELS[Math.min(Math.floor(p.value), 3)]} (${p.value.toFixed(2)})`}</title></circle>
      })}
      <text className="end-lbl" x={lastX - 12} y={lastY - 14} textAnchor="end">{LEVELS[Math.min(Math.floor(last.value), 3)]}</text>
    </svg>
  )
}

function MinutesChart({ days, goal }: { days: Stats['days']; goal: number }) {
  const W = 720, H = 220, L = 34, R = 10, T = 16, B = 28
  const max = Math.max(60, Math.ceil(Math.max(...days.map((p) => p.minutes)) / 15) * 15)
  const bw = (W - L - R) / days.length, barW = bw - 10
  const y = (v: number) => T + (1 - v / max) * (H - T - B)
  const ticks = [0, 1, 2, 3, 4].map((k) => (max / 4) * k)
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Son ${days.length} günün pratik dakikaları, hedef ${goal} dakika`}>
      {ticks.map((v) => (
        <g key={v}><line className="grid-l" x1={L} x2={W - R} y1={y(v)} y2={y(v)} /><text x={L - 8} y={y(v) + 4} textAnchor="end">{Math.round(v)}</text></g>
      ))}
      {days.map((p, i) => {
        const v = Math.round(p.minutes)
        const x0 = L + i * bw + 5, h = y(0) - y(v), today = i === days.length - 1, r = Math.min(4, h)
        return (
          <g key={p.date}>
            {v > 0
              ? <path className={`bar-r ${today ? 'today' : v >= goal ? 'met' : ''}`} d={`M${x0},${y(0)} V${y(v) + r} Q${x0},${y(v)} ${x0 + r},${y(v)} H${x0 + barW - r} Q${x0 + barW},${y(v)} ${x0 + barW},${y(v) + r} V${y(0)} Z`}><title>{`${shortDate(p.date)}: ${v} dk`}</title></path>
              : <rect x={x0} y={y(0) - 2} width={barW} height={2} rx={1} fill="var(--line-strong)" />}
            <text x={x0 + barW / 2} y={H - 8} textAnchor="middle" style={today ? { fill: 'var(--text)', fontWeight: 800 } : undefined}>{today ? 'Bugün' : Number(p.date.slice(8))}</text>
          </g>
        )
      })}
      <line className="goal-l" x1={L} x2={W - R} y1={y(goal)} y2={y(goal)} />
      <text className="goal-t" x={W - R} y={y(goal) - 6} textAnchor="end">Hedef {goal} dk</text>
    </svg>
  )
}

export function Progress() {
  const { stats, error } = useStats()
  const last14 = stats?.days.slice(-14) ?? []
  const met = last14.filter((p) => p.minutes >= (stats?.goals.minutes ?? 30)).length
  const hasPoints = (stats?.curve.at(-1)?.value ?? 0) > 0
  const recent = stats?.approved.slice(0, 5) ?? []
  const next = stats?.next_unit
  return (
    <section className="view" aria-labelledby="h-progress">
      <div className="view-head">
        <div><h1 id="h-progress">İlerleme</h1><p>Haftalık özet ve seviye tahmini</p></div>
        {error && <span className="pill pill-bad">Sunucuya ulaşılamadı</span>}
      </div>
      {stats && (
        <>
          <div className="prog-grid">
            <article className="card">
              <div className="card-head"><div><h2>Dilbilgisi seviyesi</h2><p className="muted" style={{ fontSize: 13 }}>Konuşma puanlarından, haftalık</p></div><span className="pill pill-brand">Şu an {stats.level}</span></div>
              <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 460 }}><CefrChart curve={stats.curve} /></div></div>
              {!hasPoints && <p className="muted" style={{ fontSize: 13 }}>Henüz konuşma puanın yok. Bir ünite seçip Alex'le konuştukça eğri yükselir.</p>}
            </article>
            <article className="card">
              <div className="card-head"><h2>Onaylanan konular</h2><span className="pill num">{stats.approved.length} / {stats.units_total} ünite</span></div>
              <ul className="cando">
                {recent.map((u) => (
                  <li key={u.unit} className="ok">
                    <span className="cb"><Icon name="check" /></span>
                    <div><p>Ünite {u.unit} · {u.title}</p><small>Onaylandı: {shortDate(u.approved_at.slice(0, 10))} · {u.points} puan</small></div>
                    <span className="lv">{u.band}</span>
                  </li>
                ))}
                {next && (
                  <li>
                    <span className="cb"><Icon name="check" /></span>
                    <div><p>Ünite {next.unit} · {next.title}</p><small>Sıradaki · {next.points} / {next.required} konuşma puanı</small></div>
                    <span className="lv">sırada</span>
                  </li>
                )}
              </ul>
            </article>
          </div>
          <article className="card" style={{ marginTop: 'var(--s-5)' }}>
            <div className="card-head"><div><h2>Günlük dakika</h2><p className="muted" style={{ fontSize: 13 }}>Son 14 gün · hedef {stats.goals.minutes} dk</p></div><span className="pill pill-good num">Hedef tutan gün: {met} / 14</span></div>
            <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 520 }}><MinutesChart days={last14} goal={stats.goals.minutes} /></div></div>
          </article>
        </>
      )}
    </section>
  )
}
