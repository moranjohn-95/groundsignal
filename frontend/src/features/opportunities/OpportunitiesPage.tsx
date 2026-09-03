import { useState } from 'react'

import {
  fetchGeocodedLocation,
  LocationNotFoundError,
  type GeocodedLocation,
} from '../../api/locations'
import {
  fetchOpportunities,
  type Opportunity,
  type OpportunityFeedResponse,
  type OpportunitySort,
} from '../../api/opportunities'
import OpportunityFilters from './OpportunityFilters'
import type {
  OpportunityFilterOptions,
  OpportunityFilterValues,
} from './OpportunityFilters'
import OpportunityList from './OpportunityList'
import OpportunityState from './OpportunityState'

const OPPORTUNITY_PAGE_SIZE = 20

interface OpportunitySearchRequest {
  filters: OpportunityFilterOptions
  latitude: number
  longitude: number
  resultLocation: string
}

type SearchState =
  | { status: 'initial' }
  | { status: 'locating' }
  | { status: 'loading' }
  | { status: 'location-not-found' }
  | { status: 'geolocation-error' }
  | { status: 'geocoding-error' }
  | {
      status: 'opportunities-error'
      resultLocation: string
      request: OpportunitySearchRequest
    }
  | {
      status: 'success'
      resultLocation: string
      response: OpportunityFeedResponse
      request: OpportunitySearchRequest
    }

type RefreshState = 'idle' | 'refreshing' | 'error'

interface BrowserCoordinates {
  latitude: number
  longitude: number
}

interface OpportunitiesPageProps {
  onViewOpportunity?: (opportunity: Opportunity) => void
}

