import { useState } from 'react'

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
  | { status: 'success'; response: OpportunityFeedResponse }
  | { status: 'error' }

function OpportunitiesPage() {
  const resultsHeadingId = 'top-opportunities-heading'
  const [searchState, setSearchState] = useState<SearchState>({
    status: 'initial',
  })

  async function handleSearch(filters: OpportunityFilterValues) {
    setSearchState({ status: 'loading' })

    try {
      const response = await fetchOpportunities({
        ...filters,
        limit: 20,
      })
      setSearchState({ status: 'success', response })
    } catch {
      setSearchState({ status: 'error' })
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
          <p>Enter a latitude and longitude to find nearby opportunities.</p>
        )}

        {searchState.status === 'loading' && (
          <p role="status">Loading opportunities…</p>
        )}

        {searchState.status === 'error' && (
          <p role="alert">
            We could not load opportunities. Please check the details and try
            again.
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
