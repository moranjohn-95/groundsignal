from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api.auth import router as auth_router
from .api.locations import router as locations_router
from .api.opportunities import router as opportunities_router
from .api.planning_applications import router as planning_applications_router
from .api.saved_opportunities import router as saved_opportunities_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(locations_router)
app.include_router(opportunities_router)
app.include_router(planning_applications_router)
app.include_router(saved_opportunities_router)


@app.middleware("http")
async def no_store_saved_opportunities(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/api/v1/saved-opportunities" or path.startswith(
        "/api/v1/saved-opportunities/"
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_without_auth_secrets(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/v1/auth/"):
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid account request."},
            headers={"Cache-Control": "no-store"},
        )
    return await request_validation_exception_handler(request, exc)


@app.get("/health")
def read_health():
    return {"status": "ok"}


@app.get("/")
def read_root():
    return {"message": "GroundSignal API"}
