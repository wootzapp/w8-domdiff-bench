"""Official agent-browser CLI integration used by the task recorder."""

# Re-export the adapter's public surface so callers do not depend on its internal
# file layout.
from .client import (
    AgentBrowserClient,
    AgentBrowserError,
    AgentBrowserObservation,
    AgentBrowserPage,
    agent_browser_session_name,
)

__all__ = [
    "AgentBrowserClient",
    "AgentBrowserError",
    "AgentBrowserObservation",
    "AgentBrowserPage",
    "agent_browser_session_name",
]
