# -*- coding: utf-8 -*-
"""FastAPI app — error envelope + router wiring."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..state.errors import DomainError
from . import routes_backtests, routes_demo, routes_holds, routes_offers

app = FastAPI(title="Âu Lạc Railway API v1")


@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"error_code": exc.error_code, "message": exc.message, "details": exc.details},
    )


app.include_router(routes_demo.router, prefix="/api/v1")
app.include_router(routes_offers.router, prefix="/api/v1")
app.include_router(routes_holds.router, prefix="/api/v1")
app.include_router(routes_backtests.router, prefix="/api/v1")
