const categories = [
  ['residential', 'Residential'],
  ['commercial', 'Commercial'],
  ['industrial', 'Industrial'],
  ['energy', 'Energy'],
  ['infrastructure', 'Infrastructure'],
  ['mixed_use', 'Mixed use'],
  ['other', 'Other'],
] as const

function OpportunityFilters() {
  return (
    <form className="opportunity-filters" aria-label="Opportunity filters">
      <fieldset>
        <legend>Search criteria</legend>

        <div className="form-field">
          <label htmlFor="opportunity-location">Location</label>
          <input
            id="opportunity-location"
            name="location"
            type="text"
            autoComplete="street-address"
          />
        </div>

        <div className="form-field">
          <label htmlFor="opportunity-radius">Radius</label>
          <select id="opportunity-radius" name="radius" defaultValue="25">
            <option value="10">10 km</option>
            <option value="25">25 km</option>
            <option value="50">50 km</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="opportunity-recent-period">Recent period</label>
          <select
            id="opportunity-recent-period"
            name="recentPeriod"
            defaultValue="30"
          >
            <option value="7">7 days</option>
            <option value="30">30 days</option>
            <option value="60">60 days</option>
            <option value="90">90 days</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="opportunity-category">Category</label>
          <select id="opportunity-category" name="category" defaultValue="">
            <option value="">All categories</option>
            {categories.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </fieldset>

      <button type="submit">Find opportunities</button>
    </form>
  )
}

export default OpportunityFilters
