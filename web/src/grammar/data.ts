import { useCallback, useEffect, useMemo, useState } from 'react'

export interface GrammarSubtopic {
  id: string
  title: string
  /** Turkish name, when the book gives one */
  tr?: string
  /** The book's own label, e.g. "1.A" */
  code?: string
  kind?: 'exercises' | 'guide'
}

export interface GrammarTopic {
  id: number
  title: string
  /** CEFR band of the unit, decides how many speaking points approve it */
  band?: string
  /** Turkish name of the topic, when the book gives one */
  tr?: string
  /** Page where the unit starts in the book */
  page?: number
  /** Short tag shown instead of the number, for sections outside the 46 units ("E1") */
  label?: string
  /** Extra sections only: whether it is shown on the roadmap */
  roadmap?: boolean
  /** A pre-learning card exists for this unit */
  has_lesson?: boolean
  subtopics: GrammarSubtopic[]
}

export interface GrammarCourse {
  source: string
  /** false while the list is the placeholder sample, not the book's real table of contents */
  verified: boolean
  topics: GrammarTopic[]
  /** Unnumbered sections of the book (pronunciation, common errors, readings…) */
  extras?: GrammarTopic[]
}

export type Stage = 'uyuyan' | 'kodlama' | 'kisa_sureli' | 'pekisme' | 'uzun_sureli'
export const STAGE_LABEL: Record<Stage, string> = {
  uyuyan: 'Uyuyan',
  kodlama: 'Kodlama',
  kisa_sureli: 'Kısa süreli bellek',
  pekisme: 'Pekişme',
  uzun_sureli: 'Uzun süreli bellek',
}

/** What the brain knows about one subtopic (neuron): mastery 0-100, its memory stage and when it should be tested next. */
export interface SubtopicProgress {
  score: number
  /** retrievals + re-readings */
  attempts: number
  /** real recall attempts (the testing effect: only these build durable memory) */
  retrievals?: number
  stage?: Stage
  dueAt?: string | null
  due?: boolean
  stability?: number
}
export type GrammarProgress = Record<string, SubtopicProgress>

export function useGrammarCourse() {
  const [course, setCourse] = useState<GrammarCourse | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    fetch('/api/grammar')
      .then((r) => (r.ok ? (r.json() as Promise<GrammarCourse>) : Promise.reject()))
      .then(setCourse)
      .catch(() => setError(true))
  }, [])
  return { course, error }
}

/** Pre-learning card (konu anlatımı): a 30-60 second read, checked against the sources it lists. */
export interface LessonCard {
  unit: number
  title: string
  title_tr: string
  focus: string
  meaning: string
  when_to_use: string[]
  examples: { en: string; tr: string }[]
  structure: string[]
  speaking_clue: string
  common_mistakes: { wrong: string; right: string; why: string }[]
  speaking_scenario: { opener: string; note: string }
  /** One line for the chat and review screens */
  refresher: string
  sources: { name: string; url: string; checked: 'page-read' | 'search-snippet' }[]
  read_seconds: number
  /** high: a source page was read; medium: only search results were available */
  verified: 'high' | 'medium'
  checked_on: string
}

const SEEN_KEY = 'ingpro.lessonsSeen'
function seenSet(): Set<number> {
  try { return new Set<number>(JSON.parse(localStorage.getItem(SEEN_KEY) ?? '[]')) } catch { return new Set() }
}
/** Remembered per browser only: it decides whether "Alex'le çalış" shows the card first, nothing else. */
export const lessonSeen = (unit: number) => seenSet().has(unit)
export function markLessonSeen(unit: number) {
  try { localStorage.setItem(SEEN_KEY, JSON.stringify([...seenSet().add(unit)])) } catch { /* private window: the card just shows again */ }
}

export function useLesson(unit: number | null) {
  const [got, setGot] = useState<{ unit: number; card: LessonCard | null } | null>(null)
  useEffect(() => {
    if (unit === null) return
    let live = true
    fetch(`/api/grammar/lesson/${unit}`)
      .then((r) => (r.ok ? (r.json() as Promise<LessonCard>) : null))
      .catch(() => null)
      .then((card) => { if (live) setGot({ unit, card }) })
    return () => { live = false }
  }, [unit])
  const ready = got !== null && got.unit === unit // never show the previous unit's card
  return { card: ready ? got.card : null, loading: unit !== null && !ready }
}

export interface ReviewResult {
  sub_id: string
  score: number
  stage: Stage
  stage_label: string
  promoted: boolean
  interval_days: number
  due_at: string
  xp: number
  confusion_partners: { sub_id: string; title: string; weight: number; reason: string | null }[]
}
export interface ExposeResult {
  sub_id: string
  score: number
  stage: Stage
  stage_label: string
  xp: number
}

/** Speaking points of a unit and its approval (A1-A2: 30 points, B1-B2: 60, C1: 90). */
export interface UnitProgress {
  points: number
  required: number
  band: string
  approved: boolean
  approved_at: string | null
  /** sentences that used the target grammar correctly, and how many a unit needs whatever its points */
  correct_uses: number
  min_correct: number
}

interface BrainSnapshot {
  xp: number
  due_count: number
  units: Record<string, UnitProgress>
  /** highest word level that currently counts as a "new" word (opens up with progress) */
  vocab_level?: string
  neurons: Record<string, { score: number; stage: Stage; attempts: number; retrievals: number; stability: number; due_at: string | null; due: boolean }>
}

/** Progress lives in the server's brain (SQLite), which mirrors it into the Obsidian vault. */
export function useBrain() {
  const [snap, setSnap] = useState<BrainSnapshot | null>(null)
  const [error, setError] = useState(false)

  const load = useCallback(
    () =>
      fetch('/api/brain/progress')
        .then((r) => (r.ok ? (r.json() as Promise<BrainSnapshot>) : Promise.reject()))
        .then((d) => {
          setSnap(d)
          setError(false)
        })
        .catch(() => setError(true)),
    [],
  )

  useEffect(() => {
    void load()
    const again = () => document.visibilityState === 'visible' && void load() // a test may have come due while the tab was hidden
    document.addEventListener('visibilitychange', again)
    return () => document.removeEventListener('visibilitychange', again)
  }, [load])

  const progress = useMemo<GrammarProgress>(
    () =>
      Object.fromEntries(
        Object.entries(snap?.neurons ?? {}).map(([id, n]) => [
          id,
          { score: n.score, attempts: n.attempts, retrievals: n.retrievals, stage: n.stage, dueAt: n.due_at, due: n.due, stability: n.stability },
        ]),
      ),
    [snap],
  )

  const post = useCallback(
    async <T,>(path: string, body: object): Promise<T> => {
      const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!r.ok) throw new Error(await r.text())
      const result = (await r.json()) as T
      await load()
      return result
    },
    [load],
  )

  return {
    progress,
    units: snap?.units ?? ({} as Record<string, UnitProgress>),
    vocabLevel: snap?.vocab_level ?? 'A1',
    xp: snap?.xp ?? 0,
    dueCount: snap?.due_count ?? 0,
    ready: snap !== null,
    error,
    review: (subId: string, rating: 1 | 2 | 3 | 4) => post<ReviewResult>('/api/brain/review', { sub_id: subId, rating }),
    expose: (subId: string) => post<ExposeResult>('/api/brain/expose', { sub_id: subId }),
  }
}
