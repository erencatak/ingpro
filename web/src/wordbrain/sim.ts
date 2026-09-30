import type { WordNetwork } from './data'

/** One neuron's place in the picture. Pure layout state, no drawing. */
export interface Body {
  id: string
  x: number
  y: number
  vx: number
  vy: number
  r: number
  region: number
}

/**
 * A small force layout that reads like a cortex: every semantic category is a "region" anchored on a ring,
 * neurons are pulled towards their region's anchor, pushed off each other, and pulled together along synapses
 * (stronger synapse = shorter, tighter link). Words without a category drift in the middle.
 */
export class Layout {
  bodies: Body[] = []
  regions: string[] = []
  private index = new Map<string, Body>()
  private links: { a: Body; b: Body; w: number }[] = []

  constructor(net: WordNetwork, w: number, h: number, prev?: Layout) {
    this.regions = [...new Set(net.nodes.map((n) => n.category).filter((c): c is string => !!c))].sort()
    for (const n of net.nodes) {
      const old = prev?.index.get(n.id)
      const region = n.category ? this.regions.indexOf(n.category) : -1
      const [ax, ay] = this.anchor(region, w, h)
      const b: Body = old
        ? { ...old, region }
        : { id: n.id, x: ax + Math.cos(this.bodies.length * 2.4) * 40, y: ay + Math.sin(this.bodies.length * 2.4) * 40, vx: 0, vy: 0, r: 0, region }
      b.r = 7 + Math.min(10, Math.sqrt(n.retrievals) * 2.2) + Math.min(5, n.stability / 4)
      this.bodies.push(b)
      this.index.set(n.id, b)
    }
    for (const e of net.edges) {
      const a = this.index.get(e.a), b = this.index.get(e.b)
      if (a && b) this.links.push({ a, b, w: e.weight })
    }
  }

  get(id: string) {
    return this.index.get(id)
  }

  anchor(region: number, w: number, h: number): [number, number] {
    if (region < 0 || this.regions.length === 0) return [w / 2, h / 2]
    const t = (region / this.regions.length) * Math.PI * 2 - Math.PI / 2
    const rx = this.regions.length === 1 ? 0 : w * 0.34, ry = this.regions.length === 1 ? 0 : h * 0.32
    return [w / 2 + Math.cos(t) * rx, h / 2 + 12 + Math.sin(t) * ry]
  }

  /** One integration step. Returns the total motion, so the caller can let it rest once it settles. */
  step(w: number, h: number): number {
    const bs = this.bodies
    for (let i = 0; i < bs.length; i++) {
      for (let j = i + 1; j < bs.length; j++) {
        const a = bs[i], b = bs[j]
        let dx = b.x - a.x, dy = b.y - a.y
        let d2 = dx * dx + dy * dy
        if (d2 > 260 * 260) continue
        if (d2 < 0.01) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 0.25 }
        const min = a.r + b.r + 36
        const f = Math.min(4, ((min * min) / d2) * 0.9) // capped: a crowded start must not fling neurons into the corners
        const d = Math.sqrt(d2)
        const fx = (dx / d) * f, fy = (dy / d) * f
        a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy
      }
    }
    for (const { a, b, w: wt } of this.links) {
      const dx = b.x - a.x, dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const cross = a.region !== b.region
      const rest = cross ? 150 : 60 + (1 - wt) * 50
      const f = (d - rest) * 0.01 * (0.4 + wt) * (cross ? 0.25 : 1) // links across regions stretch; regions stay distinct
      a.vx += (dx / d) * f; a.vy += (dy / d) * f; b.vx -= (dx / d) * f; b.vy -= (dy / d) * f
    }
    let motion = 0
    for (const b of bs) {
      const [ax, ay] = this.anchor(b.region, w, h)
      b.vx += (ax - b.x) * 0.012
      b.vy += (ay - b.y) * 0.012
      b.vx *= 0.82; b.vy *= 0.82
      b.x = Math.max(b.r + 8, Math.min(w - b.r - 8, b.x + b.vx))
      b.y = Math.max(b.r + 8, Math.min(h - b.r - 8, b.y + b.vy))
      motion += Math.abs(b.vx) + Math.abs(b.vy)
    }
    return motion
  }
}
