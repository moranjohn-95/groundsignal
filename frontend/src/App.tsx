import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type MouseEvent,
} from 'react'

import type { Opportunity } from './api/opportunities'
import OpportunityDetailPage from './features/opportunities/OpportunityDetailPage'
import OpportunitiesPage from './features/opportunities/OpportunitiesPage'

type AppRoute =
  | { page: 'opportunities' }
  | {
      page: 'opportunity-detail'
      opportunityId: number
      distanceKm?: number
      preservesOpportunities: boolean
    }
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

  function showOpportunities() {
    window.history.pushState(null, '', '/')
    setRoute({ page: 'opportunities' })
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

          {route.page === 'not-found' && (
            <section
              className="opportunity-detail-state"
              aria-labelledby="not-found-heading"
            >
              <h2 id="not-found-heading">Page not found</h2>
              <p>The opportunity address is invalid or no longer available.</p>
              <a href="/" onClick={handleBackToOpportunities}>
                Back to opportunities
              </a>
            </section>
          )}
        </div>
      </main>

      <footer className="site-footer">
        <div className="app-container site-footer__inner">
          <p>SiteForecaster planning intelligence.</p>
        </div>
      </footer>
    </>
  )
}

export default App
