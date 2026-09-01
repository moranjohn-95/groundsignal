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
  page: 1,
  page_size: 20,
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

function opportunityDetailResponse() {
  return jsonResponse({
    ...opportunity,
    distance_km: undefined,
  })
}

function mockManualSearchRequests() {
  const fetchMock = vi.fn().mockImplementation((request: string) => {
    const url = new URL(request, 'http://localhost')
    if (url.pathname === '/api/v1/locations/geocode') {
      return Promise.resolve(jsonResponse(traleeLocation))
    }
    if (url.pathname === '/api/v1/opportunities') {
      const page = Number(url.searchParams.get('page'))
      return Promise.resolve(
        jsonResponse({
          ...opportunityFeed,
          page,
        }),
      )
    }
    return Promise.resolve(opportunityDetailResponse())
  })
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
      screen.getByRole('heading', { level: 1, name: 'SiteForecaster' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
    const legalNavigation = screen.getByRole('navigation', { name: 'Legal' })
    expect(
      within(legalNavigation).getByRole('link', { name: 'Data sources' }),
    ).toHaveAttribute('href', '/data-sources')
    expect(
      within(legalNavigation).getByRole('link', { name: 'Privacy' }),
    ).toHaveAttribute('href', '/privacy')
    expect(
      within(legalNavigation).getByRole('link', { name: 'Terms' }),
    ).toHaveAttribute('href', '/terms')
    expect(
      screen.getByText('Enter an Irish location to find nearby opportunities.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Location' })).toBeRequired()
    expect(screen.getByText('Google Maps').closest('p')).toHaveClass(
      'google-maps-attribution',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    [
      '/data-sources',
      'Data sources',
      /Contains Irish Public Sector Data licensed under/i,
    ],
    [
      '/privacy',
      'Privacy Policy',
      /Google Maps Platform Geocoding services/i,
    ],
    [
      '/terms',
      'Terms of Use',
      /opportunity-score assessments are derived by SiteForecaster/i,
    ],
  ])('renders the %s page on a direct visit', (pathname, title, content) => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState(null, '', pathname)

    render(<App />)

    expect(screen.getByRole('heading', { level: 2, name: title })).toBeInTheDocument()
    expect(screen.getByText(content)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('navigates between legal pages from the footer without a page reload', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()

    await user.click(screen.getByRole('link', { name: 'Data sources' }))
    expect(window.location.pathname).toBe('/data-sources')
    expect(
      screen.getByText(/not provided or endorsed by the Irish Government/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', {
        name: /Creative Commons Attribution 4.0 International/i,
      }),
    ).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/4.0/')

    await user.click(screen.getByRole('link', { name: 'Privacy' }))
    expect(window.location.pathname).toBe('/privacy')
    expect(
      screen.getByRole('link', { name: /Google's Privacy Policy/i }),
    ).toHaveAttribute('href', 'https://policies.google.com/privacy')
    expect(
      screen.getByText(/does not intentionally create a user location history/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Terms' }))
    expect(window.location.pathname).toBe('/terms')
    expect(
      screen.getByText(/official planning records remain the authoritative source/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', {
        name: /Google Maps\/Google Earth Additional Terms of Service/i,
      }),
    ).toHaveAttribute('href', 'https://maps.google.com/help/terms_maps/')

    act(() => window.history.back())
    await waitFor(() => expect(window.location.pathname).toBe('/privacy'))
    expect(
      screen.getByRole('heading', { level: 2, name: 'Privacy Policy' }),
    ).toBeInTheDocument()

    act(() => window.history.forward())
    await waitFor(() => expect(window.location.pathname).toBe('/terms'))
    expect(
      screen.getByRole('heading', { level: 2, name: 'Terms of Use' }),
    ).toBeInTheDocument()
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
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Sort' }),
      'nearest',
    )
    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
    const detail = await openOpportunity(user)

    expect(window.location.pathname).toBe('/opportunities/20')
    expect(within(detail).getByText('4.3 km')).toBeInTheDocument()
    await waitFor(() =>
      expect(
        within(detail).getByRole('heading', {
          level: 2,
          name: `Opportunity ${opportunity.application_number} details`,
        }),
      ).toHaveFocus(),
    )
    expect(fetchMock).toHaveBeenCalledTimes(5)
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
    expect(screen.getByRole('combobox', { name: 'Sort' })).toHaveValue(
      'nearest',
    )
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
    expect(
      screen.getByText('Opportunities near Tralee, Co. Kerry, Ireland'),
    ).toBeInTheDocument()
    const results = screen.getByRole('list', { name: 'Top opportunities' })
    const restoredOpportunityAction = within(results).getByRole('link', {
      name: 'View opportunity',
    })
    expect(restoredOpportunityAction).toHaveAttribute(
      'href',
      '/opportunities/20',
    )
    await waitFor(() => expect(restoredOpportunityAction).toHaveFocus())
    expect(fetchMock).toHaveBeenCalledTimes(5)
    expect(scrollToMock).toHaveBeenCalledWith(0, 640)

    const opportunityRequests = fetchMock.mock.calls
      .map(([request]) => new URL(request as string, 'http://localhost'))
      .filter(({ pathname }) => pathname === '/api/v1/opportunities')
    expect(
      opportunityRequests.map((url) => [
        url.searchParams.get('sort'),
        url.searchParams.get('page'),
      ]),
    ).toEqual([
      ['best', '1'],
      ['nearest', '1'],
      ['nearest', '2'],
    ])
  })

  it('restores the same search state when the browser Back action is used', async () => {
    const fetchMock = mockManualSearchRequests()
    render(<App />)

    const user = await submitManualSearch()
    const detail = await openOpportunity(user)
    await waitFor(() =>
      expect(
        within(detail).getByRole('heading', {
          level: 2,
          name: `Opportunity ${opportunity.application_number} details`,
        }),
      ).toHaveFocus(),
    )

    act(() => window.history.back())

    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(screen.getByRole('textbox', { name: 'Location' })).toHaveValue('Tralee')
    expect(
      screen.getByText('Opportunities near Tralee, Co. Kerry, Ireland'),
    ).toBeInTheDocument()
    const results = screen.getByRole('list', { name: 'Top opportunities' })
    const restoredOpportunityAction = within(results).getByRole('link', {
      name: 'View opportunity',
    })
    expect(restoredOpportunityAction).toHaveFocus()
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

    const detailHeading = await screen.findByRole('heading', {
      level: 2,
      name: `Opportunity ${opportunity.application_number} details`,
    })
    expect(detailHeading).toBeInTheDocument()
    await waitFor(() => expect(detailHeading).toHaveFocus())
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

  it.each(['/unknown-route', '/opportunities/not-a-valid-id'])(
    'renders the dedicated 404 page without requesting the API for %s',
    (pathname) => {
      const fetchMock = vi.fn()
      vi.stubGlobal('fetch', fetchMock)
      window.history.replaceState(null, '', pathname)

      render(<App />)

      expect(
        screen.getByRole('heading', { level: 2, name: 'Page not found' }),
      ).toBeInTheDocument()
      expect(
        screen.getByText("We couldn't find the page you're looking for."),
      ).toBeInTheDocument()
      expect(
        screen.getByText('Check the address or return to the main search.'),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: 'Back to opportunities' }),
      ).toHaveAttribute('href', '/')
      expect(fetchMock).not.toHaveBeenCalled()
    },
  )

  it('returns from the 404 page through the existing client-side navigation', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState(null, '', '/unknown-route')
    render(<App />)

    const user = userEvent.setup()
    await user.click(screen.getByRole('link', { name: 'Back to opportunities' }))

    expect(window.location.pathname).toBe('/')
    expect(
      screen.getByText('Enter an Irish location to find nearby opportunities.'),
    ).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
