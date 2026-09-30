import { useEffect, useState } from 'react'

export type WordStage = 'uyuyan' | 'hizli_tanima' | 'entegre'
export type SynapseKind = 'semantic' | 'cooccurrence'

export interface WordNeuron {
  id: string
  cefr: string | null
  category: string | null
  stage: WordStage
  valence: number | null
  arousal: number | null
  dominance: number | null
  vad_source: 'dataset' | 'llm' | null
  retrievals: number
  successes: number
  stability: number
  last_event_at: string | null
}

export interface WordSynapse {
  a: string
  b: string
  kind: SynapseKind
  weight: number
  co: number
}

export interface WordNetwork {
  nodes: WordNeuron[]
  edges: WordSynapse[]
  stats: { neurons: number; synapses: number; integrated: number; last_consolidation: string | null }
}

export const STAGE_LABEL: Record<WordStage, string> = { uyuyan: 'Uyuyan', hizli_tanima: 'Hızlı tanıma', entegre: 'Entegre' }
export const KIND_LABEL: Record<SynapseKind, string> = { semantic: 'Anlam ortaklığı', cooccurrence: 'Birlikte kullanım' }
export const CATEGORY_LABEL: Record<string, string> = {
  work: 'İş', food: 'Yemek', travel: 'Seyahat', tech: 'Teknoloji', feelings: 'Duygular', home: 'Ev',
  people: 'İnsanlar', weather: 'Hava', hobbies: 'Hobiler', health: 'Sağlık', shopping: 'Alışveriş',
}

/** The vocabulary brain (server: brain/service.py word_network); reloads when the tab comes back. */
export function useWordNetwork() {
  const [net, setNet] = useState<WordNetwork | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    const load = () =>
      fetch('/api/words/brain')
        .then((r) => (r.ok ? (r.json() as Promise<WordNetwork>) : Promise.reject()))
        .then((d) => { setNet(d); setError(false) })
        .catch(() => setError(true))
    void load()
    const again = () => document.visibilityState === 'visible' && void load()
    document.addEventListener('visibilitychange', again)
    return () => document.removeEventListener('visibilitychange', again)
  }, [])
  return { net, error }
}
