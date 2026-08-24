import type { Opportunity } from '../../api/opportunities'

interface OpportunityCardProps {
  opportunity: Opportunity
}

const MAX_HEADING_LENGTH = 96
const KERRY_PLANNING_AUTHORITY = 'Kerry County Council'
const KERRY_EPLANNING_APPLICATION_BASE_URL =
  'https://www.eplanning.ie/KerryCC/AppFileRefDetails'

function formatLabel(value: string) {
  const label = value.replaceAll('_', ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IE', {
    dateStyle: 'long',
    timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`))
}

function formatDistance(distanceKm: number) {
  return `${new Intl.NumberFormat('en-IE', {
    maximumFractionDigits: 1,
  }).format(distanceKm)} km`
}

function normalizeDescription(description: string | null) {
  const normalizedDescription = description?.replaceAll(/\s+/g, ' ').trim()
  return normalizedDescription === '' ? null : (normalizedDescription ?? null)
}

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

function officialApplicationUrl(opportunity: Opportunity) {
  if (
    opportunity.planning_authority === KERRY_PLANNING_AUTHORITY &&
    opportunity.application_number.trim() !== ''
  ) {
    const reference = encodeURIComponent(opportunity.application_number)
    return `${KERRY_EPLANNING_APPLICATION_BASE_URL}/${reference}/0`
  }

  return opportunity.application_url
}

function OpportunityCard({ opportunity }: OpportunityCardProps) {
  const headingId = `opportunity-${opportunity.id}-heading`
  const description = normalizeDescription(opportunity.description)
  const heading = displayHeading(description, opportunity.application_number)
  const opportunityLevel = formatLabel(opportunity.opportunity_level)
  const opportunityLevelClass = opportunity.opportunity_level.replaceAll('_', '-')
  const applicationUrl = officialApplicationUrl(opportunity)

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
            <strong>{formatLabel(opportunity.category)}</strong>
          </li>
          <li>
            <span>Distance</span>
            <strong>{formatDistance(opportunity.distance_km)}</strong>
          </li>
          <li>
            <span>Received</span>
            <strong>
              {opportunity.received_date === null ? (
                'Not provided'
              ) : (
                <time dateTime={opportunity.received_date}>
                  {formatDate(opportunity.received_date)}
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

      {applicationUrl !== null && (
        <footer className="opportunity-card__footer">
          <a
            className="opportunity-card__action"
            href={applicationUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            View official application
          </a>
        </footer>
      )}
    </article>
  )
}

export default OpportunityCard
