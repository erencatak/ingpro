import { MicVAD } from '@ricky0123/vad-web'
import { useCallback, useEffect, useRef, useState } from 'react'
import { PcmPlayer } from './player'

export type VoiceState = 'connecting' | 'idle' | 'listening' | 'thinking' | 'speaking'
export type CorrectionMode = 'flow' | 'teacher'
export type SpeechLang = 'auto' | 'en' | 'tr'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  /** language the server understood the user to speak */
  lang?: 'en' | 'tr'
}

/** Speaking points of one spoken sentence (only in a session about a grammar unit). */
export interface UsageResult {
  valid: boolean
  rule: number | null
  points: number
  reason: string
  spoken?: boolean
  new_words?: string[]
  feedback_tr?: string
  correction?: string | null
}
export interface UnitState {
  points: number
  required: number
  band: string
  approved: boolean
  newlyApproved: boolean
  correctUses: number
  minCorrect: number
}

export interface TurnMetrics {
  sttMs?: number
  firstTokenMs?: number
  /** end of user speech → first tutor audio, as the user experiences it */
  responseMs?: number
}

/** Running total for the whole session (Alex + the judge), straight from the SDK's own usage report. */
export interface TokenTotals {
  totalTokens: number
  costUsd: number
}

/** One sentence-starter suggestion for the cheat sheet: a blanked pattern ("I worked ___ at ___."), not a full example. */
export interface Starter {
  id: string
  en: string
  tr: string
  grammar: string
}

type ServerEvent =
  | { type: 'ready' }
  | { type: 'user_transcript'; turn: number; text: string; lang: 'en' | 'tr'; stt_ms: number }
  | { type: 'assistant_start'; turn: number }
  | { type: 'assistant_delta'; turn: number; text: string }
  | { type: 'assistant_end'; turn: number; text: string; first_token_ms: number | null }
  | ({ type: 'usage'; turn: number; unit_points?: number; required?: number; band?: string; approved?: boolean; newly_approved?: boolean; correct_uses?: number; min_correct?: number } & UsageResult)
  | { type: 'tokens'; total_tokens: number; cost_usd: number }
  | { type: 'starters'; turn: number; items: Starter[] }
  | { type: 'error'; message: string }

interface Options {
  scenario: string
  mode: CorrectionMode
  /** number of the grammar unit this session practices; its spoken sentences earn speaking points */
  topic?: number | null
  /** scenario === 'interview' only: the job field to interview for */
  field?: string
  /** scenario === 'custom' only: the AI-generated role-play instruction to use instead of a fixed scenarios.json entry */
  customPrompt?: string
}

// A2 speakers pause mid-sentence to think; the silence-based VAD sometimes reads that pause as "done talking"
// and ships a half sentence. Push-to-talk sidesteps the guess entirely: hold Space (or the mic button), the mic
// stays open no matter how long you pause, and only releasing it means "send this".
const PTT_STORAGE_KEY = 'ingpro.pttMode'
const MIN_PTT_SAMPLES = 4800 // 300ms at 16kHz — same floor as the auto-VAD's minSpeechMs, so a stray tap sends nothing

function concatFloat32(chunks: Float32Array[]): Float32Array {
  const total = chunks.reduce((n, c) => n + c.length, 0)
  const out = new Float32Array(total)
  let offset = 0
  for (const c of chunks) {
    out.set(c, offset)
    offset += c.length
  }
  return out
}

