import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const account = {
  id: 7,
  email: 'customer@example.com',
  is_active: true,
  created_at: '2026-09-29T12:00:00Z',
}

const opportunity = {
  id: 20,
  source_object_id: 120,
  application_number: 'TEST-20',
  planning_authority: 'Sample Council',
  description: 'New electrical installation and lighting.',
  address: 'Main Street, Tralee',
  application_type: 'Permission',
  application_status: 'Pending',
  decision: null,
  received_date: '2026-09-29',
  application_url: 'https://example.test/planning/20',
  category: 'commercial',
  distance_km: 2.5,
  opportunity_score: 75,
  raw_opportunity_score: 75,
  opportunity_level: 'high',
  opportunity_breakdown: {
    project_scope: 25,
    electrical_relevance: 30,
    project_scale: 10,
    lead_timing: 10,
    category_fit: 0,
  },
  opportunity_score_components: [],
  electrical_work_brief: {
    evidence_level: 'direct',
    summary: 'Electrical work evidenced.',
    signals: [],
  },
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function mockServer(initialUser: typeof account | null = null) {
  let currentUser = initialUser
  let savedItems: Array<{ id: number; saved_at: string; opportunity: { id: number } }> = []
  let listStatus = 200
  let saveStatus = 201
  let nextSaveId = 40
  const fetchMock = vi.fn().mockImplementation((request: string, options?: RequestInit) => {
    const url = new URL(request, 'http://localhost')
    if (url.pathname === '/api/v1/auth/me') {
      return Promise.resolve(currentUser ? jsonResponse(currentUser) : jsonResponse(null, 401))
    }
    if (url.pathname === '/api/v1/auth/signup' || url.pathname === '/api/v1/auth/login') {
      currentUser = account
      return Promise.resolve(jsonResponse(account, url.pathname.endsWith('/signup') ? 201 : 200))
    }
    if (url.pathname === '/api/v1/auth/logout') {
      currentUser = null
      return Promise.resolve(jsonResponse(null, 204))
    }
    if (url.pathname === '/api/v1/locations/geocode') {
      return Promise.resolve(jsonResponse({
        query: 'Tralee', display_name: 'Tralee, Co. Kerry, Ireland',
        latitude: 52.2704, longitude: -9.7026,
      }))
    }
    if (url.pathname === '/api/v1/opportunities') {
      return Promise.resolve(jsonResponse({
        items: [opportunity], page: 1, page_size: 20, total: 1, total_pages: 1,
      }))
    }
    if (url.pathname === '/api/v1/planning-applications/20') {
      return Promise.resolve(jsonResponse(opportunity))
    }
    if (url.pathname === '/api/v1/saved-opportunities' && !options?.method) {
      if (!currentUser) return Promise.resolve(jsonResponse(null, 401))
      if (listStatus !== 200) return Promise.resolve(jsonResponse(null, listStatus))
      const offset = Number(url.searchParams.get('offset') ?? 0)
      const limit = Number(url.searchParams.get('limit') ?? 20)
      return Promise.resolve(jsonResponse({
        items: savedItems.slice(offset, offset + limit), total: savedItems.length,
        limit, offset,
      }))
    }
    if (url.pathname === '/api/v1/saved-opportunities' && options?.method === 'POST') {
      if (!currentUser) return Promise.resolve(jsonResponse(null, 401))
      if (saveStatus !== 201) return Promise.resolve(jsonResponse(null, saveStatus))
      const planningId = JSON.parse(options.body as string).planning_application_id as number
      const existing = savedItems.find((item) => item.opportunity.id === planningId)
      if (existing) return Promise.resolve(jsonResponse(existing, 200))
      const saved = {
        id: nextSaveId++, saved_at: '2026-09-30T12:00:00Z', opportunity: { id: planningId },
      }
      savedItems = [...savedItems, saved]
      return Promise.resolve(jsonResponse(saved, 201))
    }
    if (url.pathname.startsWith('/api/v1/saved-opportunities/') && options?.method === 'DELETE') {
      if (!currentUser) return Promise.resolve(jsonResponse(null, 401))
      savedItems = savedItems.filter((item) => item.id !== Number(url.pathname.split('/').at(-1)))
      return Promise.resolve(jsonResponse(null, 204))
    }
    throw new Error(`Unexpected request: ${request}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return {
    fetchMock,
    setListStatus: (status: number) => { listStatus = status },
    setSaveStatus: (status: number) => { saveStatus = status },
  }
}

describe('opportunity saving', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/')
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  })

  afterEach(() => {
    window.history.replaceState(null, '', '/')
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('shows saved state after save and refresh, then removes the save', async () => {
    const server = mockServer(account)
    window.history.replaceState(null, '', '/opportunities/20')
    const first = render(<App />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Save opportunity' }))
    expect(await screen.findByRole('button', { name: 'Remove saved opportunity' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Saved to your account.')
    const post = server.fetchMock.mock.calls.find(([url, options]) =>
      url === '/api/v1/saved-opportunities' && options?.method === 'POST',
    )
    expect(post?.[1]).toMatchObject({
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    })
    expect(JSON.parse(post?.[1].body as string)).toEqual({ planning_application_id: 20 })

    first.unmount()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Remove saved opportunity' }))
    expect(await screen.findByRole('button', { name: 'Save opportunity' })).toBeInTheDocument()
    const removal = server.fetchMock.mock.calls.find(([, options]) => options?.method === 'DELETE')
    expect(removal?.[0]).toBe('/api/v1/saved-opportunities/40')
    expect(removal?.[1]).toMatchObject({ credentials: 'same-origin' })
  })

  it('returns through login to the same detail and preserves search Back state', async () => {
    const server = mockServer()
    render(<App />)
    const user = userEvent.setup()
    await user.type(screen.getByRole('textbox', { name: 'Location' }), 'Tralee')
    await user.click(screen.getByRole('button', { name: 'Find opportunities' }))
    await user.click(await screen.findByRole('link', { name: 'View opportunity' }))
    await user.click(await screen.findByRole('button', { name: 'Save opportunity' }))
    expect(window.location.pathname).toBe('/signup')
    expect(new URLSearchParams(window.location.search).get('returnTo')).toBe('/opportunities/20')
    const loginLinks = screen.getAllByRole('link', { name: 'Log in' })
    expect(loginLinks).toHaveLength(2)
    expect(loginLinks[0]).toHaveAttribute(
      'href', '/login?returnTo=%2Fopportunities%2F20&save=1',
    )
    expect(loginLinks[1]).toHaveAttribute('href', loginLinks[0].getAttribute('href'))
    await user.click(loginLinks[0])
    expect(window.location.pathname).toBe('/login')
    expect(new URLSearchParams(window.location.search).get('returnTo')).toBe('/opportunities/20')
    await user.type(screen.getByRole('textbox', { name: 'Email address' }), account.email)
    await user.type(screen.getByLabelText('Password'), 'a-long-test-password-123')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(window.location.pathname).toBe('/opportunities/20'))
    expect(await screen.findByRole('button', { name: 'Remove saved opportunity' })).toBeInTheDocument()
    expect(server.fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST' &&
      options.body?.toString().includes('planning_application_id'))).toHaveLength(1)

    await user.click(screen.getByRole('link', { name: 'Back to opportunities' }))
    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(screen.getByRole('textbox', { name: 'Location' })).toHaveValue('Tralee')
    expect(screen.getByText('Opportunities near Tralee, Co. Kerry, Ireland')).toBeInTheDocument()
  })

  it('returns through signup and saves the opportunity without a prior history marker', async () => {
    mockServer()
    window.history.replaceState(null, '', '/signup?returnTo=%2Fopportunities%2F20&save=1')
    render(<App />)
    const user = userEvent.setup()
    await user.type(await screen.findByRole('textbox', { name: 'Email address' }), account.email)
    await user.type(screen.getByLabelText('Password', { exact: true }), 'a-long-test-password-123')
    await user.type(screen.getByLabelText('Confirm password'), 'a-long-test-password-123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(window.location.pathname).toBe('/opportunities/20'))
    expect(await screen.findByRole('button', { name: 'Remove saved opportunity' })).toBeInTheDocument()
  })

  it('rejects an external return destination and never sends a save', async () => {
    const server = mockServer()
    window.history.replaceState(null, '', '/signup?returnTo=https%3A%2F%2Fevil.example&save=1')
    render(<App />)
    const user = userEvent.setup()
    await user.type(await screen.findByRole('textbox', { name: 'Email address' }), account.email)
    await user.type(screen.getByLabelText('Password', { exact: true }), 'a-long-test-password-123')
    await user.type(screen.getByLabelText('Confirm password'), 'a-long-test-password-123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(server.fetchMock.mock.calls.some(([url]) =>
      url === '/api/v1/saved-opportunities')).toBe(false)
  })

  it('offers retry on lookup and mutation errors', async () => {
    const server = mockServer(account)
    server.setListStatus(500)
    window.history.replaceState(null, '', '/opportunities/20')
    render(<App />)
    const user = userEvent.setup()
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not check whether this opportunity is saved.')
    server.setListStatus(200)
    await user.click(screen.getByRole('button', { name: 'Retry saved status' }))
    server.setSaveStatus(500)
    await user.click(await screen.findByRole('button', { name: 'Save opportunity' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not save this opportunity.')
    server.setSaveStatus(201)
    await user.click(screen.getByRole('button', { name: 'Save opportunity' }))
    expect(await screen.findByRole('button', { name: 'Remove saved opportunity' })).toBeInTheDocument()

  })

  it('updates account state when saved-status lookup returns 401', async () => {
    const server = mockServer(account)
    server.setListStatus(401)
    window.history.replaceState(null, '', '/opportunities/20')
    render(<App />)
    expect(await screen.findByText('Your session expired. Log in to save this opportunity.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign up' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save opportunity' })).toBeInTheDocument()
  })
})
