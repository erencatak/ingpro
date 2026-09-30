import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useVoiceChat, type CorrectionMode, type SpeechLang, type VoiceState } from '../audio/useVoiceChat'
import { Icon } from '../components/Icon'
import { useGrammarCourse, useLesson } from '../grammar/data'
import { PointsMeter, RuleLegend, UsageNote } from '../grammar/Points'
import '../styles/grammar.css'

const SCENARIOS = [
  { slug: 'free', label: 'Serbest sohbet', desc: 'Serbest sohbet · günün nasıl geçti?' },
  { slug: 'interview', label: 'İş görüşmesi', desc: 'İş görüşmesi · Alex, seçtiğin pozisyon için mülakatçı' },
  { slug: 'restaurant', label: 'Restoran', desc: 'Restoran · Alex garson, sen sipariş veriyorsun' },
]

interface CustomScenario { title: string; description: string; prompt: string }
const SPEEDS = [0.8, 0.9, 1.0, 1.1, 1.2]
const LANGS: [SpeechLang, string][] = [['auto', 'Otomatik'], ['en', 'English'], ['tr', 'Türkçe']]

// The orb has four looks; idle-with-mic-off reads as "muted". In push-to-talk, the mic can be "on" (hardware
// open) without actually listening — it only listens while held — so that state also reads as "muted", not "listening".
function orbState(state: VoiceState, micOn: boolean, pttEnabled: boolean): 'listening' | 'thinking' | 'speaking' | 'muted' {
  if (state === 'thinking' || state === 'speaking') return state
  if (state === 'listening') return 'listening'
  if (pttEnabled) return 'muted'
  return micOn ? 'listening' : 'muted'
}

function statusLabel(state: VoiceState, micOn: boolean, pttEnabled: boolean): string {
  if (state === 'connecting') return 'Bağlanıyor…'
  if (state === 'thinking') return 'Düşünüyor'
  if (state === 'speaking') return 'Konuşuyor'
  if (state === 'listening') return 'Dinliyor'
  if (pttEnabled) return micOn ? 'Basılı tut ve konuş' : 'Mikrofon kapalı'
  return micOn ? 'Dinliyor' : 'Mikrofon kapalı'
}

