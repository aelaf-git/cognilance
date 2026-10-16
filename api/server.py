"""FastAPI app assembly for the coordinator API.

Routes live in ``api/routes``; shared stores in ``api/deps``.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request

from api.auth.session import get_user_id, resolve_user_id, set_user_cookie
from api.deps import init_stores, mission_store
from api.routes import ALL_ROUTERS
from core.broker.proxy import docs_router, gmail_router
from core.context.request import current_user_id, current_user_timezone
from core.context.users.timezone import activate_user_timezone, client_timezone_from_request
from core.registry import validate_all
from core.runtime.checkpointer import close_checkpointer
from pipelines.coordinator_board.graph import init_graph
from workers.schedulers.ticker import tick_subscriptions


def create_app() -> FastAPI:
    init_stores()

    app = FastAPI(
        title="Cognilance Coordinator",
        description="Cognilance — durable runs, coordinator + specialists, OAuth tools",
        version="0.5.0",
    )
    for router in (gmail_router, docs_router, *ALL_ROUTERS):
        app.include_router(router)

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        user_id = get_user_id(request) or resolve_user_id(request)
        request.state.user_id = user_id
        user_token = current_user_id.set(user_id)
        tz_token = activate_user_timezone(
            user_id, from_client=client_timezone_from_request(request)
        )
        try:
            response = await call_next(request)
        finally:
            current_user_timezone.reset(tz_token)
            current_user_id.reset(user_token)
        if not get_user_id(request):
            set_user_cookie(response, user_id)
        return response

    @app.on_event("startup")
    async def on_startup() -> None:
        validate_all(strict=False)
        init_stores()
        recovered = mission_store.recover_stale_running()
        if recovered:
            print(f"Recovered {recovered} stale running mission(s)", flush=True)
        await init_graph()

        async def subscription_ticker_loop() -> None:
            while True:
                try:
                    await tick_subscriptions()
                except Exception as exc:
                    print(f"Subscription ticker error: {exc}", flush=True)
                await asyncio.sleep(5)

        asyncio.create_task(subscription_ticker_loop())

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await close_checkpointer()

    return app


app = create_app()
