import OpportunityFilters from './OpportunityFilters'
import OpportunityList from './OpportunityList'
import { temporaryOpportunityFixtures } from './opportunityFixtures'

function OpportunitiesPage() {
  const resultsHeadingId = 'top-opportunities-heading'

  return (
    <>
      <section aria-labelledby="opportunities-heading">
        <h2 id="opportunities-heading">Opportunities near you</h2>
        <p>
          GroundSignal ranks recent planning applications by their potential
          relevance to electrical contractors.
        </p>

        <OpportunityFilters />
      </section>

      <section className="opportunity-results" aria-labelledby={resultsHeadingId}>
        <h2 id={resultsHeadingId}>Top opportunities</h2>
        <OpportunityList
          opportunities={temporaryOpportunityFixtures}
          labelledBy={resultsHeadingId}
        />
      </section>
    </>
  )
}

export default OpportunitiesPage
