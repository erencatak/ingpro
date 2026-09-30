import { useEffect, useMemo, useState } from 'react'
import { DemoBadge } from '../components/DemoBadge'
import { Icon } from '../components/Icon'
import type { ViewId } from '../components/useRoute'
import { EXERCISES } from '../data/mock'

const CONFETTI = ['#B9A0FF', '#FFD166', '#5CD6A0', '#FF8391', '#6FE3C8', '#F3A6E8', '#FF9F43']

function Confetti() {
  const pieces = useMemo(
    () =>
      Array.from({ length: 90 }, (_, i) => ({
        left: Math.random() * 100,
        color: CONFETTI[i % CONFETTI.length],
        x: Math.random() * 200 - 100,
        r: Math.random() * 900 + 180,
        d: 2.2 + Math.random() * 1.8,
        dl: Math.random() * 0.5,
        round: i % 3 === 0,
      })),
    [],
  )
  return (
    <div className="confetti" aria-hidden="true">
      {pieces.map((p, i) => (
        <i
          key={i}
          style={{
            left: `${p.left}%`, background: p.color,
            ['--x' as string]: `${p.x}px`, ['--r' as string]: `${p.r}deg`, ['--d' as string]: `${p.d}s`, ['--dl' as string]: `${p.dl}s`,
            ...(p.round ? { width: 8, height: 8, borderRadius: '50%' } : {}),
          }}
        />
      ))}
    </div>
  )
}

// Word-bank chips are shuffled deterministically so the exercise is stable across renders
const shuffle = (words: string[]) => words.map((w, i) => ({ w, i })).sort((a, b) => ((a.i * 7) % 11) - ((b.i * 7) % 11))

