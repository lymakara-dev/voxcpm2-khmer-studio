"""Flatten FastAPI/pydantic validation errors into the same clean
`{"detail": "<string>"}` shape as HTTPException, so the frontend can
always display `detail` verbatim without branching on error shape."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _flatten(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        msg = err["msg"]
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts) or "Invalid request."


def install(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": _flatten(exc)},
        )
