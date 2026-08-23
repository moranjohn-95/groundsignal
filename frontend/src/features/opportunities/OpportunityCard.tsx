import type { OpportunityFixture } from './opportunityFixtures'

interface OpportunityCardProps {
  opportunity: OpportunityFixture
}

function formatLabel(value: string) {
  const label = value.replace('_', ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function OpportunityCard({ opportunity }: OpportunityCardProps) {
  const headingId = `opportunity-${opportunity.id}-heading`

  return (
    <article className="opportunity-card" aria-labelledby={headingId}>
      <h3 id={headingId}>{opportunity.title}</h3>

      <dl className="opportunity-details">
        <div>
          <dt>Opportunity score</dt>
          <dd>{opportunity.score}</dd>
        </div>
        <div>
          <dt>Opportunity level</dt>
          <dd>{formatLabel(opportunity.level)}</dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>{formatLabel(opportunity.category)}</dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>
            <address>{opportunity.address}</address>
          </dd>
        </div>
        <div>
          <dt>Distance</dt>
          <dd>{opportunity.distanceKm} km</dd>
        </div>
        <div>
          <dt>Received</dt>
          <dd>
            <time dateTime={opportunity.receivedDate}>
              {opportunity.receivedDateLabel}
            </time>
          </dd>
        </div>
      </dl>

      <button type="button">View opportunity</button>
    </article>
  )
}

export default OpportunityCard
