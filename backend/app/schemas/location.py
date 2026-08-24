from pydantic import BaseModel


class LocationGeocodeResponse(BaseModel):
    query: str
    display_name: str
    latitude: float
    longitude: float
