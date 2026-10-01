import type { OpportunityDetail } from './opportunities'

export interface SavedOpportunity {
  id: number
  saved_at: string
  opportunity: OpportunityDetail
}

interface SavedOpportunityList {
  items: SavedOpportunity[]
  total: number
}

export class SavedOpportunityApiError extends Error {
  constructor(public readonly status: number) {
    super(`Saved opportunity request failed with status ${status}.`)
    this.name = 'SavedOpportunityApiError'
  }
}

const endpoint = '/api/v1/saved-opportunities'

export async function listSavedOpportunities(): Promise<SavedOpportunity[]> {
  const items: SavedOpportunity[] = []
  while (true) {
    const response = await fetch(`${endpoint}?limit=100&offset=${items.length}`, {
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (!response.ok) throw new SavedOpportunityApiError(response.status)
    const page = (await response.json()) as SavedOpportunityList
    items.push(...page.items)
    if (page.items.length === 0 || items.length >= page.total) return items
  }
}

export async function findSavedOpportunity(
  planningApplicationId: number,
): Promise<SavedOpportunity | null> {
  let offset = 0
  while (true) {
    const response = await fetch(`${endpoint}?limit=100&offset=${offset}`, {
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (!response.ok) throw new SavedOpportunityApiError(response.status)
    const page = (await response.json()) as SavedOpportunityList
    const match = page.items.find(
      (item) => item.opportunity.id === planningApplicationId,
    )
    if (match) return match
    offset += page.items.length
    if (page.items.length === 0 || offset >= page.total) return null
  }
}

export async function saveOpportunity(
  planningApplicationId: number,
): Promise<SavedOpportunity> {
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ planning_application_id: planningApplicationId }),
  })
  if (!response.ok) throw new SavedOpportunityApiError(response.status)
  return (await response.json()) as SavedOpportunity
}

export async function removeSavedOpportunity(saveId: number): Promise<void> {
  const response = await fetch(`${endpoint}/${saveId}`, {
    method: 'DELETE',
    credentials: 'same-origin',
  })
  if (!response.ok) throw new SavedOpportunityApiError(response.status)
}
