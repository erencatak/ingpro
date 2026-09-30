import { useEffect, useState } from 'react'

export interface Skill { name: string; value: number | null; level: string | null }
export interface Stats {
  today: { minutes: number; xp: number }
  goals: { minutes: number; xp: number; hours: number }
  days: { date: string; minutes: number; xp: number }[]
  week: { date: string; state: '' | 'on' | 'today' }[]
  streak: number
  hours_total: number
  skills: Skill[]
  level: string
  curve: { date: string; value: number }[]
  approved: { unit: number; title: string; approved_at: string; points: number; band: string }[]
  units_total: number
  next_unit: { unit: number; title: string; points: number; required: number } | null
  due_count: number
  xp_total: number
}

/** The learner's real numbers (server/src/ingpro/stats.py); reloads when the tab comes back, like the grammar map does. */
export function useStats() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    const load = () =>
      fetch('/api/stats')
        .then((r) => (r.ok ? (r.json() as Promise<Stats>) : Promise.reject()))
        .then((d) => { setStats(d); setError(false) })
        .catch(() => setError(true))
    void load()
    const again = () => document.visibilityState === 'visible' && void load()
    document.addEventListener('visibilitychange', again)
    return () => document.removeEventListener('visibilitychange', again)
  }, [])
  return { stats, error }
}
