import type { Ref } from 'react'

type OpportunityStateVariant = 'loading' | 'empty' | 'error'

interface OpportunityStateProps {
  variant: OpportunityStateVariant
  title: string
  children?: string
  action?: {
    label: string
    onClick: () => void
  }
  headingId?: string
  headingRef?: Ref<HTMLHeadingElement>
  headingLevel?: 2 | 3
}

function OpportunityState({
  variant,
  title,
  children,
  action,
  headingId,
  headingRef,
  headingLevel = 3,
}: OpportunityStateProps) {
  const isError = variant === 'error'
  const heading =
    headingLevel === 2 ? (
      <h2 id={headingId} ref={headingRef} tabIndex={-1}>
        {title}
      </h2>
    ) : (
      <h3 id={headingId}>{title}</h3>
    )

  return (
    <div
      className={`opportunity-state opportunity-state--${variant}`}
      role={isError ? 'alert' : 'status'}
      aria-atomic="true"
    >
      {variant === 'loading' && (
        <span className="opportunity-state__spinner" aria-hidden="true">
          <svg viewBox="0 0 24 24" focusable="false">
            <circle cx="12" cy="12" r="8" />
            <path d="M12 4a8 8 0 0 1 8 8" />
          </svg>
        </span>
      )}
      <div className="opportunity-state__content">
        {heading}
        {children !== undefined && <p>{children}</p>}
        {action !== undefined && (
          <button
            className="button button--secondary opportunity-state__action"
            type="button"
            onClick={action.onClick}
          >
            {action.label}
          </button>
        )}
      </div>
    </div>
  )
}

export default OpportunityState
