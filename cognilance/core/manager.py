"""CognilanceManager — discover and hire agents from any framework."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import uvicorn

from cognilance.config import Config, DEFAULT_PORT
from cognilance.core.hire_result import HireResult
from cognilance.core.models import AgentCard, AgentVisibility, TaskResult, TaskState, TraceContext
from cognilance.core.tracing import TraceEmitter
from cognilance.payments import (
    EscrowStatus,
    HirePayment,
    PaymentConfig,
    PaymentError,
    PaymentService,
)
from cognilance.registry.client import RegistryClient
from cognilance.transport.a2a import A2AClient


class CognilanceManager:
    """
    Hire and discover agents on the Cognilance marketplace.

    Drop this into any existing project — LangChain, CrewAI, FastAPI, a script.
    No server or registry listing required. Use CognilanceWorker when you also want to be hired.

        async with CognilanceManager.from_env() as manager:
            agents = await manager.discover(skills=["translation"])
            result = await manager.hire(agents[0], input_text="Hello")

    When ``payment`` is enabled and an agent has ``price_usd_cents > 0``, ``hire``
    locks mock USDC into escrow before the A2A call. Call ``settle_hire`` after
    your validation succeeds, or ``refund_hire`` on failure. Managers are
    responsible for settle/refund — the SDK does not auto-release on hire success.
    """

    def __init__(
        self,
        *,
        registry_url: str | None = None,
        agent_id: str | None = None,
        config: Config | None = None,
        trace: TraceContext | None = None,
        task_id: str | None = None,
        agent_name: str = "Manager",
        payment: PaymentConfig | PaymentService | None = None,
    ) -> None:
        cfg = config or Config.from_env()
        self._registry_url = (registry_url or cfg.registry_url).rstrip("/")
        self._agent_id = agent_id
        self._registry = RegistryClient(registry_url=self._registry_url)
        self._a2a = A2AClient()
        # Trace context: inherited when nested inside another hire chain,
        # otherwise this manager is the root of a new hire chain.
        self._trace = trace or TraceContext()
        self._task_id = task_id or f"manager-{uuid.uuid4().hex[:12]}"
        self._agent_name = agent_name
        self._emitter = TraceEmitter(registry_url=self._registry_url)
        if isinstance(payment, PaymentService):
            self._payments: PaymentService | None = payment
        elif isinstance(payment, PaymentConfig):
            self._payments = PaymentService(payment) if payment.enabled else None
        else:
            # Default: payments enabled from env (mock ledger).
            pc = PaymentConfig.from_env()
            self._payments = PaymentService(pc) if pc.enabled else None
        self._pending_payments: list[HirePayment] = []

    @property
    def payments(self) -> PaymentService | None:
        return self._payments

    @property
    def pending_payments(self) -> list[HirePayment]:
        return list(self._pending_payments)

    @classmethod
    def from_env(
        cls,
        *,
        agent_id: str | None = None,
        payment: PaymentConfig | PaymentService | None = None,
    ) -> CognilanceManager:
        """Create a manager using COGNILANCE_REGISTRY_URL from .env."""
        return cls(agent_id=agent_id, payment=payment)

    async def close(self) -> None:
        await self._registry.close()
        await self._a2a.close()
        await self._emitter.close()

    async def __aenter__(self) -> CognilanceManager:
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    @property
    def trace_id(self) -> str:
        """ID correlating every event in this hire chain (visible on the dashboard)."""
        return self._trace.trace_id

    @property
    def agent_name(self) -> str:
        return self._agent_name

    async def _emit(self, type: str, text: str = "", **data: Any) -> None:
        await self._emitter.emit(
            trace_id=self._trace.trace_id,
            task_id=self._task_id,
            parent_task_id=self._trace.parent_task_id,
            depth=self._trace.depth,
            agent_name=self._agent_name,
            type=type,
            text=text,
            data=data,
        )

    async def discover(
        self,
        *,
        skills: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[AgentCard]:
        """Search the registry for agents with matching skills."""
        agents = await self._registry.discover(
            skills=skills,
            tags=tags,
            limit=limit,
            exclude_id=self._agent_id,
        )
        await self._emit(
            "discover",
            text=f"Searched marketplace (skills={skills or 'any'}) — {len(agents)} found",
            skills=skills or [],
            tags=tags or [],
            found=len(agents),
            names=[a.name for a in agents],
        )
        return agents

    async def hire(
        self,
        agent: AgentCard,
        *,
        input_text: str = "",
        input_data: dict[str, Any] | None = None,
        payer_user_id: str | None = None,
        mission_id: str | None = None,
    ) -> HireResult:
        """Send a task to another agent and await the result.

        If payments are enabled and ``agent.price_usd_cents > 0``, funds the
        escrow before the A2A call. Does not auto-settle — call
        ``settle_hire`` / ``refund_hire`` after your validation.
        """
        child_trace = self._trace.child(self._task_id)
        hire_id = f"hire-{uuid.uuid4().hex}"
        payment: HirePayment | None = None

        if self._payments and agent.price_usd_cents > 0:
            if not agent.payout_wallet:
                raise PaymentError(
                    f"Agent {agent.name} is priced ({agent.price_usd_cents}¢) "
                    "but has no payout_wallet"
                )
            if not payer_user_id:
                raise PaymentError(
                    "payer_user_id is required for paid hires"
                )
            payment = self._payments.fund_escrow(
                hire_id=hire_id,
                agent_wallet=agent.payout_wallet,
                amount_base_units=0,
                price_usd_cents=agent.price_usd_cents,
                payer_user_id=payer_user_id,
                agent_id=agent.id,
                mission_id=mission_id,
            )
            self._pending_payments.append(payment)
            await self._emit(
                "escrow_funded",
                text=f"Escrowed {payment.amount_base_units} base units for {agent.name}",
                hire_id=hire_id,
                amount_base_units=payment.amount_base_units,
                agent=agent.name,
            )

        await self._emit(
            "hire_started",
            text=f"Hiring {agent.name}",
            agent=agent.name,
            agent_url=agent.url,
            input_text=input_text,
        )
        started = time.monotonic()
        try:
            result = await self._a2a.send_task(
                agent.url,
                input_text=input_text,
                input_data=input_data,
                trace=child_trace.model_dump(),
            )
        except Exception as exc:
            if payment is not None and self._payments is not None:
                try:
                    self._payments.refund_escrow(payment.hire_id)
                    payment.status = EscrowStatus.REFUNDED
                    self._pending_payments = [
                        p
                        for p in self._pending_payments
                        if p.hire_id != payment.hire_id
                    ]
                    await self._emit(
                        "escrow_refunded",
                        text=f"Refunded escrow for failed hire of {agent.name}",
                        hire_id=payment.hire_id,
                    )
                except PaymentError:
                    pass
            await self._emit(
                "hire_failed",
                text=f"{agent.name} unreachable: {exc}",
                agent=agent.name,
            )
            raise
        duration_ms = int((time.monotonic() - started) * 1000)
        if result.status.state == TaskState.FAILED:
            if payment is not None and self._payments is not None:
                try:
                    self._payments.refund_escrow(payment.hire_id)
                    payment.status = EscrowStatus.REFUNDED
                    self._pending_payments = [
                        p
                        for p in self._pending_payments
                        if p.hire_id != payment.hire_id
                    ]
                    await self._emit(
                        "escrow_refunded",
                        text=f"Refunded escrow after {agent.name} failed",
                        hire_id=payment.hire_id,
                    )
                    payment = None
                except PaymentError:
                    pass
            await self._emit(
                "hire_failed",
                text=f"{agent.name} failed: {result.status.message or 'unknown error'}",
                agent=agent.name,
                duration_ms=duration_ms,
            )
            raise RuntimeError(
                f"Agent {agent.name} failed: {result.status.message or 'unknown error'}"
            )
        await self._emit(
            "hire_completed",
            text=f"{agent.name} delivered in {duration_ms / 1000:.1f}s",
            agent=agent.name,
            duration_ms=duration_ms,
            output_text=result.output.text,
        )
        return HireResult(result=result, payment=payment)

    async def settle_hire(self, payment: HirePayment | str) -> str:
        """Release escrow (90/10) after validation. Returns tx signature."""
        if self._payments is None:
            raise PaymentError("Payments are not enabled on this manager")
        hire_id = payment.hire_id if isinstance(payment, HirePayment) else payment
        tx = self._payments.release_escrow(hire_id)
        self._pending_payments = [
            p for p in self._pending_payments if p.hire_id != hire_id
        ]
        await self._emit("escrow_released", text=f"Released escrow {hire_id}", hire_id=hire_id)
        return tx

    async def refund_hire(self, payment: HirePayment | str) -> str:
        """Refund escrow to the payer. Returns tx signature."""
        if self._payments is None:
            raise PaymentError("Payments are not enabled on this manager")
        hire_id = payment.hire_id if isinstance(payment, HirePayment) else payment
        tx = self._payments.refund_escrow(hire_id)
        self._pending_payments = [
            p for p in self._pending_payments if p.hire_id != hire_id
        ]
        await self._emit("escrow_refunded", text=f"Refunded escrow {hire_id}", hire_id=hire_id)
        return tx

    async def settle_all(self, *, mission_id: str | None = None) -> list[str]:
        """Settle every funded escrow for this manager (optionally filtered by mission)."""
        if self._payments is None:
            return []
        pending = list(self._pending_payments)
        if mission_id:
            pending = [p for p in pending if p.mission_id == mission_id]
            # Also pull from store in case of multi-manager instances
            pending.extend(
                p
                for p in self._payments.list_mission_escrows(mission_id)
                if p.status.value == "funded"
                and p.hire_id not in {x.hire_id for x in pending}
            )
        sigs: list[str] = []
        for p in pending:
            if p.status.value != "funded":
                continue
            try:
                sigs.append(await self.settle_hire(p))
            except PaymentError:
                continue
        return sigs

    async def refund_all(self, *, mission_id: str | None = None) -> list[str]:
        """Refund every funded escrow for this manager (optionally filtered by mission)."""
        if self._payments is None:
            return []
        pending = list(self._pending_payments)
        if mission_id:
            pending = [p for p in pending if p.mission_id == mission_id]
            pending.extend(
                p
                for p in self._payments.list_mission_escrows(mission_id)
                if p.status.value == "funded"
                and p.hire_id not in {x.hire_id for x in pending}
            )
        sigs: list[str] = []
        for p in pending:
            if p.status.value != "funded":
                continue
            try:
                sigs.append(await self.refund_hire(p))
            except PaymentError:
                continue
        return sigs

    async def discover_and_hire(
        self,
        *,
        skills: list[str],
        input_text: str,
        fallback_fn: Callable[[str], str] | Callable[[str], Awaitable[str]] | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
        payer_user_id: str | None = None,
        mission_id: str | None = None,
    ) -> TaskResult | str:
        """Find the best matching agent and hire them, or run a local fallback."""
        agents = await self.discover(skills=skills, tags=tags, limit=limit)
        if agents:
            hired = await self.hire(
                agents[0],
                input_text=input_text,
                payer_user_id=payer_user_id,
                mission_id=mission_id,
            )
            return hired.result
        if fallback_fn is None:
            raise RuntimeError(f"No agents found with skills {skills}")
        result = fallback_fn(input_text)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def register(
        self,
        *,
        name: str,
        url: str,
        skills: list[str],
        description: str = "",
        visibility: AgentVisibility | str = AgentVisibility.PUBLIC,
        tags: list[str] | None = None,
        payout_wallet: str | None = None,
        price_usd_cents: int = 0,
    ) -> AgentCard:
        """List your agent on the marketplace (you still need a server at `url`)."""
        vis = AgentVisibility(visibility) if isinstance(visibility, str) else visibility
        card = await self._registry.register(
            name=name,
            url=url,
            skills=skills,
            description=description,
            visibility=vis,
            tags=tags or [],
            payout_wallet=payout_wallet,
            price_usd_cents=price_usd_cents,
        )
        self._agent_id = card.id
        return card

    async def get_agent(self, agent_id: str) -> AgentCard:
        """Look up a single agent by ID."""
        return await self._registry.get_agent(agent_id)

    def chat(
        self,
        handler: Callable[[CognilanceManager, str], Awaitable[str]],
        *,
        description: str = "",
        host: str = "0.0.0.0",
        port: int | None = None,
        open_ui: bool = False,
    ) -> None:
        """
        Start a local chat UI and optional terminal loop.

        Managers are not listed on the registry — this only serves GET/POST /chat
        on the given port. Pass an async handler: ``async def handle(manager, message) -> str``.
        """
        import threading
        import time
        import webbrowser

        from cognilance.transport.manager_chat import ManagerChatServer

        listen_port = port or DEFAULT_PORT
        server = ManagerChatServer(
            manager=self,
            handler=handler,
            description=description,
        )

        thread = threading.Thread(
            target=lambda: uvicorn.run(server.app, host=host, port=listen_port),
            daemon=True,
            name=f"cognilance-manager-{self._agent_name}",
        )
        thread.start()

        health_url = f"http://127.0.0.1:{listen_port}/health"
        for _ in range(60):
            try:
                if httpx.get(health_url, timeout=0.5).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            raise RuntimeError(f"{self._agent_name} failed to start on port {listen_port}")

        chat_url = f"http://127.0.0.1:{listen_port}/chat"
        print(f"\n{self._agent_name} chat UI: {chat_url}")
        print("Terminal below — or use the chat UI in your browser. Commands: agents, exit.\n")

        if open_ui:
            webbrowser.open(chat_url)

        while True:
            try:
                line = input(f"{self._agent_name}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break
            try:
                reply = asyncio.run(server._dispatch(line))
                print(f"\n{reply}\n")
            except Exception as exc:
                print(f"Error: {exc}\n")
