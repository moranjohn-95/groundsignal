import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type MouseEvent,
} from 'react'

import type { Opportunity } from './api/opportunities'
import { saveOpportunity, SavedOpportunityApiError } from './api/savedOpportunities'
import {
  fetchCurrentUser,
  logoutAccount,
  type CurrentUser,
} from './api/auth'
import AccountPage from './features/account/AccountPage'
import DashboardPage from './features/dashboard/DashboardPage'
import { readSaveReturn, saveReturnSearch } from './features/account/saveReturn'
import {
  DataSourcesPage,
  PrivacyPage,
  TermsPage,
} from './features/LegalPages'
import NotFoundPage from './features/NotFoundPage'
import OpportunityDetailPage from './features/opportunities/OpportunityDetailPage'
import type { SaveReturnOutcome } from './features/opportunities/SaveOpportunityControl'
import OpportunitiesPage from './features/opportunities/OpportunitiesPage'

type LegalPage = 'data-sources' | 'privacy' | 'terms'

type AppRoute =
  | { page: 'opportunities' }
  | { page: 'signup' | 'login' }
  | { page: 'dashboard' }
  | {
      page: 'opportunity-detail'
      opportunityId: number
      distanceKm?: number
      preservesOpportunities: boolean
      preservesDashboard: boolean
    }
  | { page: LegalPage }
  | { page: 'not-found' }

interface OpportunityHistoryState {
  distanceKm?: unknown
  preservesOpportunities?: unknown
  preservesDashboard?: unknown
  saveReturnDepth?: unknown
  saveReturnOpportunityId?: unknown
}

type SessionState =
  | { status: 'checking' | 'anonymous' | 'error' }
  | { status: 'authenticated'; user: CurrentUser }

function routeFromLocation(
  pathname: string,
  historyState: OpportunityHistoryState | null,
): AppRoute {
  if (pathname === '/') {
    return { page: 'opportunities' }
  }

  if (pathname === '/dashboard') return { page: 'dashboard' }

  if (pathname === '/signup' || pathname === '/login') {
    return { page: pathname.slice(1) as 'signup' | 'login' }
  }

  const legalPages: Record<string, LegalPage> = {
    '/data-sources': 'data-sources',
    '/privacy': 'privacy',
    '/terms': 'terms',
  }
  const legalPage = legalPages[pathname]
  if (legalPage !== undefined) {
    return { page: legalPage }
  }

  const detailMatch = /^\/opportunities\/(\d+)$/.exec(pathname)
  if (detailMatch === null) {
    return { page: 'not-found' }
  }

  const opportunityId = Number(detailMatch[1])
  if (!Number.isSafeInteger(opportunityId) || opportunityId <= 0) {
    return { page: 'not-found' }
  }

  const candidateDistance = historyState?.distanceKm
  const distanceKm =
    typeof candidateDistance === 'number' &&
    Number.isFinite(candidateDistance) &&
    candidateDistance >= 0
      ? candidateDistance
      : undefined

  return {
    page: 'opportunity-detail',
    opportunityId,
    distanceKm,
    preservesOpportunities: historyState?.preservesOpportunities === true,
    preservesDashboard: historyState?.preservesDashboard === true,
  }
}

function routeForSession(
  pathname: string,
  historyState: OpportunityHistoryState | null,
  isAuthenticated: boolean,
): AppRoute {
  if (!isAuthenticated && pathname === '/dashboard') {
    window.history.replaceState(null, '', '/login?returnTo=%2Fdashboard')
    return { page: 'login' }
  }
  if (isAuthenticated && (pathname === '/signup' || pathname === '/login')) {
    const destination = new URLSearchParams(window.location.search).get('returnTo') === '/dashboard' ? '/dashboard' : '/'
    window.history.replaceState(null, '', destination)
    return routeFromLocation(destination, null)
  }
  return routeFromLocation(pathname, historyState)
}

function saveReturnDepth(
  historyState: OpportunityHistoryState | null,
  opportunityId: number,
): number | null {
  const depth = historyState?.saveReturnDepth
  return historyState?.saveReturnOpportunityId === opportunityId &&
    typeof depth === 'number' &&
    Number.isSafeInteger(depth) &&
    depth > 0 &&
    depth < window.history.length
    ? depth
    : null
}

