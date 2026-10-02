import type { Opportunity } from '../../api/opportunities'
import OpportunityCard from './OpportunityCard'
import QuickSaveOpportunityControl from './QuickSaveOpportunityControl'
import type { SaveAccess } from './useOpportunitySave'

interface OpportunityListProps {
  isBusy?: boolean
  opportunities: Opportunity[]
  labelledBy: string
  onViewOpportunity?: (opportunity: Opportunity) => void
  saveAccess?: SaveAccess
  onRequestSaveAuthentication?: (opportunityId: number) => void
  onSaveSessionExpired?: () => void
}

function OpportunityList({
  isBusy = false,
  opportunities,
  labelledBy,
  onViewOpportunity,
  saveAccess,
  onRequestSaveAuthentication,
  onSaveSessionExpired,
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
            quickSaveControl={saveAccess !== undefined ? (
              <QuickSaveOpportunityControl
                opportunityId={opportunity.id}
                access={saveAccess}
                onRequestAuthentication={onRequestSaveAuthentication}
                onSessionExpired={onSaveSessionExpired}
              />
            ) : undefined}
          />
        </li>
      ))}
    </ul>
  )
}

export default OpportunityList
