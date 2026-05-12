"""
AgentSystem — Service runner for autonomous operation.

Provides:
- Windows service wrapper (via nssm or pythonw)
- Health check endpoint
- Auto-restart on failure
- Daemon mode for continuous operation
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


class ServiceRunner:
    """
    Runs the AgentSystem as a long-lived autonomous service.

    Modes:
    - daemon: Continuous loop processing events + user input
    - headless: Only processes notification events (no interactive input)
    """

    def __init__(self, mode: str = "daemon"):
        self.mode = mode
        self._running = False
        self._started_at: Optional[datetime] = None
        self._event_count = 0
        self._error_count = 0

    @property
    def uptime_seconds(self) -> float:
        if self._started_at:
            return (datetime.now(timezone.utc) - self._started_at).total_seconds()
        return 0.0

    def health_check(self) -> dict:
        """Return current health status."""
        return {
            "status": "running" if self._running else "stopped",
            "mode": self.mode,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "events_processed": self._event_count,
            "errors": self._error_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def run_headless(self):
        """
        Run in headless mode — only processes notification gateway events.
        No interactive input. Designed for unattended operation.
        """
        from agents.orchestrator import Orchestrator
        from agents.email_agent import EMAIL_TOOLS
        from agents.calendar_agent import CALENDAR_TOOLS
        from agents.social_agent import SOCIAL_TOOLS
        from agents.finance_agent import FINANCE_TOOLS
        from agents.business_agent import BUSINESS_TOOLS
        from config import get_agent_configs
        from tools.notification import create_default_gateway

        self._running = True
        self._started_at = datetime.now(timezone.utc)

        # Build orchestrator
        agent_configs = get_agent_configs()
        orchestrator = Orchestrator()

        agents_to_register = [
            ("EmailAgent", "email_agent", EMAIL_TOOLS),
            ("CalendarAgent", "calendar_agent", CALENDAR_TOOLS),
            ("SocialAgent", "social_agent", SOCIAL_TOOLS),
            ("FinanceAgent", "finance_agent", FINANCE_TOOLS),
            ("BusinessAgent", "business_agent", BUSINESS_TOOLS),
        ]
        for name, cfg_key, tools in agents_to_register:
            cfg = agent_configs.get(cfg_key, {})
            orchestrator.register_agent(
                name=name,
                system_message=cfg.get("system_message", f"You are the {name}."),
                description=cfg.get("description", name),
                tools=tools,
            )

        # Start notification gateway
        gateway = create_default_gateway()
        await gateway.start()

        log_action("ServiceRunner", "start_headless", f"Agents: {orchestrator.agent_names}")
        logger.info(f"AgentSystem running in headless mode with {len(orchestrator.agent_names)} agents")

        try:
            while self._running:
                event = await gateway.get_next_event(timeout=30.0)
                if event:
                    try:
                        response = await orchestrator.handle_user_input(event.to_prompt())
                        self._event_count += 1
                        logger.info(f"Processed event: {event} → {response[:100]}...")
                    except Exception as e:
                        self._error_count += 1
                        logger.error(f"Error processing event {event}: {e}", exc_info=True)
                        log_action(
                            "ServiceRunner", "event_error",
                            str(event)[:200], str(e),
                            status="error",
                        )
        except asyncio.CancelledError:
            logger.info("Headless service cancelled")
        finally:
            await gateway.stop()
            self._running = False
            log_action("ServiceRunner", "stop_headless", f"Events: {self._event_count}, Errors: {self._error_count}")

    def stop(self):
        """Signal the service to stop."""
        self._running = False
        logger.info("Service stop requested")


def setup_signal_handlers(runner: ServiceRunner):
    """Set up graceful shutdown signal handlers."""
    def handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        runner.stop()

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


# --- Windows Service Installation Helper ---

NSSM_INSTALL_SCRIPT = r"""
@echo off
REM Install AgentSystem as a Windows service using nssm
REM Download nssm from https://nssm.cc/download

SET SERVICE_NAME=AgentSystem
SET PYTHON_PATH=%~dp0.venv\Scripts\pythonw.exe
SET SCRIPT_PATH=%~dp0scripts\run_headless.py
SET LOG_PATH=%~dp0memory\service.log

echo Installing %SERVICE_NAME% as a Windows service...

nssm install %SERVICE_NAME% "%PYTHON_PATH%" "%SCRIPT_PATH%"
nssm set %SERVICE_NAME% AppDirectory "%~dp0"
nssm set %SERVICE_NAME% AppStdout "%LOG_PATH%"
nssm set %SERVICE_NAME% AppStderr "%LOG_PATH%"
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateBytes 10485760
nssm set %SERVICE_NAME% AppRestartDelay 5000
nssm set %SERVICE_NAME% Description "Autonomous multi-agent productivity system"

echo Service installed. Start with: nssm start %SERVICE_NAME%
echo View logs at: %LOG_PATH%
pause
"""


def generate_install_script():
    """Generate the Windows service install script."""
    script_dir = Path(__file__).resolve().parent.parent / "scripts"
    script_dir.mkdir(exist_ok=True)

    bat_path = script_dir / "install_service.bat"
    bat_path.write_text(NSSM_INSTALL_SCRIPT, encoding="utf-8")
    logger.info(f"Service install script generated: {bat_path}")
    return bat_path
