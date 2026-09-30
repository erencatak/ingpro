import type { CSSProperties } from 'react'
import { SPRITE } from './sprite'

/** Renders the icon symbols once; <Icon> elements reference them via <use>. */
export function Sprite() {
  return <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true" dangerouslySetInnerHTML={{ __html: SPRITE }} />
}

export function Icon({ name, size, className = '', style }: { name: string; size?: 'sm' | 'lg'; className?: string; style?: CSSProperties }) {
  return (
    <svg className={`ic ${size ? `ic-${size}` : ''} ${className}`} style={style} aria-hidden="true">
      <use href={`#i-${name}`} />
    </svg>
  )
}

export function Flame({ small }: { small?: boolean }) {
  return (
    <svg className="flame" style={small ? { width: 20, height: 20 } : undefined} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="var(--flame)" d="M12 23c4.4 0 7.5-3 7.5-7.4 0-4.8-3.7-6.9-4.8-11.6-2.2 1.6-3.2 3.7-3.2 5.8C10.4 8.7 9.9 7.6 9.9 6.6 7 9 5 12.2 5 15.6 5 20 8 23 12 23Z" />
      <path className="f-in" fill="var(--flame-2)" d="M12 22c2.2 0 3.8-1.5 3.8-3.7 0-2.4-1.8-3.4-2.4-5.8-1.9 1.4-3.6 3.2-3.6 5.8 0 2.2 0 3.7 2.2 3.7Z" />
    </svg>
  )
}
