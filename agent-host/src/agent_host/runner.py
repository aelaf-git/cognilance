"""Process manager — start/stop hosted agents via cognilance run."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from agent_host.config import Settings, get_settings
from agent_host.store import AgentStore, HostedAgent


class RunnerError(Exception):
    pass


class AgentRunner:
    def __init__(
        self,
        store: AgentStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._store = store or AgentStore()
        self._settings = settings or get_settings()
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[str]] = {}

    def allocate_port(self) -> int:
        used = self._store.allocated_ports()
        for port in range(self._settings.port_range_start, self._settings.port_range_end + 1):
            if port not in used:
                return port
        raise RunnerError("No free ports in configured pool")

    def log_path(self, agent: HostedAgent) -> Path:
        return Path(agent.extract_dir) / "agent.log"

    def tail_logs(self, agent: HostedAgent, *, lines: int = 200) -> str:
        path = self.log_path(agent)
        if not path.is_file():
            return ""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        all_lines = content.splitlines()
        return "\n".join(all_lines[-lines:])

    def _append_log(self, agent: HostedAgent, text: str) -> None:
        path = self.log_path(agent)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)
            if not text.endswith("\n"):
                fh.write("\n")

    def _pip_install(self, agent: HostedAgent) -> None:
        req = Path(agent.extract_dir) / "requirements.txt"
        if not req.is_file():
            return
        self._append_log(agent, f"--- pip install -r requirements.txt ---")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req)],
                cwd=agent.extract_dir,
                capture_output=True,
                text=True,
                timeout=self._settings.pip_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RunnerError("pip install timed out") from exc
        self._append_log(agent, result.stdout or "")
        if result.stderr:
            self._append_log(agent, result.stderr)
        if result.returncode != 0:
            raise RunnerError(f"pip install failed (exit {result.returncode})")

    def _wait_for_health(self, port: int) -> None:
        url = f"http://127.0.0.1:{port}/health"
        deadline = time.monotonic() + self._settings.health_timeout_seconds
        while time.monotonic() < deadline:
            try:
                resp = httpx.get(url, timeout=2.0)
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RunnerError(f"Agent did not become healthy on port {port}")

    def _verify_registry(self, port: int) -> bool:
        url = f"{self._settings.registry_url.rstrip('/')}/v1/agents/discover"
        try:
            resp = httpx.get(url, timeout=5.0)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError):
            return False
        if isinstance(payload, dict):
            agents = payload.get("agents", [])
        else:
            agents = payload
        needle = f":{port}"
        for item in agents if isinstance(agents, list) else []:
            agent_url = str(item.get("url", ""))
            if needle in agent_url:
                return True
        return False

    def start(self, agent_id: str) -> HostedAgent:
        with self._lock:
            agent = self._store.get(agent_id)
            if agent is None:
                raise RunnerError("Agent not found")
            if agent.status == "running" and agent.pid:
                if self._is_running(agent.pid):
                    return agent
            entry = Path(agent.extract_dir) / agent.entry_file
            if not entry.is_file():
                raise RunnerError(f"Entry file missing: {agent.entry_file}")

            port = self.allocate_port()
            self._store.update_status(agent_id, status="starting", port=port, pid=None, error_message=None)
            agent = self._store.get(agent_id)
            assert agent is not None

            self._append_log(agent, f"--- starting on port {port} ---")
            try:
                self._pip_install(agent)
            except RunnerError as exc:
                self._store.update_status(
                    agent_id, status="error", port=None, pid=None, error_message=str(exc), clear_runtime=True
                )
                raise

            env = os.environ.copy()
            env.update(self._store.get_env_vars(agent_id))
            env["COGNILANCE_PORT"] = str(port)
            env["COGNILANCE_REGISTRY_URL"] = self._settings.registry_url
            log_path = self.log_path(agent)
            log_fh = log_path.open("a", encoding="utf-8")
            cmd = [
                sys.executable,
                "-m",
                "cognilance.cli.main",
                "run",
                str(entry),
                "--port",
                str(port),
                "--host",
                "0.0.0.0",
            ]
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=agent.extract_dir,
                    env=env,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            except OSError as exc:
                log_fh.close()
                self._store.update_status(
                    agent_id, status="error", port=None, pid=None, error_message=str(exc), clear_runtime=True
                )
                raise RunnerError(str(exc)) from exc

            self._processes[agent_id] = proc
            self._store.update_status(agent_id, status="starting", port=port, pid=proc.pid)

            try:
                self._wait_for_health(port)
            except RunnerError as exc:
                self.stop(agent_id, force=True)
                self._store.update_status(
                    agent_id, status="error", port=None, pid=None, error_message=str(exc), clear_runtime=True
                )
                raise

            registry_ok = self._verify_registry(port)
            if not registry_ok:
                self._append_log(agent, "warning: agent healthy but not yet visible in registry discover")

            updated = self._store.update_status(
                agent_id, status="running", port=port, pid=proc.pid, error_message=None
            )
            assert updated is not None
            return updated

    def stop(self, agent_id: str, *, force: bool = False) -> HostedAgent:
        with self._lock:
            agent = self._store.get(agent_id)
            if agent is None:
                raise RunnerError("Agent not found")

            proc = self._processes.pop(agent_id, None)
            pid = proc.pid if proc else agent.pid
            if proc is not None:
                self._terminate(proc, force=force)
            elif pid:
                self._terminate_pid(pid, force=force)

            if agent:
                self._append_log(agent, "--- stopped ---")

            updated = self._store.update_status(
                agent_id, status="stopped", port=None, pid=None, error_message=None, clear_runtime=True
            )
            assert updated is not None
            return updated

    @staticmethod
    def _is_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    @staticmethod
    def _terminate(proc: subprocess.Popen[str], *, force: bool = False) -> None:
        if proc.poll() is not None:
            return
        if force:
            proc.kill()
            proc.wait(timeout=5)
            return
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    @staticmethod
    def _terminate_pid(pid: int, *, force: bool = False) -> None:
        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except OSError:
            return
        if not force:
            for _ in range(20):
                try:
                    os.kill(pid, 0)
                except OSError:
                    return
                time.sleep(0.5)
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
