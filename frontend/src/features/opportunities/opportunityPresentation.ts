import type {
  ElectricalWorkBrief,
  ElectricalWorkSignal,
  Opportunity,
} from '../../api/opportunities'

type OfficialApplicationOpportunity = Pick<
  Opportunity,
  'application_number' | 'application_url' | 'planning_authority'
>

const KERRY_PLANNING_AUTHORITY = 'Kerry County Council'
const KERRY_EPLANNING_APPLICATION_BASE_URL =
  'https://www.eplanning.ie/KerryCC/AppFileRefDetails'
const ALLOWED_APPLICATION_URL_PROTOCOLS = new Set(['http:', 'https:'])
const ELECTRICAL_EVIDENCE_LEVELS = new Set([
  'direct',
  'possible',
  'inferred',
  'unavailable',
])
const ELECTRICAL_WORK_TYPES = new Set([
  'ev_charging',
  'substation_distribution',
  'battery_storage',
  'renewable_generation',
  'lighting',
  'electrical_installation',
  'electrical_plant_equipment',
])
const SCORE_CAP_EXPLANATIONS = {
  unavailable: 'no specific electrical opportunity was identified',
  possible: 'electrical work is possible but not strongly evidenced',
  inferred: 'electrical work is inferred rather than directly evidenced',
} as const

export const unavailableElectricalWorkBrief: ElectricalWorkBrief = {
  evidence_level: 'unavailable',
  summary:
    'No specific electrical work identified in the planning description.',
  signals: [],
}

export function electricalEvidenceLabel(brief: ElectricalWorkBrief) {
  if (brief.evidence_level === 'direct') return 'Confirmed signal'
  if (brief.evidence_level === 'possible') return 'Possible electrical work'
  if (brief.evidence_level === 'inferred') return 'Likely opportunity'
  return 'No specific signal'
}

export function electricalWorkSummary(brief: ElectricalWorkBrief) {
  return brief.evidence_level === 'unavailable'
    ? unavailableElectricalWorkBrief.summary
    : brief.summary
}

export function electricalWorkCardHeading(brief: ElectricalWorkBrief) {
  if (brief.evidence_level === 'direct') return 'Confirmed electrical work'
  if (brief.evidence_level === 'possible') return 'Possible electrical work'
  if (brief.evidence_level === 'inferred') return 'Implied electrical work'
  return 'No specific electrical work'
}

export function electricalWorkBriefFor(
  opportunity: Pick<Opportunity, 'electrical_work_brief'>,
) {
  // Keep cards usable while older API responses are still missing this field.
  const brief: unknown = opportunity.electrical_work_brief
  return isElectricalWorkBrief(brief) ? brief : unavailableElectricalWorkBrief
}

export function scoreCapMessageFor(
  opportunity: Pick<
    Opportunity,
    | 'opportunity_score'
    | 'raw_opportunity_score'
    | 'electrical_work_brief'
  >,
) {
  const rawScore = opportunity.raw_opportunity_score
  const effectiveScore = opportunity.opportunity_score
  const evidenceLevel = electricalWorkBriefFor(opportunity).evidence_level

  if (
    !isOpportunityScore(rawScore) ||
    !isOpportunityScore(effectiveScore) ||
    rawScore <= effectiveScore ||
    evidenceLevel === 'direct'
  ) {
    return null
  }

  return `Raw score: ${rawScore}. Final score capped at ${effectiveScore} because ${SCORE_CAP_EXPLANATIONS[evidenceLevel]}.`
}

function isElectricalWorkSignal(value: unknown): value is ElectricalWorkSignal {
  if (typeof value !== 'object' || value === null) return false

  const signal = value as Record<string, unknown>
  return (
    typeof signal.evidence === 'string' &&
    typeof signal.work_type === 'string' &&
    ELECTRICAL_WORK_TYPES.has(signal.work_type)
  )
}

function isElectricalWorkBrief(value: unknown): value is ElectricalWorkBrief {
  if (typeof value !== 'object' || value === null) return false

  const brief = value as Record<string, unknown>
  return (
    typeof brief.evidence_level === 'string' &&
    ELECTRICAL_EVIDENCE_LEVELS.has(brief.evidence_level) &&
    typeof brief.summary === 'string' &&
    Array.isArray(brief.signals) &&
    brief.signals.every(isElectricalWorkSignal)
  )
}

function isOpportunityScore(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 100
}

export function safeApplicationUrl(value: string | null) {
  if (value === null || value !== value.trim() || /\s/.test(value)) {
    return null
  }

  try {
    const url = new URL(value)
    if (
      !ALLOWED_APPLICATION_URL_PROTOCOLS.has(url.protocol) ||
      url.hostname === '' ||
      url.username !== '' ||
      url.password !== ''
    ) {
      return null
    }
  } catch {
    return null
  }

  return value
}

export function formatOpportunityLabel(value: string) {
  const label = value.replaceAll('_', ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export function formatOpportunityDate(value: string) {
  return new Intl.DateTimeFormat('en-IE', {
    dateStyle: 'long',
    timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`))
}

export function formatOpportunityDistance(distanceKm: number) {
  return `${new Intl.NumberFormat('en-IE', {
    maximumFractionDigits: 1,
  }).format(distanceKm)} km`
}

export function formatOpportunityLocation(address: string | null) {
  if (address === null) return null

  const parts = address
    .split(',')
    .map((part) => part.replaceAll(/\s+/g, ' ').trim())
    .filter((part) => part !== '')

  if (parts.length === 0) return null
  if (parts.length <= 2) return [parts.join(', ')]

  return [parts.slice(0, 2).join(', '), parts.slice(2).join(', ')]
}

export function normalizeOpportunityDescription(description: string | null) {
  const normalizedDescription = description?.replaceAll(/\s+/g, ' ').trim()
  return normalizedDescription === '' ? null : (normalizedDescription ?? null)
}

export function officialApplicationUrl(
  opportunity: OfficialApplicationOpportunity,
) {
  // Kerry application references have a stable official ePlanning URL.
  if (
    opportunity.planning_authority === KERRY_PLANNING_AUTHORITY &&
    opportunity.application_number.trim() !== ''
  ) {
    const reference = encodeURIComponent(opportunity.application_number)
    return `${KERRY_EPLANNING_APPLICATION_BASE_URL}/${reference}/0`
  }

  return safeApplicationUrl(opportunity.application_url)
}
