import type { GrammarProgress, GrammarTopic, UnitProgress } from './data'

/* Display rules. The score itself comes from the server's brain (server/src/ingpro/brain/rules.py); see the vault note Beyin/02-Ogrenme-Kurallari. */
export const DONE_AT = 80 // topic mastery that counts as "learned"
export const STAR_AT = [50, 75, 90] as const // mastery needed for 1, 2 and 3 stars

export type TopicStatus = 'new' | 'learning' | 'done'

export function topicMastery(topic: GrammarTopic, progress: GrammarProgress): number {
  if (!topic.subtopics.length) return 0
  const sum = topic.subtopics.reduce((acc, s) => acc + (progress[s.id]?.score ?? 0), 0)
  return Math.round(sum / topic.subtopics.length)
}

/** Stars need a real recall attempt for every subtopic, so one lucky subtopic (or re-reading) can't earn them. */
export function topicStars(topic: GrammarTopic, progress: GrammarProgress): number {
  if (!topic.subtopics.every((s) => (progress[s.id]?.retrievals ?? 0) > 0)) return 0
  const m = topicMastery(topic, progress)
  return STAR_AT.filter((t) => m >= t).length
}

/** Units of the book are approved by speaking points (A1-A2: 30, B1-B2: 60, C1: 90). Extra sections have no points: memory mastery decides. */
export function topicStatus(topic: GrammarTopic, progress: GrammarProgress, unit?: UnitProgress): TopicStatus {
  const practiced = topic.subtopics.some((s) => (progress[s.id]?.attempts ?? 0) > 0)
  if (unit) return unit.approved ? 'done' : unit.points > 0 || practiced ? 'learning' : 'new'
  if (topicMastery(topic, progress) >= DONE_AT) return 'done'
  return practiced ? 'learning' : 'new'
}

/** The first topic in book order that isn't approved yet: nothing is locked, this is only the suggestion. */
export function nextTopicId(topics: GrammarTopic[], progress: GrammarProgress, units: Record<string, UnitProgress>): number | null {
  return topics.find((t) => topicStatus(t, progress, units[String(t.id)]) !== 'done')?.id ?? null
}
