import type { Opportunity } from '../../api/opportunities'
import OpportunityCard from './OpportunityCard'

interface OpportunityListProps {
  opportunities: Opportunity[]
  labelledBy: string
}

function OpportunityList({ opportunities, labelledBy }: OpportunityListProps) {
  return (
    <ul className="opportunity-list" aria-labelledby={labelledBy}>
      {opportunities.map((opportunity) => (
        <li key={opportunity.id}>
          <OpportunityCard opportunity={opportunity} />
        </li>
      ))}
    </ul>
  )
}

export default OpportunityList
