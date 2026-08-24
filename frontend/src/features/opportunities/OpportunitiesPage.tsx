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
} from '../../api/opportunities'
import OpportunityFilters from './OpportunityFilters'
import type {
  OpportunityFilterOptions,
  OpportunityFilterValues,
} from './OpportunityFilters'
import OpportunityList from './OpportunityList'

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
    }

interface BrowserCoordinates {
  latitude: number
  longitude: number
}

interface OpportunitiesPageProps {
  onViewOpportunity?: (opportunity: Opportunity) => void
}

type OpportunitySort = 'best' | 'nearest' | 'newest'

function compareOptionalNumbers(
  firstValue: unknown,
  secondValue: unknown,
  direction: 'ascending' | 'descending',
) {
  const first =
    typeof firstValue === 'number' && Number.isFinite(firstValue)
      ? firstValue
      : null
  const second =
    typeof secondValue === 'number' && Number.isFinite(secondValue)
      ? secondValue
      : null

  if (first === null) {
    return second === null ? 0 : 1
  }
  if (second === null) {
    return -1
  }

  return direction === 'ascending' ? first - second : second - first
}

function receivedTimestamp(receivedDate: unknown) {
  if (typeof receivedDate !== 'string') {
    return null
  }

  const timestamp = Date.parse(receivedDate)
  return Number.isFinite(timestamp) ? timestamp : null
}

function sortedOpportunities(
  opportunities: Opportunity[],
  sortBy: OpportunitySort,
) {
  return opportunities
    .map((opportunity, originalIndex) => ({ opportunity, originalIndex }))
    .sort((first, second) => {
      let comparison: number

      if (sortBy === 'nearest') {
        comparison = compareOptionalNumbers(
          first.opportunity.distance_km,
          second.opportunity.distance_km,
          'ascending',
        )
      } else if (sortBy === 'newest') {
        comparison = compareOptionalNumbers(
          receivedTimestamp(first.opportunity.received_date),
          receivedTimestamp(second.opportunity.received_date),
          'descending',
        )
      } else {
        comparison = compareOptionalNumbers(
          first.opportunity.opportunity_score,
          second.opportunity.opportunity_score,
          'descending',
        )
      }

      return comparison === 0
        ? first.originalIndex - second.originalIndex
        : comparison
    })
    .map(({ opportunity }) => opportunity)
}

function OpportunitiesPage({ onViewOpportunity }: OpportunitiesPageProps) {
  const resultsHeadingId = 'top-opportunities-heading'
  const [currentCoordinates, setCurrentCoordinates] =
    useState<BrowserCoordinates | null>(null)
  const [locationQuery, setLocationQuery] = useState('')
  const [sortBy, setSortBy] = useState<OpportunitySort>('best')
  const [searchState, setSearchState] = useState<SearchState>({
    status: 'initial',
  })

  async function loadOpportunities(
    filters: OpportunityFilterOptions,
    latitude: number,
    longitude: number,
    resultLocation: string,
  ) {
    setSearchState({ status: 'loading' })

    try {
      const response = await fetchOpportunities({
        latitude,
        longitude,
        radiusKm: filters.radiusKm,
        recentDays: filters.recentDays,
        category: filters.category,
        limit: 20,
      })
      setSearchState({ status: 'success', resultLocation, response })
    } catch {
      setSearchState({ status: 'opportunities-error', resultLocation })
    }
  }

  async function handleSearch(filters: OpportunityFilterValues) {
    if (filters.location === '' && currentCoordinates !== null) {
      await loadOpportunities(
        filters,
        currentCoordinates.latitude,
        currentCoordinates.longitude,
        'your current location',
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
      filters,
      location.latitude,
      location.longitude,
      location.display_name,
    )
  }

  function handleUseCurrentLocation() {
    setCurrentCoordinates(null)
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
    if (currentCoordinates !== null) {
      setCurrentCoordinates(null)
      setSearchState({ status: 'initial' })
    }
  }

  const isLoading =
    searchState.status === 'locating' || searchState.status === 'loading'
  const displayedOpportunities =
    searchState.status === 'success'
      ? sortedOpportunities(searchState.response.items, sortBy)
      : []

  return (
    <>
      <section
        className="opportunities-search"
        aria-labelledby="opportunities-heading"
      >
        <div className="opportunities-intro">
          <h2 id="opportunities-heading">Opportunities near you</h2>
          <p>
            GroundSignal ranks recent planning applications by their potential
            relevance to electrical contractors.
          </p>
        </div>

        <OpportunityFilters
          isCurrentLocationSelected={currentCoordinates !== null}
          isLoading={isLoading}
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
        aria-busy={isLoading}
      >
        <h2 id={resultsHeadingId}>Top opportunities</h2>

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
                    onChange={(event) =>
                      setSortBy(event.currentTarget.value as OpportunitySort)
                    }
                  >
                    <option value="best">Best opportunity</option>
                    <option value="nearest">Nearest</option>
                    <option value="newest">Newest</option>
                  </select>
                </div>
              </div>
              <p role="status">
                {searchState.response.returned_count} opportunities returned.
              </p>
              <OpportunityList
                opportunities={displayedOpportunities}
                labelledBy={resultsHeadingId}
                onViewOpportunity={onViewOpportunity}
              />
            </>
          )}
      </section>
    </>
  )
}

export default OpportunitiesPage
