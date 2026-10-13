"""Background worker — processes queued orchestrator missions."""

from __future__ import annotations

import asyncio
import logging
import time

import orchestrator.env  # noqa: F401

from orchestrator.apps.store import init_all_stores
from orchestrator.graph import init_graph
from orchestrator.runtime.runner import run_mission
from orchestrator.missions.store import MissionStore
from orchestrator.subscriptions.ticker import tick_subscriptions

logger = logging.getLogger(__name__)


async def worker_loop(*, poll_interval: float = 1.0) -> None:
    store = MissionStore()
    store.init_db()
    init_all_stores()
    recovered = store.recover_stale_running()
    if recovered:
        logger.info("Recovered %s stale running mission(s)", recovered)
    await init_graph()
    logger.info("Orchestrator worker started — polling for queued missions")
    while True:
        mission = store.claim_next_queued()
        if mission:
            logger.info("Running mission %s", mission.id)
            try:
                await run_mission(store, mission.id)
                logger.info("Mission %s finished with status %s", mission.id, store.get_mission(mission.id).status)
            except Exception:
                logger.exception("Mission %s failed", mission.id)
        try:
            await tick_subscriptions()
        except Exception:
            logger.exception("Subscription tick failed")
        await asyncio.sleep(poll_interval)


def cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print("Cognilance Orchestrator Worker — processing queued missions", flush=True)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    cli()
