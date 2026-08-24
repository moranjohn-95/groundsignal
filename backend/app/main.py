from fastapi import FastAPI

from .api.locations import router as locations_router
from .api.opportunities import router as opportunities_router
from .api.planning_applications import router as planning_applications_router

app = FastAPI()

app.include_router(locations_router)
app.include_router(opportunities_router)
app.include_router(planning_applications_router)


@app.get("/")
def read_root():
    return {"message": "GroundSignal API"}
