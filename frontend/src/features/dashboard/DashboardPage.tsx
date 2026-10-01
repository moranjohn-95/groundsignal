import { useEffect, useState, type MouseEvent } from 'react'

import { listSavedOpportunities, removeSavedOpportunity, SavedOpportunityApiError, type SavedOpportunity } from '../../api/savedOpportunities'
import { formatOpportunityDate, formatOpportunityLabel, normalizeOpportunityDescription } from '../opportunities/opportunityPresentation'
import OpportunityState from '../opportunities/OpportunityState'

interface Props {
  onNavigate: (event: MouseEvent<HTMLAnchorElement>) => void
  onViewOpportunity: (opportunityId: number) => void
  onSessionExpired: () => void
}

type ListState =
  | { status: 'loading' | 'error' }
  | { status: 'ready'; items: SavedOpportunity[] }

export default function DashboardPage({ onNavigate, onViewOpportunity, onSessionExpired }: Props) {
  const [list, setList] = useState<ListState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [removingId, setRemovingId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)

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

  function retry() {
    setFeedback(null)
    setList({ status: 'loading' })
    setAttempt((value) => value + 1)
  }

  async function remove(item: SavedOpportunity) {
    if (removingId !== null) return
    setRemovingId(item.id)
    setFeedback(null)
    try {
      await removeSavedOpportunity(item.id)
      setList((current) => current.status === 'ready'
        ? { status: 'ready', items: current.items.filter((saved) => saved.id !== item.id) }
        : current)
      setFeedback('Opportunity removed from your saves.')
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

  function openDetail(event: MouseEvent<HTMLAnchorElement>, id: number) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    onViewOpportunity(id)
  }

  return <section className="dashboard" aria-labelledby="dashboard-heading">
    <div className="dashboard__intro">
      <span className="dashboard__accent" aria-hidden="true" />
      <h2 id="dashboard-heading">Your dashboard</h2>
      <p>Keep track of the planning opportunities you have saved.</p>
    </div>
    {feedback && <p className="dashboard__feedback" role="status">{feedback}</p>}
    {list.status === 'loading' && <OpportunityState variant="loading" title="Loading saved opportunities">Retrieving your saves.</OpportunityState>}
    {list.status === 'error' && <OpportunityState variant="error" title="Saved opportunities unavailable" action={{ label: 'Try again', onClick: retry }}>We could not load your saves right now.</OpportunityState>}
    {list.status === 'ready' && (list.items.length === 0
      ? <div className="dashboard__empty">
          <h3>No saved opportunities yet</h3>
          <p>Find a planning opportunity that interests you and save it for later.</p>
          <a className="button button--primary" href="/" onClick={onNavigate}>Search opportunities</a>
        </div>
      : <>
          <h3 className="dashboard__list-heading">Saved opportunities <span>({list.items.length})</span></h3>
          <ul className="dashboard__list">
            {list.items.map((item) => {
              const opportunity = item.opportunity
              const title = normalizeOpportunityDescription(opportunity.description) ?? `Planning application ${opportunity.application_number}`
              return <li key={item.id} className="dashboard-card">
                <div className="dashboard-card__content">
                  <span className="dashboard-card__level">{formatOpportunityLabel(opportunity.opportunity_level)} opportunity</span>
                  <h4>{title}</h4>
                  <p>{opportunity.address || opportunity.planning_authority}</p>
                  <dl>
                    <div><dt>Category</dt><dd>{formatOpportunityLabel(opportunity.category)}</dd></div>
                    <div><dt>Reference</dt><dd>{opportunity.application_number}</dd></div>
                    <div><dt>Saved</dt><dd><time dateTime={item.saved_at}>{formatOpportunityDate(item.saved_at.slice(0, 10))}</time></dd></div>
                  </dl>
                </div>
                <div className="dashboard-card__actions">
                  <a className="opportunity-card__action" href={`/opportunities/${opportunity.id}`} onClick={(event) => openDetail(event, opportunity.id)}>View opportunity</a>
                  <button type="button" className="button button--secondary" disabled={removingId !== null} onClick={() => void remove(item)}>{removingId === item.id ? 'Removing…' : 'Remove save'}</button>
                </div>
              </li>
            })}
          </ul>
        </>)}
  </section>
}
