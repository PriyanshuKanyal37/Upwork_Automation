import type { ReactNode } from 'react'

type BrandWordmarkProps = {
  compact?: boolean
  eyebrow?: ReactNode
}

export function BrandWordmark({ compact = false, eyebrow }: BrandWordmarkProps) {
  return (
    <div className={['brand-lockup', compact ? 'brand-lockup--compact' : ''].join(' ').trim()}>
      <div className="brand-copy">
        {eyebrow ? <div className="brand-eyebrow">{eyebrow}</div> : null}
        <p className="brand-title" aria-label="Ladder Jobs">
          <span className="brand-title-main">Ladder</span>
          <span className="brand-title-divider">/</span>
          <span className="brand-title-accent">Jobs</span>
        </p>
        <p className="brand-subtitle">AI proposal workflow</p>
      </div>
    </div>
  )
}
