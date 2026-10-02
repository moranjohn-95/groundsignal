import {
  type SaveAccess,
  type SaveReturnOutcome,
  useOpportunitySave,
} from './useOpportunitySave'

export type { SaveAccess, SaveReturnOutcome } from './useOpportunitySave'

interface SaveOpportunityControlProps {
  opportunityId: number
  access: SaveAccess
  initialOutcome?: SaveReturnOutcome | null
  onRequestAuthentication?: (opportunityId: number) => void
  onSessionExpired?: () => void
}

export default function SaveOpportunityControl({
  opportunityId,
  access,
  initialOutcome,
  onRequestAuthentication,
  onSessionExpired,
}: SaveOpportunityControlProps) {
  const {
    buttonLabel,
    disabled,
    handleAction,
    isSaved,
    message,
  } = useOpportunitySave({
    opportunityId,
    access,
    initialOutcome,
    onRequestAuthentication,
    onSessionExpired,
  })

  return (
    <div className="opportunity-detail__save">
      <button
        className={`button ${isSaved ? 'button--secondary' : 'button--primary'}`}
        type="button"
        onClick={() => void handleAction()}
        disabled={disabled}
      >
        {buttonLabel}
      </button>
      {isSaved && (
        <p className="opportunity-detail__save-status" role="status">Saved to your account.</p>
      )}
      {access === 'anonymous' && (
        <p className="opportunity-detail__save-status">
          Create a free account or log in to save this opportunity.
        </p>
      )}
      {access === 'error' && (
        <p className="opportunity-detail__save-status" role="alert">
          Account check unavailable. Retry from the header.
        </p>
      )}
      {message && <p className="opportunity-detail__save-error" role="alert">{message}</p>}
    </div>
  )
}
