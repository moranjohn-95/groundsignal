import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const account = { id: 7, email: 'customer@example.com', is_active: true, created_at: '2026-09-29T12:00:00Z' }
const opportunity = {
  id: 42, application_number: 'PL-42', planning_authority: 'Dublin City Council',
  description: 'Install rooftop solar panels', address: '42 Main Street, Dublin',
  category: 'energy', opportunity_level: 'high', opportunity_score: 80,
  received_date: '2026-09-20',
}
const saved = { id: 9, saved_at: '2026-09-30T12:00:00Z', opportunity }

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response
}

function server(options: { authenticated?: boolean; saves?: typeof saved[]; listStatus?: number; deleteStatus?: number } = {}) {
  let loggedIn = options.authenticated ?? true
  let saves = options.saves ?? [saved]
  const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (url === '/api/v1/auth/me') return Promise.resolve(response(loggedIn ? account : null, loggedIn ? 200 : 401))
    if (url === '/api/v1/auth/login') { loggedIn = true; return Promise.resolve(response(account)) }
    if (url.startsWith('/api/v1/saved-opportunities?')) return Promise.resolve(response({ items: saves, total: saves.length }, options.listStatus ?? 200))
    if (url === '/api/v1/saved-opportunities/9' && init?.method === 'DELETE') {
      if (!options.deleteStatus || options.deleteStatus === 204) saves = []
      return Promise.resolve(response(null, options.deleteStatus ?? 204))
    }
    if (url === '/api/v1/planning-applications/42') return Promise.resolve(response(null, 404))
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('customer dashboard', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/dashboard')
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  })
  afterEach(() => {
    window.history.replaceState(null, '', '/')
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('sends a visitor to login and returns to dashboard after login', async () => {
    server({ authenticated: false, saves: [] })
    render(<App />)
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(window.location.search).toBe('?returnTo=%2Fdashboard')
    const user = userEvent.setup()
    await user.type(screen.getByRole('textbox', { name: 'Email address' }), account.email)
    await user.type(screen.getByLabelText('Password', { exact: true }), 'test-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'No saved opportunities yet' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/dashboard')
    expect(screen.getByRole('link', { name: 'Search opportunities' })).toHaveAttribute('href', '/')
  })

  it('lists all saves, opens detail, and returns to the dashboard', async () => {
    const fetchMock = server()
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Install rooftop solar panels' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
    await userEvent.setup().click(screen.getByRole('link', { name: 'View opportunity' }))
    expect(window.location.pathname).toBe('/opportunities/42')
    expect(await screen.findByRole('link', { name: 'Back to dashboard' })).toBeInTheDocument()
    act(() => window.history.back())
    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
    expect(screen.getByRole('heading', { name: 'Install rooftop solar panels' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/saved-opportunities?'))).toHaveLength(2)
  })

  it('removes a save and shows confirmation', async () => {
    const fetchMock = server()
    render(<App />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Remove save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Opportunity removed from your saves.')
    expect(screen.getByRole('heading', { name: 'No saved opportunities yet' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/saved-opportunities/9', expect.objectContaining({ method: 'DELETE' }))
  })

  it('shows load and removal errors with recovery actions', async () => {
    server({ listStatus: 500 })
    const first = render(<App />)
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
    first.unmount()
    server({ deleteStatus: 500 })
    render(<App />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Remove save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Could not remove this save.')
    expect(screen.getByRole('heading', { name: 'Install rooftop solar panels' })).toBeInTheDocument()
  })

  it('returns an expired dashboard session to login', async () => {
    server({ listStatus: 401 })
    render(<App />)
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(window.location.search).toBe('?returnTo=%2Fdashboard')
    expect(screen.getByRole('alert')).toHaveTextContent('Your session expired.')
  })
})
