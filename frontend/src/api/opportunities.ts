export const planningApplicationCategories = [
  'residential',
  'commercial',
  'industrial',
  'energy',
  'infrastructure',
  'mixed_use',
  'other',
] as const

export type PlanningApplicationCategory =
  (typeof planningApplicationCategories)[number]

export type OpportunityLevel =
  | 'very_high'
  | 'high'
  | 'medium'
  | 'low'
  | 'very_low'

export interface OpportunityBreakdown {
  project_scope: number
  electrical_relevance: number
  project_scale: number
  lead_timing: number
  category_fit: number
}

export type OpportunityScoreComponentName = keyof OpportunityBreakdown

export interface OpportunityScoreComponent {
  name: OpportunityScoreComponentName
  points_awarded: number
  maximum_points: number
  explanation: string
}

export interface Opportunity {
  id: number
  application_number: string
  planning_authority: string
  description: string | null
  address: string | null
  application_type: string | null
  application_status: string | null
  decision: string | null
  received_date: string | null
  application_url: string | null
  category: PlanningApplicationCategory
  distance_km: number
  opportunity_score: number
  opportunity_level: OpportunityLevel
  opportunity_breakdown: OpportunityBreakdown
  opportunity_score_components: OpportunityScoreComponent[]
}

export interface OpportunityFeedResponse {
  items: Opportunity[]
  limit: number
  returned_count: number
}

export type OpportunityDetail = Omit<Opportunity, 'distance_km'> & {
  distance_km?: number
}

export interface OpportunityQuery {
  latitude: number
  longitude: number
  radiusKm: number
  recentDays: number
  category?: PlanningApplicationCategory
  limit: number
}

export class OpportunityNotFoundError extends Error {
  constructor() {
    super('Opportunity not found.')
    this.name = 'OpportunityNotFoundError'
  }
}

export async function fetchOpportunity(
  opportunityId: number,
): Promise<OpportunityDetail> {
  const response = await fetch(
    `/api/v1/planning-applications/${opportunityId}`,
  )

  if (response.status === 404) {
    throw new OpportunityNotFoundError()
  }

  if (!response.ok) {
    throw new Error(`Opportunity request failed with status ${response.status}.`)
  }

  return (await response.json()) as OpportunityDetail
}

export async function fetchOpportunities(
  query: OpportunityQuery,
): Promise<OpportunityFeedResponse> {
  const parameters = new URLSearchParams({
    latitude: String(query.latitude),
    longitude: String(query.longitude),
    radius_km: String(query.radiusKm),
    recent_days: String(query.recentDays),
    limit: String(query.limit),
  })

  if (query.category !== undefined) {
    parameters.set('category', query.category)
  }

  const response = await fetch(`/api/v1/opportunities?${parameters.toString()}`)

  if (!response.ok) {
    throw new Error(`Opportunity request failed with status ${response.status}.`)
  }

  return (await response.json()) as OpportunityFeedResponse
}