function OpportunitiesPage({ onViewOpportunity }: OpportunitiesPageProps) {
  const resultsHeadingId = 'top-opportunities-heading'
  const [currentCoordinates, setCurrentCoordinates] =
    useState<BrowserCoordinates | null>(null)
  const [locationQuery, setLocationQuery] = useState('')
  const [sortBy, setSortBy] = useState<OpportunitySort>('best')
  const [refreshState, setRefreshState] = useState<RefreshState>('idle')
  const [searchState, setSearchState] = useState<SearchState>({
    status: 'initial',
  })

  async function loadOpportunities(
    request: OpportunitySearchRequest,
    page: number,
    sort: OpportunitySort,
    preserveResults = false,
  ) {
    // Keep the current cards visible while sorting or changing pages.
    if (preserveResults) {
      setRefreshState('refreshing')
    } else {
      setRefreshState('idle')
      setSearchState({ status: 'loading' })
    }

    try {
      const response = await fetchOpportunities({
        latitude: request.latitude,
        longitude: request.longitude,
        radiusKm: request.filters.radiusKm,
        recentDays: request.filters.recentDays,
        category: request.filters.category,
        page,
        pageSize: OPPORTUNITY_PAGE_SIZE,
        sort,
      })
      setSearchState({
        status: 'success',
        resultLocation: request.resultLocation,
        response,
        request,
      })
      setRefreshState('idle')
    } catch {
      if (preserveResults) {
        setRefreshState('error')
      } else {
        setSearchState({
          status: 'opportunities-error',
          resultLocation: request.resultLocation,
          request,
        })
      }
    }
  }

  async function handleSearch(filters: OpportunityFilterValues) {
    setRefreshState('idle')

    if (filters.location === '' && currentCoordinates !== null) {
      // Reuse browser coordinates instead of geocoding an empty location field.
      await loadOpportunities(
        {
          filters,
          latitude: currentCoordinates.latitude,
          longitude: currentCoordinates.longitude,
          resultLocation: 'your current location',
        },
        1,
        sortBy,
      )
      return
    }

    setSearchState({ status: 'loading' })

    let location: GeocodedLocation

    try {
      location = await fetchGeocodedLocation(filters.location)
    } catch (error) {
      setSearchState({
        status:
          error instanceof LocationNotFoundError
            ? 'location-not-found'
            : 'geocoding-error',
      })
      return
    }

    await loadOpportunities(
      {
        filters,
        latitude: location.latitude,
        longitude: location.longitude,
        resultLocation: location.display_name,
      },
      1,
      sortBy,
    )
  }

  function handleUseCurrentLocation() {
    setCurrentCoordinates(null)
    setRefreshState('idle')
    setSearchState({ status: 'locating' })

    if (navigator.geolocation === undefined) {
      setSearchState({ status: 'geolocation-error' })
      return
    }

    try {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setCurrentCoordinates({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          })
          setLocationQuery('')
          setSearchState({ status: 'initial' })
        },
        () => setSearchState({ status: 'geolocation-error' }),
      )
    } catch {
      setSearchState({ status: 'geolocation-error' })
    }
  }

  function handleLocationChange(location: string) {
    setLocationQuery(location)
    setRefreshState('idle')
    if (currentCoordinates !== null) {
      // Typing a location switches the search away from browser coordinates.
      setCurrentCoordinates(null)
      setSearchState({ status: 'initial' })
    }
  }

  const isInitialLoading =
    searchState.status === 'locating' || searchState.status === 'loading'
  const isRefreshing = refreshState === 'refreshing'
  const isRequestActive = isInitialLoading || isRefreshing

  function handleSortChange(sort: OpportunitySort) {
    setSortBy(sort)
    if (searchState.status === 'success' && !isRefreshing) {
      void loadOpportunities(searchState.request, 1, sort, true)
    }
  }

  function handlePageChange(page: number) {
    if (searchState.status === 'success' && !isRefreshing) {
      void loadOpportunities(searchState.request, page, sortBy, true)
    }
  }

  function handleRetry() {
    if (searchState.status === 'opportunities-error') {
      void loadOpportunities(searchState.request, 1, sortBy)
      return
    }

    if (searchState.status === 'success' && refreshState === 'error') {
      void loadOpportunities(
        searchState.request,
        searchState.response.page,
        sortBy,
        true,
      )
    }
  }

  return (
    <>
      <section
        className="opportunities-search"
        aria-labelledby="opportunities-heading"
      >
        <div className="opportunities-intro">
          <h2 id="opportunities-heading">Opportunities near you</h2>
          <p>
            SiteForecaster ranks recent planning applications by their potential
            relevance to electrical contractors.
          </p>
        </div>

        <OpportunityFilters
          isCurrentLocationSelected={currentCoordinates !== null}
          isLoading={isRequestActive}
          isLocating={searchState.status === 'locating'}
          location={locationQuery}
          onLocationChange={handleLocationChange}
          onSearch={(filters) => void handleSearch(filters)}
          onUseCurrentLocation={handleUseCurrentLocation}
        />
      </section>

      <section
        className="opportunity-results"
        aria-labelledby={resultsHeadingId}
      >
        <h2 id={resultsHeadingId} tabIndex={-1}>
          Top opportunities
        </h2>

        {searchState.status === 'initial' && (
          <p className="opportunity-results__empty-message">
            Enter an Irish location to find nearby opportunities.
          </p>
        )}

        {searchState.status === 'loading' && (
          <OpportunityState variant="loading" title="Finding opportunities...">
            Searching recent planning applications near you.
          </OpportunityState>
        )}

        {searchState.status === 'locating' && (
          <OpportunityState variant="loading" title="Finding your location...">
            This will only take a moment.
          </OpportunityState>
        )}

        {searchState.status === 'location-not-found' && (
          <OpportunityState variant="error" title="Location not found">
            Check the spelling or try another Irish location.
          </OpportunityState>
        )}

        {searchState.status === 'geocoding-error' && (
          <OpportunityState variant="error" title="Location search unavailable">
            We could not look up that location right now. Please try again later.
          </OpportunityState>
        )}

        {searchState.status === 'geolocation-error' && (
          <OpportunityState
            variant="error"
            title="Current location unavailable"
          >
            Enter an Irish location instead, or try again.
          </OpportunityState>
        )}

        {(searchState.status === 'success' ||
          searchState.status === 'opportunities-error') && (
          <h3 className="opportunity-results__location">
            Opportunities near {searchState.resultLocation}
          </h3>
        )}

        {searchState.status === 'opportunities-error' && (
          <OpportunityState
            variant="error"
            title="We couldn't load opportunities"
            action={{ label: 'Try again', onClick: handleRetry }}
          >
            Check your connection and try the same search again.
          </OpportunityState>
        )}

        {searchState.status === 'success' &&
          searchState.response.items.length === 0 && (
            <OpportunityState variant="empty" title="No opportunities found">
              Try increasing the search radius, widening the recent period, or
              selecting a different category.
            </OpportunityState>
          )}

        {searchState.status === 'success' &&
          searchState.response.items.length > 0 && (
            <>
              <div className="opportunity-results__toolbar">
                <div className="opportunity-results__sort">
                  <label htmlFor="opportunity-sort">
                    <svg
                      className="opportunity-results__sort-icon"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                      focusable="false"
                    >
                      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
                      <circle cx="16" cy="7" r="2" />
                      <circle cx="8" cy="17" r="2" />
                    </svg>
                    Sort
                  </label>
                  <select
                    id="opportunity-sort"
                    value={sortBy}
                    disabled={isRefreshing}
                    onChange={(event) =>
                      handleSortChange(
                        event.currentTarget.value as OpportunitySort,
                      )
                    }
                  >
                    <option value="best">Best opportunity</option>
                    <option value="nearest">Nearest</option>
                    <option value="newest">Newest</option>
                  </select>
                </div>
                <p className="opportunity-results__count" role="status">
                  {isRefreshing ? (
                    'Refreshing opportunities...'
                  ) : (
                    <>
                      {searchState.response.total}{' '}
                      {searchState.response.total === 1
                        ? 'opportunity'
                        : 'opportunities'}
                      <span className="visually-hidden">
                        {' '}
                        Page {searchState.response.page} of{' '}
                        {searchState.response.total_pages}.
                      </span>
                    </>
                  )}
                </p>
              </div>
              {refreshState === 'error' && (
                <OpportunityState
                  variant="error"
                  title="We couldn't refresh opportunities"
                  action={{ label: 'Try again', onClick: handleRetry }}
                >
                  Your current results are still available.
                </OpportunityState>
              )}
              <OpportunityList
                isBusy={isRefreshing}
                opportunities={searchState.response.items}
                labelledBy={resultsHeadingId}
                onViewOpportunity={onViewOpportunity}
              />
              <nav
                className="opportunity-pagination"
                aria-label="Opportunity result pages"
              >
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={
                    isRefreshing || searchState.response.page <= 1
                  }
                  onClick={() =>
                    handlePageChange(searchState.response.page - 1)
                  }
                >
                  Previous
                </button>
                <p>
                  Page {searchState.response.page} of{' '}
                  {searchState.response.total_pages}
                </p>
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={
                    isRefreshing ||
                    searchState.response.page >=
                    searchState.response.total_pages
                  }
                  onClick={() =>
                    handlePageChange(searchState.response.page + 1)
                  }
                >
                  Next
                </button>
              </nav>
            </>
          )}
      </section>
    </>
  )
}

export default OpportunitiesPage