/** #sohbet?topic=13 opens a session about grammar unit 13: its spoken sentences earn speaking points. */
function useTopicParam(): number | null {
  const read = () => {
    const m = location.hash.match(/[?&]topic=(\d+)/)
    return m ? Number(m[1]) : null
  }
  const [topic, setTopic] = useState(read)
  useEffect(() => {
    const on = () => setTopic(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return topic
}

function useElapsed(resetKey: unknown) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    setSeconds(0)
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [resetKey])
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

export function Chat() {
  const [scenario, setScenario] = useState('free')
  const [mode, setMode] = useState<CorrectionMode>('flow')
  const [speed, setSpeedState] = useState(0.9)
  const [draft, setDraft] = useState('')
  const [lang, setLangState] = useState<SpeechLang>('auto')
  const [helpOpen, setHelpOpen] = useState(false)
  const [helpDraft, setHelpDraft] = useState('')
  const [field, setField] = useState('')
  const [fieldDraft, setFieldDraft] = useState('')
  const [customScenario, setCustomScenario] = useState<CustomScenario | null>(null)
  const [customFormOpen, setCustomFormOpen] = useState(false)
  const [customDraft, setCustomDraft] = useState('')
  const [customLoading, setCustomLoading] = useState(false)
  const [customError, setCustomError] = useState<string | null>(null)
  const topicId = useTopicParam()
  const { course } = useGrammarCourse()
  const topic = course?.topics.find((t) => t.id === topicId)
  const scored = topicId !== null && topic !== undefined // only the book's numbered units earn speaking points
  const { card } = useLesson(scored && topic?.has_lesson ? topicId : null)
  type UnitMeter = { points: number; required: number; band: string; approved: boolean; correct_uses: number; min_correct: number; vocab_level?: string }
  const [fetched, setFetched] = useState<{ topic: number; meter: UnitMeter } | null>(null)
  const firstUnit = fetched && fetched.topic === topicId ? fetched.meter : null // never the previous topic's meter
  const chat = useVoiceChat({
    scenario,
    mode,
    topic: topicId,
    field,
    customPrompt: scenario === 'custom' ? customScenario?.prompt ?? '' : '',
  })
  const unit = chat.unit ? { ...chat.unit, correct_uses: chat.unit.correctUses, min_correct: chat.unit.minCorrect } : firstUnit
  const elapsed = useElapsed(`${scenario}/${mode}/${topicId}/${field}`)
  const body = useRef<HTMLDivElement>(null)
  const current =
    scenario === 'custom' && customScenario
      ? { slug: 'custom', label: customScenario.title, desc: customScenario.description }
      : scenario === 'interview'
        ? { slug: 'interview', label: 'İş görüşmesi', desc: `İş görüşmesi · Alex, ${field || 'seçtiğin'} pozisyon için mülakatçı` }
        : (SCENARIOS.find((s) => s.slug === scenario) ?? SCENARIOS[0])

  useEffect(() => {
    body.current?.scrollTo({ top: body.current.scrollHeight, behavior: 'smooth' })
  }, [chat.messages])

  useEffect(() => {
    if (!topicId) return
    fetch(`/api/brain/unit/${topicId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((meter: UnitMeter) => setFetched({ topic: topicId, meter }))
      .catch(() => {})
  }, [topicId])

  const toggleMic = () => void (chat.micOn ? chat.stopMic() : chat.startMic())

  // Space held down = "I'm talking, whatever the pause": bypasses the silence-detector's guess entirely.
  const holdToTalk = () => {
    if (!chat.micOn) void chat.startMic() // frames only start flowing once the mic is actually up; harmless race
    chat.pttDown()
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (/INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName)) return
      if (e.key === 'm' || e.key === 'M') toggleMic()
      if (e.key === 'Escape') chat.interrupt()
      if (chat.pttEnabled && e.code === 'Space') {
        e.preventDefault() // every repeat too, or the browser scrolls the page once the OS key-repeat kicks in
        if (!e.repeat) holdToTalk()
      }
    }
    const onKeyUp = (e: KeyboardEvent) => {
      if (chat.pttEnabled && e.code === 'Space') chat.pttUp()
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('keyup', onKeyUp)
    }
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    chat.sendText(text)
    setDraft('')
  }

  const submitHelp = (e: FormEvent) => {
    e.preventDefault()
    const text = helpDraft.trim()
    if (!text) return
    chat.sendText(`Bunu nasıl söylerim: ${text}`)
    setHelpDraft('')
    setHelpOpen(false)
  }

  const submitField = (e: FormEvent) => {
    e.preventDefault()
    setField(fieldDraft.trim())
  }

  const submitCustomScenario = async (e: FormEvent) => {
    e.preventDefault()
    const text = customDraft.trim()
    if (!text) return
    setCustomLoading(true)
    setCustomError(null)
    try {
      const r = await fetch('/api/scenarios/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: text }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => null)
        throw new Error(body?.detail || 'Senaryo oluşturulamadı')
      }
      const gen = (await r.json()) as CustomScenario
      setCustomScenario(gen)
      setScenario('custom')
      setCustomFormOpen(false)
      setCustomDraft('')
    } catch (err) {
      setCustomError(err instanceof Error ? err.message : 'Senaryo oluşturulamadı')
    } finally {
      setCustomLoading(false)
    }
  }

  const look = orbState(chat.state, chat.micOn, chat.pttEnabled)
  const status = statusLabel(chat.state, chat.micOn, chat.pttEnabled)

  return (
    <section className="view" aria-labelledby="h-chat">
      <div className="chat-toolbar">
        <div className="scenarios" role="group" aria-label="Senaryo seç">
          {SCENARIOS.map((s) => (
            <button key={s.slug} className="chip" aria-pressed={scenario === s.slug} onClick={() => setScenario(s.slug)}>
              {s.label}
            </button>
          ))}
          {customScenario && (
            <button className="chip" aria-pressed={scenario === 'custom'} onClick={() => setScenario('custom')}>
              {customScenario.title}
            </button>
          )}
          <button className="chip" aria-pressed={customFormOpen} onClick={() => setCustomFormOpen((o) => !o)}>
            Senaryo oluştur
          </button>
        </div>
        <div className="chat-toggles">
          <div className="seg" role="group" aria-label="Düzeltme modu">
            <button aria-pressed={mode === 'flow'} onClick={() => setMode('flow')}>Akış</button>
            <button aria-pressed={mode === 'teacher'} onClick={() => setMode('teacher')}>Öğretmen</button>
          </div>
          <div className="seg" role="group" aria-label="Konuşma modu" title="Basılı konuş: mikrofon sadece bastığın sürece dinler, duraksamalarında cümleni erken kesip göndermez">
            <button aria-pressed={!chat.pttEnabled} onClick={() => chat.setPtt(false)}>Otomatik dinleme</button>
            <button aria-pressed={chat.pttEnabled} onClick={() => chat.setPtt(true)}>Basılı konuş</button>
          </div>
        </div>
      </div>

      {scenario === 'interview' && (
        <form className="tr-help" onSubmit={submitField}>
          <span className="q">Hangi pozisyon için mülakat olsun?</span>
          <input
            value={fieldDraft}
            onChange={(e) => setFieldDraft(e.target.value)}
            placeholder={field || 'ör. yazılım geliştirici, hemşire, garson…'}
            style={{ height: 44, padding: '0 14px', borderRadius: 'var(--r-md)', border: '1px solid var(--line-strong)', background: 'var(--surface-2)', outline: 'none' }}
          />
          <button className="btn btn-sm" type="submit">Ayarla</button>
        </form>
      )}

      {customFormOpen && (
        <form className="tr-help" onSubmit={submitCustomScenario}>
          <span className="q">Senaryonu tarif et, AI oluştursun (ör. hayvanat bahçesinde bekçiyle konuşma):</span>
          <input
            autoFocus
            value={customDraft}
            onChange={(e) => setCustomDraft(e.target.value)}
            placeholder="ör. bir kütüphanede kitap arıyorsun"
            style={{ height: 44, padding: '0 14px', borderRadius: 'var(--r-md)', border: '1px solid var(--line-strong)', background: 'var(--surface-2)', outline: 'none' }}
          />
          <button className="btn btn-sm" type="submit" disabled={customLoading}>{customLoading ? 'Oluşturuluyor…' : 'Oluştur ve başla'}</button>
          {customError && <span className="hf-note" style={{ color: 'var(--bad-text)' }}>{customError}</span>}
        </form>
      )}

      {scored && (
        <article className="card gr-focus">
          <div className="gr-focus-head">
            <div>
              <span className="pill pill-brand">Konu pratiği</span>
              <h2>{topic ? `${String(topic.id).padStart(2, '0')} · ${topic.title}` : `Konu ${topicId}`}</h2>
              <p className="muted">Bu konuyu kullanarak İngilizce konuş. Sesli söylediğin net cümleler puan kazanır.</p>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => { location.hash = 'sohbet' }}>Konuyu bırak</button>
          </div>
          {card && (
            <p className="gr-refresh"><Icon name="bulb" size="sm" /><span>{card.refresher}</span>
              <a href={`#gramer/${card.unit}/hazirlik`}>Konu anlatımı</a></p>
          )}
          <PointsMeter unit={unit} />
          {chat.unit?.newlyApproved && <p className="gr-approved" role="status"><Icon name="trophy" />Bu konu onaylandı. Gramer ekranında yeşil tikle görünecek.</p>}
          <details className="gr-rules-fold">
            <summary>Puan kuralları</summary>
            <RuleLegend vocabLevel={firstUnit?.vocab_level} />
          </details>
        </article>
      )}

      <div className="chat-grid">
        <div className="card stage" data-state={look}>
          <span className="state-pill" aria-live="polite"><i /><span>{status}</span></span>
          <div className="orb" aria-hidden="true">
            <span className="orb-ring" /><span className="orb-ring" /><span className="orb-ring" />
            <div className="orb-dots"><i /><i /><i /></div>
            <div className="orb-core"><div className="face"><div className="eyes"><span className="eye" /><span className="eye" /></div><span className="mouth" /></div></div>
          </div>
          <div className="wave" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></div>
          <div className="stage-meta">
            <h2 id="h-chat">Alex</h2>
            <p>{current.desc}</p>
          </div>
          <div className="targets">
            <span className="target num">{elapsed}</span>
            {chat.tokens !== null && (
              <span className="target num" title={`Bu oturumda Alex + puanlama toplamı · tahmini maliyet $${chat.tokens.costUsd.toFixed(4)}`}>
                {chat.tokens.totalTokens.toLocaleString('tr-TR')} token
              </span>
            )}
            {chat.metrics.responseMs !== undefined && <span className="target num" title="Konuşman bitti → Alex'in sesi">cevap {(chat.metrics.responseMs / 1000).toFixed(1)} sn</span>}
          </div>
          <div className="mic-row">
            <button className="round-btn" aria-pressed={helpOpen} onClick={() => setHelpOpen((o) => !o)}>
              <span className="circle"><Icon name="globe" /></span>Türkçe yardım
            </button>
            {chat.pttEnabled ? (
              <button
                className="btn mic"
                aria-pressed={chat.state === 'listening'}
                aria-label="Basılı tut ve konuş"
                disabled={chat.state === 'connecting'}
                onContextMenu={(e) => e.preventDefault()}
                onPointerDown={(e) => { e.preventDefault(); holdToTalk() }}
                onPointerUp={chat.pttUp}
                onPointerLeave={chat.pttUp}
                onPointerCancel={chat.pttUp}
              >
                <Icon name="mic" />
              </button>
            ) : (
              <button className="btn mic" aria-pressed={!chat.micOn} aria-label={chat.micOn ? 'Mikrofonu kapat' : 'Mikrofonu aç'} onClick={toggleMic} disabled={chat.state === 'connecting'}>
                <Icon name={chat.micOn ? 'mic' : 'micoff'} />
              </button>
            )}
            <button className="round-btn" onClick={chat.interrupt}>
              <span className="circle"><Icon name="stop" /></span>Sustur
            </button>
          </div>
          {chat.error && <p className="hf-note" style={{ color: 'var(--bad-text)' }} role="alert">{chat.error}</p>}
          <div className="speed">
            <span id="speedLbl" className="muted" style={{ fontSize: 'var(--t-sm)', fontWeight: 600 }}>Alex'in hızı</span>
            <div className="seg" role="group" aria-labelledby="speedLbl">
              {SPEEDS.map((v) => (
                <button key={v} aria-pressed={speed === v} onClick={() => { setSpeedState(v); chat.setSpeed(v) }}>{v.toFixed(1)}x</button>
              ))}
            </div>
          </div>
          <div className="speed">
            <span id="langLbl" className="muted" style={{ fontSize: 'var(--t-sm)', fontWeight: 600 }}>Konuştuğum dil</span>
            <div className="seg" role="group" aria-labelledby="langLbl">
              {LANGS.map(([v, label]) => (
                <button key={v} aria-pressed={lang === v} onClick={() => { setLangState(v); chat.setLang(v) }}>{label}</button>
              ))}
            </div>
          </div>
          <div className="shortcuts">
            <span><kbd>M</kbd> mikrofon</span>
            {chat.pttEnabled && <span><kbd>Space</kbd> basılı tut, konuş</span>}
            <span><kbd>Esc</kbd> Alex'i sustur</span>
          </div>
        </div>

        <div className="card transcript">
          <div className="tr-head">
            <h2>Konuşma dökümü</h2>
            {chat.micOn && !chat.pttEnabled && <span className="hf-note"><Icon name="mic" size="sm" />Mikrofon açık: sen konuşunca dinler</span>}
            {chat.pttEnabled && <span className="hf-note"><Icon name="mic" size="sm" />Basılı konuş: Space'e (ya da mikrofon düğmesine) bas, konuş, bırak</span>}
          </div>
          <div className="tr-body" ref={body} aria-live="polite">
            <span className="sys">{current.label} · {mode === 'teacher' ? 'Öğretmen modu' : 'Akış modu'}</span>
            {chat.messages.map((m) => (
              <div key={m.id} className={`msg ${m.role === 'user' ? 'me' : 'alex'}`}>
                {m.role === 'assistant' && <span className="av av-alex" />}
                <div>
                  <div className="bubble en">
                    {m.text || <span className="typing"><i /><i /><i /></span>}
                  </div>
                  {m.role === 'user' && m.lang === 'tr' && !scored && <div className="bubble-meta">Türkçe algılandı</div>}
                  {m.role === 'user' && scored && <UsageNote u={chat.usage[Number(m.id.slice(1))]} refresher={card?.refresher} />}
                </div>
              </div>
            ))}
          </div>
          {helpOpen && (
            <form className="tr-help" onSubmit={submitHelp}>
              <span className="q">Türkçe yaz, Alex İngilizcesini söylesin:</span>
              <input
                className="en"
                autoFocus
                value={helpDraft}
                onChange={(e) => setHelpDraft(e.target.value)}
                placeholder="ör. bilgisayarım sürekli donuyor"
                style={{ height: 44, padding: '0 14px', borderRadius: 'var(--r-md)', border: '1px solid var(--line-strong)', background: 'var(--surface-2)', outline: 'none' }}
              />
            </form>
          )}
          <form className="composer" onSubmit={submit}>
            <label htmlFor="chatInput" className="sr">Mesaj yaz</label>
            <input id="chatInput" autoComplete="off" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Yaz ya da mikrofona konuş…" />
            <button className="btn" type="submit" aria-label="Gönder" disabled={chat.state === 'connecting'}><Icon name="send" /></button>
          </form>
        </div>
      </div>

      {chat.starters.length > 0 && (
        <article className="card starters">
          <div className="card-head">
            <h2><Icon name="sparkle" size="sm" />Cümle kalıpları</h2>
            <span className="muted" style={{ fontSize: 'var(--t-sm)' }}>Boşlukları doldurup söyle — daha uzun cümle kurmak için bir kopya kağıdı</span>
          </div>
          <div className="starter-list">
            {chat.starters.map((s) => (
              <div className="starter" key={s.id}>
                <span className="starter-en">{s.en}</span>
                <span className="starter-tr">{s.tr}</span>
                <span className="pill starter-tag">{s.grammar}</span>
              </div>
            ))}
          </div>
        </article>
      )}
    </section>
  )
}
