export interface OpportunityFixture {
  id: number
  title: string
  score: number
  level: 'very_high' | 'high' | 'medium' | 'low' | 'very_low'
  category:
    | 'residential'
    | 'commercial'
    | 'industrial'
    | 'energy'
    | 'infrastructure'
    | 'mixed_use'
    | 'other'
  address: string
  distanceKm: number
  receivedDate: string
  receivedDateLabel: string
}

// Temporary representative data for building the frontend structure only.
export const temporaryOpportunityFixtures: OpportunityFixture[] = [
  {
    id: 1,
    title:
      'Construction of a three-storey enterprise centre with offices, workshops and associated site works',
    score: 88,
    level: 'very_high',
    category: 'commercial',
    address: 'Manor West Business Park, Tralee, Co. Kerry',
    distanceKm: 3.4,
    receivedDate: '2026-08-18',
    receivedDateLabel: '18 August 2026',
  },
  {
    id: 2,
    title:
      'Development of a 20 MW solar farm with battery storage and grid connection',
    score: 82,
    level: 'high',
    category: 'energy',
    address: 'Ballyduff, Co. Kerry',
    distanceKm: 8.9,
    receivedDate: '2026-08-15',
    receivedDateLabel: '15 August 2026',
  },
  {
    id: 3,
    title:
      'Construction of 36 houses, 24 apartments and associated site development works',
    score: 76,
    level: 'high',
    category: 'residential',
    address: 'Killarney Road, Tralee, Co. Kerry',
    distanceKm: 5.7,
    receivedDate: '2026-08-12',
    receivedDateLabel: '12 August 2026',
  },
]