export function useVoiceChat({ scenario, mode, topic = null, field = '', customPrompt = '' }: Options) {
  const [state, setState] = useState<VoiceState>('connecting')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [metrics, setMetrics] = useState<TurnMetrics>({})
  const [usage, setUsage] = useState<Record<number, UsageResult>>({})
  const [unit, setUnit] = useState<UnitState | null>(null)
  const [tokens, setTokens] = useState<TokenTotals | null>(null)
  const [starters, setStarters] = useState<Starter[]>([])
  const [micOn, setMicOn] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pttEnabled, setPttEnabled] = useState(() => localStorage.getItem(PTT_STORAGE_KEY) === '1')

  const ws = useRef<WebSocket | null>(null)
  const vad = useRef<MicVAD | null>(null)
  const player = useRef<PcmPlayer | null>(null)
  const activeTurn = useRef(0)
  const speechEndedAt = useRef<number | null>(null)
  const awaitingReply = useRef(false)
  const starting = useRef(false)
  const speed = useRef(0.9)
  // a session about a grammar unit practices English: the recognizer must not switch to Turkish on accented speech
  const sttLang = useRef<SpeechLang>(topic ? 'en' : 'auto')
  const pttMode = useRef(pttEnabled) // read inside MicVAD callbacks, which close over refs, not state
  const pttActive = useRef(false) // Space/mic button currently held down
  const pttFrames = useRef<Float32Array[]>([])

  const interrupt = useCallback(() => {
    player.current?.stop()
    activeTurn.current = -1 // drop any audio still in flight for the old turn
    awaitingReply.current = false
    ws.current?.send(JSON.stringify({ type: 'interrupt' }))
  }, [])

  // One WebSocket per (scenario, mode): the tutor's system prompt is fixed when the session opens.
  useEffect(() => {
    const p = new PcmPlayer()
    p.onIdle = () => setState(awaitingReply.current ? 'thinking' : 'idle')
    player.current = p
    awaitingReply.current = false
    activeTurn.current = 0
    sttLang.current = topic ? 'en' : 'auto'
    setMessages([])
    setMetrics({})
    setUsage({})
    setUnit(null)
    setTokens(null)
    setStarters([])
    setError(null)
    setState('connecting')
    pttActive.current = false
    pttFrames.current = []

    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const params = new URLSearchParams({ scenario, mode })
    if (topic) params.set('topic', String(topic))
    if (field) params.set('field', field)
    if (customPrompt) params.set('custom_prompt', customPrompt)
    const socket = new WebSocket(`${proto}://${location.host}/ws/voice?${params.toString()}`)
    socket.binaryType = 'arraybuffer'
    ws.current = socket

    socket.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) {
        const turn = new DataView(ev.data).getUint32(0, true)
        if (turn !== activeTurn.current) return
        if (speechEndedAt.current !== null) {
          const responseMs = Math.round(performance.now() - speechEndedAt.current)
          setMetrics((m) => ({ ...m, responseMs }))
          speechEndedAt.current = null
        }
        p.enqueue(new Int16Array(ev.data, 4))
        setState('speaking')
        return
      }
      const msg = JSON.parse(ev.data) as ServerEvent
      switch (msg.type) {
        case 'ready':
          socket.send(JSON.stringify({ type: 'settings', speed: speed.current, stt_lang: sttLang.current }))
          setState('idle')
          break
        case 'user_transcript':
          setMessages((m) => [...m, { id: `u${msg.turn}`, role: 'user', text: msg.text, lang: msg.lang }])
          setMetrics({ sttMs: msg.stt_ms })
          break
        case 'assistant_start':
          activeTurn.current = msg.turn
          awaitingReply.current = true
          setState('thinking')
          setMessages((m) => [...m, { id: `a${msg.turn}`, role: 'assistant', text: '' }])
          break
        case 'assistant_delta':
          setMessages((m) => m.map((x) => (x.id === `a${msg.turn}` ? { ...x, text: x.text + msg.text } : x)))
          break
        case 'assistant_end':
          awaitingReply.current = false
          setMetrics((m) => ({ ...m, firstTokenMs: msg.first_token_ms ?? undefined }))
          if (!p.playing) setState('idle')
          break
        case 'usage':
          setUsage((u) => ({ ...u, [msg.turn]: msg }))
          if (msg.unit_points !== undefined && msg.required !== undefined) {
            // Judgements finish in any order: the meter never goes backwards, and "just approved" stays until the topic changes
            setUnit((prev) => ({
              points: Math.max(prev?.points ?? 0, msg.unit_points!),
              required: msg.required!,
              band: msg.band ?? prev?.band ?? '',
              approved: !!msg.approved || !!prev?.approved,
              newlyApproved: !!msg.newly_approved || !!prev?.newlyApproved,
              correctUses: Math.max(prev?.correctUses ?? 0, msg.correct_uses ?? 0),
              minCorrect: msg.min_correct ?? prev?.minCorrect ?? 0,
            }))
          }
          break
        case 'tokens':
          setTokens({ totalTokens: msg.total_tokens, costUsd: msg.cost_usd })
          break
        case 'starters':
          setStarters(msg.items)
          break
        case 'error':
          awaitingReply.current = false
          setError(msg.message)
          setState('idle')
          break
      }
    }
    socket.onclose = () => {
      if (ws.current === socket) setState('connecting')
    }

    return () => {
      socket.close()
      p.stop()
    }
  }, [scenario, mode, topic, field, customPrompt])

  // The microphone outlives reconnects; only tear it down when the screen goes away.
  useEffect(
    () => () => {
      void vad.current?.destroy()
      vad.current = null
    },
    [],
  )

  const startMic = useCallback(async () => {
    if (starting.current) return // ignore clicks while the mic permission prompt / model load is pending
    starting.current = true
    setError(null)
    try {
      await player.current?.resume() // also plays Alex's greeting if it arrived before the first click
      if (!vad.current) {
        vad.current = await MicVAD.new({
          model: 'v5',
          baseAssetPath: '/vad/',
          onnxWASMBasePath: '/vad/',
          // A2 speakers pause to think mid-sentence; don't cut them off too early
          redemptionMs: 900,
          minSpeechMs: 300,
          getStream: () =>
            navigator.mediaDevices.getUserMedia({
              audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
            }),
          onSpeechRealStart: () => {
            if (pttMode.current) return // Space/the mic button decides start/end, not the silence detector
            if (player.current?.playing || awaitingReply.current) interrupt()
            setState('listening')
          },
          onSpeechEnd: (audio: Float32Array) => {
            if (pttMode.current) return
            speechEndedAt.current = performance.now()
            setState('thinking')
            ws.current?.send(audio.buffer as ArrayBuffer)
          },
          onVADMisfire: () => {
            if (pttMode.current) return
            setState(awaitingReply.current ? 'thinking' : 'idle')
          },
          onFrameProcessed: (_probs, frame) => {
            // push-to-talk still rides on the VAD's own 16kHz-resampled frames — it just decides "send it" by
            // key-hold instead of by the silence model, so no separate mic/resampling pipeline is needed.
            if (pttMode.current && pttActive.current) pttFrames.current.push(frame.slice())
          },
        })
      }
      await vad.current.start()
      setMicOn(true)
    } catch (e) {
      vad.current = null
      const denied = e instanceof DOMException && e.name === 'NotAllowedError'
      setError(denied ? 'Mikrofon izni verilmedi. Adres çubuğundaki kilit simgesinden izin ver.' : `Mikrofon başlatılamadı: ${e instanceof Error ? e.message : e}`)
    } finally {
      starting.current = false
    }
  }, [interrupt])

  const stopMic = useCallback(async () => {
    await vad.current?.pause()
    setMicOn(false)
    setState((s) => (s === 'listening' ? 'idle' : s))
  }, [])

  /** Hold-to-talk: call on key/pointer-down. Safe to call before the mic has finished starting — frames simply
   * won't arrive yet, so a very first press before the model loads just captures less (never garbage). */
  const pttDown = useCallback(() => {
    if (!pttMode.current || pttActive.current) return
    pttActive.current = true
    pttFrames.current = []
    if (player.current?.playing || awaitingReply.current) interrupt()
    setState('listening')
  }, [interrupt])

  /** Call on key/pointer-up: flushes whatever was captured while held as one turn, same as the auto-VAD's onSpeechEnd. */
  const pttUp = useCallback(() => {
    if (!pttMode.current || !pttActive.current) return
    pttActive.current = false
    const audio = concatFloat32(pttFrames.current)
    pttFrames.current = []
    if (audio.length < MIN_PTT_SAMPLES) {
      setState(awaitingReply.current ? 'thinking' : 'idle')
      return
    }
    speechEndedAt.current = performance.now()
    setState('thinking')
    ws.current?.send(audio.buffer as ArrayBuffer)
  }, [])

  const setPtt = useCallback((enabled: boolean) => {
    if (pttActive.current) {
      // mid-hold mode switch: no clean "end of turn" signal, so drop it rather than send a truncated guess
      pttActive.current = false
      pttFrames.current = []
      setState((s) => (s === 'listening' ? (awaitingReply.current ? 'thinking' : 'idle') : s))
    }
    pttMode.current = enabled
    setPttEnabled(enabled)
    localStorage.setItem(PTT_STORAGE_KEY, enabled ? '1' : '0')
  }, [])

  const sendText = useCallback(
    (text: string) => {
      void player.current?.resume()
      if (player.current?.playing || awaitingReply.current) interrupt()
      speechEndedAt.current = performance.now()
      ws.current?.send(JSON.stringify({ type: 'text', text }))
    },
    [interrupt],
  )

  const setSpeed = useCallback((value: number) => {
    speed.current = value
    ws.current?.send(JSON.stringify({ type: 'settings', speed: value }))
  }, [])

  const setLang = useCallback((value: SpeechLang) => {
    sttLang.current = value
    ws.current?.send(JSON.stringify({ type: 'settings', stt_lang: value }))
  }, [])

  return {
    state, messages, metrics, usage, unit, tokens, starters, micOn, error,
    startMic, stopMic, sendText, interrupt, setSpeed, setLang,
    pttEnabled, setPtt, pttDown, pttUp,
  }
}
