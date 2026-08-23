import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { OpportunityFeedResponse } from '../../api/opportunities'
import OpportunitiesPage from './OpportunitiesPage'

const opportunityFeed: OpportunityFeedResponse = {
  items: [
    {
      id: 20,
      application_number: '26/1042',
      planning_authority: 'Kerry County Council',
      description:
        'Construction of a new industrial manufacturing facility with electrical infrastructure.',
      address: 'Manor West Business Park, Tralee, Co. Kerry',
      application_type: 'Permission',
      application_status: 'Pending',
      decision: null,
      received_date: '2026-08-18',
      application_url: 'https://example.test/planning/26-1042',
      category: 'industrial',
      distance_km: 4.25,
      opportunity_score: 96,
      opportunity_level: 'very_high',
      opportunity_breakdown: {
        project_scope: 30,
        electrical_relevance: 30,
        project_scale: 16,
        lead_timing: 10,
        category_fit: 10,
      },
    },
  ],
  limit: 20,
  returned_count: 1,
}

const emptyFeed: OpportunityFeedResponse = {
  items: [],
  limit: 20,
  returned_count: 0,
}

function jsonResponse(
  body: OpportunityFeedResponse,
  status = 200,
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

async function submitSearch({
  category,
  radius = '25',
  recentDays = '30',
}: {
  category?: string
  radius?: string
  recentDays?: string
} = {}) {
  const user = userEvent.setup()

  await user.type(screen.getByRole('spinbutton', { name: 'Latitude' }), '52.2704')
  await user.type(
    screen.getByRole('spinbutton', { name: 'Longitude' }),
    '-9.7026',
  )
  await user.selectOptions(screen.getByRole('combobox', { name: 'Radius' }), radius)
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Recent period' }),
    recentDays,
  )

  if (category !== undefined) {
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Category' }),
      category,
    )
  }

  await user.click(screen.getByRole('button', { name: 'Find opportunities' }))
}

describe('OpportunitiesPage', () => {
  let fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the accessible form and waits for a submission before requesting', () => {
    render(<OpportunitiesPage />)

    expect(
      screen.getByRole('heading', { level: 2, name: 'Opportunities near you' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: 'Top opportunities' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('form', { name: 'Opportunity filters' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('spinbutton', { name: 'Latitude' }),
    ).toBeRequired()
    expect(
      screen.getByRole('spinbutton', { name: 'Longitude' }),
    ).toBeRequired()
    expect(screen.getByRole('combobox', { name: 'Radius' })).toHaveValue('25')
    expect(screen.getByRole('combobox', { name: 'Recent period' })).toHaveValue(
      '30',
    )
    expect(screen.getByRole('combobox', { name: 'Category' })).toHaveValue('')
    expect(
      screen.getByRole('button', { name: 'Find opportunities' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/enter a latitude and longitude/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('requests the endpoint with every submitted query parameter', async () => {
    fetchMock.mockResolvedValue(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await submitSearch({
      category: 'commercial',
      radius: '50',
      recentDays: '60',
    })

    await screen.findByText('No opportunities found for this search.')
    expect(fetchMock).toHaveBeenCalledTimes(1)

    const requestUrl = new URL(
      fetchMock.mock.calls[0][0] as string,
      'http://localhost',
    )
    expect(requestUrl.pathname).toBe('/api/v1/opportunities')
    expect(requestUrl.searchParams.get('latitude')).toBe('52.2704')
    expect(requestUrl.searchParams.get('longitude')).toBe('-9.7026')
    expect(requestUrl.searchParams.get('radius_km')).toBe('50')
    expect(requestUrl.searchParams.get('recent_days')).toBe('60')
    expect(requestUrl.searchParams.get('category')).toBe('commercial')
    expect(requestUrl.searchParams.get('limit')).toBe('20')
  })

  it('omits category when All categories is selected', async () => {
    fetchMock.mockResolvedValue(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    await screen.findByText('No opportunities found for this search.')
    const requestUrl = new URL(
      fetchMock.mock.calls[0][0] as string,
      'http://localhost',
    )
    expect(requestUrl.searchParams.has('category')).toBe(false)
  })

  it('announces loading while the request is in progress', async () => {
    let resolveRequest: (response: Response) => void = () => undefined
    fetchMock.mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveRequest = resolve
      }),
    )
    render(<OpportunitiesPage />)

    await submitSearch()

    expect(screen.getByRole('status')).toHaveTextContent('Loading opportunities')
    expect(
      screen.getByRole('button', { name: 'Find opportunities' }),
    ).toBeDisabled()

    resolveRequest(jsonResponse(emptyFeed))
    await screen.findByText('No opportunities found for this search.')
  })

  it('renders successful API results and their score details', async () => {
    fetchMock.mockResolvedValue(jsonResponse(opportunityFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    const results = await screen.findByRole('list', {
      name: 'Top opportunities',
    })
    const opportunity = within(results).getByRole('article', {
      name: /industrial manufacturing facility/i,
    })

    expect(within(opportunity).getByText('96')).toBeInTheDocument()
    expect(within(opportunity).getByText('Very high')).toBeInTheDocument()
    expect(within(opportunity).getByText('Industrial')).toBeInTheDocument()
    expect(within(opportunity).getByText('4.25 km')).toBeInTheDocument()
    expect(
      within(opportunity).getByText('Kerry County Council'),
    ).toBeInTheDocument()
    expect(within(opportunity).getByText('26/1042')).toBeInTheDocument()
    expect(
      within(opportunity).getByText(
        'Manor West Business Park, Tralee, Co. Kerry',
      ),
    ).toBeInTheDocument()
    expect(within(opportunity).getByText('18 August 2026')).toBeInTheDocument()
    expect(within(opportunity).getByText('Score breakdown')).toBeInTheDocument()
    expect(
      within(opportunity).getByRole('link', { name: 'View opportunity' }),
    ).toHaveAttribute('href', 'https://example.test/planning/26-1042')
  })

  it('announces a successful empty result', async () => {
    fetchMock.mockResolvedValue(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    expect(await screen.findByRole('status')).toHaveTextContent(
      'No opportunities found for this search.',
    )
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it.each([
    ['API failure', () => Promise.resolve(jsonResponse(emptyFeed, 500))],
    ['network failure', () => Promise.reject(new Error('Network unavailable'))],
  ])('announces an %s', async (_name, request) => {
    fetchMock.mockImplementation(request)
    render(<OpportunitiesPage />)

    await submitSearch()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'We could not load opportunities',
    )
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
})
