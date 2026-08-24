import type { Opportunity } from '../../api/opportunities'
import OpportunityCard from './OpportunityCard'

interface OpportunityListProps {
  opportunities: Opportunity[]
  labelledBy: string
  onViewOpportunity?: (opportunity: Opportunity) => void
}

function OpportunityList({
  opportunities,
  labelledBy,
  onViewOpportunity,
}: OpportunityListProps) {
  return (
    <ul className="opportunity-list" aria-labelledby={labelledBy}>
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
