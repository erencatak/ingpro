/** The four speaking-point rules, in the order the learner sees them. */
export const RULES = [
  { rule: 1, points: 3, text: 'Kural doğru + yeni kelime + net telaffuz' },
  { rule: 2, points: 2, text: 'Kural doğru + bilinen kelime + net telaffuz' },
  { rule: 3, points: 1, text: 'Kural eksik ya da hatalı + kelime + net telaffuz' },
  { rule: 4, points: 0, text: 'Yalnızca kelimelerle konuşma' },
] as const

export const REQUIRED_TEXT = 'Onay için: A1–A2 konu 30, B1–B2 konu 60, C1 konu 90 puan.'
