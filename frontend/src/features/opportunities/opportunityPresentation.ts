import type { Opportunity } from '../../api/opportunities'

type OfficialApplicationOpportunity = Pick<
  Opportunity,
  'application_number' | 'application_url' | 'planning_authority'
>

const KERRY_PLANNING_AUTHORITY = 'Kerry County Council'
const KERRY_EPLANNING_APPLICATION_BASE_URL =
  'https://www.eplanning.ie/KerryCC/AppFileRefDetails'
const ALLOWED_APPLICATION_URL_PROTOCOLS = new Set(['http:', 'https:'])

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
