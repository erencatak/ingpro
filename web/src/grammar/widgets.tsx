import { useEffect, useState, type CSSProperties } from 'react'
import type { TopicStatus } from './scoring'

const TAU = Math.PI * 2

/** Same ring as the daily goal on the Today screen (.ring-wrap), filled in after mount so it animates. */
export function Ring({ value, label, size = 140 }: { value: number; label: string; size?: number }) {
  const R = 58
  const C = TAU * R
  const [on, setOn] = useState(false)
  useEffect(() => {
    const id = requestAnimationFrame(() => setOn(true))
    return () => cancelAnimationFrame(id)
  }, [])
  return (
    <div className="ring-wrap" style={{ width: size, height: size }} role="img" aria-label={`${label} yüzde ${value}`}>
      <svg viewBox="0 0 132 132">
        <circle className="track" cx="66" cy="66" r={R} strokeWidth="12" />
        <circle className="ring-a" cx="66" cy="66" r={R} strokeWidth="12" strokeDasharray={C} strokeDashoffset={on ? C * (1 - value / 100) : C} />
      </svg>
      <div className="ring-center"><strong className="num">%{value}</strong><span>{label}</span></div>
    </div>
  )
}

/** Small ring on the topic cards. */
export function MiniRing({ value, done }: { value: number; done: boolean }) {
  const R = 15
  const C = TAU * R
  return (
    <svg className={`gr-mini ${done ? 'done' : ''}`} viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">
      <circle className="track" cx="20" cy="20" r={R} />
      <circle className="arc" cx="20" cy="20" r={R} strokeDasharray={C} strokeDashoffset={C * (1 - value / 100)} transform="rotate(-90 20 20)" />
    </svg>
  )
}

/** One tick per topic across the whole book: the entire roadmap in a single line. */
export function Timeline({ statuses, next }: { statuses: TopicStatus[]; next: number | null }) {
  return (
    <div className="gr-timeline" aria-hidden="true">
      {statuses.map((s, i) => (
        <i key={i} className={`${s} ${i + 1 === next ? 'next' : ''}`} style={{ '--i': i } as CSSProperties} />
      ))}
    </div>
  )
}
