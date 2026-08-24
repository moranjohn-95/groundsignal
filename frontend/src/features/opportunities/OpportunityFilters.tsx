import type { FormEvent } from 'react'

import {
  planningApplicationCategories,
  type PlanningApplicationCategory,
} from '../../api/opportunities'

export interface OpportunityFilterValues {
  location: string
  radiusKm: number
  recentDays: number
  category?: PlanningApplicationCategory
}

interface OpportunityFiltersProps {
  isLoading: boolean
  onSearch: (filters: OpportunityFilterValues) => void
}

function formatCategory(category: PlanningApplicationCategory) {
  const label = category.replace('_', ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function OpportunityFilters({ isLoading, onSearch }: OpportunityFiltersProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const data = new FormData(event.currentTarget)
    const category = data.get('category')

    onSearch({
      location: String(data.get('location')).trim(),
      radiusKm: Number(data.get('radiusKm')),
      recentDays: Number(data.get('recentDays')),
      category:
        typeof category === 'string' && category !== ''
          ? (category as PlanningApplicationCategory)
          : undefined,
    })
  }

  return (
    <form
      className="opportunity-filters"
      aria-label="Opportunity filters"
      onSubmit={handleSubmit}
    >
      <fieldset>
        <legend>Search criteria</legend>

        <div className="form-field">
          <label htmlFor="opportunity-location">Location</label>
          <input
            id="opportunity-location"
            name="location"
            type="text"
            placeholder="e.g. Tralee, Co. Kerry"
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="opportunity-radius">Radius</label>
          <select id="opportunity-radius" name="radiusKm" defaultValue="25">
            <option value="10">10 km</option>
            <option value="25">25 km</option>
            <option value="50">50 km</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="opportunity-recent-period">Recent period</label>
          <select
            id="opportunity-recent-period"
            name="recentDays"
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
            {planningApplicationCategories.map((category) => (
              <option key={category} value={category}>
                {formatCategory(category)}
              </option>
            ))}
          </select>
        </div>
      </fieldset>

      <button type="submit" disabled={isLoading}>
        Find opportunities
      </button>
    </form>
  )
}

export default OpportunityFilters
