import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const account = {
  id: 7,
  email: 'customer@example.com',
  is_active: true,
  created_at: '2026-09-29T12:00:00Z',
}

const password = 'a-long-test-password-123'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function mockAccountServer(initialUser: typeof account | null = null) {
  let currentUser = initialUser
  let signupStatus = 201
  let loginStatus = 200
  let meStatus: number | null = null
  let logoutStatus = 204
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url === '/api/v1/auth/me') {
      return Promise.resolve(
        meStatus !== null
          ? jsonResponse(null, meStatus)
          : currentUser === null
            ? jsonResponse(null, 401)
            : jsonResponse(currentUser),
      )
    }
    if (url === '/api/v1/auth/signup') {
      if (signupStatus === 201) currentUser = account
      return Promise.resolve(jsonResponse(signupStatus === 201 ? account : null, signupStatus))
    }
    if (url === '/api/v1/auth/login') {
      if (loginStatus === 200) currentUser = account
      return Promise.resolve(jsonResponse(loginStatus === 200 ? account : null, loginStatus))
    }
    if (url === '/api/v1/auth/logout') {
      if (logoutStatus === 204) currentUser = null
      return Promise.resolve(jsonResponse(null, logoutStatus))
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return {
    fetchMock,
    setSignupStatus: (status: number) => { signupStatus = status },
    setLoginStatus: (status: number) => { loginStatus = status },
    setMeStatus: (status: number | null) => { meStatus = status },
    setLogoutStatus: (status: number) => { logoutStatus = status },
  }
}

async function fillCredentials(user: ReturnType<typeof userEvent.setup>, signup: boolean) {
  await user.type(await screen.findByRole('textbox', { name: 'Email address' }), account.email)
  await user.type(screen.getByLabelText('Password', { exact: true }), password)
  if (signup) {
    await user.type(screen.getByLabelText('Confirm password'), password)
  }
}

