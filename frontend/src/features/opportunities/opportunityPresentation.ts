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

export const unavailableElectricalWorkBrief: ElectricalWorkBrief = {
  evidence_level: 'unavailable',
  summary: 'Electrical work is not evidenced by the available planning data.',
  signals: [],
}

export function electricalEvidenceLabel(brief: ElectricalWorkBrief) {
  if (brief.evidence_level === 'direct') return 'Directly evidenced'
  if (brief.evidence_level === 'inferred') return 'Inferred opportunity'
  return 'Limited evidence'
}

export function electricalWorkBriefFor(
  opportunity: Pick<Opportunity, 'electrical_work_brief'>,
) {
  const brief: unknown = opportunity.electrical_work_brief
  return isElectricalWorkBrief(brief) ? brief : unavailableElectricalWorkBrief
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

export function normalizeOpportunityDescription(description: string | null) {
  const normalizedDescription = description?.replaceAll(/\s+/g, ' ').trim()
  return normalizedDescription === '' ? null : (normalizedDescription ?? null)
}

export function officialApplicationUrl(
  opportunity: OfficialApplicationOpportunity,
) {
  if (
    opportunity.planning_authority === KERRY_PLANNING_AUTHORITY &&
    opportunity.application_number.trim() !== ''
  ) {
    const reference = encodeURIComponent(opportunity.application_number)
    return `${KERRY_EPLANNING_APPLICATION_BASE_URL}/${reference}/0`
  }

  return safeApplicationUrl(opportunity.application_url)
}
