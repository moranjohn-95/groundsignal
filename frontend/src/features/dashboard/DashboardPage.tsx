import { useEffect, useState, type MouseEvent } from 'react'

import {
  listSavedOpportunities,
  removeSavedOpportunity,
  SavedOpportunityApiError,
  type SavedOpportunity,
} from '../../api/savedOpportunities'
import OpportunityCard from '../opportunities/OpportunityCard'
import OpportunityState from '../opportunities/OpportunityState'
import { electricalWorkBriefFor } from '../opportunities/opportunityPresentation'

interface Props {
  onNavigate: (event: MouseEvent<HTMLAnchorElement>) => void
  onViewOpportunity: (opportunityId: number) => void
  onSessionExpired: () => void
}

type ListState =
  | { status: 'loading' | 'error' }
  | { status: 'ready'; items: SavedOpportunity[] }

type SavedOpportunitySort =
  | 'recently-saved'
  | 'best-opportunity'
  | 'newest-received'
  | 'oldest-received'

function timestampFor(value: unknown) {
  if (typeof value !== 'string') return null
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

function scoreFor(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function compareValues(
  first: number | null,
  second: number | null,
  direction: 'ascending' | 'descending',
) {
  if (first === null) return second === null ? 0 : 1
  if (second === null) return -1
  return direction === 'ascending' ? first - second : second - first
}

function sortSavedOpportunities(
  items: SavedOpportunity[],
  sort: SavedOpportunitySort,
) {
  return items
    .map((item, index) => ({ item, index }))
    .sort((first, second) => {
      const firstOpportunity = first.item.opportunity
      const secondOpportunity = second.item.opportunity
      const comparison = sort === 'best-opportunity'
        ? compareValues(
            scoreFor(firstOpportunity.opportunity_score),
            scoreFor(secondOpportunity.opportunity_score),
            'descending',
          )
        : sort === 'oldest-received'
          ? compareValues(
              timestampFor(firstOpportunity.received_date),
              timestampFor(secondOpportunity.received_date),
              'ascending',
            )
          : sort === 'newest-received'
            ? compareValues(
                timestampFor(firstOpportunity.received_date),
                timestampFor(secondOpportunity.received_date),
                'descending',
              )
            : compareValues(
                timestampFor(first.item.saved_at),
                timestampFor(second.item.saved_at),
                'descending',
              )
      return comparison === 0 ? first.index - second.index : comparison
    })
    .map(({ item }) => item)
}

function summaryFor(items: SavedOpportunity[]) {
  const scores = items
    .map((item) => scoreFor(item.opportunity.opportunity_score))
    .filter((score): score is number => score !== null)

  return {
    savedCount: items.length,
    bestScore: scores.length === 0 ? null : Math.max(...scores),
    confirmedSignalCount: items.filter(
      (item) => electricalWorkBriefFor(item.opportunity).evidence_level === 'direct',
    ).length,
  }
}

export default function DashboardPage({ onNavigate, onViewOpportunity, onSessionExpired }: Props) {
  const [list, setList] = useState<ListState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [removingId, setRemovingId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [removalStatus, setRemovalStatus] = useState<string | null>(null)
  const [sort, setSort] = useState<SavedOpportunitySort>('recently-saved')
  const summary = list.status === 'ready' ? summaryFor(list.items) : null

  useEffect(() => {
    let cancelled = false
    void listSavedOpportunities().then((items) => {
      if (!cancelled) setList({ status: 'ready', items })
    }).catch((error: unknown) => {
      if (cancelled) return
      if (error instanceof SavedOpportunityApiError && error.status === 401) {
        onSessionExpired()
      } else {
        setList({ status: 'error' })
      }
    })
    return () => { cancelled = true }
  }, [attempt, onSessionExpired])

  useEffect(() => {
    if (removalStatus === null) return
    const timeout = window.setTimeout(() => setRemovalStatus(null), 4000)
    return () => window.clearTimeout(timeout)
  }, [removalStatus])

  function retry() {
    setFeedback(null)
    setRemovalStatus(null)
    setList({ status: 'loading' })
    setAttempt((value) => value + 1)
  }

  async function remove(item: SavedOpportunity) {
    if (removingId !== null) return
    setRemovingId(item.id)
    setFeedback(null)
    setRemovalStatus(null)
    try {
      await removeSavedOpportunity(item.id)
      setList((current) => current.status === 'ready'
        ? { status: 'ready', items: current.items.filter((saved) => saved.id !== item.id) }
        : current)
      setRemovalStatus('Removed from saved opportunities')
    } catch (error: unknown) {
      if (error instanceof SavedOpportunityApiError && error.status === 401) {
        onSessionExpired()
      } else {
        setFeedback('Could not remove this save. Please try again.')
      }
    } finally {
      setRemovingId(null)
    }
  }

  return <section className="dashboard" aria-labelledby="dashboard-heading">
    <div className="dashboard__intro">
      <p className="dashboard__eyebrow">Customer portal</p>
      <h2 id="dashboard-heading">Dashboard</h2>
      <p>Your saved planning opportunities at a glance.</p>
    </div>
    {feedback && <p className="dashboard__feedback" role="status">{feedback}</p>}
    {list.status === 'loading' && <OpportunityState variant="loading" title="Loading saved opportunities">Retrieving your saves.</OpportunityState>}
    {list.status === 'error' && <OpportunityState variant="error" title="Saved opportunities unavailable" action={{ label: 'Try again', onClick: retry }}>We could not load your saves right now.</OpportunityState>}
    {summary !== null && (
      <section className="dashboard__overview" aria-label="Dashboard overview">
        <dl className="dashboard__summary">
          <div className="dashboard__summary-card">
            <span className="dashboard__summary-icon dashboard__summary-icon--saved" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5V21l-6-3.5L6 21V4.5Z" />
              </svg>
            </span>
            <div>
              <dt>Saved opportunities</dt>
              <dd>{summary.savedCount}</dd>
            </div>
          </div>
          <div className="dashboard__summary-card">
            <span className="dashboard__summary-icon dashboard__summary-icon--best" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="m4 17 6-6 4 4 6-7M15 8h5v5" />
              </svg>
            </span>
            <div>
              <dt>Best opportunity</dt>
              <dd>{summary.bestScore ?? '—'}</dd>
            </div>
          </div>
          <div className="dashboard__summary-card">
            <span className="dashboard__summary-icon dashboard__summary-icon--confirmed" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="m13 2-10 12h7l-1 8 10-12h-7l1-6Z" />
              </svg>
            </span>
            <div>
              <dt>Confirmed electrical signals</dt>
              <dd>{summary.confirmedSignalCount}</dd>
            </div>
          </div>
        </dl>
      </section>
    )}
    {list.status === 'ready' && <>
      {(list.items.length > 0 || removalStatus !== null) && (
        <div className="dashboard__list-toolbar">
          <div className="dashboard__list-heading-group">
            {list.items.length > 0 && (
              <h3 className="dashboard__list-heading">Saved opportunities</h3>
            )}
            {removalStatus !== null && (
              <p className="dashboard__removal-status" role="status" aria-live="polite">
                {removalStatus}
              </p>
            )}
          </div>
          {list.items.length > 0 && (
            <div className="opportunity-results__sort">
              <label htmlFor="saved-opportunity-sort">
                <svg className="opportunity-results__sort-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path d="m3 7 4-4 4 4M7 3v18m6-4 4 4 4-4M17 21V3" />
                </svg>
                Sort
              </label>
              <select
                id="saved-opportunity-sort"
                value={sort}
                onChange={(event) => setSort(event.currentTarget.value as SavedOpportunitySort)}
              >
                <option value="recently-saved">Recently saved</option>
                <option value="best-opportunity">Best opportunity</option>
                <option value="newest-received">Newest received</option>
                <option value="oldest-received">Oldest received</option>
              </select>
            </div>
          )}
        </div>
      )}
      {list.items.length === 0
        ? <div className="dashboard__empty">
          <h3>No saved opportunities yet</h3>
          <p>Find a planning opportunity that interests you and save it for later.</p>
          <a className="button button--primary" href="/" onClick={onNavigate}>Search opportunities</a>
        </div>
        :
          <ul className="opportunity-list dashboard__list">
            {sortSavedOpportunities(list.items, sort).map((item) => (
              <li key={item.id}>
                <OpportunityCard
                  opportunity={item.opportunity}
                  onViewOpportunityById={onViewOpportunity}
                  savedAt={item.saved_at}
                  secondaryAction={
                    <button
                      type="button"
                      className="button button--secondary"
                      disabled={removingId !== null}
                      onClick={() => void remove(item)}
                    >
                      {removingId === item.id ? 'Removing…' : 'Remove save'}
                    </button>
                  }
                />
              </li>
            ))}
          </ul>
      }
    </>}
  </section>
}
