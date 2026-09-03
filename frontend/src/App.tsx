import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type MouseEvent,
} from 'react'

import type { Opportunity } from './api/opportunities'
import {
  DataSourcesPage,
  PrivacyPage,
  TermsPage,
} from './features/LegalPages'
import NotFoundPage from './features/NotFoundPage'
import OpportunityDetailPage from './features/opportunities/OpportunityDetailPage'
import OpportunitiesPage from './features/opportunities/OpportunitiesPage'

type LegalPage = 'data-sources' | 'privacy' | 'terms'

type AppRoute =
  | { page: 'opportunities' }
  | {
      page: 'opportunity-detail'
      opportunityId: number
      distanceKm?: number
      preservesOpportunities: boolean
    }
  | { page: LegalPage }
  | { page: 'not-found' }

interface OpportunityHistoryState {
  distanceKm?: unknown
  preservesOpportunities?: unknown
}

function routeFromLocation(
  pathname: string,
  historyState: OpportunityHistoryState | null,
): AppRoute {
  if (pathname === '/') {
    return { page: 'opportunities' }
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
  }
}

function App() {
  const opportunitiesScrollPosition = useRef<number | null>(null)
  const opportunityFocusTarget = useRef<number | null>(null)
  const [route, setRoute] = useState(() =>
    routeFromLocation(window.location.pathname, window.history.state),
  )

  useEffect(() => {
    function handleHistoryChange(event: PopStateEvent) {
      setRoute(routeFromLocation(window.location.pathname, event.state))
    }

    window.addEventListener('popstate', handleHistoryChange)
    return () => window.removeEventListener('popstate', handleHistoryChange)
  }, [])

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

  function navigateTo(pathname: string) {
    window.history.pushState(null, '', pathname)
    setRoute(routeFromLocation(pathname, null))
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
    })
  }

  function returnToOpportunities() {
    if (
      route.page === 'opportunity-detail' &&
      route.preservesOpportunities
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
    navigateTo(destination.pathname)
  }

  return (
    <>
      <header className="site-header">
        <div className="app-container site-header__inner">
          <h1 className="site-brand">SiteForecaster</h1>
        </div>
      </header>

      <main className="site-main">
        <div className="app-container">
          <div hidden={route.page !== 'opportunities'}>
            <OpportunitiesPage onViewOpportunity={showOpportunity} />
          </div>

          {route.page === 'opportunity-detail' && (
            <OpportunityDetailPage
              key={route.opportunityId}
              opportunityId={route.opportunityId}
              distanceKm={route.distanceKm}
              onBack={returnToOpportunities}
            />
          )}

          {route.page === 'data-sources' && <DataSourcesPage />}

          {route.page === 'privacy' && <PrivacyPage />}

          {route.page === 'terms' && <TermsPage />}

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
