import { Icon } from '../components/Icon'

import { REQUIRED_TEXT, RULES } from './pointRules'

interface Meter {
  points: number
  required: number
  band?: string
  approved: boolean
  correct_uses?: number
  min_correct?: number
}

/** Progress of a unit towards its approval. */
export function PointsMeter({ unit }: { unit: Meter | null }) {
  if (!unit) return null
  const pct = Math.min(100, Math.round((unit.points / unit.required) * 100))
  return (
    <div className="gr-meter">
      <div className="gr-meter-top">
        <strong className="num">{unit.points} <small>/ {unit.required} puan</small></strong>
        {unit.approved ? <span className="pill pill-good"><Icon name="check" size="sm" />Onaylı</span> : <span className="muted num">%{pct}</span>}
      </div>
      <div className="bar" role="progressbar" aria-valuenow={unit.points} aria-valuemin={0} aria-valuemax={unit.required}>
        <i style={{ width: `${pct}%`, background: unit.approved ? 'var(--good)' : undefined }} />
      </div>
      {!unit.approved && (
        <small className="muted">
          {unit.points < unit.required
            ? `Onaya ${unit.required - unit.points} puan kaldı`
            : `Puan tamam. Onay için konunun gramerini doğru kullandığın ${Math.max(0, (unit.min_correct ?? 0) - (unit.correct_uses ?? 0))} cümle daha gerekli.`}
        </small>
      )}
    </div>
  )
}

export function RuleLegend({ vocabLevel = 'A1' }: { vocabLevel?: string }) {
  return (
    <div className="gr-rules">
      <ul>
        {RULES.map((r) => (
          <li key={r.rule}><b className={`num pts p${r.points}`}>{r.points}</b><span>{r.text}</span></li>
        ))}
      </ul>
      <small className="muted">
        {REQUIRED_TEXT} Ayrıca konunun gramerini doğru kullandığın en az 3 cümle gerekir.
        <b> Yeni kelime:</b> şu an {vocabLevel} seviyesindeki (temel) kelimelerden, doğru gramerle 3 kereden az kullandıkların. Daha üst seviye kelimeler ilerledikçe açılır; onları kullanabilirsin ama yeni sayılmazlar.
        Sesli ve net söylenmiş İngilizce cümleler sayılır; yazılı mesaj, Türkçe konuşma ve aynı cümlenin tekrarı puan vermez.
      </small>
    </div>
  )
}

interface Usage {
  valid: boolean
  rule: number | null
  points: number
  reason: string
  spoken?: boolean
  new_words?: string[]
  feedback_tr?: string
  correction?: string | null
}

/** Under a spoken sentence: what it earned and why. */
/** `refresher` (the lesson card's one line) shows only when the sentence needed a correction. */
export function UsageNote({ u, refresher }: { u?: Usage; refresher?: string }) {
  if (!u) return <div className="bubble-meta">Puanlanıyor…</div>
  if (u.spoken === false) return null // typed messages (also the Turkish help box) are not scored: no note
  const label = RULES.find((r) => r.rule === u.rule)?.text
  return (
    <div className={`gr-usage ${u.valid ? '' : 'off'}`}>
      {u.valid ? (
        <>
          <span className={`pts-badge p${u.points}`}>+{u.points} puan</span>
          <span className="muted">{label}</span>
          {u.new_words && u.new_words.length > 0 && <span className="muted">· yeni kelime: <b>{u.new_words.join(', ')}</b></span>}
        </>
      ) : (
        <span className="muted">{u.reason}</span>
      )}
      {u.valid && u.feedback_tr && <p>{u.feedback_tr}</p>}
      {u.valid && u.correction && <p className="fix">Düzeltme: <i>{u.correction}</i></p>}
      {u.valid && u.correction && refresher && <p className="muted">Hatırlatma: {refresher}</p>}
    </div>
  )
}
