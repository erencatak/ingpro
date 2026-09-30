/** Plays the tutor's sentence-by-sentence PCM chunks back to back, and can be cut off instantly (barge-in). */

const SAMPLE_RATE = 24000

export class PcmPlayer {
  private ctx = new AudioContext({ sampleRate: SAMPLE_RATE })
  private nextStart = 0
  private sources = new Set<AudioBufferSourceNode>()
  onIdle?: () => void

  get playing() {
    return this.sources.size > 0
  }

  /** Browsers keep audio suspended until a user gesture; call this from one (e.g. the mic button). */
  resume() {
    return this.ctx.resume()
  }

  enqueue(pcm16: Int16Array) {
    if (this.ctx.state === 'suspended') void this.ctx.resume()
    const buffer = this.ctx.createBuffer(1, pcm16.length, SAMPLE_RATE)
    const channel = buffer.getChannelData(0)
    for (let i = 0; i < pcm16.length; i++) channel[i] = pcm16[i] / 32768

    const source = this.ctx.createBufferSource()
    source.buffer = buffer
    source.connect(this.ctx.destination)
    const startAt = Math.max(this.ctx.currentTime + 0.02, this.nextStart)
    source.start(startAt)
    this.nextStart = startAt + buffer.duration
    this.sources.add(source)
    source.onended = () => {
      this.sources.delete(source)
      if (!this.playing) this.onIdle?.()
    }
  }

  stop() {
    for (const s of this.sources) {
      s.onended = null
      s.stop()
    }
    this.sources.clear()
    this.nextStart = 0
  }
}
