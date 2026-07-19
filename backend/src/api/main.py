# -*- coding: utf-8 -*-
"""FastAPI app — error envelope + router wiring."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..state.errors import DomainError
from . import (routes_allocation, routes_backtests, routes_booking_requests,
              routes_demo, routes_group, routes_holds, routes_offers,
              routes_waitlist)
from .deps import load_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_models()          # Pricer + DemandModel 1 lần lúc boot, fail-closed nếu lỗi
    yield


app = FastAPI(title="Âu Lạc Railway API v1", lifespan=lifespan)


@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"error_code": exc.error_code, "message": exc.message, "details": exc.details},
    )


app.include_router(routes_demo.router, prefix="/api/v1")
app.include_router(routes_offers.router, prefix="/api/v1")
app.include_router(routes_booking_requests.router, prefix="/api/v1")
app.include_router(routes_holds.router, prefix="/api/v1")
app.include_router(routes_backtests.router, prefix="/api/v1")
app.include_router(routes_group.router, prefix="/api/v1")
app.include_router(routes_waitlist.router, prefix="/api/v1")
app.include_router(routes_allocation.router, prefix="/api/v1")
