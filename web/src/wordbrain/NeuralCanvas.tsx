import { useEffect, useRef } from 'react'
import { CATEGORY_LABEL, type WordNetwork, type WordNeuron } from './data'
import { Layout } from './sim'

export type ColorMode = 'emotion' | 'category'

interface Props {
  net: WordNetwork
  mode: ColorMode
  selected: string | null
  onSelect: (id: string | null) => void
}

/** An action potential travelling along one synapse. */
interface Spike { edge: number; t: number; dir: 1 | -1; speed: number; strength: number }

interface Theme { dark: boolean; text: string; muted: string; surface: string; line: string; brand: string }

const CATEGORY_HUES: Record<string, number> = {
  feelings: 330, work: 205, food: 28, travel: 170, tech: 250, home: 45, people: 290, weather: 190, hobbies: 110, health: 355, shopping: 75,
}

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return (h >>> 0) / 4294967295
}

function readTheme(el: HTMLElement): Theme {
  const cs = getComputedStyle(el)
  const v = (n: string) => cs.getPropertyValue(n).trim()
  const surface = v('--surface') || '#181522'
  const m = surface.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i)
  const lum = m ? (0.2126 * parseInt(m[1], 16) + 0.7152 * parseInt(m[2], 16) + 0.0722 * parseInt(m[3], 16)) / 255 : 0
  return { dark: lum < 0.5, text: v('--text'), muted: v('--muted') || v('--text-2'), surface, line: v('--line-strong'), brand: v('--brand') }
}

/** Valence 1-9 on a diverging scale: unpleasant = cool blue, neutral = brand violet, pleasant = warm rose. */
function emotionHsl(n: WordNeuron, dark: boolean): [number, number, number] {
  if (n.valence == null) return [255, 8, dark ? 62 : 55]
  const t = (n.valence - 1) / 8
  const hue = t < 0.5 ? 215 + (262 - 215) * (t / 0.5) : 262 + (345 - 262) * ((t - 0.5) / 0.5)
  const sat = 55 + Math.abs(t - 0.5) * 70
  return [hue, sat, dark ? 68 : 52]
}

function categoryHsl(n: WordNeuron, dark: boolean): [number, number, number] {
  if (!n.category) return [255, 8, dark ? 62 : 55]
  return [CATEGORY_HUES[n.category] ?? 260, 72, dark ? 66 : 48]
}

const hsla = ([h, s, l]: [number, number, number], a: number) => `hsla(${h} ${s}% ${l}% / ${a})`

