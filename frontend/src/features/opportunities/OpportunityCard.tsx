import type { MouseEvent } from 'react'

import type { Opportunity } from '../../api/opportunities'
import {
  formatOpportunityDate,
  formatOpportunityDistance,
  formatOpportunityLabel,
  electricalEvidenceLabel,
  electricalWorkBriefFor,
  normalizeOpportunityDescription,
} from './opportunityPresentation'

interface OpportunityCardProps {
  opportunity: Opportunity
  onViewOpportunity?: (opportunity: Opportunity) => void
}

const MAX_HEADING_LENGTH = 96

function displayHeading(description: string | null, applicationNumber: string) {
  if (description === null) {
    return `Planning application ${applicationNumber}`
  }

  if (description.length <= MAX_HEADING_LENGTH) {
    return description
  }

  const headingCandidate = description.slice(0, MAX_HEADING_LENGTH + 1)
  const lastWordBoundary = headingCandidate.lastIndexOf(' ')
  const endIndex =
    lastWordBoundary >= MAX_HEADING_LENGTH * 0.65
      ? lastWordBoundary
      : MAX_HEADING_LENGTH

  return `${description.slice(0, endIndex).trimEnd()}…`
}

function OpportunityCard({
  opportunity,
  onViewOpportunity,
}: OpportunityCardProps) {
  const headingId = `opportunity-${opportunity.id}-heading`
  const description = normalizeOpportunityDescription(opportunity.description)
  const heading = displayHeading(description, opportunity.application_number)
  const opportunityLevel = formatOpportunityLabel(
    opportunity.opportunity_level,
  )
  const opportunityLevelClass = opportunity.opportunity_level.replaceAll('_', '-')
  const electricalWorkBrief = electricalWorkBriefFor(opportunity)

  function handleViewOpportunity(event: MouseEvent<HTMLAnchorElement>) {
    if (
      onViewOpportunity === undefined ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return
    }

    event.preventDefault()
    onViewOpportunity(opportunity)
  }

  return (
    <article
      className={`opportunity-card opportunity-card--${opportunityLevelClass}`}
      aria-labelledby={headingId}
    >
      <header className="opportunity-card__header">
        <div className="opportunity-card__priority">
          <span className="opportunity-level">
            {opportunityLevel} opportunity
          </span>
          <p className="opportunity-score">
            <span>Score</span>
            <strong>{opportunity.opportunity_score}</strong>
          </p>
        </div>

        <h3 id={headingId}>{heading}</h3>

        <ul className="opportunity-summary" aria-label="Opportunity summary">
          <li>
            <span>Category</span>
            <strong>{formatOpportunityLabel(opportunity.category)}</strong>
          </li>
          <li>
            <span>Distance</span>
            <strong>{formatOpportunityDistance(opportunity.distance_km)}</strong>
          </li>
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

      <dl className="opportunity-metadata">
        <div className="opportunity-metadata__location">
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
          <dt>Reference</dt>
          <dd>{opportunity.application_number}</dd>
        </div>
      </dl>

      <section
        className="electrical-work-brief"
        aria-label="Likely electrical work"
      >
        <span
          className={`electrical-work-brief__status electrical-work-brief__status--${electricalWorkBrief.evidence_level}`}
        >
          {electricalEvidenceLabel(electricalWorkBrief)}
        </span>
        <strong>Likely electrical work</strong>
        <p>{electricalWorkBrief.summary}</p>
      </section>

      <div className="opportunity-card__disclosures">
        {description !== null && (
          <details className="opportunity-description">
            <summary>Planning description</summary>
            <p>{description}</p>
          </details>
        )}

        <details className="opportunity-score-details">
          <summary>Score breakdown</summary>
          <dl className="opportunity-breakdown">
            <div>
              <dt>Project scope</dt>
              <dd>{opportunity.opportunity_breakdown.project_scope}</dd>
            </div>
            <div>
              <dt>Electrical relevance</dt>
              <dd>{opportunity.opportunity_breakdown.electrical_relevance}</dd>
            </div>
            <div>
              <dt>Project scale</dt>
              <dd>{opportunity.opportunity_breakdown.project_scale}</dd>
            </div>
            <div>
              <dt>Lead timing</dt>
              <dd>{opportunity.opportunity_breakdown.lead_timing}</dd>
            </div>
            <div>
              <dt>Category fit</dt>
              <dd>{opportunity.opportunity_breakdown.category_fit}</dd>
            </div>
          </dl>
        </details>
      </div>

      <footer className="opportunity-card__footer">
        <a
          className="opportunity-card__action"
          href={`/opportunities/${opportunity.id}`}
          id={`opportunity-${opportunity.id}-action`}
          onClick={handleViewOpportunity}
        >
          View opportunity
        </a>
      </footer>
    </article>
  )
}

export default OpportunityCard
