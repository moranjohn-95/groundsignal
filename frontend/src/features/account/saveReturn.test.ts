import { describe, expect, it } from 'vitest'

import { readSaveReturn, saveReturnSearch } from './saveReturn'


describe('saved-opportunity return destination', () => {
  it('accepts only a canonical local opportunity path', () => {
    expect(readSaveReturn(saveReturnSearch(20))).toEqual({
      opportunityId: 20,
      path: '/opportunities/20',
    })
  })

  it.each([
    '?returnTo=https%3A%2F%2Fevil.example&save=1',
    '?returnTo=%2F%2Fevil.example&save=1',
    '?returnTo=%2Fopportunities%2F20%3Fnext%3D%2F%2Fevil.example&save=1',
    '?returnTo=%2Fopportunities%2F20%23fragment&save=1',
    '?returnTo=%2Fopportunities%2F0&save=1',
    '?returnTo=%2Fopportunities%2F999999999999999999999&save=1',
    '?returnTo=%2Fopportunities%2F20&save=0',
  ])('rejects an unsafe or invalid destination: %s', (search) => {
    expect(readSaveReturn(search)).toBeNull()
  })
})
