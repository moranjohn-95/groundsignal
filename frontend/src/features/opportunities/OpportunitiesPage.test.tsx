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
    expect(opportunityUrl.searchParams.get('limit')).toBe('20')
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
    expect(opportunityUrl.searchParams.get('limit')).toBe('20')
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
