export interface SaveReturn {
  opportunityId: number
  path: string
}

export function readSaveReturn(search: string): SaveReturn | null {
  const params = new URLSearchParams(search)
  if (params.get('save') !== '1') return null
  const destination = params.get('returnTo')
  const match = destination && /^\/opportunities\/([1-9]\d*)$/.exec(destination)
  if (!match) return null
  const opportunityId = Number(match[1])
  if (!Number.isSafeInteger(opportunityId)) return null
  return { opportunityId, path: `/opportunities/${opportunityId}` }
}

export function saveReturnSearch(opportunityId: number): string {
  return `?${new URLSearchParams({
    returnTo: `/opportunities/${opportunityId}`,
    save: '1',
  })}`
}
