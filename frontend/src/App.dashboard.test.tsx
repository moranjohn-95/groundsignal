import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

function savedOpportunityPaths() {
  return screen.getAllByRole('link', { name: 'View opportunity' })
    .map((link) => link.getAttribute('href'))
}

function summaryCard(label: string) {
  const overview = screen.getByRole('region', { name: 'Dashboard overview' })
  return within(overview).getByText(label).parentElement as HTMLElement
}

function mobileNavigation() {
  return document.getElementById('mobile-account-navigation') as HTMLElement
}

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response
}

function server(options: { authenticated?: boolean; saves?: Array<{ id: number }>; listStatus?: number; deleteStatus?: number } = {}) {
  let loggedIn = options.authenticated ?? true
  let saves = options.saves ?? [saved]
  const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (url === '/api/v1/auth/me') return Promise.resolve(response(loggedIn ? account : null, loggedIn ? 200 : 401))
    if (url === '/api/v1/auth/login') { loggedIn = true; return Promise.resolve(response(account)) }
    if (url === '/api/v1/auth/logout') { loggedIn = false; return Promise.resolve(response(null, 204)) }
    if (url.startsWith('/api/v1/saved-opportunities?')) return Promise.resolve(response({ items: saves, total: saves.length }, options.listStatus ?? 200))
    if (url === '/api/v1/saved-opportunities/9' && init?.method === 'DELETE') {
      if (!options.deleteStatus || options.deleteStatus === 204) saves = saves.filter((item) => item.id !== 9)
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
    vi.useRealTimers()
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
    const title = await screen.findByRole('heading', { name: 'Install rooftop solar panels' })
    const card = title.closest('article')
    expect(card).toHaveClass('opportunity-card--high')
    expect(card).toHaveTextContent('Score')
    expect(card).toHaveTextContent('80')
    expect(card).toHaveTextContent('Energy')
    expect(card).toHaveTextContent('20 September 2026')
    expect(card).toHaveTextContent('42 Main Street, Dublin')
    expect(card).toHaveTextContent('No specific electrical work')
    expect(card).toHaveTextContent('Saved 30 September 2026')
    expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Opportunities' })).toHaveAttribute('href', '/')
    expect(screen.getAllByText('customer@example.com')[0]).toHaveClass('account-nav__email')
    const avatar = document.querySelector('.account-nav__avatar')
    expect(avatar).toHaveTextContent('C')
    expect(avatar).toHaveAttribute('aria-hidden', 'true')
    await userEvent.setup().click(screen.getByRole('link', { name: 'View opportunity' }))
    expect(window.location.pathname).toBe('/opportunities/42')
    expect(await screen.findByRole('link', { name: 'Back to dashboard' })).toBeInTheDocument()
    act(() => window.history.back())
    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
    expect(screen.getByRole('heading', { name: 'Install rooftop solar panels' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/saved-opportunities?'))).toHaveLength(2)
  })

  it('uses the public opportunity grid for saved cards', async () => {
    const saves = [
      saved,
      { ...saved, id: 10, opportunity: { ...opportunity, id: 43, application_number: 'PL-43' } },
      { ...saved, id: 11, opportunity: { ...opportunity, id: 44, application_number: 'PL-44' } },
    ]
    server({ saves })
    render(<App />)

    await screen.findAllByRole('heading', { name: 'Install rooftop solar panels' })
    const savedList = document.querySelector('ul.dashboard__list')
    expect(savedList).toHaveClass('opportunity-list')
    expect(within(savedList as HTMLElement).getAllByRole('article')).toHaveLength(3)
    expect(within(savedList as HTMLElement).getAllByRole('link', { name: 'View opportunity' })).toHaveLength(3)
    const removeButtons = within(savedList as HTMLElement).getAllByRole('button', { name: 'Remove saved opportunity' })
    expect(removeButtons).toHaveLength(3)
    expect(removeButtons[0]).toHaveAttribute('aria-pressed', 'true')
    expect(removeButtons[0]).toHaveClass('opportunity-card__save-button--saved')
  })

  it('shows dashboard navigation for signed-in public visitors and a login link for signed-out visitors', async () => {
    window.history.replaceState(null, '', '/')
    server()
    const first = render(<App />)

    const dashboardLink = await screen.findByRole('link', { name: 'Dashboard' })
    expect(dashboardLink).toHaveAttribute('href', '/dashboard')
    expect(screen.queryByRole('link', { name: 'Opportunities' })).not.toBeInTheDocument()
    await userEvent.setup().click(dashboardLink)
    expect(window.location.pathname).toBe('/dashboard')

    first.unmount()
    window.history.replaceState(null, '', '/')
    server({ authenticated: false })
    render(<App />)
    expect(await screen.findByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
  })

  it('opens the authenticated mobile menu with contextual navigation and closes it after navigation', async () => {
    server()
    render(<App />)
    const user = userEvent.setup()
    const menuButton = await screen.findByRole('button', { name: 'Open navigation menu' })
    expect(menuButton).toHaveAttribute('aria-controls', 'mobile-account-navigation')
    expect(menuButton).toHaveAttribute('aria-expanded', 'false')
    expect(mobileNavigation()).toHaveAttribute('hidden')

    await user.click(menuButton)
    expect(menuButton).toHaveAccessibleName('Close navigation menu')
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
    expect(within(mobileNavigation()).getByText('customer@example.com')).toBeInTheDocument()
    const opportunitiesLink = within(mobileNavigation()).getByRole('link', { name: 'Opportunities' })
    expect(opportunitiesLink).toHaveAttribute('href', '/')
    expect(within(mobileNavigation()).getByRole('button', { name: 'Log out' })).toBeInTheDocument()

    await user.click(opportunitiesLink)
    expect(window.location.pathname).toBe('/')
    expect(menuButton).toHaveAccessibleName('Open navigation menu')
    expect(mobileNavigation()).toHaveAttribute('hidden')

    await user.click(menuButton)
    expect(within(mobileNavigation()).getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/dashboard')
  })

  it('shows login when signed out and closes the mobile menu on logout', async () => {
    server()
    const first = render(<App />)
    const user = userEvent.setup()
    const menuButton = await screen.findByRole('button', { name: 'Open navigation menu' })
    await user.click(menuButton)
    await user.click(within(mobileNavigation()).getByRole('button', { name: 'Log out' }))
    await screen.findByRole('link', { name: 'Log in' })
    expect(mobileNavigation()).toHaveAttribute('hidden')

    first.unmount()
    window.history.replaceState(null, '', '/')
    server({ authenticated: false })
    render(<App />)
    const signedOutMenuButton = await screen.findByRole('button', { name: 'Open navigation menu' })
    await user.click(signedOutMenuButton)
    expect(within(mobileNavigation()).getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
  })

  it('logs out through the separate navigation action', async () => {
    server()
    render(<App />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Log out' }))
    await screen.findByRole('link', { name: 'Log in' })
    expect(window.location.pathname).toBe('/')
    expect(screen.queryByText('customer@example.com')).not.toBeInTheDocument()
  })

  it('shows calculated saved-opportunity overview values', async () => {
    const confirmedSave = {
      ...saved,
      id: 10,
      opportunity: {
        ...opportunity,
        id: 43,
        application_number: 'PL-43',
        opportunity_score: 92,
        electrical_work_brief: {
          evidence_level: 'direct',
          summary: 'Electrical work evidenced: solar infrastructure.',
          signals: [],
        },
      },
    }
    server({ saves: [saved, confirmedSave] })
    render(<App />)

    await screen.findByRole('region', { name: 'Dashboard overview' })
    const overview = screen.getByRole('region', { name: 'Dashboard overview' })
    expect(overview.querySelectorAll('.dashboard__summary-icon[aria-hidden="true"]')).toHaveLength(3)
    expect(overview.querySelectorAll('.dashboard__summary-icon svg[aria-hidden]')).toHaveLength(0)
    expect(summaryCard('Saved opportunities')).toHaveTextContent('2')
    expect(summaryCard('Best opportunity')).toHaveTextContent('92')
    expect(summaryCard('Confirmed electrical signals')).toHaveTextContent('1')
  })

  it('shows empty overview values when there are no saved opportunities', async () => {
    server({ saves: [] })
    render(<App />)

    await screen.findByRole('heading', { name: 'No saved opportunities yet' })
    expect(summaryCard('Saved opportunities')).toHaveTextContent('0')
    expect(summaryCard('Best opportunity')).toHaveTextContent('—')
    expect(summaryCard('Confirmed electrical signals')).toHaveTextContent('0')
  })

  it('sorts saved opportunities locally and keeps missing values last', async () => {
    const saves = [
      saved,
      {
        ...saved,
        id: 10,
        saved_at: '2026-10-01T12:00:00Z',
        opportunity: {
          ...opportunity,
          id: 43,
          application_number: 'PL-43',
          opportunity_score: 95,
          received_date: null,
        },
      },
      {
        ...saved,
        id: 11,
        saved_at: '2026-09-25T12:00:00Z',
        opportunity: {
          ...opportunity,
          id: 44,
          application_number: 'PL-44',
          opportunity_score: undefined as unknown as number,
          received_date: '2026-09-25',
        },
      },
    ]
    server({ saves })
    render(<App />)

    const sortControl = await screen.findByRole('combobox', { name: 'Sort' })
    expect(sortControl).toHaveValue('recently-saved')
    expect(screen.getByRole('option', { name: 'Recently saved' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Best opportunity' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Newest received' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Oldest received' })).toBeInTheDocument()
    expect(savedOpportunityPaths()).toEqual(['/opportunities/43', '/opportunities/42', '/opportunities/44'])

    const user = userEvent.setup()
    await user.selectOptions(sortControl, 'best-opportunity')
    expect(savedOpportunityPaths()).toEqual(['/opportunities/43', '/opportunities/42', '/opportunities/44'])

    await user.selectOptions(sortControl, 'newest-received')
    expect(savedOpportunityPaths()).toEqual(['/opportunities/44', '/opportunities/42', '/opportunities/43'])

    await user.selectOptions(sortControl, 'oldest-received')
    expect(savedOpportunityPaths()).toEqual(['/opportunities/42', '/opportunities/44', '/opportunities/43'])
  })

  it('removes a save with the shared bookmark and clears its floating toast', async () => {
    const secondSave = {
      ...saved,
      id: 10,
      opportunity: {
        ...opportunity,
        id: 43,
        application_number: 'PL-43',
        opportunity_score: 90,
        electrical_work_brief: {
          evidence_level: 'direct',
          summary: 'Electrical work evidenced: solar infrastructure.',
          signals: [],
        },
      },
    }
    const fetchMock = server({ saves: [saved, secondSave] })
    render(<App />)
    const [removeButton] = await screen.findAllByRole('button', { name: 'Remove saved opportunity' })
    vi.useFakeTimers()
    fireEvent.click(removeButton)
    await act(async () => { await Promise.resolve() })
    const removalStatus = screen.getByText('Removed from saved opportunities')
    expect(removalStatus).toHaveAttribute('aria-live', 'polite')
    expect(removalStatus).toHaveClass('opportunity-card__save-status')
    expect(screen.getByRole('heading', { name: 'Saved opportunities' })).toBeInTheDocument()
    expect(savedOpportunityPaths()).toEqual(['/opportunities/43'])
    expect(summaryCard('Saved opportunities')).toHaveTextContent('1')
    expect(summaryCard('Best opportunity')).toHaveTextContent('90')
    expect(summaryCard('Confirmed electrical signals')).toHaveTextContent('1')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/saved-opportunities/9', expect.objectContaining({ method: 'DELETE' }))
    act(() => vi.advanceTimersByTime(2000))
    expect(screen.queryByText('Removed from saved opportunities')).not.toBeInTheDocument()
  })

  it('shows load and removal errors with recovery actions', async () => {
    server({ listStatus: 500 })
    const first = render(<App />)
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
    first.unmount()
    server({ deleteStatus: 500 })
    render(<App />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Remove saved opportunity' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not remove this saved opportunity.')
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
