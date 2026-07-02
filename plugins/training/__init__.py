"""Training plugin for Hermes Coach.

Registers all coaching tools via the Hermes plugin ctx interface:
  - intervals_icu   : fetch athlete data from intervals.icu (6 tools)
  - weather         : Open-Meteo forecast (1 tool)
  - coaching        : retrieve coach-brain knowledge (1 tool)
  - onboarding      : /start slash command handler (1 tool)
  - sandbox_client  : autonomous tool development via k8s Jobs (1 tool)
  - render_chart    : generate dark-mode PNG charts for Discord (3 tools)
"""

from __future__ import annotations


def register(ctx):
    """Called by Hermes plugin discovery at gateway startup."""
    from .intervals_icu import register_tools as register_intervals
    from .weather import register_tools as register_weather
    from .coaching import register_tools as register_coaching
    from .onboarding import register_tools as register_onboarding
    from .sandbox_client import register_tools as register_sandbox
    from .render_chart import register_tools as register_charts

    register_intervals(ctx)
    register_weather(ctx)
    register_coaching(ctx)
    register_onboarding(ctx)
    register_sandbox(ctx)
    register_charts(ctx)
