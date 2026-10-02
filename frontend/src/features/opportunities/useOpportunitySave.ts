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

export type SuccessfulSaveAction = 'saved' | 'removed'

interface UseOpportunitySaveOptions {
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

export function useOpportunitySave({
  opportunityId,
  access,
  initialOutcome,
  onRequestAuthentication,
  onSessionExpired,
}: UseOpportunitySaveOptions) {
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

  async function handleAction(): Promise<SuccessfulSaveAction | null> {
    if (access !== 'authenticated') {
      if (access === 'anonymous') onRequestAuthentication?.(opportunityId)
      return null
    }
    if (state.status === 'lookup-error') {
      setState({ status: 'loading' })
      setMessage(null)
      setLookupAttempt((attempt) => attempt + 1)
      return null
    }
    if (state.status === 'loading' || pending) return null
    const removing = state.status === 'saved'
    setPending(removing ? 'removing' : 'saving')
    setMessage(null)
    try {
      if (removing) {
        await removeSavedOpportunity(state.saveId)
        setState({ status: 'unsaved' })
        return 'removed' as const
      } else {
        const saved = await saveOpportunity(opportunityId)
        setState({ status: 'saved', saveId: saved.id })
        return 'saved' as const
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
      return null
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

  return {
    buttonLabel,
    disabled:
      access === 'checking' ||
      access === 'error' ||
      pending !== null ||
      (access === 'authenticated' && state.status === 'loading'),
    isSaved: state.status === 'saved' && access === 'authenticated',
    isRemoving: pending === 'removing',
    message,
    handleAction,
  }
}
