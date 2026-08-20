from fastapi import FastAPI

from .api.planning_applications import router as planning_applications_router

app = FastAPI()

app.include_router(planning_applications_router)


@app.get("/")
def read_root():
    return {"message": "GroundSignal API"}
