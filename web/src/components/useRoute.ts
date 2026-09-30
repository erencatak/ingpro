import { useCallback, useEffect, useState } from 'react'

export const VIEWS = [
  { id: 'home', slug: 'bugun', label: 'Bugün', icon: 'home' },
  { id: 'chat', slug: 'sohbet', label: 'Sohbet', icon: 'chat' },
  { id: 'practice', slug: 'alistirma', label: 'Alıştırma', icon: 'target' },
  { id: 'grammar', slug: 'gramer', label: 'Gramer', icon: 'book' },
  { id: 'vocab', slug: 'kelimeler', label: 'Kelimeler', icon: 'cards' },
  { id: 'wordbrain', slug: 'beyin', label: 'Beyin', icon: 'sparkle' },
  { id: 'errors', slug: 'hatalar', label: 'Hatalar', icon: 'bug' },
  { id: 'progress', slug: 'ilerleme', label: 'İlerleme', icon: 'chart' },
] as const

export type ViewId = (typeof VIEWS)[number]['id']

// A view may own a sub-path or query after its slug (#gramer/12, #sohbet?topic=13)
const fromHash = (): ViewId => VIEWS.find((v) => v.slug === location.hash.slice(1).split(/[/?]/)[0])?.id ?? 'home'

export function useRoute() {
  const [view, setView] = useState<ViewId>(fromHash)

  useEffect(() => {
    const onHash = () => setView(fromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = useCallback((id: ViewId) => {
    const slug = VIEWS.find((v) => v.id === id)!.slug
    history.replaceState(null, '', `#${slug}`)
    setView(id)
    window.dispatchEvent(new HashChangeEvent('hashchange')) // replaceState is silent; views with a sub-path listen for this
    window.scrollTo(0, 0)
  }, [])

  return { view, go }
}
