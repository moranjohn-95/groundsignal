import { useState } from 'react'

import {
  fetchGeocodedLocation,
  LocationNotFoundError,
  type GeocodedLocation,
} from '../../api/locations'
import {
  fetchOpportunities,
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

function OpportunitiesPage() {
  const resultsHeadingId = 'top-opportunities-heading'
  const [currentCoordinates, setCurrentCoordinates] =
    useState<BrowserCoordinates | null>(null)
  const [locationQuery, setLocationQuery] = useState('')
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

  return (
    <>
      <section aria-labelledby="opportunities-heading">
        <h2 id="opportunities-heading">Opportunities near you</h2>
        <p>
          GroundSignal ranks recent planning applications by their potential
          relevance to electrical contractors.
        </p>

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
              <p role="status">
                {searchState.response.returned_count} opportunities returned.
              </p>
              <OpportunityList
                opportunities={searchState.response.items}
                labelledBy={resultsHeadingId}
              />
            </>
          )}
      </section>
    </>
  )
}

export default OpportunitiesPage