function initialsFor(email: string) {
  const localPart = email.split('@', 1)[0] ?? ''
  const words = localPart.match(/[A-Za-z0-9]+/g) ?? []
  const initials = words.slice(0, 2).map((word) => word[0]).join('')
  return initials === '' ? '?' : initials.toUpperCase()
}

function App() {
  const [searchVersion, setSearchVersion] = useState(0)
  const [sessionState, setSessionState] = useState<SessionState>({ status: 'checking' })
  const [sessionCheckAttempt, setSessionCheckAttempt] = useState(0)
  const [logoutPending, setLogoutPending] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [accountError, setAccountError] = useState<string | null>(null)
  const [postAuthSaveOutcome, setPostAuthSaveOutcome] = useState<SaveReturnOutcome | null>(null)
  const authVersion = useRef(0)
  const opportunitiesScrollPosition = useRef<number | null>(null)
  const opportunityFocusTarget = useRef<number | null>(null)
  const [route, setRoute] = useState(() =>
    routeFromLocation(window.location.pathname, window.history.state),
  )

  useEffect(() => {
    let cancelled = false
    const version = authVersion.current
    void fetchCurrentUser()
      .then((user) => {
        if (cancelled || version !== authVersion.current) return
        if ((user !== null && (window.location.pathname === '/signup' || window.location.pathname === '/login')) ||
            (user === null && window.location.pathname === '/dashboard')) {
          setRoute(routeForSession(window.location.pathname, window.history.state, user !== null))
        }
        setSessionState(user ? { status: 'authenticated', user } : { status: 'anonymous' })
      })
      .catch(() => {
        if (!cancelled && version === authVersion.current) {
          setSessionState({ status: 'error' })
        }
      })
    return () => {
      cancelled = true
    }
  }, [sessionCheckAttempt])

  useEffect(() => {
    function handleHistoryChange(event: PopStateEvent) {
      const nextRoute = routeForSession(
        window.location.pathname, event.state, sessionState.status === 'authenticated',
      )
      if (
        nextRoute.page !== 'opportunity-detail' ||
        nextRoute.opportunityId !== postAuthSaveOutcome?.opportunityId
      ) {
        setPostAuthSaveOutcome(null)
      }
      setRoute(nextRoute)
    }

    window.addEventListener('popstate', handleHistoryChange)
    return () => window.removeEventListener('popstate', handleHistoryChange)
  }, [postAuthSaveOutcome?.opportunityId, sessionState.status])

  const accountRoute = route.page === 'signup' || route.page === 'login' ? route.page : null
  const isAccountRoute = accountRoute !== null
  const accountSaveReturn = isAccountRoute ? readSaveReturn(window.location.search) : null
  const accountReturnQuery = accountSaveReturn
    ? saveReturnSearch(accountSaveReturn.opportunityId)
    : isAccountRoute && new URLSearchParams(window.location.search).get('returnTo') === '/dashboard'
      ? '?returnTo=%2Fdashboard'
      : ''

  useLayoutEffect(() => {
    // Restore list context when a visitor returns from an opportunity detail page.
    if (
      route.page === 'opportunities' &&
      opportunitiesScrollPosition.current !== null
    ) {
      window.scrollTo(0, opportunitiesScrollPosition.current)
    }

    if (
      route.page === 'opportunities' &&
      opportunityFocusTarget.current !== null
    ) {
      const opportunityAction = document.getElementById(
        `opportunity-${opportunityFocusTarget.current}-action`,
      )
      const fallbackHeading = document.getElementById(
        'top-opportunities-heading',
      )
      const focusTarget = opportunityAction ?? fallbackHeading
      focusTarget?.focus({ preventScroll: true })
    }
  }, [route.page])

  function navigateTo(destination: string, historyState: OpportunityHistoryState | null = null) {
    const url = new URL(destination, window.location.origin)
    if (url.origin !== window.location.origin) return
    window.history.pushState(historyState, '', url.pathname + url.search)
    setRoute(routeForSession(url.pathname, historyState, sessionState.status === 'authenticated'))
    if (url.pathname !== `/opportunities/${postAuthSaveOutcome?.opportunityId}`) {
      setPostAuthSaveOutcome(null)
    }
  }

  async function handleAuthenticated(user: CurrentUser) {
    const saveReturn = readSaveReturn(window.location.search)
    const depth = saveReturn
      ? saveReturnDepth(window.history.state, saveReturn.opportunityId)
      : null
    authVersion.current += 1
    setAccountError(null)
    if (saveReturn) {
      let sessionExpired = false
      try {
        const saved = await saveOpportunity(saveReturn.opportunityId)
        setPostAuthSaveOutcome({
          opportunityId: saveReturn.opportunityId,
          status: 'saved',
          saveId: saved.id,
        })
      } catch (error: unknown) {
        if (error instanceof SavedOpportunityApiError && error.status === 401) {
          authVersion.current += 1
          sessionExpired = true
          setAccountError('Your session expired. Log in to save this opportunity.')
        }
        setPostAuthSaveOutcome({
          opportunityId: saveReturn.opportunityId,
          status: 'error',
          message:
            error instanceof SavedOpportunityApiError && error.status === 404
              ? 'This opportunity is no longer available to save.'
              : 'Could not save this opportunity. Try again below.',
        })
      }
      setSessionState(sessionExpired ? { status: 'anonymous' } : { status: 'authenticated', user })
      if (window.location.pathname !== '/signup' && window.location.pathname !== '/login') return
      if (depth !== null) {
        window.history.go(-depth)
      } else {
        window.history.replaceState(null, '', saveReturn.path)
        setRoute(routeFromLocation(saveReturn.path, null))
      }
      return
    }
    setSessionState({ status: 'authenticated', user })
    const destination = new URLSearchParams(window.location.search).get('returnTo') === '/dashboard' ? '/dashboard' : '/'
    window.history.pushState(null, '', destination)
    setRoute(routeFromLocation(destination, null))
  }

  const handleSaveSessionExpired = useCallback(() => {
    authVersion.current += 1
    setSessionState({ status: 'anonymous' })
    setAccountError('Your session expired. Log in to save this opportunity.')
  }, [])

  const handleDashboardSessionExpired = useCallback(() => {
    authVersion.current += 1
    setSessionState({ status: 'anonymous' })
    setAccountError('Your session expired. Log in to view your dashboard.')
    window.history.replaceState(null, '', '/login?returnTo=%2Fdashboard')
    setRoute({ page: 'login' })
  }, [])

  function requestSaveAuthentication(opportunityId: number) {
    setPostAuthSaveOutcome(null)
    navigateTo(`/signup${saveReturnSearch(opportunityId)}`, {
      saveReturnDepth: 1,
      saveReturnOpportunityId: opportunityId,
    })
  }

  async function handleLogout() {
    if (logoutPending) return
    setLogoutPending(true)
    setAccountError(null)
    try {
      await logoutAccount()
      authVersion.current += 1
      setSessionState({ status: 'anonymous' })
      navigateTo('/')
    } catch {
      setAccountError('Could not log out. Please try again.')
    } finally {
      setLogoutPending(false)
    }
  }

  function retrySessionCheck() {
    setSessionState({ status: 'checking' })
    setSessionCheckAttempt((attempt) => attempt + 1)
  }

  function showOpportunities() {
    navigateTo('/')
  }

  function showOpportunity(opportunity: Opportunity) {
    opportunitiesScrollPosition.current = window.scrollY
    opportunityFocusTarget.current = opportunity.id
    const historyState: OpportunityHistoryState = {
      distanceKm: opportunity.distance_km,
      preservesOpportunities: true,
      preservesDashboard: false,
    }
    window.history.pushState(
      historyState,
      '',
      `/opportunities/${opportunity.id}`,
    )
    setRoute({
      page: 'opportunity-detail',
      opportunityId: opportunity.id,
      distanceKm: opportunity.distance_km,
      preservesOpportunities: true,
      preservesDashboard: false,
    })
  }

  function showSavedOpportunity(opportunityId: number) {
    navigateTo(`/opportunities/${opportunityId}`, { preservesDashboard: true })
  }

  function returnToOpportunities() {
    if (
      route.page === 'opportunity-detail' &&
      (route.preservesOpportunities || route.preservesDashboard)
    ) {
      // Return through browser history only when the current list is still there.
      window.history.back()
      return
    }

    showOpportunities()
  }

  function handleBackToOpportunities(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return
    }

    event.preventDefault()
    showOpportunities()
  }

  function handleInternalNavigation(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return
    }

    const destination = new URL(event.currentTarget.href)
    if (destination.origin !== window.location.origin) {
      return
    }

    event.preventDefault()
    const saveReturn = accountRoute === null ? null : readSaveReturn(window.location.search)
    if (saveReturn && destination.pathname === saveReturn.path) {
      const depth = saveReturnDepth(window.history.state, saveReturn.opportunityId)
      setPostAuthSaveOutcome(null)
      if (depth !== null) {
        window.history.go(-depth)
      } else {
        window.history.replaceState(null, '', saveReturn.path)
        setRoute(routeFromLocation(saveReturn.path, null))
      }
      return
    }
    if (saveReturn && (destination.pathname === '/signup' || destination.pathname === '/login')) {
      const nextReturn = readSaveReturn(destination.search)
      const depth = saveReturnDepth(window.history.state, saveReturn.opportunityId)
      if (nextReturn?.opportunityId === saveReturn.opportunityId && depth !== null) {
        navigateTo(destination.pathname + destination.search, {
          saveReturnDepth: depth + 1,
          saveReturnOpportunityId: saveReturn.opportunityId,
        })
        return
      }
    }
    if (destination.pathname === '/') {
      // Remount the search and its filters, including when already at home.
      setSearchVersion((version) => version + 1)
      opportunitiesScrollPosition.current = null
      opportunityFocusTarget.current = null
      window.scrollTo(0, 0)
    }
    navigateTo(destination.pathname + destination.search)
  }

  function handleMobileNavigation(event: MouseEvent<HTMLAnchorElement>) {
    setMobileMenuOpen(false)
    handleInternalNavigation(event)
  }

  function handleMobileLogout() {
    setMobileMenuOpen(false)
    void handleLogout()
  }

  return (
    <>
      <header className="site-header">
        <div className="app-container site-header__inner">
          <h1 className="site-brand">
            <a href="/" onClick={handleInternalNavigation}>
              SiteForecaster
            </a>
          </h1>
          <nav className="account-nav account-nav--desktop" aria-label="Account">
            {sessionState.status === 'checking' && (
              <span className="account-nav__status">Checking account…</span>
            )}
            {sessionState.status === 'authenticated' ? (
              <>
                <span className="account-nav__identity">
                  <span className="account-nav__avatar" aria-hidden="true">
                    {initialsFor(sessionState.user.email)}
                  </span>
                  <span className="account-nav__email">{sessionState.user.email}</span>
                </span>
                <span className="account-nav__links">
                  {route.page === 'dashboard' ? (
                    <a href="/" onClick={handleInternalNavigation}>Opportunities</a>
                  ) : (
                    <a href="/dashboard" onClick={handleInternalNavigation}>Dashboard</a>
                  )}
                </span>
                <button type="button" onClick={() => void handleLogout()} disabled={logoutPending}>
                  {logoutPending ? 'Logging out…' : 'Log out'}
                </button>
              </>
            ) : sessionState.status !== 'checking' && (
              <>
                {sessionState.status === 'error' && (
                  <button type="button" onClick={retrySessionCheck}>Retry account check</button>
                )}
                <a href={`/login${accountReturnQuery}`} onClick={handleInternalNavigation}>Log in</a>
                <a className="account-nav__signup" href={`/signup${accountReturnQuery}`} onClick={handleInternalNavigation}>
                  Sign up
                </a>
              </>
            )}
          </nav>
          <button
            type="button"
            className="header-menu-toggle"
            aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-controls="mobile-account-navigation"
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen((open) => !open)}
          >
            <span aria-hidden="true" />
            <span aria-hidden="true" />
            <span aria-hidden="true" />
          </button>
          <nav
            id="mobile-account-navigation"
            className="account-nav account-nav--mobile"
            aria-label="Account navigation"
            hidden={!mobileMenuOpen}
          >
            {sessionState.status === 'checking' && (
              <span className="account-nav__status">Checking account…</span>
            )}
            {sessionState.status === 'authenticated' ? (
              <>
                <span className="account-nav__identity">
                  <span className="account-nav__avatar" aria-hidden="true">
                    {initialsFor(sessionState.user.email)}
                  </span>
                  <span className="account-nav__email">{sessionState.user.email}</span>
                </span>
                <span className="account-nav__links">
                  {route.page === 'dashboard' ? (
                    <a href="/" onClick={handleMobileNavigation}>Opportunities</a>
                  ) : (
                    <a href="/dashboard" onClick={handleMobileNavigation}>Dashboard</a>
                  )}
                </span>
                <button type="button" onClick={handleMobileLogout} disabled={logoutPending}>
                  {logoutPending ? 'Logging out…' : 'Log out'}
                </button>
              </>
            ) : sessionState.status !== 'checking' && (
              <a href={`/login${accountReturnQuery}`} onClick={handleMobileNavigation}>Log in</a>
            )}
          </nav>
        </div>
      </header>

      {accountError && <p className="account-alert" role="alert">{accountError}</p>}

      <main className="site-main">
        <div className="app-container">
          <div hidden={route.page !== 'opportunities' && !(isAccountRoute && sessionState.status === 'authenticated')}>
            <OpportunitiesPage
              key={searchVersion}
              onViewOpportunity={showOpportunity}
            />
          </div>

          {route.page === 'opportunity-detail' && (
            <OpportunityDetailPage
              key={route.opportunityId}
              opportunityId={route.opportunityId}
              distanceKm={route.distanceKm}
              onBack={returnToOpportunities}
              backToDashboard={route.preservesDashboard}
              saveAccess={sessionState.status}
              saveUserId={sessionState.status === 'authenticated' ? sessionState.user.id : undefined}
              saveReturnOutcome={
                postAuthSaveOutcome?.opportunityId === route.opportunityId
                  ? postAuthSaveOutcome
                  : null
              }
              onRequestSaveAuthentication={requestSaveAuthentication}
              onSaveSessionExpired={handleSaveSessionExpired}
            />
          )}

          {route.page === 'dashboard' && sessionState.status === 'checking' && (
            <p role="status">Checking your account…</p>
          )}
          {route.page === 'dashboard' && sessionState.status === 'error' && (
            <div role="alert">Could not check your account. <button type="button" onClick={retrySessionCheck}>Try again</button></div>
          )}
          {route.page === 'dashboard' && sessionState.status === 'authenticated' && (
            <DashboardPage
              key={sessionState.user.id}
              onNavigate={handleInternalNavigation}
              onViewOpportunity={showSavedOpportunity}
              onSessionExpired={handleDashboardSessionExpired}
            />
          )}

          {accountRoute !== null && sessionState.status !== 'checking' && sessionState.status !== 'authenticated' && (
            <AccountPage
              key={accountRoute}
              mode={accountRoute}
              currentUser={null}
              onAuthenticated={handleAuthenticated}
              onNavigate={handleInternalNavigation}
              saveReturn={accountSaveReturn}
              returnToDashboard={accountReturnQuery === '?returnTo=%2Fdashboard'}
            />
          )}

          {route.page === 'data-sources' && (
            <DataSourcesPage onBackHome={handleInternalNavigation} />
          )}

          {route.page === 'privacy' && (
            <PrivacyPage onBackHome={handleInternalNavigation} />
          )}

          {route.page === 'terms' && (
            <TermsPage onBackHome={handleInternalNavigation} />
          )}

          {route.page === 'not-found' && (
            <NotFoundPage onBackToOpportunities={handleBackToOpportunities} />
          )}
        </div>
      </main>

      <footer className="site-footer">
        <div className="app-container site-footer__inner">
          <p>SiteForecaster planning intelligence.</p>
          <nav className="site-footer__nav" aria-label="Legal">
            <a href="/data-sources" onClick={handleInternalNavigation}>
              Data sources
            </a>
            <a href="/privacy" onClick={handleInternalNavigation}>
              Privacy
            </a>
            <a href="/terms" onClick={handleInternalNavigation}>
              Terms
            </a>
          </nav>
        </div>
      </footer>
    </>
  )
}

export default App
