import type { Opportunity } from '../../api/opportunities'
import OpportunityCard from './OpportunityCard'

interface OpportunityListProps {
  isBusy?: boolean
  opportunities: Opportunity[]
  labelledBy: string
  onViewOpportunity?: (opportunity: Opportunity) => void
}

function OpportunityList({
  isBusy = false,
  opportunities,
  labelledBy,
  onViewOpportunity,
}: OpportunityListProps) {
  return (
    <ul
      className="opportunity-list"
      aria-busy={isBusy}
      aria-labelledby={labelledBy}
    >
      {opportunities.map((opportunity) => (
        <li key={opportunity.id}>
          <OpportunityCard
            opportunity={opportunity}
            onViewOpportunity={onViewOpportunity}
          />
        </li>
      ))}
    </ul>
  )
}

export default OpportunityList
