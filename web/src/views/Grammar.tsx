import { useCallback, useEffect, useMemo, useState } from 'react'
import { Icon } from '../components/Icon'
import { STAGE_LABEL, lessonSeen, useBrain, useGrammarCourse, type ExposeResult, type GrammarProgress, type GrammarSubtopic, type GrammarTopic, type ReviewResult, type SubtopicProgress, type UnitProgress } from '../grammar/data'
import { PointsMeter, RuleLegend } from '../grammar/Points'
import { Lesson } from './Lesson'
import { MiniRing, Ring, Timeline } from '../grammar/widgets'
import { DONE_AT, STAR_AT, topicMastery, topicStars, topicStatus, type TopicStatus } from '../grammar/scoring'
import '../styles/grammar.css'

const pad = (n: number) => String(n).padStart(2, '0')
const tag = (t: GrammarTopic) => t.label ?? pad(t.id)
const KIND_TAG = { exercises: 'Ex', guide: 'Rehber' } as const
const STAGE_PILL = { uyuyan: '', kodlama: '', kisa_sureli: '', pekisme: 'pill-brand', uzun_sureli: 'pill-good' } as const

function inDays(d: number): string {
  if (d < 1 / 24) return 'birazdan'
  if (d < 1) return `${Math.round(d * 24)} saat sonra`
  if (d < 1.5) return 'yarın'
  return `${Math.round(d)} gün sonra`
}
function dueText(iso?: string | null, due?: boolean): string | null {
  if (!iso) return null
  return due ? 'zamanı geldi' : inDays((Date.parse(iso) - Date.now()) / 86400000)
}
type Brain = ReturnType<typeof useBrain>
const STATUS_LABEL: Record<TopicStatus, string> = { done: 'Onaylı', learning: 'Çalışılıyor', new: 'Başlanmadı' }
type Units = Record<string, UnitProgress>
const EMPTY_UNIT: UnitProgress = { points: 0, required: 30, band: 'A1-A2', approved: false, approved_at: null, correct_uses: 0, min_correct: 3 }
/** The book's numbered units are approved by speaking points; until the server answered they count as not started, never as "done by memory". Extras (ids 101+) have no points. */
const unitOf = (units: Units, id: number): UnitProgress | undefined => (id < 100 ? (units[String(id)] ?? EMPTY_UNIT) : undefined)
const STATUS_PILL: Record<TopicStatus, string> = { done: 'pill-good', learning: 'pill-brand', new: '' }

