import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const traleeLocation = {
  query: 'Tralee',
  display_name: 'Tralee, Co. Kerry, Ireland',
  latitude: 52.2704,
  longitude: -9.7026,
}

const opportunity = {
  id: 20,
  application_number: '26/1042',
  planning_authority: 'Kerry County Council',
  description: 'Construction of a new industrial facility with electrical works.',
  address: 'Tralee, Co. Kerry',
  application_type: 'Permission',
  application_status: 'Pending',
  decision: null,
  received_date: '2026-08-18',
  application_url: 'https://example.test/planning/26-1042',
  category: 'industrial',
  distance_km: 4.25,
  opportunity_score: 80,
  opportunity_level: 'very_high',
  opportunity_breakdown: {
    project_scope: 30,
    electrical_relevance: 30,
    project_scale: 0,
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
        'The planning description includes "electrical works", a strong electrical indicator.',
    },
    {
      name: 'project_scale',
      points_awarded: 0,
      maximum_points: 20,
      explanation:
        'No valid residential unit count or floor area was available.',
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
}

const opportunityFeed = {
  items: [opportunity],
  limit: 20,
  returned_count: 1,
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function opportunityDetailResponse() {
  return jsonResponse({
    ...opportunity,
    distance_km: undefined,
  })
}

function mockManualSearchRequests() {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(traleeLocation))
    .mockResolvedValueOnce(jsonResponse(opportunityFeed))
    .mockResolvedValueOnce(opportunityDetailResponse())
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function submitManualSearch() {
  const user = userEvent.setup()

  await user.type(screen.getByRole('textbox', { name: 'Location' }), 'Tralee')
  await user.selectOptions(screen.getByRole('combobox', { name: 'Radius' }), '50')
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Recent period' }),
    '60',
  )
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Category' }),
    'industrial',
  )
  await user.click(screen.getByRole('button', { name: 'Find opportunities' }))

  return user
}

async function openOpportunity(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('link', { name: 'View opportunity' }))
  return screen.findByRole('article', {
    name: 'Opportunity 26/1042',
  })
}

describe('App', () => {
  let scrollToMock: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    window.history.replaceState(null, '', '/')
    Object.defineProperty(window, 'scrollY', {
      configurable: true,
      value: 0,
    })
    scrollToMock = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  })

  afterEach(() => {
    window.history.replaceState(null, '', '/')
    Reflect.deleteProperty(navigator, 'geolocation')
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('renders the normal initial Opportunities page and semantic landmarks', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    expect(
      screen.getByRole('heading', { level: 1, name: 'GroundSignal' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(
      screen.getByText('Enter an Irish location to find nearby opportunities.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Location' })).toBeRequired()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('restores a manual search, filters, results, and scroll position from the detail back link', async () => {
    const fetchMock = mockManualSearchRequests()
    Object.defineProperty(window, 'scrollY', {
      configurable: true,
      value: 640,
    })
    render(<App />)

    const user = await submitManualSearch()
    expect(
      await screen.findByText('Opportunities near Tralee, Co. Kerry, Ireland'),
    ).toBeInTheDocument()
    const detail = await openOpportunity(user)

    expect(window.location.pathname).toBe('/opportunities/20')
    expect(within(detail).getByText('4.3 km')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(3)
    await user.click(screen.getByRole('link', { name: 'Back to opportunities' }))

    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(screen.getByRole('textbox', { name: 'Location' })).toHaveValue('Tralee')
    expect(screen.getByRole('combobox', { name: 'Radius' })).toHaveValue('50')
    expect(screen.getByRole('combobox', { name: 'Recent period' })).toHaveValue(
      '60',
    )
    expect(screen.getByRole('combobox', { name: 'Category' })).toHaveValue(
      'industrial',
    )
    expect(
      screen.getByText('Opportunities near Tralee, Co. Kerry, Ireland'),
    ).toBeInTheDocument()
    const results = screen.getByRole('list', { name: 'Top opportunities' })
    expect(
      within(results).getByRole('link', { name: 'View opportunity' }),
    ).toHaveAttribute('href', '/opportunities/20')
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(scrollToMock).toHaveBeenCalledWith(0, 640)
  })

  it('restores the same search state when the browser Back action is used', async () => {
    const fetchMock = mockManualSearchRequests()
    render(<App />)

    const user = await submitManualSearch()
    await openOpportunity(user)

    act(() => window.history.back())

    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(screen.getByRole('textbox', { name: 'Location' })).toHaveValue('Tralee')
    expect(
      screen.getByText('Opportunities near Tralee, Co. Kerry, Ireland'),
    ).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Top opportunities' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('restores selected current location, coordinates, filters, and results', async () => {
    const getCurrentPositionMock = vi.fn<Geolocation['getCurrentPosition']>()
    getCurrentPositionMock.mockImplementation((onSuccess) => {
      onSuccess({
        coords: { latitude: 53.3498, longitude: -6.2603 },
      } as GeolocationPosition)
    })
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: getCurrentPositionMock },
    })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(opportunityFeed))
      .mockResolvedValueOnce(opportunityDetailResponse())
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()

    await user.click(
      screen.getByRole('button', { name: 'Use my current location' }),
    )
    await user.selectOptions(screen.getByRole('combobox', { name: 'Radius' }), '10')
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Recent period' }),
      '90',
    )
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Category' }),
      'commercial',
    )
    await user.click(screen.getByRole('button', { name: 'Find opportunities' }))
    await openOpportunity(user)
    await user.click(screen.getByRole('link', { name: 'Back to opportunities' }))

    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(screen.getByText('Current location selected.')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Location' })).toHaveValue('')
    expect(screen.getByRole('textbox', { name: 'Location' })).not.toBeRequired()
    expect(screen.getByRole('combobox', { name: 'Radius' })).toHaveValue('10')
    expect(screen.getByRole('combobox', { name: 'Recent period' })).toHaveValue(
      '90',
    )
    expect(screen.getByRole('combobox', { name: 'Category' })).toHaveValue(
      'commercial',
    )
    expect(
      screen.getByText('Opportunities near your current location'),
    ).toBeInTheDocument()
    expect(getCurrentPositionMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledTimes(2)

    const opportunitiesUrl = new URL(
      fetchMock.mock.calls[0][0] as string,
      'http://localhost',
    )
    expect(opportunitiesUrl.pathname).toBe('/api/v1/opportunities')
    expect(opportunitiesUrl.searchParams.get('latitude')).toBe('53.3498')
    expect(opportunitiesUrl.searchParams.get('longitude')).toBe('-6.2603')
  })

  it('supports a direct detail visit without prior search state', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(opportunityDetailResponse())
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState(null, '', '/opportunities/20')
    render(<App />)

    expect(
      await screen.findByRole('heading', {
        level: 2,
        name: 'Opportunity 26/1042',
      }),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(
      screen.queryByRole('heading', { level: 2, name: 'Opportunities near you' }),
    ).not.toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole('link', { name: 'Back to opportunities' }))

    expect(window.location.pathname).toBe('/')
    expect(
      screen.getByText('Enter an Irish location to find nearby opportunities.'),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(scrollToMock).not.toHaveBeenCalled()
  })

  it('does not request the API for an invalid opportunity route', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState(null, '', '/opportunities/not-a-valid-id')

    render(<App />)

    expect(
      screen.getByRole('heading', { level: 2, name: 'Page not found' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to opportunities' })).toHaveAttribute(
      'href',
      '/',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
