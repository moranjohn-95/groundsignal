import type { Opportunity } from '../../api/opportunities'

interface OpportunityCardProps {
  opportunity: Opportunity
}

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

function OpportunityCard({ opportunity }: OpportunityCardProps) {
  const headingId = `opportunity-${opportunity.id}-heading`
  const description =
    opportunity.description ??
    `Planning application ${opportunity.application_number}`

  return (
    <article className="opportunity-card" aria-labelledby={headingId}>
      <h3 id={headingId}>{description}</h3>

      <dl className="opportunity-details">
        <div>
          <dt>Opportunity score</dt>
          <dd>{opportunity.opportunity_score}</dd>
        </div>
        <div>
          <dt>Opportunity level</dt>
          <dd>{formatLabel(opportunity.opportunity_level)}</dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>{formatLabel(opportunity.category)}</dd>
        </div>
        <div>
          <dt>Planning authority</dt>
          <dd>{opportunity.planning_authority}</dd>
        </div>
        <div>
          <dt>Application number</dt>
          <dd>{opportunity.application_number}</dd>
        </div>
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
          <dt>Distance</dt>
          <dd>{opportunity.distance_km} km</dd>
        </div>
        <div>
          <dt>Received</dt>
          <dd>
            {opportunity.received_date === null ? (
              'Not provided'
            ) : (
              <time dateTime={opportunity.received_date}>
                {formatDate(opportunity.received_date)}
              </time>
            )}
          </dd>
        </div>
      </dl>

      <details>
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

      {opportunity.application_url !== null && (
        <a href={opportunity.application_url}>View opportunity</a>
      )}
    </article>
  )
}

export default OpportunityCard
