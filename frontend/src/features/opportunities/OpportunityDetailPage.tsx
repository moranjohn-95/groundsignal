import { useEffect, useRef, useState, type MouseEvent } from 'react'

import {
  fetchOpportunity,
  OpportunityNotFoundError,
  type OpportunityDetail,
} from '../../api/opportunities'
import {
  formatOpportunityDate,
  formatOpportunityDistance,
  formatOpportunityLabel,
  officialApplicationUrl,
} from './opportunityPresentation'

type DetailState =
  | { status: 'loading' }
  | { status: 'not-found' }
  | { status: 'error' }
  | { status: 'success'; opportunity: OpportunityDetail }

interface OpportunityDetailPageProps {
  opportunityId: number
  distanceKm?: number
  onBack?: () => void
}

function OpportunityDetailPage({
  opportunityId,
  distanceKm,
  onBack,
}: OpportunityDetailPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [detailState, setDetailState] = useState<DetailState>({
    status: 'loading',
  })

  useEffect(() => {
    let ignoreResult = false

    void fetchOpportunity(opportunityId)
      .then((opportunity) => {
        if (!ignoreResult) {
          setDetailState({ status: 'success', opportunity })
        }
      })
      .catch((error: unknown) => {
        if (!ignoreResult) {
          setDetailState({
            status:
              error instanceof OpportunityNotFoundError ? 'not-found' : 'error',
          })
        }
      })

    return () => {
      ignoreResult = true
    }
  }, [opportunityId])

  useEffect(() => {
    headingRef.current?.focus()
  }, [detailState.status])

  function handleBack(event: MouseEvent<HTMLAnchorElement>) {
    if (
      onBack === undefined ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return
    }

    event.preventDefault()
    onBack()
  }

  const backLink = (
    <a className="opportunity-detail__back" href="/" onClick={handleBack}>
      Back to opportunities
    </a>
  )

  if (detailState.status === 'loading') {
    return (
      <section className="opportunity-detail-state" aria-labelledby="detail-heading">
        {backLink}
        <h2 id="detail-heading" ref={headingRef} tabIndex={-1}>
          Opportunity details
        </h2>
        <p role="status">Loading opportunity...</p>
      </section>
    )
  }

  if (detailState.status === 'not-found') {
    return (
      <section className="opportunity-detail-state" aria-labelledby="detail-heading">
        {backLink}
        <h2 id="detail-heading" ref={headingRef} tabIndex={-1}>
          Opportunity not found
        </h2>
        <p role="alert">
          This opportunity could not be found. It may no longer be available.
        </p>
      </section>
    )
  }

  if (detailState.status === 'error') {
    return (
      <section className="opportunity-detail-state" aria-labelledby="detail-heading">
        {backLink}
        <h2 id="detail-heading" ref={headingRef} tabIndex={-1}>
          Opportunity unavailable
        </h2>
        <p role="alert">
          We could not load this opportunity. Please try again later.
        </p>
      </section>
    )
  }

  const { opportunity } = detailState
  const opportunityLevel = formatOpportunityLabel(
    opportunity.opportunity_level,
  )
  const opportunityLevelClass = opportunity.opportunity_level.replaceAll('_', '-')
  const applicationUrl = officialApplicationUrl(opportunity)
  const availableDistance = distanceKm ?? opportunity.distance_km

  return (
    <div className="opportunity-detail-page">
      {backLink}

      <article
        className={`opportunity-detail opportunity-detail--${opportunityLevelClass}`}
        aria-labelledby="detail-heading"
      >
        <header className="opportunity-detail__header">
          <div className="opportunity-card__priority">
            <span className="opportunity-level">
              {opportunityLevel} opportunity
            </span>
            <p className="opportunity-score">
              <span>Score</span>
              <strong>{opportunity.opportunity_score}</strong>
            </p>
          </div>

          <p className="opportunity-detail__eyebrow">Planning application</p>
          <h2 id="detail-heading" ref={headingRef} tabIndex={-1}>
            Opportunity {opportunity.application_number}
          </h2>

          <ul className="opportunity-detail__summary" aria-label="Opportunity summary">
            <li>
              <span>Category</span>
              <strong>{formatOpportunityLabel(opportunity.category)}</strong>
            </li>
            {availableDistance !== undefined && (
              <li>
                <span>Distance</span>
                <strong>{formatOpportunityDistance(availableDistance)}</strong>
              </li>
            )}
            <li>
              <span>Received</span>
              <strong>
                {opportunity.received_date === null ? (
                  'Not provided'
                ) : (
                  <time dateTime={opportunity.received_date}>
                    {formatOpportunityDate(opportunity.received_date)}
                  </time>
                )}
              </strong>
            </li>
          </ul>
        </header>

        <div className="opportunity-detail__body">
          <section aria-labelledby="planning-description-heading">
            <h3 id="planning-description-heading">Planning description</h3>
            <p className="opportunity-detail__description">
              {opportunity.description ?? 'Not provided'}
            </p>
          </section>

          <section aria-labelledby="application-details-heading">
            <h3 id="application-details-heading">Application details</h3>
            <dl className="opportunity-detail__metadata">
              <div>
                <dt>Location</dt>
                <dd>
                  {opportunity.address === null ? (
                    'Not provided'
                  ) : (
                    <address>{opportunity.address}</address>
                  )}
                </dd>
              </div>
              <div>
                <dt>Planning authority</dt>
                <dd>{opportunity.planning_authority}</dd>
              </div>
              <div>
                <dt>Application reference</dt>
                <dd>{opportunity.application_number}</dd>
              </div>
            </dl>
          </section>

          <section aria-labelledby="score-breakdown-heading">
            <h3 id="score-breakdown-heading">Score breakdown</h3>
            <dl className="opportunity-detail__breakdown">
              {opportunity.opportunity_score_components.map((component) => (
                <div key={component.name}>
                  <dt>{formatOpportunityLabel(component.name)}</dt>
                  <dd>
                    <strong className="opportunity-detail__component-score">
                      {component.points_awarded} / {component.maximum_points}
                    </strong>
                    <p>{component.explanation}</p>
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </div>

        <footer className="opportunity-detail__footer">
          {applicationUrl === null ? (
            <p>Official application link is not available for this authority.</p>
          ) : (
            <a
              className="opportunity-detail__action"
              href={applicationUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              View official application
            </a>
          )}
        </footer>
      </article>
    </div>
  )
}

export default OpportunityDetailPage
