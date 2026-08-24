import type { Opportunity } from '../../api/opportunities'

type OfficialApplicationOpportunity = Pick<
  Opportunity,
  'application_number' | 'application_url' | 'planning_authority'
>

const KERRY_PLANNING_AUTHORITY = 'Kerry County Council'
const KERRY_EPLANNING_APPLICATION_BASE_URL =
  'https://www.eplanning.ie/KerryCC/AppFileRefDetails'

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

  return opportunity.application_url
}
