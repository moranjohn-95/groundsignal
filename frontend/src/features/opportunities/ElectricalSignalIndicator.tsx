import type { ElectricalWorkBrief } from '../../api/opportunities'

interface ElectricalSignalIndicatorProps {
  evidenceLevel: ElectricalWorkBrief['evidence_level']
}

const signalStates = {
  direct: { activeIcons: 3, label: 'confirmed electrical work' },
  possible: { activeIcons: 1, label: 'possible electrical work' },
  inferred: { activeIcons: 2, label: 'implied electrical work' },
  unavailable: { activeIcons: 0, label: 'no specific electrical work' },
} as const

function ElectricalSignalIndicator({
  evidenceLevel,
}: ElectricalSignalIndicatorProps) {
  const { activeIcons, label } = signalStates[evidenceLevel]

  return (
    <div
      className="electrical-signal-indicator"
      role="img"
      aria-label={`Electrical signal: ${label}`}
    >
      {[0, 1, 2].map((index) => (
        <svg
          key={index}
          className={`electrical-signal-indicator__icon electrical-signal-indicator__icon--${index < activeIcons ? 'active' : 'inactive'}`}
          viewBox="0 0 24 24"
          aria-hidden="true"
          focusable="false"
        >
          <path d="M13 2 3 14h7l-1 8 10-12h-7z" />
        </svg>
      ))}
    </div>
  )
}

export default ElectricalSignalIndicator
