"""FastAPI app assembly for the coordinator API.

Routes live in ``api/routes``; shared stores in ``api/deps``.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.auth.guard import is_public_request
from api.auth.session import get_user_id
from api.deps import init_stores
from api.routes import ALL_ROUTERS
from core.broker.proxy import docs_router, gmail_router
from core.context.request import current_user_id, current_user_timezone
from core.context.users.timezone import activate_user_timezone, client_timezone_from_request
from core.registry import validate_all
from core.runtime.checkpointer import close_checkpointer
from core.runtime.runner import recover_interrupted_runs
from pipelines.coordinator_board.graph import init_graph
from workers.schedulers.ticker import tick_subscriptions

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    init_stores()

    app = FastAPI(
        title="Cognilance Coordinator",
        description="Cognilance: durable runs, coordinator + specialists, OAuth tools",
        version="0.5.0",
    )
    for router in (gmail_router, docs_router, *ALL_ROUTERS):
        app.include_router(router)

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        user_id = get_user_id(request)
        request.state.user_id = user_id
        if not user_id and not is_public_request(request):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        user_token = None
        tz_token = None
        if user_id:
            user_token = current_user_id.set(user_id)
            tz_token = activate_user_timezone(
                user_id, from_client=client_timezone_from_request(request)
            )
        try:
            response = await call_next(request)
        finally:
            if tz_token is not None:
                current_user_timezone.reset(tz_token)
            if user_token is not None:
                current_user_id.reset(user_token)
        return response

    @app.on_event("startup")
    async def on_startup() -> None:
        validate_all(strict=False)
        init_stores()
        recovered = mission_store.recover_stale_running()
        if recovered:
            logger.info("Recovered %s stale running mission(s)", recovered)
        await init_graph()

        async def subscription_ticker_loop() -> None:
            while True:
                try:
                    await tick_subscriptions()
                except Exception:
                    logger.exception("Subscription ticker error")
                await asyncio.sleep(5)

        asyncio.create_task(subscription_ticker_loop())

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await close_checkpointer()

    return app


app = create_app()
