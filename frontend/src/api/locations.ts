export interface GeocodedLocation {
  query: string
  display_name: string
  latitude: number
  longitude: number
}

export class LocationNotFoundError extends Error {
  constructor() {
    super('Location not found.')
    this.name = 'LocationNotFoundError'
  }
}

export async function fetchGeocodedLocation(
  query: string,
): Promise<GeocodedLocation> {
  const parameters = new URLSearchParams({ query })
  const response = await fetch(
    `/api/v1/locations/geocode?${parameters.toString()}`,
  )

  if (response.status === 404) {
    throw new LocationNotFoundError()
  }

  if (!response.ok) {
    throw new Error(`Geocoding request failed with status ${response.status}.`)
  }

  return (await response.json()) as GeocodedLocation
}
