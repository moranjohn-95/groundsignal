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
  | { status: 'opportunities-error'; resultLocation: string }
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
        })
      }
    }
  }

  async function handleSearch(filters: OpportunityFilterValues) {
    setRefreshState('idle')

    if (filters.location === '' && currentCoordinates !== null) {
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

        {searchState.status === 'initial' && currentCoordinates === null && (
          <p>Enter an Irish location to find nearby opportunities.</p>
        )}

        {searchState.status === 'initial' && currentCoordinates !== null && (
          <p>Adjust the filters if needed, then find opportunities.</p>
        )}

        {searchState.status === 'loading' && (
          <p role="status">Searching for opportunities...</p>
        )}

        {searchState.status === 'locating' && (
          <p role="status">Getting your current location...</p>
        )}

        {searchState.status === 'location-not-found' && (
          <p role="alert">
            We could not find that location. Check the spelling and try again.
          </p>
        )}

        {searchState.status === 'geocoding-error' && (
          <p role="alert">
            Location search is unavailable right now. Please try again later.
          </p>
        )}

        {searchState.status === 'geolocation-error' && (
          <p role="alert">
            We could not access your current location. Enter a location instead
            or try again.
          </p>
        )}

        {(searchState.status === 'success' ||
          searchState.status === 'opportunities-error') && (
          <h3>Opportunities near {searchState.resultLocation}</h3>
        )}

        {searchState.status === 'opportunities-error' && (
          <p role="alert">
            We could not load opportunities. Please try again.
          </p>
        )}

        {searchState.status === 'success' &&
          searchState.response.items.length === 0 && (
            <p role="status">No opportunities found for this search.</p>
          )}

        {searchState.status === 'success' &&
          searchState.response.items.length > 0 && (
            <>
              <div className="opportunity-results__toolbar">
                <div className="opportunity-results__sort">
                  <label htmlFor="opportunity-sort">Sort by</label>
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
              </div>
              <p role="status">
                {isRefreshing ? (
                  'Refreshing opportunities...'
                ) : (
                  <>
                    Showing {searchState.response.items.length} of{' '}
                    {searchState.response.total} opportunities.
                    <span className="visually-hidden">
                      {' '}
                      Page {searchState.response.page} of{' '}
                      {searchState.response.total_pages}.
                    </span>
                  </>
                )}
              </p>
              {refreshState === 'error' && (
                <p role="alert">
                  We could not refresh opportunities. Your current results are
                  still available.
                </p>
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
