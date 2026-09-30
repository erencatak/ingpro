import type { WordNetwork, WordNeuron, WordStage } from './data'

// Illustrative only (shown with the "Örnek veri" badge): what the brain looks like after a few weeks of talking.
const W: [string, string, WordStage, number, number, number, number][] = [
  // id, category, stage, valence, arousal, retrievals, stability
  ['happy', 'feelings', 'entegre', 8.5, 6.1, 9, 14], ['sad', 'feelings', 'entegre', 2.1, 3.5, 5, 8],
  ['excited', 'feelings', 'hizli_tanima', 7.8, 6.9, 3, 3], ['nervous', 'feelings', 'hizli_tanima', 3.1, 6.6, 4, 2],
  ['tired', 'feelings', 'entegre', 3.6, 2.6, 7, 11], ['worried', 'feelings', 'hizli_tanima', 2.4, 5.9, 3, 1],
  ['meeting', 'work', 'entegre', 5.3, 3.7, 8, 12], ['project', 'work', 'entegre', 6.0, 4.1, 6, 9],
  ['colleague', 'work', 'hizli_tanima', 6.1, 3.5, 3, 2], ['interview', 'work', 'hizli_tanima', 5.3, 5.8, 4, 3],
  ['coffee', 'food', 'entegre', 6.9, 4.9, 10, 16], ['dinner', 'food', 'entegre', 7.2, 4.1, 5, 7],
  ['menu', 'food', 'hizli_tanima', 6.5, 3.5, 3, 2], ['order', 'food', 'hizli_tanima', 5.8, 4.2, 3, 1],
  ['flight', 'travel', 'hizli_tanima', 6.1, 5.4, 3, 2], ['trip', 'travel', 'entegre', 7.4, 5.6, 5, 8],
  ['hotel', 'travel', 'hizli_tanima', 6.7, 4.1, 3, 1], ['music', 'hobbies', 'entegre', 7.6, 5.2, 6, 10],
  ['movie', 'hobbies', 'hizli_tanima', 7.1, 4.9, 3, 2], ['family', 'people', 'entegre', 7.6, 4.8, 7, 12],
  ['friend', 'people', 'entegre', 8.1, 5.0, 6, 9], ['kitchen', 'home', 'hizli_tanima', 6.4, 3.4, 3, 1],
]

const CO: [string, string, number][] = [
  ['coffee', 'meeting', 0.62], ['tired', 'meeting', 0.48], ['happy', 'trip', 0.55], ['excited', 'flight', 0.4],
  ['nervous', 'interview', 0.58], ['dinner', 'family', 0.51], ['happy', 'friend', 0.44], ['music', 'friend', 0.3],
  ['coffee', 'project', 0.27], ['tired', 'project', 0.22], ['hotel', 'trip', 0.35], ['menu', 'order', 0.46],
  ['dinner', 'kitchen', 0.24], ['movie', 'friend', 0.28], ['worried', 'interview', 0.2], ['coffee', 'friend', 0.18],
]

export function demoNetwork(): WordNetwork {
  const nodes: WordNeuron[] = W.map(([id, category, stage, valence, arousal, retrievals, stability]) => ({
    id, category, stage, valence, arousal, dominance: 5, vad_source: 'dataset', cefr: 'A2',
    retrievals, successes: retrievals, stability, last_event_at: null,
  }))
  const edges: WordNetwork['edges'] = []
  const byCat = new Map<string, string[]>()
  for (const n of nodes) byCat.set(n.category!, [...(byCat.get(n.category!) ?? []), n.id])
  for (const ids of byCat.values())
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) edges.push({ a: ids[i], b: ids[j], kind: 'semantic', weight: 0.2, co: 0 })
  for (const [a, b, weight] of CO) edges.push({ a, b, kind: 'cooccurrence', weight, co: Math.round(weight * 10) })
  return { nodes, edges, stats: { neurons: nodes.length, synapses: edges.length, integrated: nodes.filter((n) => n.stage === 'entegre').length, last_consolidation: null } }
}
