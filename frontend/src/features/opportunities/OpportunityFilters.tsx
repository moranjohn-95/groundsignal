import type { FormEvent } from 'react'

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
  isCurrentLocationSelected: boolean
  isLoading: boolean
  isLocating: boolean
  location: string
  onLocationChange: (location: string) => void
  onSearch: (filters: OpportunityFilterValues) => void
  onUseCurrentLocation: () => void
}

type FieldIconName = 'location' | 'radius' | 'period' | 'category'

function FieldLabelIcon({ name }: { name: FieldIconName }) {
  if (name === 'location') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M12 21s7-5.3 7-12a7 7 0 1 0-14 0c0 6.7 7 12 7 12Z" />
        <circle cx="12" cy="9" r="2.25" />
      </svg>
    )
  }

  if (name === 'radius') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="7" />
        <circle cx="12" cy="12" r="2" />
        <path d="M12 2v3M22 12h-3M12 22v-3M2 12h3" />
      </svg>
    )
  }

  if (name === 'period') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <rect x="4" y="5" width="16" height="15" rx="2" />
        <path d="M8 3v4M16 3v4M4 10h16" />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="4" width="6" height="6" rx="1" />
      <rect x="4" y="14" width="6" height="6" rx="1" />
      <rect x="14" y="14" width="6" height="6" rx="1" />
    </svg>
  )
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
  isCurrentLocationSelected,
  isLoading,
  isLocating,
  location,
  onLocationChange,
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
      location: location.trim(),
      ...readFilterOptions(data),
    })
  }

  return (
    <>
    <form
      className="opportunity-filters"
      aria-label="Opportunity filters"
      onSubmit={handleSubmit}
    >
      <fieldset className="opportunity-filters__fieldset">
        <legend>Search criteria</legend>

        <div className="opportunity-filters__grid">
          <div className="form-field form-field--location">
            <label htmlFor="opportunity-location">
              <FieldLabelIcon name="location" />
              Location
            </label>
            <div className="location-controls">
              <input
                id="opportunity-location"
                name="location"
                type="text"
                placeholder="e.g. Tralee, Co. Kerry"
                required={!isCurrentLocationSelected}
                disabled={isLoading}
                value={location}
                onChange={(event) =>
                  onLocationChange(event.currentTarget.value)
                }
              />
              <button
                className="button button--secondary"
                type="button"
                disabled={isLoading}
                onClick={onUseCurrentLocation}
              >
                {isLocating
                  ? 'Getting current location...'
                  : 'Use my current location'}
              </button>
            </div>
            {isCurrentLocationSelected && (
              <p className="current-location-status" role="status">
                Current location selected.
              </p>
            )}
            <p className="google-maps-attribution">
              <span translate="no">Google Maps</span>
            </p>
          </div>

          <div className="form-field">
            <label htmlFor="opportunity-radius">
              <FieldLabelIcon name="radius" />
              Radius
            </label>
            <select
              id="opportunity-radius"
              name="radiusKm"
              defaultValue="25"
              disabled={isLoading}
            >
              <option value="10">10 km</option>
              <option value="25">25 km</option>
              <option value="50">50 km</option>
            </select>
          </div>

          <div className="form-field">
            <label htmlFor="opportunity-recent-period">
              <FieldLabelIcon name="period" />
              Recent period
            </label>
            <select
              id="opportunity-recent-period"
              name="recentDays"
              defaultValue="30"
              disabled={isLoading}
            >
              <option value="7">7 days</option>
              <option value="30">30 days</option>
              <option value="60">60 days</option>
              <option value="90">90 days</option>
            </select>
          </div>

          <div className="form-field form-field--category">
            <label htmlFor="opportunity-category">
              <FieldLabelIcon name="category" />
              Category
            </label>
            <select
              id="opportunity-category"
              name="category"
              defaultValue=""
              disabled={isLoading}
            >
              <option value="">All categories</option>
              {planningApplicationCategories.map((category) => (
                <option key={category} value={category}>
                  {formatCategory(category)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </fieldset>

      <div className="opportunity-filters__actions">
        <button
          className="button button--primary"
          type="submit"
          disabled={isLoading}
        >
          Find opportunities
        </button>
      </div>
    </form>
    <aside
      className="opportunity-search-insight"
      aria-label="How opportunities are ranked"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M13 2 3 14h7l-1 8 10-12h-7z" />
      </svg>
      <p>We rank applications by electrical relevance, project scope and timing.</p>
    </aside>
    </>
  )
}

export default OpportunityFilters
