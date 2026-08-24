import type { FormEvent, MouseEvent } from 'react'

import {
  planningApplicationCategories,
  type PlanningApplicationCategory,
} from '../../api/opportunities'

export interface OpportunityFilterOptions {
  radiusKm: number
  recentDays: number
  category?: PlanningApplicationCategory
}

export interface OpportunityFilterValues extends OpportunityFilterOptions {
  location: string
}

interface OpportunityFiltersProps {
  isLoading: boolean
  isLocating: boolean
  onSearch: (filters: OpportunityFilterValues) => void
  onUseCurrentLocation: (filters: OpportunityFilterOptions) => void
}

function formatCategory(category: PlanningApplicationCategory) {
  const label = category.replace('_', ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function readFilterOptions(data: FormData): OpportunityFilterOptions {
  const category = data.get('category')

  return {
    radiusKm: Number(data.get('radiusKm')),
    recentDays: Number(data.get('recentDays')),
    category:
      typeof category === 'string' && category !== ''
        ? (category as PlanningApplicationCategory)
        : undefined,
  }
}

function OpportunityFilters({
  isLoading,
  isLocating,
  onSearch,
  onUseCurrentLocation,
}: OpportunityFiltersProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isLoading) {
      return
    }

    const data = new FormData(event.currentTarget)

    onSearch({
      location: String(data.get('location')).trim(),
      ...readFilterOptions(data),
    })
  }

  function handleUseCurrentLocation(event: MouseEvent<HTMLButtonElement>) {
    const form = event.currentTarget.form
    if (form !== null) {
      onUseCurrentLocation(readFilterOptions(new FormData(form)))
    }
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
          <button
            type="button"
            disabled={isLoading}
            onClick={handleUseCurrentLocation}
          >
            {isLocating
              ? 'Getting current location...'
              : 'Use my current location'}
          </button>
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
