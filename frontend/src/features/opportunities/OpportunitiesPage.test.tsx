import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { GeocodedLocation } from '../../api/locations'
import type { OpportunityFeedResponse } from '../../api/opportunities'
import OpportunitiesPage from './OpportunitiesPage'

const traleeLocation: GeocodedLocation = {
  query: 'Tralee',
  display_name: 'Tralee, Co. Kerry, Ireland',
  latitude: 52.2704,
  longitude: -9.7026,
}

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
      opportunity_score_components: [
        {
          name: 'project_scope',
          points_awarded: 30,
          maximum_points: 30,
          explanation: 'New industrial development indicators were identified.',
        },
        {
          name: 'electrical_relevance',
          points_awarded: 30,
          maximum_points: 30,
          explanation:
            'The planning description includes "electrical infrastructure", a strong electrical indicator.',
        },
        {
          name: 'project_scale',
          points_awarded: 16,
          maximum_points: 20,
          explanation:
            'A floor area of 2,500 square metres was identified, indicating a large development.',
        },
        {
          name: 'lead_timing',
          points_awarded: 10,
          maximum_points: 10,
          explanation:
            'The application was received 6 days ago, within the last 14 days.',
        },
        {
          name: 'category_fit',
          points_awarded: 10,
          maximum_points: 10,
          explanation:
            'The application is classified as Industrial, which receives 10 points for category fit.',
        },
      ],
    },
  ],
  page: 1,
  page_size: 20,
  total: 1,
  total_pages: 1,
}

const emptyFeed: OpportunityFeedResponse = {
  items: [],
  page: 1,
  page_size: 20,
  total: 0,
  total_pages: 0,
}

const sortingFeed: OpportunityFeedResponse = {
  items: [
    {
      ...opportunityFeed.items[0],
      id: 20,
      application_number: 'SORT-20',
      opportunity_score: 96,
      distance_km: 4.25,
      received_date: '2026-08-18',
    },
    {
      ...opportunityFeed.items[0],
      id: 22,
      application_number: 'SORT-22',
      opportunity_score: 70,
      distance_km: 1,
      received_date: '2026-08-10',
    },
    {
      ...opportunityFeed.items[0],
      id: 21,
      application_number: 'SORT-21',
      opportunity_score: 55,
      distance_km: 9,
      received_date: '2026-08-23',
    },
    {
      ...opportunityFeed.items[0],
      id: 23,
      application_number: 'SORT-23',
      opportunity_score: 25,
      distance_km: 3,
      received_date: null,
    },
  ],
  page: 1,
  page_size: 20,
  total: 4,
  total_pages: 1,
}

const nearestFeed: OpportunityFeedResponse = {
  ...sortingFeed,
  items: [
    sortingFeed.items[1],
    sortingFeed.items[3],
    sortingFeed.items[0],
    sortingFeed.items[2],
  ],
}

const newestFeed: OpportunityFeedResponse = {
  ...sortingFeed,
  items: [
    sortingFeed.items[2],
    sortingFeed.items[0],
    sortingFeed.items[1],
    sortingFeed.items[3],
  ],
}

const firstPageFeed: OpportunityFeedResponse = {
  ...opportunityFeed,
  total: 21,
  total_pages: 2,
}