describe('customer account pages', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/')
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  })

  afterEach(() => {
    window.history.replaceState(null, '', '/')
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('signs up, omits confirmation from the API, and returns to public opportunities', async () => {
    const { fetchMock } = mockAccountServer()
    render(<App />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('link', { name: 'Sign up' }))
    expect(window.location.pathname).toBe('/signup')
    expect(screen.getByRole('heading', { name: 'Create your account' })).toHaveFocus()
    expect(screen.queryByRole('link', { name: /forgot password/i })).not.toBeInTheDocument()

    await user.type(screen.getByRole('textbox', { name: 'Email address' }), account.email)
    await user.type(screen.getByLabelText('Password', { exact: true }), password)
    await user.type(screen.getByLabelText('Confirm password'), 'different-password')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.')
    expect(fetchMock).not.toHaveBeenCalledWith('/api/v1/auth/signup', expect.anything())

    await user.clear(screen.getByLabelText('Confirm password'))
    await user.type(screen.getByLabelText('Confirm password'), password)
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(screen.getByText(`Signed in as ${account.email}`)).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Location' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Sign up' })).not.toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url]) => url === '/api/v1/auth/signup')
    expect(call?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    })
    expect(JSON.parse(call?.[1].body as string)).toEqual({
      email: account.email,
      password,
    })
  })

  it('links signup and login through browser history and supports public return', async () => {
    mockAccountServer()
    render(<App />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('link', { name: 'Log in' }))
    expect(window.location.pathname).toBe('/login')
    expect(screen.getByRole('heading', { name: 'Log in' })).toHaveFocus()
    await user.click(screen.getByRole('link', { name: 'Create an account' }))
    expect(window.location.pathname).toBe('/signup')
    act(() => window.history.back())
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    await user.click(screen.getByRole('link', { name: 'Back to opportunities' }))
    expect(window.location.pathname).toBe('/')
    expect(screen.getByRole('textbox', { name: 'Location' })).toBeInTheDocument()
  })

  it('shows login errors and then logs in with the real API contract', async () => {
    const server = mockAccountServer()
    server.setLoginStatus(401)
    window.history.replaceState(null, '', '/login')
    render(<App />)
    const user = userEvent.setup()
    await fillCredentials(user, false)
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.')
    expect(window.location.pathname).toBe('/login')
    server.setLoginStatus(200)
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
  })

  it.each([
    [409, 'An account with this email already exists. Log in instead.'],
    [422, 'Check your email and password, then try again.'],
    [429, 'Too many attempts. Please wait and try again.'],
    [500, 'The account service is unavailable right now. Please try again.'],
  ])('shows signup status %i clearly', async (status, message) => {
    const server = mockAccountServer()
    server.setSignupStatus(status)
    window.history.replaceState(null, '', '/signup')
    render(<App />)
    const user = userEvent.setup()
    await fillCredentials(user, true)
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(window.location.pathname).toBe('/signup')
  })

  it('restores the logged-in header from /me on refresh', async () => {
    const { fetchMock } = mockAccountServer(account)
    const first = render(<App />)
    expect(await screen.findByText(`Signed in as ${account.email}`)).toBeInTheDocument()
    first.unmount()
    render(<App />)
    expect(await screen.findByText(`Signed in as ${account.email}`)).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/v1/auth/me')).toHaveLength(2)
    expect(fetchMock.mock.calls.find(([url]) => url === '/api/v1/auth/me')?.[1]).toEqual({
      credentials: 'same-origin',
    })
  })

  it.each(['/signup', '/login'])(
    'redirects a signed-in direct visit to %s without showing the form and preserves Back',
    async (pathname) => {
      let resolveSession!: (response: Response) => void
      const sessionResponse = new Promise<Response>((resolve) => {
        resolveSession = resolve
      })
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/v1/auth/me') return sessionResponse
        throw new Error(`Unexpected request: ${url}`)
      })
      vi.stubGlobal('fetch', fetchMock)
      window.history.replaceState({ previousPage: true }, '', '/privacy')
      window.history.pushState(null, '', pathname)

      render(<App />)
      expect(window.location.pathname).toBe(pathname)
      expect(screen.queryByRole('textbox', { name: 'Email address' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Create your account' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Log in' })).not.toBeInTheDocument()

      await act(async () => resolveSession(jsonResponse(account)))
      await waitFor(() => expect(window.location.pathname).toBe('/'))
      expect(screen.getByText(`Signed in as ${account.email}`)).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: 'Location' })).toBeInTheDocument()
      expect(screen.queryByRole('textbox', { name: 'Email address' })).not.toBeInTheDocument()
      expect(fetchMock).toHaveBeenCalledTimes(1)

      act(() => window.history.back())
      await waitFor(() => expect(window.location.pathname).toBe('/privacy'))
      expect(window.history.state).toEqual({ previousPage: true })
      expect(screen.getByRole('heading', { name: 'Privacy Policy' })).toBeInTheDocument()
    },
  )

  it('logs out, clears the header state, and keeps public pages accessible', async () => {
    const { fetchMock } = mockAccountServer(account)
    render(<App />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('link', { name: 'Log in' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(screen.getByRole('textbox', { name: 'Location' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.find(([url]) => url === '/api/v1/auth/logout')?.[1]).toEqual({
      method: 'POST',
      credentials: 'same-origin',
    })
  })

  it('keeps the signed-in state and gives a retry message if logout fails', async () => {
    const server = mockAccountServer(account)
    server.setLogoutStatus(500)
    render(<App />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not log out. Please try again.')
    expect(screen.getByText(`Signed in as ${account.email}`)).toBeInTheDocument()
  })

  it('keeps public opportunities available when the session check fails', async () => {
    const server = mockAccountServer()
    server.setMeStatus(500)
    render(<App />)
    expect(await screen.findByRole('button', { name: 'Retry account check' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Location' })).toBeInTheDocument()
    server.setMeStatus(null)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Retry account check' }))
    expect(await screen.findByRole('link', { name: 'Sign up' })).toBeInTheDocument()
  })
})
