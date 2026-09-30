import { Icon } from './Icon'

/** Marks screens that still show placeholder data instead of the learner's real progress. */
export function DemoBadge() {
  return (
    <span className="pill pill-warn" title="Bu ekran henüz gerçek verine bağlı değil; kayıt sistemi Faz 1'de geliyor.">
      <Icon name="bulb" size="sm" />Örnek veri
    </span>
  )
}
