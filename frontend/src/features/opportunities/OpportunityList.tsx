import OpportunityCard from './OpportunityCard'
import type { OpportunityFixture } from './opportunityFixtures'

interface OpportunityListProps {
  opportunities: OpportunityFixture[]
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
