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
import type { OpportunityFilterValues } from './OpportunityFilters'
import OpportunityList from './OpportunityList'

type SearchState =
  | { status: 'initial' }
  | { status: 'loading' }
  | { status: 'location-not-found' }
  | { status: 'geocoding-error' }
  | { status: 'opportunities-error'; location: GeocodedLocation }
  | {
      status: 'success'
      location: GeocodedLocation
      response: OpportunityFeedResponse
    }

function OpportunitiesPage() {
  const resultsHeadingId = 'top-opportunities-heading'
  const [searchState, setSearchState] = useState<SearchState>({
    status: 'initial',
  })

  async function handleSearch(filters: OpportunityFilterValues) {
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

    try {
      const response = await fetchOpportunities({
        latitude: location.latitude,
        longitude: location.longitude,
        radiusKm: filters.radiusKm,
        recentDays: filters.recentDays,
        category: filters.category,
        limit: 20,
      })
      setSearchState({ status: 'success', location, response })
    } catch {
      setSearchState({ status: 'opportunities-error', location })
    }
  }

  return (
    <>
      <section aria-labelledby="opportunities-heading">
        <h2 id="opportunities-heading">Opportunities near you</h2>
        <p>
          GroundSignal ranks recent planning applications by their potential
          relevance to electrical contractors.
        </p>

        <OpportunityFilters
          isLoading={searchState.status === 'loading'}
          onSearch={(filters) => void handleSearch(filters)}
        />
      </section>

      <section
        className="opportunity-results"
        aria-labelledby={resultsHeadingId}
        aria-busy={searchState.status === 'loading'}
      >
        <h2 id={resultsHeadingId}>Top opportunities</h2>

        {searchState.status === 'initial' && (
          <p>Enter an Irish location to find nearby opportunities.</p>
        )}

        {searchState.status === 'loading' && (
          <p role="status">Searching for opportunities...</p>
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

        {(searchState.status === 'success' ||
          searchState.status === 'opportunities-error') && (
          <p>Opportunities near {searchState.location.display_name}</p>
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