/** The topic page lives at #gramer/<id>, its pre-learning card at #gramer/<id>/hazirlik; #gramer alone is the map. */
function useTopicRoute(): [number | null, (id: number | null, prep?: boolean) => void, boolean] {
  const read = () => {
    const m = location.hash.match(/^#gramer\/(\d+)(\/hazirlik)?/)
    return { id: m ? Number(m[1]) : null, prep: Boolean(m?.[2]) }
  }
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const on = () => setRoute(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const open = useCallback((next: number | null, prep = false) => {
    location.hash = next === null ? 'gramer' : `gramer/${next}${prep ? '/hazirlik' : ''}`
    window.scrollTo(0, 0)
  }, [])
  return [route.id, open, route.prep]
}

function Stars({ count }: { count: number }) {
  return (
    <span className="gr-stars" role="img" aria-label={`${count} / 3 yıldız`}>
      {[0, 1, 2].map((i) => <Icon key={i} name="star" className={i < count ? 'on' : ''} />)}
    </span>
  )
}

function Notice() {
  return (
    <p className="gr-note" role="note">
      <Icon name="bulb" size="sm" />
      <span><b>Bu liste kitaptan değil.</b> Kitabın konu listesi (content/grammar/yener.json) bulunamadı, örnek taslak gösteriliyor.</span>
    </p>
  )
}

type Filter = 'all' | 'due' | TopicStatus
const FILTERS: [Filter, string][] = [['all', 'Tümü'], ['due', 'Tekrar zamanı'], ['done', 'Onaylı'], ['learning', 'Çalışılan'], ['new', 'Başlanmamış']]

function TopicCard({ topic, progress, unit, next, open }: { topic: GrammarTopic; progress: GrammarProgress; unit?: UnitProgress; next: boolean; open: (id: number) => void }) {
  const status = topicStatus(topic, progress, unit)
  const m = topicMastery(topic, progress)
  return (
    <li>
      <button className="gr-card" data-status={status} data-next={next ? 'true' : undefined} onClick={() => open(topic.id)}>
        <span className="top">
          <span className="no num">{tag(topic)}</span>
          {next ? <span className="pill pill-brand">Sıradaki</span>
            : topic.subtopics.some((x) => progress[x.id]?.due) ? <span className="pill pill-warn">Tekrar</span>
            : status === 'done' ? <span className="ok"><Icon name="check" /></span> : null}
        </span>
        <b className="ttl">{topic.title}</b>
        {topic.tr && <span className="tr">{topic.tr}</span>}
        <span className="bot">
          <MiniRing value={m} done={status === 'done'} />
          <span className="meta">
            <b className="num">{status === 'new' ? '—' : `%${m}`}</b>
            <small>{topic.subtopics.length} alt başlık</small>
            {unit && <small className={unit.approved ? 'ok-text' : ''}>{unit.approved ? 'Onaylı' : `${unit.points} / ${unit.required} puan`}</small>}
          </span>
        </span>
      </button>
    </li>
  )
}

function RoadMap({ topics, extras, progress, units, xp, dueCount, verified, open }: { topics: GrammarTopic[]; extras: GrammarTopic[]; progress: GrammarProgress; units: Units; xp: number; dueCount: number; verified: boolean; open: (id: number) => void }) {
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')

  const statuses = useMemo(() => topics.map((t) => topicStatus(t, progress, unitOf(units, t.id))), [topics, progress, units])
  const next = useMemo(() => topics.find((_, i) => statuses[i] !== 'done')?.id ?? null, [topics, statuses])
  const nextTopic = topics.find((t) => t.id === next)
  const nextUnit = nextTopic ? unitOf(units, nextTopic.id) : undefined
  const done = statuses.filter((s) => s === 'done').length
  const overall = Math.round(topics.reduce((a, t) => a + topicMastery(t, progress), 0) / topics.length)  // memory mastery; approval is by speaking points
  const subtotal = topics.reduce((a, t) => a + t.subtopics.length, 0)
  const subDone = topics.reduce((a, t) => a + t.subtopics.filter((s) => (progress[s.id]?.score ?? 0) >= DONE_AT).length, 0)

  const q = query.trim().toLocaleLowerCase('tr')
  const visible = (t: GrammarTopic) => {
    if (filter === 'due' ? !t.subtopics.some((x) => progress[x.id]?.due) : filter !== 'all' && topicStatus(t, progress, unitOf(units, t.id)) !== filter) return false
    if (!q) return true
    return [t.title, t.tr ?? '', ...t.subtopics.map((s) => s.title + ' ' + (s.tr ?? ''))].some((x) => x.toLocaleLowerCase('tr').includes(q))
  }
  const shown = topics.filter(visible)
  const extrasShown = extras.filter(visible)

  return (
    <div className="gr">
      {!verified && <Notice />}
      <article className="card gr-hero">
        <Ring value={overall} label="bellek" />
        <div className="gr-hero-main">
          <div className="gr-stats">
            <div className="tile"><div className="t-top"><i style={{ background: 'var(--xp)' }} />XP</div><strong className="num">{xp.toLocaleString('tr-TR')}</strong><small>XP</small></div>
            <div className="tile"><div className="t-top"><i style={{ background: 'var(--good)' }} />Onaylı konu</div><strong className="num">{done}</strong><small>/ {topics.length} konu</small></div>
            <div className="tile"><div className="t-top"><i style={{ background: 'var(--brand)' }} />Alt başlık</div><strong className="num">{subDone}</strong><small>/ {subtotal} alt başlık</small></div>
          </div>
          {dueCount > 0 && (
            <div className="gr-due">
              <span className="pill pill-warn">Tekrar zamanı</span>
              <span><b className="num">{dueCount}</b> alt başlığın testi geldi. Unutma eğrisine yakalanmadan hatırlamayı dene.</span>
              <button className="btn btn-sm btn-ghost" onClick={() => setFilter('due')}>Göster</button>
            </div>
          )}
          {nextTopic && (
            <div className="gr-next">
              <div>
                <span className="pill pill-brand">Sıradaki konu</span>
                <h2>{tag(nextTopic)} · {nextTopic.title}</h2>
                <p className="muted">{nextTopic.tr}{nextUnit && ` · ${nextUnit.points} / ${nextUnit.required} puan`}</p>
              </div>
              <button className="btn" onClick={() => open(nextTopic.id)}>Devam et<Icon name="send" /></button>
            </div>
          )}
        </div>
      </article>

      <Timeline statuses={statuses} next={next} />

      <div className="gr-toolbar">
        <div className="gr-chips" role="group" aria-label="Konu filtresi">
          {FILTERS.map(([id, label]) => (
            <button key={id} className="chip" aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>
          ))}
        </div>
        <label className="gr-search">
          <Icon name="search" size="sm" />
          <input type="search" placeholder="Konu ara" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Konu ara" />
        </label>
      </div>

      {shown.length + extrasShown.length === 0 && <p className="gr-empty muted">Eşleşen konu yok.</p>}
      <ol className="gr-grid">
        {shown.map((t) => <TopicCard key={t.id} topic={t} progress={progress} unit={unitOf(units, t.id)} next={t.id === next} open={open} />)}
      </ol>

      {extrasShown.length > 0 && (
        <>
          <div className="gr-section">
            <h3>Ek bölümler</h3>
            <p className="muted">46 ünitenin dışında, kitabın konuşma pratiğiyle doğrudan ilgili bölümleri. Genel hakimiyete sayılmaz.</p>
          </div>
          <ol className="gr-grid">
            {extrasShown.map((t) => <TopicCard key={t.id} topic={t} progress={progress} next={false} open={open} />)}
          </ol>
        </>
      )}
    </div>
  )
}

type Outcome = { type: 'review'; r: ReviewResult } | { type: 'read'; r: ExposeResult }

/** One subtopic (neuron). "Test et" is retrieval practice: try to recall first, then rate honestly. */
function SubRow({ sub, tag, p, brain, goTo }: { sub: GrammarSubtopic; tag: string; p?: SubtopicProgress; brain: Brain; goTo: (subId: string) => void }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [failed, setFailed] = useState(false)
  const score = p?.score ?? 0
  const stage = p?.stage ?? 'uyuyan'
  const next = dueText(p?.dueAt, p?.due)

  const run = async (job: () => Promise<Outcome>) => {
    setBusy(true)
    setFailed(false)
    try {
      setOutcome(await job())
    } catch {
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }
  const rate = (rating: 1 | 2 | 3 | 4) => run(async () => ({ type: 'review', r: await brain.review(sub.id, rating) }))
  const read = () => run(async () => ({ type: 'read', r: await brain.expose(sub.id) }))

  return (
    <li className={p && score >= DONE_AT ? 'ok' : ''}>
      <span className="cb"><Icon name="check" /></span>
      <div className="body">
        <p><span className="id num">{tag}</span>{sub.title}</p>
        {sub.tr && <span className="tr">{sub.tr}</span>}
        <span className="bar"><i style={{ width: `${score}%` }} /></span>
        {stage !== 'uyuyan' && (
          <span className="gr-stage">
            <span className={`pill ${STAGE_PILL[stage]}`}>{STAGE_LABEL[stage]}</span>
            {next && <span className={p?.due ? 'due' : 'muted'}>Sonraki test: {next}</span>}
          </span>
        )}
      </div>
      <div className="side">
        <span className="lv num">{p ? `%${score}` : '—'}</span>
        <button className={`btn btn-sm ${p?.due ? '' : 'btn-ghost'}`} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {p?.due ? 'Tekrar zamanı' : 'Test et'}
        </button>
      </div>
      {open && (
        <div className="gr-test">
          <p><b>Önce hatırlamaya çalış.</b> Kitabı kapat, bu alt başlığı kendi cümlelerinle anlat ve iki örnek ver. Sonra dürüstçe değerlendir:</p>
          <div className="gr-rate">
            <button className="btn btn-sm btn-bad" disabled={busy} onClick={() => rate(1)}>Hatırlayamadım</button>
            <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => rate(2)}>Zor hatırladım</button>
            <button className="btn btn-sm" disabled={busy} onClick={() => rate(3)}>İyi hatırladım</button>
            <button className="btn btn-sm btn-good" disabled={busy} onClick={() => rate(4)}>Kolay</button>
          </div>
          <button className="gr-link" disabled={busy} onClick={read}>Sadece okudum, test etmeden</button>
          {failed && <p className="gr-fail" role="alert">Kaydedilemedi. Sunucu çalışıyor mu?</p>}
          {outcome?.type === 'review' && (
            <div className="gr-result" role="status">
              <b>{outcome.r.stage_label}</b> · güç %{outcome.r.score} · sonraki test {inDays(outcome.r.interval_days)} · +{outcome.r.xp} XP
              {outcome.r.promoted && <> · <b>aşama atladın</b></>}
              {outcome.r.confusion_partners.length > 0 && (
                <div className="gr-confuse">
                  Bunu şununla karıştırıyor olabilirsin, ayırt etmek için ikisini de test et:
                  {outcome.r.confusion_partners.map((c) => (
                    <button key={c.sub_id} className="gr-link" onClick={() => goTo(c.sub_id)}>{c.sub_id} · {c.title}{c.reason ? ` (${c.reason})` : ''}</button>
                  ))}
                </div>
              )}
            </div>
          )}
          {outcome?.type === 'read' && (
            <div className="gr-result" role="status">
              Okuma kaydedildi: güç %{outcome.r.score}. Sadece okumak gücü en fazla %{30}'a çıkarır; kalıcı öğrenme için hatırlamayı dene.
            </div>
          )}
        </div>
      )}
    </li>
  )
}

function TopicPage({ topics, extras, progress, units, brain, id, open, verified }: { topics: GrammarTopic[]; extras: GrammarTopic[]; progress: GrammarProgress; units: Units; brain: Brain; id: number; open: (id: number | null, prep?: boolean) => void; verified: boolean }) {
  // Previous / next stay inside the group the topic belongs to (46 units, or the extra sections)
  const isExtra = extras.some((t) => t.id === id)
  const group = isExtra ? extras : topics
  const index = group.findIndex((t) => t.id === id)
  const topic = group[index]
  const prev = group[index - 1]
  const nextT = group[index + 1]

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (/INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName)) return
      if (e.key === 'ArrowLeft' && prev) open(prev.id)
      if (e.key === 'ArrowRight' && nextT) open(nextT.id)
      if (e.key === 'Escape') open(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [prev, nextT, open])

  if (!topic) {
    return (
      <div className="gr">
        <p className="gr-empty muted">Böyle bir konu yok.</p>
        <button className="btn btn-ghost btn-sm" onClick={() => open(null)}>← Haritaya dön</button>
      </div>
    )
  }

  const mastery = topicMastery(topic, progress)
  const stars = topicStars(topic, progress)
  const unit = unitOf(units, topic.id)
  const status = topicStatus(topic, progress, unit)
  const nextStar = STAR_AT.find((t) => mastery < t)

  return (
    <div className="gr">
      {!verified && <Notice />}
      <div className="gr-crumbs">
        <button className="btn btn-ghost btn-sm" onClick={() => open(null)}>← Harita</button>
        <span className="muted num">{isExtra ? `Ek bölüm ${index + 1} / ${group.length}` : `Konu ${pad(topic.id)} / ${pad(group.length)}`}</span>
      </div>

      <article className="card gr-head">
        <Ring value={mastery} label="bellek" size={150} />
        <div className="gr-head-text">
          <div className="gr-pills">
            <span className={`pill ${STATUS_PILL[status]}`}>{!unit && status === 'done' ? 'Tamamlandı' : STATUS_LABEL[status]}</span>
            {topic.page && <span className="pill num">Kitap s. {topic.page}</span>}
          </div>
          <h2>{topic.title}</h2>
          {topic.tr && <p className="muted tr">{topic.tr}</p>}
          <div className="gr-meta">
            <Stars count={stars} />
            <span className="muted">
              Yıldız ve halka, bellek testlerindeki hakimiyeti gösterir{stars < 3 && nextStar && <> (sıradaki yıldız %{nextStar})</>}. {unit ? 'Konunun onayı konuşma puanıyla verilir.' : 'Bu bölüm bellek hakimiyetiyle tamamlanır.'}
            </span>
          </div>
        </div>
      </article>

      {unit && brain.ready && (
        <article className="card gr-points" aria-label="Konuşma puanı">
          <div className="card-head">
            <h2>Konuşma puanı</h2>
            <span className="pill">{unit.band} · onay için {unit.required} puan</span>
          </div>
          <PointsMeter unit={unit} />
          <RuleLegend vocabLevel={brain.vocabLevel} />
          <div className="gr-actions">
            {topic.has_lesson && <button className="btn btn-ghost" onClick={() => open(topic.id, true)}>Konu anlatımı<Icon name="book" /></button>}
            <button className="btn" onClick={() => {
              if (topic.has_lesson && !lessonSeen(topic.id)) open(topic.id, true) // first time: the short card, then the talk
              else location.hash = `sohbet?topic=${topic.id}`
            }}>Alex'le çalış<Icon name="send" /></button>
          </div>
        </article>
      )}

      <article className="card" aria-label="Alt başlıklar">
        <div className="card-head"><h2>Alt başlıklar</h2><span className="pill num">{topic.subtopics.length}</span></div>
        <ul className="gr-subs">
          {topic.subtopics.map((sub) => (
            <SubRow
              key={sub.id}
              sub={sub}
              tag={sub.code || (sub.kind ? KIND_TAG[sub.kind] : topic.label ? `${topic.label}.${sub.id.split('.')[1]}` : sub.id)}
              p={progress[sub.id]}
              brain={brain}
              goTo={(subId) => {
                const unit = [...topics, ...extras].find((t) => t.subtopics.some((x) => x.id === subId))
                if (unit) open(unit.id)
              }}
            />
          ))}
        </ul>
        <div className="gr-actions">
          <button className="btn btn-ghost" disabled title="Ayrı bir konu sınavı henüz yok: konu onayı konuşma puanıyla veriliyor">Konu sınavı · yakında</button>
        </div>
      </article>

      <nav className="gr-pager" aria-label="Konular arası">
        {prev ? (
          <button className="card" onClick={() => open(prev.id)}><small className="muted">← Önceki · {tag(prev)}</small><b>{prev.title}</b></button>
        ) : <span />}
        {nextT ? (
          <button className="card r" onClick={() => open(nextT.id)}><small className="muted">{tag(nextT)} · Sonraki →</small><b>{nextT.title}</b></button>
        ) : <span />}
      </nav>
    </div>
  )
}

export function Grammar() {
  const { course, error } = useGrammarCourse()
  const [topicId, open, prep] = useTopicRoute()
  const topics = useMemo(() => course?.topics ?? [], [course])
  const extras = useMemo(() => (course?.extras ?? []).filter((t) => t.roadmap), [course])
  const brain = useBrain()

  return (
    <section className="view" aria-labelledby="h-grammar">
      <div className="view-head">
        <div>
          <h1 id="h-grammar">Gramer</h1>
          <p>{course ? `${topics.length} konu, kitap sırasıyla` : 'Yol haritası yükleniyor…'}</p>
        </div>
      </div>
      {(error || brain.error) && <p className="hf-note" style={{ color: 'var(--bad-text)' }} role="alert">{error ? 'Gramer listesi yüklenemedi.' : 'İlerleme yüklenemedi.'} Sunucu çalışıyor mu?</p>}
      {course && topics.length > 0 && topicId !== null && prep && topics.some((t) => t.id === topicId)
        ? <Lesson topic={topics.find((t) => t.id === topicId)!} back={() => open(topicId)} />
        : course && topics.length > 0 && (topicId === null
        ? <RoadMap topics={topics} extras={extras} progress={brain.progress} units={brain.units} xp={brain.xp} dueCount={brain.dueCount} verified={course.verified} open={open} />
        : <TopicPage topics={topics} extras={extras} progress={brain.progress} units={brain.units} brain={brain} id={topicId} open={open} verified={course.verified} />)}
    </section>
  )
}
