import { useEffect, useState } from 'react'

import {
  findSavedOpportunity,
  removeSavedOpportunity,
  saveOpportunity,
  SavedOpportunityApiError,
} from '../../api/savedOpportunities'

export type SaveAccess = 'checking' | 'anonymous' | 'error' | 'authenticated'
export type SaveReturnOutcome =
  | { opportunityId: number; status: 'saved'; saveId: number }
  | { opportunityId: number; status: 'error'; message: string }

type SaveState =
  | { status: 'loading' }
  | { status: 'unsaved' }
  | { status: 'saved'; saveId: number }
  | { status: 'lookup-error' }

interface SaveOpportunityControlProps {
  opportunityId: number
  access: SaveAccess
  initialOutcome?: SaveReturnOutcome | null
  onRequestAuthentication?: (opportunityId: number) => void
  onSessionExpired?: () => void
}

function initialState(outcome: SaveReturnOutcome | null | undefined): SaveState {
  if (outcome?.status === 'saved') return { status: 'saved', saveId: outcome.saveId }
  if (outcome?.status === 'error') return { status: 'unsaved' }
  return { status: 'loading' }
}

export default function SaveOpportunityControl({
  opportunityId,
  access,
  initialOutcome,
  onRequestAuthentication,
  onSessionExpired,
}: SaveOpportunityControlProps) {
  const [state, setState] = useState<SaveState>(() => initialState(initialOutcome))
  const [message, setMessage] = useState<string | null>(
    initialOutcome?.status === 'error' ? initialOutcome.message : null,
  )
  const [pending, setPending] = useState<'saving' | 'removing' | null>(null)
  const [lookupAttempt, setLookupAttempt] = useState(0)

  useEffect(() => {
    if (access !== 'authenticated' || initialOutcome) return
    let active = true
    void findSavedOpportunity(opportunityId)
      .then((saved) => {
        if (active) {
          setState(saved ? { status: 'saved', saveId: saved.id } : { status: 'unsaved' })
          setMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!active) return
        if (error instanceof SavedOpportunityApiError && error.status === 401) {
          onSessionExpired?.()
        } else {
          setState({ status: 'lookup-error' })
          setMessage('Could not check whether this opportunity is saved. Try again.')
        }
      })
    return () => {
      active = false
    }
  }, [access, initialOutcome, lookupAttempt, onSessionExpired, opportunityId])

  async function handleAction() {
    if (access !== 'authenticated') {
      if (access === 'anonymous') onRequestAuthentication?.(opportunityId)
      return
    }
    if (state.status === 'lookup-error') {
      setState({ status: 'loading' })
      setMessage(null)
      setLookupAttempt((attempt) => attempt + 1)
      return
    }
    if (state.status === 'loading' || pending) return
    const removing = state.status === 'saved'
    setPending(removing ? 'removing' : 'saving')
    setMessage(null)
    try {
      if (removing) {
        await removeSavedOpportunity(state.saveId)
        setState({ status: 'unsaved' })
      } else {
        const saved = await saveOpportunity(opportunityId)
        setState({ status: 'saved', saveId: saved.id })
      }
    } catch (error: unknown) {
      if (error instanceof SavedOpportunityApiError && error.status === 401) {
        onSessionExpired?.()
      } else {
        setMessage(
          removing
            ? 'Could not remove this saved opportunity. Try again.'
            : 'Could not save this opportunity. Try again.',
        )
      }
    } finally {
      setPending(null)
    }
  }

  const buttonLabel =
    access === 'checking'
      ? 'Checking account...'
      : access === 'error'
        ? 'Account unavailable'
        : pending === 'saving'
          ? 'Saving...'
          : pending === 'removing'
            ? 'Removing...'
            : state.status === 'loading' && access === 'authenticated'
              ? 'Checking saved status...'
              : state.status === 'lookup-error' && access === 'authenticated'
                ? 'Retry saved status'
                : state.status === 'saved' && access === 'authenticated'
                  ? 'Remove saved opportunity'
                  : 'Save opportunity'

  return (
    <div className="opportunity-detail__save">
      <button
        className={`button ${state.status === 'saved' && access === 'authenticated' ? 'button--secondary' : 'button--primary'}`}
        type="button"
        onClick={() => void handleAction()}
        disabled={
          access === 'checking' ||
          access === 'error' ||
          pending !== null ||
          (access === 'authenticated' && state.status === 'loading')
        }
      >
        {buttonLabel}
      </button>
      {access === 'authenticated' && state.status === 'saved' && (
        <p className="opportunity-detail__save-status" role="status">Saved to your account.</p>
      )}
      {access === 'anonymous' && (
        <p className="opportunity-detail__save-status">
          Create a free account or log in to save this opportunity.
        </p>
      )}
      {access === 'error' && (
        <p className="opportunity-detail__save-status" role="alert">
          Account check unavailable. Retry from the header.
        </p>
      )}
      {message && <p className="opportunity-detail__save-error" role="alert">{message}</p>}
    </div>
  )
}
