import { useEffect, useRef, useState, type MouseEvent } from 'react'

import {
  type SaveAccess,
  type SaveReturnOutcome,
  type SuccessfulSaveAction,
  useOpportunitySave,
} from './useOpportunitySave'

interface QuickSaveOpportunityControlProps {
  opportunityId: number
  access: SaveAccess
  initialOutcome?: SaveReturnOutcome | null
  onRequestAuthentication?: (opportunityId: number) => void
  onSessionExpired?: () => void
  onSuccessfulAction?: (action: SuccessfulSaveAction) => void
  onToast?: (message: string) => void
}

interface QuickSaveToastProps {
  message: string | null
}

export function QuickSaveToast({ message }: QuickSaveToastProps) {
  if (message === null) return null
  return (
    <p className="opportunity-card__save-status" role="status" aria-live="polite">
      {message}
    </p>
  )
}

export default function QuickSaveOpportunityControl({
  opportunityId,
  access,
  initialOutcome,
  onRequestAuthentication,
  onSessionExpired,
  onSuccessfulAction,
  onToast,
}: QuickSaveOpportunityControlProps) {
  const {
    buttonLabel,
    disabled,
    handleAction,
    isRemoving,
    isSaved,
    message,
  } = useOpportunitySave({
    opportunityId,
    access,
    initialOutcome,
    onRequestAuthentication,
    onSessionExpired,
  })
  const [status, setStatus] = useState<string | null>(null)
  const statusTimeout = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (statusTimeout.current !== null) {
        window.clearTimeout(statusTimeout.current)
      }
    }
  }, [])

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()
    void handleAction().then((action) => {
      if (action === null) return
      const message =
        action === 'saved'
          ? 'Opportunity saved'
          : 'Removed from saved opportunities'
      if (onToast !== undefined) {
        onToast(message)
      } else {
        setStatus(message)
        if (statusTimeout.current !== null) {
          window.clearTimeout(statusTimeout.current)
        }
        statusTimeout.current = window.setTimeout(() => setStatus(null), 2000)
      }
      onSuccessfulAction?.(action)
    })
  }

  const isPressed = isSaved && !isRemoving

  return (
    <div className="opportunity-card__quick-save">
      <button
        className={`opportunity-card__save-button${isPressed ? ' opportunity-card__save-button--saved' : ''}`}
        type="button"
        aria-label={buttonLabel}
        aria-pressed={isPressed}
        disabled={disabled}
        onClick={handleClick}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5V21l-6-3.5L6 21V4.5Z" />
        </svg>
      </button>
      <QuickSaveToast message={status} />
      {message !== null && (
        <p className="opportunity-card__save-error" role="alert">
          {message}
        </p>
      )}
    </div>
  )
}