export function NeuralCanvas({ net, mode, selected, onSelect }: Props) {
  const wrap = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const layout = useRef<Layout | null>(null)
  const hover = useRef<string | null>(null)
  const sel = useRef(selected)
  const fire = useRef<string | null>(null)

  // A click on a neuron fires it: the spikes spread along all of its synapses (spreading activation).
  useEffect(() => {
    sel.current = selected
    if (selected) fire.current = selected
  }, [selected])

  useEffect(() => {
    const el = canvas.current!, box = wrap.current!
    const ctx = el.getContext('2d')!
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
    const byId = new Map(net.nodes.map((n) => [n.id, n]))
    const neighbors = new Map<string, Set<string>>()
    for (const e of net.edges) {
      if (!neighbors.has(e.a)) neighbors.set(e.a, new Set())
      if (!neighbors.has(e.b)) neighbors.set(e.b, new Set())
      neighbors.get(e.a)!.add(e.b)
      neighbors.get(e.b)!.add(e.a)
    }
    let w = 0, h = 0, dpr = 1
    let theme = readTheme(box)
    let spikes: Spike[] = []
    let frame = 0, raf = 0, settled = 0, lastFire = 0
    let drag: { id: string; dx: number; dy: number; sx: number; sy: number; moved: boolean } | null = null

    const resize = () => {
      const r = box.getBoundingClientRect()
      w = Math.max(320, r.width)
      h = Math.max(360, r.height)
      dpr = Math.min(2, window.devicePixelRatio || 1)
      el.width = w * dpr
      el.height = h * dpr
      el.style.width = `${w}px`
      el.style.height = `${h}px`
      layout.current = new Layout(net, w, h, layout.current ?? undefined)
      settled = 0
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(box)
    const themeObs = new MutationObserver(() => { theme = readTheme(box) })
    themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

    const geom = (i: number) => {
      const e = net.edges[i], L = layout.current!
      const a = L.get(e.a)!, b = L.get(e.b)!
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
      const dx = b.x - a.x, dy = b.y - a.y
      const bend = (hash(e.a + e.b) - 0.5) * 0.5
      return { a, b, cx: mx - dy * bend, cy: my + dx * bend }
    }
    const at = (g: ReturnType<typeof geom>, t: number) => {
      const u = 1 - t
      return [u * u * g.a.x + 2 * u * t * g.cx + t * t * g.b.x, u * u * g.a.y + 2 * u * t * g.cy + t * t * g.b.y]
    }

    const emit = (id: string, strength: number) => {
      net.edges.forEach((e, i) => {
        if (e.a !== id && e.b !== id) return
        spikes.push({ edge: i, t: 0, dir: e.a === id ? 1 : -1, speed: 0.006 + e.weight * 0.018, strength: strength * (0.4 + e.weight) })
      })
    }

    const color = (n: WordNeuron) => (mode === 'emotion' ? emotionHsl(n, theme.dark) : categoryHsl(n, theme.dark))

    const draw = (now: number) => {
      frame++
      const L = layout.current!
      if (settled < 400 || drag) {
        const motion = L.step(w, h)
        settled = motion < 0.4 * L.bodies.length ? settled + 4 : settled + 1
      }
      if (frame % 60 === 0) theme = readTheme(box)

      // spontaneous activity: now and then a random active neuron fires on its own
      if (!reduced && net.nodes.length && now - lastFire > 1400) {
        lastFire = now
        const active = net.nodes.filter((n) => neighbors.has(n.id))
        if (active.length) emit(active[Math.floor(Math.random() * active.length)].id, 0.7)
      }
      if (fire.current) { emit(fire.current, 1.4); fire.current = null }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)
      const focus = hover.current ?? sel.current
      const lit = focus ? new Set([focus, ...(neighbors.get(focus) ?? [])]) : null

      // cortical regions: a soft field and a faint label per semantic category
      L.regions.forEach((cat, i) => {
        const [x, y] = L.anchor(i, w, h)
        const hue = CATEGORY_HUES[cat] ?? 260
        const g = ctx.createRadialGradient(x, y, 0, x, y, Math.min(w, h) * 0.2)
        g.addColorStop(0, `hsla(${hue} 70% ${theme.dark ? 60 : 55}% / ${theme.dark ? 0.09 : 0.07})`)
        g.addColorStop(1, `hsla(${hue} 70% 60% / 0)`)
        ctx.fillStyle = g
        ctx.beginPath()
        ctx.arc(x, y, Math.min(w, h) * 0.2, 0, Math.PI * 2)
        ctx.fill()
        ctx.font = '600 11px system-ui, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillStyle = `hsla(${hue} 50% ${theme.dark ? 75 : 35}% / 0.55)`
        ctx.fillText((CATEGORY_LABEL[cat] ?? cat).toUpperCase(), x, y - Math.min(w, h) * 0.17)
      })

      // synapses
      net.edges.forEach((e, i) => {
        const g = geom(i)
        const on = !lit || (lit.has(e.a) && lit.has(e.b))
        const na = byId.get(e.a)!, nb = byId.get(e.b)!
        ctx.beginPath()
        ctx.moveTo(g.a.x, g.a.y)
        ctx.quadraticCurveTo(g.cx, g.cy, g.b.x, g.b.y)
        if (e.kind === 'semantic') {
          ctx.setLineDash([3, 5])
          ctx.lineWidth = 1
          ctx.strokeStyle = hsla(color(na), on ? 0.35 : 0.07)
        } else {
          ctx.setLineDash([])
          ctx.lineWidth = 1 + e.weight * 3.5
          const grad = ctx.createLinearGradient(g.a.x, g.a.y, g.b.x, g.b.y)
          grad.addColorStop(0, hsla(color(na), on ? 0.55 : 0.08))
          grad.addColorStop(1, hsla(color(nb), on ? 0.55 : 0.08))
          ctx.strokeStyle = grad
        }
        ctx.stroke()
      })
      ctx.setLineDash([])

      // action potentials
      if (!reduced) {
        ctx.globalCompositeOperation = theme.dark ? 'lighter' : 'source-over'
        spikes = spikes.filter((s) => {
          s.t += s.speed
          if (s.t >= 1) return false
          const e = net.edges[s.edge]
          const g = geom(s.edge)
          const [x, y] = at(g, s.dir === 1 ? s.t : 1 - s.t)
          const target = byId.get(s.dir === 1 ? e.b : e.a)!
          const fade = Math.sin(Math.PI * s.t)
          const r = 2 + s.strength * 2.5
          const glow = ctx.createRadialGradient(x, y, 0, x, y, r * 4)
          glow.addColorStop(0, hsla(color(target), 0.9 * fade))
          glow.addColorStop(1, hsla(color(target), 0))
          ctx.fillStyle = glow
          ctx.beginPath()
          ctx.arc(x, y, r * 4, 0, Math.PI * 2)
          ctx.fill()
          return true
        })
        ctx.globalCompositeOperation = 'source-over'
      }

      // neurons
      const t = now / 1000
      for (const n of net.nodes) {
        const b = L.get(n.id)!
        const c = color(n)
        const dim = lit && !lit.has(n.id)
        const alpha = dim ? 0.18 : 1
        const arousal = n.arousal == null ? 0.4 : (n.arousal - 1) / 8
        const seed = hash(n.id)

        // halo: brighter and faster-breathing for high-arousal words
        const breathe = reduced ? 0.5 : 0.5 + 0.5 * Math.sin(t * (1 + arousal * 2.5) + seed * 6.28)
        const halo = ctx.createRadialGradient(b.x, b.y, b.r * 0.6, b.x, b.y, b.r * (2.4 + arousal * 1.4))
        halo.addColorStop(0, hsla(c, (0.25 + 0.25 * breathe) * alpha))
        halo.addColorStop(1, hsla(c, 0))
        ctx.fillStyle = halo
        ctx.beginPath()
        ctx.arc(b.x, b.y, b.r * (2.4 + arousal * 1.4), 0, Math.PI * 2)
        ctx.fill()

        // dendrites
        const count = 5 + Math.floor(seed * 4)
        ctx.strokeStyle = hsla(c, 0.55 * alpha)
        ctx.lineCap = 'round'
        for (let k = 0; k < count; k++) {
          const ang = (k / count) * Math.PI * 2 + seed * 6.28 + (reduced ? 0 : Math.sin(t * 0.4 + k) * 0.06)
          const len = b.r * (0.9 + hash(n.id + k) * 0.9)
          const x1 = b.x + Math.cos(ang) * b.r, y1 = b.y + Math.sin(ang) * b.r
          const x2 = b.x + Math.cos(ang) * (b.r + len), y2 = b.y + Math.sin(ang) * (b.r + len)
          ctx.lineWidth = 1.6
          ctx.beginPath()
          ctx.moveTo(x1, y1)
          ctx.lineTo(x2, y2)
          ctx.stroke()
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.moveTo(x2, y2)
          ctx.lineTo(x2 + Math.cos(ang + 0.6) * len * 0.35, y2 + Math.sin(ang + 0.6) * len * 0.35)
          ctx.moveTo(x2, y2)
          ctx.lineTo(x2 + Math.cos(ang - 0.6) * len * 0.35, y2 + Math.sin(ang - 0.6) * len * 0.35)
          ctx.stroke()
        }

        // soma
        const soma = ctx.createRadialGradient(b.x - b.r * 0.35, b.y - b.r * 0.35, b.r * 0.1, b.x, b.y, b.r)
        soma.addColorStop(0, hsla([c[0], c[1], Math.min(92, c[2] + 22)], alpha))
        soma.addColorStop(1, hsla([c[0], c[1], c[2] - 8], alpha))
        ctx.fillStyle = soma
        ctx.beginPath()
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = hsla([c[0], c[1] * 0.6, theme.dark ? 20 : 30], 0.55 * alpha)
        ctx.beginPath()
        ctx.arc(b.x, b.y, b.r * 0.32, 0, Math.PI * 2)
        ctx.fill()

        // stage ring: fragile dashed (hippocampal, fast recognition) vs. solid double ring (integrated, myelinated)
        if (n.stage === 'entegre') {
          ctx.strokeStyle = hsla(c, 0.9 * alpha)
          ctx.lineWidth = 2
          ctx.beginPath(); ctx.arc(b.x, b.y, b.r + 3, 0, Math.PI * 2); ctx.stroke()
          ctx.lineWidth = 1
          ctx.beginPath(); ctx.arc(b.x, b.y, b.r + 6, 0, Math.PI * 2); ctx.stroke()
        } else if (n.stage === 'hizli_tanima') {
          ctx.setLineDash([2, 4])
          ctx.lineDashOffset = reduced ? 0 : -t * 8
          ctx.strokeStyle = hsla(c, 0.7 * alpha)
          ctx.lineWidth = 1.2
          ctx.beginPath(); ctx.arc(b.x, b.y, b.r + 4, 0, Math.PI * 2); ctx.stroke()
          ctx.setLineDash([])
        }

        if (sel.current === n.id) {
          ctx.strokeStyle = theme.text
          ctx.lineWidth = 1.5
          ctx.beginPath(); ctx.arc(b.x, b.y, b.r + 10, 0, Math.PI * 2); ctx.stroke()
        }

        // label
        const show = !dim && (focus === n.id || !lit || lit.has(n.id) || b.r > 12)
        if (show) {
          ctx.font = `${focus === n.id ? 700 : 600} 12px system-ui, sans-serif`
          ctx.textAlign = 'center'
          ctx.lineWidth = 3
          ctx.strokeStyle = theme.surface
          ctx.strokeText(n.id, b.x, b.y + b.r + 18)
          ctx.fillStyle = theme.text
          ctx.fillText(n.id, b.x, b.y + b.r + 18)
        }
      }
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)

    const pick = (ev: PointerEvent) => {
      const r = el.getBoundingClientRect()
      const x = ev.clientX - r.left, y = ev.clientY - r.top
      let best: string | null = null, bd = Infinity
      for (const b of layout.current!.bodies) {
        const d = Math.hypot(b.x - x, b.y - y)
        if (d < b.r + 8 && d < bd) { bd = d; best = b.id }
      }
      return { id: best, x, y }
    }
    const onMove = (ev: PointerEvent) => {
      const p = pick(ev)
      if (drag) {
        if (!drag.moved && Math.hypot(p.x - drag.sx, p.y - drag.sy) < 5) return // a click, not a drag
        const b = layout.current!.get(drag.id)!
        b.x = p.x - drag.dx; b.y = p.y - drag.dy; b.vx = 0; b.vy = 0
        drag.moved = true
        settled = 0
        return
      }
      hover.current = p.id
      el.style.cursor = p.id ? 'pointer' : 'default'
    }
    const onDown = (ev: PointerEvent) => {
      const p = pick(ev)
      if (!p.id) return
      const b = layout.current!.get(p.id)!
      drag = { id: p.id, dx: p.x - b.x, dy: p.y - b.y, sx: p.x, sy: p.y, moved: false }
      el.setPointerCapture(ev.pointerId)
    }
    const onUp = (ev: PointerEvent) => {
      if (drag && !drag.moved) onSelect(drag.id === sel.current ? null : drag.id)
      else if (!drag && !pick(ev).id) onSelect(null)
      drag = null
    }
    const onLeave = () => { hover.current = null }
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointerleave', onLeave)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      themeObs.disconnect()
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointerup', onUp)
      el.removeEventListener('pointerleave', onLeave)
    }
  }, [net, mode, onSelect])

  return (
    <div className="wb-canvas" ref={wrap}>
      <canvas ref={canvas} role="img" aria-label={`Kelime beyni: ${net.nodes.length} nöron, ${net.edges.length} sinaps`} />
    </div>
  )
}