export function Practice({ go }: { go: (v: ViewId) => void }) {
  const [idx, setIdx] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [order, setOrder] = useState<number[]>([])
  const [cloze, setCloze] = useState('')
  const [result, setResult] = useState<'good' | 'bad' | null>(null)
  const [correct, setCorrect] = useState(0)
  const [combo, setCombo] = useState(0)
  const [done, setDone] = useState(false)

  const ex = EXERCISES[idx]
  const answered = result !== null
  const canCheck = ex && (ex.type === 'mc' ? selected !== null : ex.type === 'order' ? order.length > 0 : cloze.trim() !== '')

  const reset = () => { setSelected(null); setOrder([]); setCloze(''); setResult(null) }
  const restart = () => { reset(); setIdx(0); setCorrect(0); setCombo(0); setDone(false) }

  const check = () => {
    let ok = false
    if (ex.type === 'mc') ok = selected === ex.answer
    if (ex.type === 'order') ok = order.map((i) => ex.words[i]).join(' ') === ex.answer
    if (ex.type === 'cloze') ok = ex.answer.includes(cloze.trim().toLowerCase())
    setResult(ok ? 'good' : 'bad')
    setCorrect((c) => c + (ok ? 1 : 0))
    setCombo((c) => (ok ? c + 1 : 0))
  }

  const next = () => {
    reset()
    if (idx + 1 >= EXERCISES.length) setDone(true)
    else setIdx(idx + 1)
  }

  const skip = () => { setCombo(0); next() }

  useEffect(() => {
    if (done) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Enter' || /BUTTON/.test((e.target as HTMLElement).tagName)) return
      if (answered) next()
      else if (canCheck) check()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (done) {
    const acc = Math.round((correct / EXERCISES.length) * 100)
    return (
      <section className="view" aria-labelledby="h-practice">
        <Confetti />
        <div className="lesson-done">
          <div className="trophy"><Icon name="trophy" /></div>
          <div>
            <h1 id="h-practice">Ders tamamlandı!</h1>
            <p style={{ marginTop: 8 }}>Örnek ders bitti. Gerçek alıştırmalar hatalarından ve sohbetlerinden üretilecek.</p>
          </div>
          <div className="done-stats">
            <div className="dstat" style={{ ['--c' as string]: 'var(--xp)', ['--ci' as string]: '#3A2600' }}><div className="h">Toplam XP</div><div className="v num"><Icon name="bolt" style={{ fill: 'var(--xp)', stroke: 'none' }} />+{correct * 10 + (acc === 100 ? 15 : 5)}</div></div>
            <div className="dstat" style={{ ['--c' as string]: 'var(--good)', ['--ci' as string]: 'var(--good-ink)' }}><div className="h">Doğruluk</div><div className="v num">{acc}%</div></div>
            <div className="dstat" style={{ ['--c' as string]: 'var(--brand)', ['--ci' as string]: 'var(--brand-ink)' }}><div className="h">Soru</div><div className="v num">{EXERCISES.length}</div></div>
          </div>
          <div className="done-actions">
            <button className="btn btn-ghost" onClick={restart}><Icon name="refresh" />Tekrar yap</button>
            <button className="btn" onClick={() => go('chat')}>Sohbete geç</button>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="view" aria-labelledby="h-practice">
      <h1 id="h-practice" className="sr">Alıştırma</h1>
      <div className="lesson">
        <div className="lesson-top">
          <button className="icon-btn" onClick={() => go('home')} aria-label="Dersten çık"><Icon name="x" /></button>
          <div className="bar" role="progressbar" aria-label="Ders ilerlemesi" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((idx / EXERCISES.length) * 100)}>
            <i style={{ width: `${Math.max(4, (idx / EXERCISES.length) * 100)}%` }} />
          </div>
          <span className="combo num" title="Üst üste doğru"><Icon name="flame-o" style={{ fill: 'var(--flame)', stroke: 'none' }} /><span>{combo}</span></span>
          <DemoBadge />
        </div>

        <div key={idx} style={{ animation: 'viewIn .4s var(--ease) both' }}>
          <p className="ex-kicker"><Icon name="sparkle" size="sm" />{ex.kicker}</p>
          <h2 className="ex-title">{ex.title}</h2>

          {ex.type === 'mc' && (
            <>
              <div className="ex-prompt"><span className="av av-alex" /><div className="speech en">{ex.prompt}</div></div>
              <div className="options" role="radiogroup" style={{ marginTop: 'var(--s-6)' }}>
                {ex.options.map((o, i) => (
                  <button
                    key={o} role="radio" aria-checked={selected === i}
                    className={`opt ${answered && i === ex.answer ? 'is-good' : ''} ${answered && selected === i && i !== ex.answer ? 'is-bad' : ''}`}
                    onClick={() => !answered && setSelected(i)}
                  >
                    <span className="k">{i + 1}</span><span>{o}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          {ex.type === 'order' && (
            <>
              <div className="ex-prompt"><span className="av av-alex" /><div className="speech">{ex.tr}</div></div>
              <div className="answer-line" style={{ marginTop: 'var(--s-6)' }}>
                {order.map((i) => (
                  <button key={i} className="wchip en" onClick={() => !answered && setOrder(order.filter((x) => x !== i))}>{ex.words[i]}</button>
                ))}
              </div>
              <div className="bank" style={{ marginTop: 'var(--s-6)' }}>
                {shuffle(ex.words).map(({ w, i }) => (
                  <button key={i} className={`wchip en ${order.includes(i) ? 'used' : ''}`} onClick={() => !answered && !order.includes(i) && setOrder([...order, i])}>{w}</button>
                ))}
              </div>
            </>
          )}

          {ex.type === 'cloze' && (
            <>
              <div className="cloze en" style={{ marginTop: 'var(--s-6)' }}>
                {ex.before} <label className="sr" htmlFor="clozeIn">Boşluk</label>
                <input id="clozeIn" autoFocus autoComplete="off" autoCapitalize="off" spellCheck={false} readOnly={answered} value={cloze} onChange={(e) => setCloze(e.target.value)} /> {ex.after}
              </div>
              <p className="hint" style={{ marginTop: 'var(--s-4)' }}><Icon name="bulb" size="sm" />{ex.hint}</p>
            </>
          )}
        </div>
      </div>

      <div className="sheet" data-fb={result ?? undefined}>
        <div className="sheet-in">
          <div className="fb fb-good"><span className="fb-ic"><Icon name="check" /></span><div><h3>Harika!</h3><p>{ex.good}</p></div></div>
          <div className="fb fb-bad"><span className="fb-ic"><Icon name="x" /></span><div><h3>Doğru cevap:</h3><p>{ex.bad}</p></div></div>
          <button className="btn btn-ghost skip" onClick={skip}>Atla</button>
          <button className={`btn ${result === 'good' ? 'btn-good' : result === 'bad' ? 'btn-bad' : ''}`} disabled={!answered && !canCheck} onClick={answered ? next : check}>
            {answered ? 'Devam' : 'Kontrol et'}
          </button>
        </div>
      </div>
    </section>
  )
}