const secondPageFeed: OpportunityFeedResponse = {
  ...opportunityFeed,
  items: [
    {
      ...opportunityFeed.items[0],
      id: 42,
      application_number: 'PAGE-42',
    },
  ],
  page: 2,
  total: 21,
  total_pages: 2,
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

async function submitSearch({
  location = 'Tralee',
  category,
  radius = '25',
  recentDays = '30',
}: {
  location?: string
  category?: string
  radius?: string
  recentDays?: string
} = {}) {
  const user = userEvent.setup()

  await user.type(screen.getByRole('textbox', { name: 'Location' }), location)
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

async function submitCurrentLocationSearch({
  category,
  radius = '25',
  recentDays = '30',
}: {
  category?: string
  radius?: string
  recentDays?: string
} = {}) {
  const user = userEvent.setup()

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

async function useCurrentLocation() {
  const user = userEvent.setup()

  await user.click(
    screen.getByRole('button', { name: 'Use my current location' }),
  )
}

function resultOpportunityPaths() {
  const results = screen.getByRole('list', { name: 'Top opportunities' })
  return within(results)
    .getAllByRole('link', { name: 'View opportunity' })
    .map((link) => link.getAttribute('href'))
}

describe('OpportunitiesPage', () => {
  let fetchMock = vi.fn()
  let getCurrentPositionMock = vi.fn<Geolocation['getCurrentPosition']>()

  beforeEach(() => {
    fetchMock = vi.fn()
    getCurrentPositionMock = vi.fn<Geolocation['getCurrentPosition']>()
    vi.stubGlobal('fetch', fetchMock)
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: getCurrentPositionMock },
    })
  })

  afterEach(() => {
    Reflect.deleteProperty(navigator, 'geolocation')
    vi.unstubAllGlobals()
  })

  it('renders a required location field instead of coordinate inputs', () => {
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

    const locationInput = screen.getByRole('textbox', { name: 'Location' })
    expect(locationInput).toBeRequired()
    expect(locationInput).toHaveAttribute('placeholder', 'e.g. Tralee, Co. Kerry')
    expect(screen.queryByLabelText('Latitude')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Longitude')).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Radius' })).toHaveValue('25')
    expect(screen.getByRole('combobox', { name: 'Recent period' })).toHaveValue(
      '30',
    )
    expect(screen.getByRole('combobox', { name: 'Category' })).toHaveValue('')
    expect(
      screen.getByText(/enter an Irish location to find nearby opportunities/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Use my current location' }),
    ).toBeInTheDocument()
    expect(getCurrentPositionMock).not.toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('requests browser location only after clicking and announces the locating state', async () => {
    render(<OpportunitiesPage />)

    await useCurrentLocation()

    expect(getCurrentPositionMock).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Getting your current location',
    )
    expect(
      screen.getByRole('button', { name: 'Getting current location...' }),
    ).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Find opportunities' }),
    ).toBeDisabled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('stores browser coordinates and searches with filters selected afterward', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await useCurrentLocation()

    await act(async () => {
      const onSuccess = getCurrentPositionMock.mock.calls[0][0]
      onSuccess({
        coords: { latitude: 53.3498, longitude: -6.2603 },
      } as GeolocationPosition)
    })

    expect(screen.getByRole('status')).toHaveTextContent(
      'Current location selected',
    )
    expect(screen.getByRole('textbox', { name: 'Location' })).not.toBeRequired()
    expect(fetchMock).not.toHaveBeenCalled()

    await submitCurrentLocationSearch({
      category: 'industrial',
      radius: '50',
      recentDays: '60',
    })

    await screen.findByText('No opportunities found for this search.')
    expect(fetchMock).toHaveBeenCalledTimes(1)

    const opportunityUrl = new URL(
      fetchMock.mock.calls[0][0] as string,
      'http://localhost',
    )
    expect(opportunityUrl.pathname).toBe('/api/v1/opportunities')
    expect(opportunityUrl.pathname).not.toBe('/api/v1/locations/geocode')
    expect(opportunityUrl.searchParams.get('latitude')).toBe('53.3498')
    expect(opportunityUrl.searchParams.get('longitude')).toBe('-6.2603')
    expect(opportunityUrl.searchParams.get('radius_km')).toBe('50')
    expect(opportunityUrl.searchParams.get('recent_days')).toBe('60')
    expect(opportunityUrl.searchParams.get('category')).toBe('industrial')
    expect(opportunityUrl.searchParams.get('page')).toBe('1')
    expect(opportunityUrl.searchParams.get('page_size')).toBe('20')
    expect(opportunityUrl.searchParams.get('sort')).toBe('best')
    expect(
      screen.getByRole('heading', {
        level: 3,
        name: 'Opportunities near your current location',
      }),
    ).toBeInTheDocument()
  })

  it('omits category from current-location searches for All categories', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await useCurrentLocation()

    await act(async () => {
      const onSuccess = getCurrentPositionMock.mock.calls[0][0]
      onSuccess({
        coords: { latitude: 52.2704, longitude: -9.7026 },
      } as GeolocationPosition)
    })

    expect(fetchMock).not.toHaveBeenCalled()
    await submitCurrentLocationSearch()

    await screen.findByText('No opportunities found for this search.')
    const opportunityUrl = new URL(
      fetchMock.mock.calls[0][0] as string,
      'http://localhost',
    )
    expect(opportunityUrl.searchParams.has('category')).toBe(false)
  })

  it('clears selected browser coordinates when a manual location is entered', async () => {
    render(<OpportunitiesPage />)

    await useCurrentLocation()
    await act(async () => {
      const onSuccess = getCurrentPositionMock.mock.calls[0][0]
      onSuccess({
        coords: { latitude: 52.2704, longitude: -9.7026 },
      } as GeolocationPosition)
    })

    expect(screen.getByText('Current location selected.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()

    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(emptyFeed))
    await submitSearch()

    await screen.findByText('No opportunities found for this search.')
    expect(screen.queryByText('Current location selected.')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Location' })).toBeRequired()
    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/locations/geocode?query=Tralee',
    )
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('allows manual location search after browser location permission is denied', async () => {
    render(<OpportunitiesPage />)

    await useCurrentLocation()

    await act(async () => {
      const onError = getCurrentPositionMock.mock.calls[0][1]
      onError?.({ code: 1, message: 'Permission denied' } as GeolocationPositionError)
    })

    expect(screen.getByRole('alert')).toHaveTextContent(
      'We could not access your current location',
    )
    expect(
      screen.getByRole('button', { name: 'Use my current location' }),
    ).toBeEnabled()
    expect(
      screen.getByRole('button', { name: 'Find opportunities' }),
    ).toBeEnabled()
    expect(fetchMock).not.toHaveBeenCalled()

    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(emptyFeed))
    await submitSearch()

    await screen.findByText('No opportunities found for this search.')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/locations/geocode?query=Tralee',
    )
  })

  it('geocodes an encoded location before requesting opportunities with all filters', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await submitSearch({
      location: 'Dún Laoghaire & Rathdown',
      category: 'commercial',
      radius: '50',
      recentDays: '60',
    })

    await screen.findByText('No opportunities found for this search.')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/locations/geocode?query=D%C3%BAn+Laoghaire+%26+Rathdown',
    )

    const opportunityUrl = new URL(
      fetchMock.mock.calls[1][0] as string,
      'http://localhost',
    )
    expect(opportunityUrl.pathname).toBe('/api/v1/opportunities')
    expect(opportunityUrl.searchParams.get('latitude')).toBe('52.2704')
    expect(opportunityUrl.searchParams.get('longitude')).toBe('-9.7026')
    expect(opportunityUrl.searchParams.get('radius_km')).toBe('50')
    expect(opportunityUrl.searchParams.get('recent_days')).toBe('60')
    expect(opportunityUrl.searchParams.get('category')).toBe('commercial')
    expect(opportunityUrl.searchParams.get('page')).toBe('1')
    expect(opportunityUrl.searchParams.get('page_size')).toBe('20')
    expect(opportunityUrl.searchParams.get('sort')).toBe('best')
  })

  it('omits category when All categories is selected', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    await screen.findByText('No opportunities found for this search.')
    const opportunityUrl = new URL(
      fetchMock.mock.calls[1][0] as string,
      'http://localhost',
    )
    expect(opportunityUrl.searchParams.has('category')).toBe(false)
  })

  it('announces loading while geocoding and prevents another submission', async () => {
    let resolveGeocoding: (response: Response) => void = () => undefined
    fetchMock
      .mockReturnValueOnce(
        new Promise<Response>((resolve) => {
          resolveGeocoding = resolve
        }),
      )
      .mockResolvedValueOnce(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    expect(screen.getByRole('status')).toHaveTextContent(
      'Searching for opportunities',
    )
    expect(
      screen.getByRole('button', { name: 'Find opportunities' }),
    ).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveGeocoding(jsonResponse(traleeLocation))
    })
    await screen.findByText('No opportunities found for this search.')
  })

  it('renders successful results and the resolved display location', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(opportunityFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    expect(
      await screen.findByText('Opportunities near Tralee, Co. Kerry, Ireland'),
    ).toBeInTheDocument()
    const results = screen.getByRole('list', { name: 'Top opportunities' })
    const opportunity = within(results).getByRole('article', {
      name: /industrial manufacturing facility/i,
    })

    expect(within(opportunity).getByText('96')).toBeInTheDocument()
    expect(within(opportunity).getByText('Very high opportunity')).toBeInTheDocument()
    expect(within(opportunity).getByText('Industrial')).toBeInTheDocument()
    expect(within(opportunity).getByText('4.3 km')).toBeInTheDocument()
    expect(
      within(opportunity).getByText('Kerry County Council'),
    ).toBeInTheDocument()
    expect(within(opportunity).getByText('26/1042')).toBeInTheDocument()
    expect(
      within(opportunity).getByText('Manor West Business Park, Tralee'),
    ).toBeInTheDocument()
    expect(within(opportunity).getByText('Co. Kerry')).toBeInTheDocument()
    expect(within(opportunity).getByText('18 August 2026')).toBeInTheDocument()
    expect(
      within(opportunity).queryByText('Score breakdown'),
    ).not.toBeInTheDocument()
    const viewOpportunityLink = within(opportunity).getByRole('link', {
      name: 'View opportunity',
    })
    expect(viewOpportunityLink).toHaveAttribute('href', '/opportunities/20')
    expect(viewOpportunityLink).not.toHaveAttribute('target')
  })

  it('requests globally sorted results without repeating geocoding or geolocation', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(sortingFeed))
      .mockResolvedValueOnce(jsonResponse(nearestFeed))
      .mockResolvedValueOnce(jsonResponse(newestFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    const sortControl = await screen.findByRole('combobox', { name: 'Sort by' })
    expect(sortControl).toHaveValue('best')
    expect(resultOpportunityPaths()).toEqual([
      '/opportunities/20',
      '/opportunities/22',
      '/opportunities/21',
      '/opportunities/23',
    ])

    const user = userEvent.setup()
    await user.selectOptions(sortControl, 'nearest')
    await waitFor(() =>
      expect(resultOpportunityPaths()).toEqual([
        '/opportunities/22',
        '/opportunities/23',
        '/opportunities/20',
        '/opportunities/21',
      ]),
    )

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Sort by' }),
      'newest',
    )
    await waitFor(() =>
      expect(resultOpportunityPaths()).toEqual([
        '/opportunities/21',
        '/opportunities/20',
        '/opportunities/22',
        '/opportunities/23',
      ]),
    )
    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(getCurrentPositionMock).not.toHaveBeenCalled()

    const requestUrls = fetchMock.mock.calls.map(([request]) =>
      new URL(request as string, 'http://localhost'),
    )
    expect(
      requestUrls.filter(
        ({ pathname }) => pathname === '/api/v1/locations/geocode',
      ),
    ).toHaveLength(1)
    expect(requestUrls.slice(1).map((url) => url.searchParams.get('sort'))).toEqual(
      ['best', 'nearest', 'newest'],
    )
    expect(requestUrls.slice(1).map((url) => url.searchParams.get('page'))).toEqual(
      ['1', '1', '1'],
    )
  })

  it('renders pagination boundaries and requests Previous and Next pages', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
      .mockResolvedValueOnce(jsonResponse(secondPageFeed))
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    const user = userEvent.setup()
    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Previous' }))
    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(getCurrentPositionMock).not.toHaveBeenCalled()

    const opportunityRequests = fetchMock.mock.calls
      .map(([request]) => new URL(request as string, 'http://localhost'))
      .filter(({ pathname }) => pathname === '/api/v1/opportunities')
    expect(
      opportunityRequests.map((url) => url.searchParams.get('page')),
    ).toEqual(['1', '2', '1'])
    expect(
      opportunityRequests.map((url) => url.searchParams.get('page_size')),
    ).toEqual(['20', '20', '20'])
  })

  it('keeps current results visible and disables controls during page and sort refreshes', async () => {
    let resolvePageRequest: (response: Response) => void = () => undefined
    let resolveSortRequest: (response: Response) => void = () => undefined
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolvePageRequest = resolve
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolveSortRequest = resolve
          }),
      )
    render(<OpportunitiesPage />)

    await submitSearch()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Next' }))

    expect(screen.getByRole('status')).toHaveTextContent(
      'Refreshing opportunities',
    )
    expect(resultOpportunityPaths()).toEqual(['/opportunities/20'])
    expect(screen.getByRole('list', { name: 'Top opportunities' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Find opportunities' }),
    ).toBeDisabled()

    await act(async () => resolvePageRequest(jsonResponse(secondPageFeed)))
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
    expect(resultOpportunityPaths()).toEqual(['/opportunities/42'])

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Sort by' }),
      'nearest',
    )
    expect(screen.getByRole('status')).toHaveTextContent(
      'Refreshing opportunities',
    )
    expect(resultOpportunityPaths()).toEqual(['/opportunities/42'])
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()

    await act(async () => resolveSortRequest(jsonResponse(firstPageFeed)))
    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
    expect(resultOpportunityPaths()).toEqual(['/opportunities/20'])
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toBeEnabled()
    expect(screen.getByRole('list', { name: 'Top opportunities' })).toHaveAttribute(
      'aria-busy',
      'false',
    )

    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(getCurrentPositionMock).not.toHaveBeenCalled()
    const paths = fetchMock.mock.calls.map(
      ([request]) => new URL(request as string, 'http://localhost').pathname,
    )
    expect(paths.filter((path) => path === '/api/v1/locations/geocode')).toEqual([
      '/api/v1/locations/geocode',
    ])
  })

  it('retains current results when a page refresh fails', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
      .mockResolvedValueOnce(jsonResponse({}, 503))
    render(<OpportunitiesPage />)

    await submitSearch()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Next' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'could not refresh opportunities',
    )
    expect(resultOpportunityPaths()).toEqual(['/opportunities/20'])
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(getCurrentPositionMock).not.toHaveBeenCalled()
  })

  it('reuses stored browser coordinates for page and sort requests', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
      .mockResolvedValueOnce(jsonResponse(secondPageFeed))
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
    render(<OpportunitiesPage />)

    await useCurrentLocation()
    await act(async () => {
      const onSuccess = getCurrentPositionMock.mock.calls[0][0]
      onSuccess({
        coords: { latitude: 53.3498, longitude: -6.2603 },
      } as GeolocationPosition)
    })
    await submitCurrentLocationSearch()

    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Sort by' }),
      'nearest',
    )
    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()

    expect(getCurrentPositionMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledTimes(3)
    const opportunityRequests = fetchMock.mock.calls.map(
      ([request]) => new URL(request as string, 'http://localhost'),
    )
    expect(
      opportunityRequests.every(
        ({ pathname }) => pathname === '/api/v1/opportunities',
      ),
    ).toBe(true)
    expect(
      opportunityRequests.map((url) => [
        url.searchParams.get('page'),
        url.searchParams.get('sort'),
      ]),
    ).toEqual([
      ['1', 'best'],
      ['2', 'best'],
      ['1', 'nearest'],
    ])
  })

  it('resets page one for sort and new-search changes', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
      .mockResolvedValueOnce(jsonResponse(secondPageFeed))
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(firstPageFeed))
    render(<OpportunitiesPage />)

    await submitSearch()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Sort by' }),
      'nearest',
    )
    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()

    await user.selectOptions(screen.getByRole('combobox', { name: 'Radius' }), '50')
    await user.click(screen.getByRole('button', { name: 'Find opportunities' }))
    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()

    const requestUrls = fetchMock.mock.calls.map(([request]) =>
      new URL(request as string, 'http://localhost'),
    )
    const geocodingRequests = requestUrls.filter(
      ({ pathname }) => pathname === '/api/v1/locations/geocode',
    )
    const opportunityRequests = requestUrls.filter(
      ({ pathname }) => pathname === '/api/v1/opportunities',
    )
    expect(geocodingRequests).toHaveLength(2)
    expect(opportunityRequests.map((url) => url.searchParams.get('page'))).toEqual([
      '1',
      '2',
      '1',
      '1',
    ])
    expect(opportunityRequests[2].searchParams.get('sort')).toBe('nearest')
    expect(opportunityRequests[3].searchParams.get('radius_km')).toBe('50')
    expect(getCurrentPositionMock).not.toHaveBeenCalled()
  })

  it('announces an empty result and retains the resolved display location', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse(emptyFeed))
    render(<OpportunitiesPage />)

    await submitSearch()

    expect(await screen.findByRole('status')).toHaveTextContent(
      'No opportunities found for this search.',
    )
    expect(
      screen.getByText('Opportunities near Tralee, Co. Kerry, Ireland'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('announces when a location is not found without requesting opportunities', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Location not found.' }, 404),
    )
    render(<OpportunitiesPage />)

    await submitSearch({ location: 'Not a real Irish location' })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'We could not find that location',
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it.each([
    ['service failure', () => Promise.resolve(jsonResponse({}, 503))],
    ['network failure', () => Promise.reject(new Error('Network unavailable'))],
  ])('announces a geocoding %s without exposing raw details', async (_name, request) => {
    fetchMock.mockImplementationOnce(request)
    render(<OpportunitiesPage />)

    await submitSearch()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Location search is unavailable right now',
    )
    expect(screen.queryByText('Network unavailable')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('announces an opportunity API failure separately', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(traleeLocation))
      .mockResolvedValueOnce(jsonResponse({}, 500))
    render(<OpportunitiesPage />)

    await submitSearch()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'We could not load opportunities',
    )
    expect(
      screen.getByText('Opportunities near Tralee, Co. Kerry, Ireland'),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('does not request anything when the required location is empty', async () => {
    render(<OpportunitiesPage />)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Find opportunities' }))

    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled())
  })
})
