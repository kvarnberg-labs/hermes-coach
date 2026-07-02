"""Chart rendering tools for hermes-coach.

Generates dark-mode PNG charts for Discord using matplotlib.

Palette validated against #1a1a19 dark surface (dataviz skill, palette.md):
  - 2-series CTL/ATL categorical: worst ΔE 69.8 — all six checks PASS
  - 3-series CTL/ATL/TSB-sign: worst ΔE 9.7 (floor band, legal with direct labels)
  - 6-step ordinal zone ramp (steps 100→600): all ordinal checks PASS

CVD note: the 3-series dark palette is in the 8–12 floor band; the relief
obligation is met by direct end-labels on every series line.

Discord output is static PNG — no hover. Every value is reachable via
direct labels or the alt_text caption (table-view equivalent).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validated dark-mode palette (#1a1a19 surface)
# ---------------------------------------------------------------------------
_C = {
    # Surfaces / chrome (palette.md § Chart chrome)
    "bg":         "#1a1a19",
    "surface2":   "#252523",
    "text_pri":   "#ffffff",
    "text_sec":   "#c3c2b7",
    "text_muted": "#898781",
    "grid":       "#2c2c2a",
    "baseline":   "#383835",
    # Categorical dark slots 1 + 2 (palette.md § Categorical palette, dark column)
    "ctl":        "#3987e5",   # slot 1 blue  — CTL (fitness)
    "atl":        "#199e70",   # slot 2 aqua  — ATL (fatigue)
    "tsb_pos":    "#3987e5",   # slot 1 blue  — positive TSB (fresh)
    "tsb_neg":    "#e66767",   # slot 6 red   — negative TSB (fatigued)
    # Sequential blue power curve (single series = slot 1 hue)
    "power":      "#3987e5",
    # Ordinal 6-step blue ramp (steps 100→600, validated dark-mode --ordinal)
    "z1": "#cde2fb",  # step 100 — Z1 recovery
    "z2": "#9ec5f4",  # step 200 — Z2 endurance
    "z3": "#6da7ec",  # step 300 — Z3 tempo
    "z4": "#3987e5",  # step 400 — Z4 threshold
    "z5": "#256abf",  # step 500 — Z5 VO2max
    "z6": "#184f95",  # step 600 — Z6+ anaerobic/neuromuscular
}


def _charts_dir() -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    d = hermes_home / "charts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ax_style(ax) -> None:
    """Apply shared dark-mode axis style."""
    ax.set_facecolor(_C["bg"])
    ax.tick_params(colors=_C["text_muted"], labelsize=9, length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(True, color=_C["grid"], linewidth=0.8, linestyle="-", alpha=0.9)
    ax.set_axisbelow(True)


def render_wellness_chart(wellness_json: str, **_: Any) -> str:
    """Render a CTL/ATL trend + TSB chart from get_wellness output.

    Two subplots — top: CTL + ATL lines; bottom: TSB diverging bars.
    No dual y-axis (different scales; separate panels are the correct form).

    Args:
        wellness_json: JSON string returned by get_wellness.

    Returns JSON with chart_path (saved PNG) and alt_text for accessibility.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        from matplotlib import dates as mdates
        from matplotlib.lines import Line2D
        from datetime import datetime as dt
    except ImportError:
        return json.dumps({
            "success": False,
            "error": "matplotlib not installed. Add 'matplotlib>=3.8' to the Dockerfile RUN.",
        })

    try:
        data = json.loads(wellness_json) if isinstance(wellness_json, str) else wellness_json
        records = [r for r in data.get("records", []) if r.get("date")]
        if len(records) < 2:
            return json.dumps({"success": False,
                               "error": "Need at least 2 wellness records to plot."})
        dates = [dt.fromisoformat(r["date"]) for r in records]
    except Exception as exc:
        return json.dumps({"success": False, "error": f"Invalid input: {exc}"})
    ctl_vals = [r.get("ctl") for r in records]
    atl_vals = [r.get("atl") for r in records]
    tsb_vals = [r.get("tsb") for r in records]

    fig = plt.figure(figsize=(10, 7), dpi=130)
    fig.patch.set_facecolor(_C["bg"])
    gs = gridspec.GridSpec(2, 1, height_ratios=[2.3, 1.0], hspace=0.06)
    ax_top = fig.add_subplot(gs[0])
    ax_bot = fig.add_subplot(gs[1], sharex=ax_top)

    _ax_style(ax_top)
    _ax_style(ax_bot)
    plt.setp(ax_top.get_xticklabels(), visible=False)

    def _clean(seq):
        return [(d, v) for d, v in zip(dates, seq) if v is not None]

    # --- CTL line (2px, area wash 10%, end-dot with surface ring, end label) ---
    ctl_pts = _clean(ctl_vals)
    if ctl_pts:
        dx, dy = zip(*ctl_pts)
        ax_top.fill_between(dx, dy, alpha=0.10, color=_C["ctl"], linewidth=0)
        ax_top.plot(dx, dy, color=_C["ctl"], linewidth=2,
                    solid_capstyle="round", solid_joinstyle="round", zorder=3)
        ax_top.plot(dx[-1], dy[-1], "o", color=_C["ctl"], markersize=9,
                    markeredgecolor=_C["bg"], markeredgewidth=2, zorder=4)
        ax_top.annotate(f"CTL {dy[-1]:.0f}", xy=(dx[-1], dy[-1]),
                        xytext=(6, 0), textcoords="offset points",
                        color=_C["text_sec"], fontsize=9, va="center", ha="left")

    # --- ATL line ---
    atl_pts = _clean(atl_vals)
    if atl_pts:
        dx, dy = zip(*atl_pts)
        ax_top.fill_between(dx, dy, alpha=0.10, color=_C["atl"], linewidth=0)
        ax_top.plot(dx, dy, color=_C["atl"], linewidth=2,
                    solid_capstyle="round", solid_joinstyle="round", zorder=3)
        ax_top.plot(dx[-1], dy[-1], "o", color=_C["atl"], markersize=9,
                    markeredgecolor=_C["bg"], markeredgewidth=2, zorder=4)
        ax_top.annotate(f"ATL {dy[-1]:.0f}", xy=(dx[-1], dy[-1]),
                        xytext=(6, 0), textcoords="offset points",
                        color=_C["text_sec"], fontsize=9, va="center", ha="left")

    # Legend — required for ≥2 series (marks carry identity, text uses text tokens)
    legend_handles = [
        Line2D([0], [0], color=_C["ctl"], linewidth=2, label="CTL — Fitness"),
        Line2D([0], [0], color=_C["atl"], linewidth=2, label="ATL — Fatigue"),
    ]
    ax_top.legend(handles=legend_handles, loc="upper left", fontsize=9,
                  facecolor=_C["surface2"], edgecolor="none",
                  labelcolor=_C["text_sec"], framealpha=0.85)
    ax_top.set_ylabel("Score", color=_C["text_sec"], fontsize=9)
    ax_top.set_title("Training Load — CTL · ATL · TSB",
                     color=_C["text_pri"], fontsize=12, fontweight="semibold", pad=10)

    # --- TSB diverging bars — blue=fresh, red=fatigued ---
    tsb_pts = _clean(tsb_vals)
    if tsb_pts:
        dx, dy = zip(*tsb_pts)
        bar_colors = [_C["tsb_pos"] if v >= 0 else _C["tsb_neg"] for v in dy]
        ax_bot.bar(dx, dy, color=bar_colors, width=0.82, align="center",
                   zorder=3, linewidth=0)
        ax_bot.axhline(0, color=_C["baseline"], linewidth=1.0, zorder=2)
        last_v = dy[-1]
        offset = 3 if last_v >= 0 else -3
        anchor = max(last_v, 0) if last_v >= 0 else min(last_v, 0)
        ax_bot.annotate(
            f"TSB {last_v:+.1f}",
            xy=(dx[-1], anchor),
            xytext=(0, offset), textcoords="offset points",
            color=_C["text_sec"], fontsize=9, ha="center",
            va="bottom" if last_v >= 0 else "top",
        )

    ax_bot.set_ylabel("TSB (Form)", color=_C["text_sec"], fontsize=9)
    ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax_bot.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
    plt.setp(ax_bot.get_xticklabels(), color=_C["text_muted"], fontsize=9)

    # Right margin for end labels
    fig.subplots_adjust(left=0.07, right=0.86, top=0.93, bottom=0.08)

    path = _charts_dir() / f"wellness_{time.time_ns()}.png"
    try:
        plt.savefig(path, dpi=130, facecolor=_C["bg"], bbox_inches="tight")
    finally:
        plt.close(fig)

    last_ctl = ctl_vals[-1]
    last_atl = atl_vals[-1]
    last_tsb = tsb_vals[-1]
    ctl_str = f"{last_ctl:.0f}" if last_ctl is not None else "?"
    atl_str = f"{last_atl:.0f}" if last_atl is not None else "?"
    tsb_str = f"{last_tsb:+.1f}" if last_tsb is not None else "?"

    return json.dumps({
        "success": True,
        "chart_path": str(path),
        "alt_text": (
            f"Training load chart over {len(records)} days. "
            f"Current CTL {ctl_str} (fitness), ATL {atl_str} (fatigue), "
            f"TSB {tsb_str} (form)."
        ),
    })


def render_power_curve_chart(
    power_json: str,
    ftp_w: Optional[int] = None,
    **_: Any,
) -> str:
    """Render a peak power curve from get_power_curve output.

    Single-series line on a log x-axis (durations span 5 seconds to 60 minutes).
    Selective direct labels at 5s, 1min, 5min, 20min, 60min.

    Args:
        power_json: JSON string returned by get_power_curve.
        ftp_w:      FTP in watts for a reference line (optional; pass from
                    get_sport_settings if available).

    Returns JSON with chart_path and alt_text.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return json.dumps({"success": False, "error": "matplotlib not installed."})

    try:
        data = json.loads(power_json) if isinstance(power_json, str) else power_json
        peaks = data.get("peak_power", {})
        if not peaks:
            return json.dumps({"success": False, "error": "No peak_power data found."})
    except Exception as exc:
        return json.dumps({"success": False, "error": f"Invalid input: {exc}"})

    _DUR_SECS = {
        "5s": 5, "10s": 10, "30s": 30,
        "1min": 60, "2min": 120, "5min": 300,
        "10min": 600, "20min": 1200, "30min": 1800, "60min": 3600,
    }
    _SECS_LABEL = {v: k for k, v in _DUR_SECS.items()}

    pts = sorted(
        [(s, w) for lbl, w in peaks.items()
         if (s := _DUR_SECS.get(lbl)) is not None and w is not None],
    )
    if len(pts) < 2:
        return json.dumps({"success": False, "error": "Need at least 2 power curve points."})

    xs, ys = zip(*pts)
    _LABEL_AT = {5, 60, 300, 1200, 3600}

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=130)
    fig.patch.set_facecolor(_C["bg"])
    _ax_style(ax)
    ax.set_xscale("log")

    # Area wash (10% opacity) + line (2px)
    ax.fill_between(xs, ys, alpha=0.10, color=_C["power"], linewidth=0)
    ax.plot(xs, ys, color=_C["power"], linewidth=2,
            solid_capstyle="round", solid_joinstyle="round", zorder=3)

    # Selective direct labels at standard durations
    for secs, watts in pts:
        if secs in _LABEL_AT:
            ax.annotate(
                f"{_SECS_LABEL.get(secs, f'{secs}s')}\n{watts:.0f}W",
                xy=(secs, watts),
                xytext=(0, 10), textcoords="offset points",
                color=_C["text_sec"], fontsize=8.5, ha="center", va="bottom",
            )
            ax.plot(secs, watts, "o", color=_C["power"], markersize=8,
                    markeredgecolor=_C["bg"], markeredgewidth=2, zorder=4)

    # FTP reference line (data annotation, not a gridline)
    ftp_int = int(ftp_w) if ftp_w else None
    if ftp_int:
        ax.axhline(ftp_int, color=_C["text_muted"], linewidth=1.0, zorder=2)
        ax.annotate(f"FTP  {ftp_int}W", xy=(xs[-1], ftp_int),
                    xytext=(-6, 4), textcoords="offset points",
                    color=_C["text_muted"], fontsize=8.5, ha="right", va="bottom")

    tick_secs = [s for s in _DUR_SECS.values() if xs[0] <= s <= xs[-1]]
    ax.set_xticks(tick_secs)
    ax.set_xticklabels([_SECS_LABEL[s] for s in tick_secs],
                       color=_C["text_muted"], fontsize=9)
    ax.set_ylabel("Watts", color=_C["text_sec"], fontsize=9)

    sport = data.get("sport", "Ride")
    days = data.get("days", "?")
    ax.set_title(f"Peak Power Curve — {sport}  ·  {days}d",
                 color=_C["text_pri"], fontsize=12, fontweight="semibold", pad=10)
    fig.subplots_adjust(left=0.10, right=0.95, top=0.88, bottom=0.12)

    path = _charts_dir() / f"power_curve_{time.time_ns()}.png"
    try:
        plt.savefig(path, dpi=130, facecolor=_C["bg"], bbox_inches="tight")
    finally:
        plt.close(fig)

    pts_dict = dict(pts)
    return json.dumps({
        "success": True,
        "chart_path": str(path),
        "alt_text": (
            f"Peak power curve for {sport} over {days} days. "
            f"5s: {pts_dict.get(5, '?')}W, "
            f"1min: {pts_dict.get(60, '?')}W, "
            f"5min: {pts_dict.get(300, '?')}W, "
            f"20min: {pts_dict.get(1200, '?')}W."
        ),
    })


def render_zone_distribution_chart(zones_json: str, **_: Any) -> str:
    """Render a training zone time-distribution horizontal bar chart.

    Uses the validated 6-step ordinal blue ramp (light=Z1 recovery → dark=Z6+ anaerobic).
    Horizontal bars so zone names fit without rotation.

    Args:
        zones_json: JSON with a 'zones' list of {name, percent} (up to 6 zones)
                    and optionally 'total_hours' and 'days'. Example:
                    {"zones": [
                       {"name": "Z1 Recovery", "percent": 15.2},
                       {"name": "Z2 Endurance", "percent": 42.1},
                       {"name": "Z3 Tempo", "percent": 18.3},
                       {"name": "Z4 Threshold", "percent": 15.0},
                       {"name": "Z5 VO2max", "percent": 7.1},
                       {"name": "Z6+ Anaerobic", "percent": 2.3}],
                     "total_hours": 12.5, "days": 28}

    Returns JSON with chart_path and alt_text.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return json.dumps({"success": False, "error": "matplotlib not installed."})

    try:
        data = json.loads(zones_json) if isinstance(zones_json, str) else zones_json
        zones = data.get("zones", [])
        if not zones:
            return json.dumps({"success": False, "error": "No zone data provided."})
        names = [z.get("name", f"Zone {i + 1}") for i, z in enumerate(zones)]
        percents = [float(z.get("percent", 0)) for z in zones]
    except Exception as exc:
        return json.dumps({"success": False, "error": f"Invalid input: {exc}"})

    ZONE_COLORS = [_C["z1"], _C["z2"], _C["z3"], _C["z4"], _C["z5"], _C["z6"]]
    colors = [ZONE_COLORS[min(i, len(ZONE_COLORS) - 1)] for i in range(len(zones))]

    # Reverse for display: Z1 at top (matplotlib barh: first item = bottom)
    names_disp = names[::-1]
    pcts_disp = percents[::-1]
    cols_disp = colors[::-1]

    fig_h = max(3.5, 0.65 * len(names) + 1.2)
    fig, ax = plt.subplots(figsize=(8, fig_h), dpi=130)
    fig.patch.set_facecolor(_C["bg"])
    _ax_style(ax)
    ax.grid(True, axis="x", color=_C["grid"], linewidth=0.8, linestyle="-", alpha=0.9)
    ax.grid(False, axis="y")

    ax.barh(names_disp, pcts_disp, color=cols_disp, height=0.55, linewidth=0)

    # Value labels at bar tips — text in text_sec, never data color
    for name, pct in zip(names_disp, pcts_disp):
        ax.annotate(
            f"{pct:.1f}%",
            xy=(pct, name),
            xytext=(4, 0), textcoords="offset points",
            color=_C["text_sec"], fontsize=9, va="center", ha="left",
        )

    ax.set_xlabel("Time in zone (%)", color=_C["text_sec"], fontsize=9)
    ax.tick_params(axis="y", colors=_C["text_sec"])
    ax.set_xlim(0, max(pcts_disp) * 1.22)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))

    total_hours = data.get("total_hours")
    days = data.get("days")
    subtitle_parts = [p for p in [
        f"{total_hours:.0f}h total" if total_hours else "",
        f"{days}d window" if days else "",
    ] if p]
    subtitle = "  ·  ".join(subtitle_parts)
    title_lines = "Training Zone Distribution" + (f"\n{subtitle}" if subtitle else "")
    ax.set_title(title_lines, color=_C["text_pri"], fontsize=12,
                 fontweight="semibold", pad=10)

    fig.subplots_adjust(left=0.22, right=0.90, top=0.88, bottom=0.13)

    path = _charts_dir() / f"zones_{time.time_ns()}.png"
    try:
        plt.savefig(path, dpi=130, facecolor=_C["bg"], bbox_inches="tight")
    finally:
        plt.close(fig)

    dominant = max(zones, key=lambda z: float(z.get("percent", 0)))
    return json.dumps({
        "success": True,
        "chart_path": str(path),
        "alt_text": (
            f"Training zone distribution, {len(zones)} zones. "
            f"Most time in {dominant.get('name', '?')}: {float(dominant.get('percent', 0)):.1f}%. "
            + (f"Total: {total_hours:.0f}h over {days} days." if total_hours and days else "")
        ),
    })


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register_tools(ctx) -> None:
    """Register chart-rendering tools with the Hermes plugin context."""
    ctx.register_tool(
        name="render_wellness_chart",
        toolset="training",
        schema={
            "name": "render_wellness_chart",
            "description": (
                "Render a training-load chart (CTL fitness, ATL fatigue, TSB form) "
                "as a dark-mode PNG. Call this after get_wellness to give the athlete "
                "a visual overview of their training load trend. "
                "Returns a chart_path to the saved PNG and alt_text for accessibility."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "wellness_json": {
                        "type": "string",
                        "description": "The full JSON string returned by get_wellness.",
                    },
                },
                "required": ["wellness_json"],
            },
        },
        handler=lambda args, **kw: render_wellness_chart(**args),
    )

    ctx.register_tool(
        name="render_power_curve_chart",
        toolset="training",
        schema={
            "name": "render_power_curve_chart",
            "description": (
                "Render a peak power curve chart as a dark-mode PNG. "
                "Call this after get_power_curve. Optionally pass ftp_w (FTP in watts) "
                "from get_sport_settings to draw an FTP reference line. "
                "Returns chart_path and alt_text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "power_json": {
                        "type": "string",
                        "description": "The full JSON string returned by get_power_curve.",
                    },
                    "ftp_w": {
                        "type": "integer",
                        "description": "FTP in watts for a reference line (optional).",
                    },
                },
                "required": ["power_json"],
            },
        },
        handler=lambda args, **kw: render_power_curve_chart(**args),
    )

    ctx.register_tool(
        name="render_zone_distribution_chart",
        toolset="training",
        schema={
            "name": "render_zone_distribution_chart",
            "description": (
                "Render a training zone distribution horizontal bar chart as a dark-mode PNG. "
                "Provide zone names and percentages that you compute from the athlete's "
                "recent activities and FTP zone boundaries. Up to 6 zones (combine Z6/Z7 "
                "as 'Z6+ Anaerobic'). Returns chart_path and alt_text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "zones_json": {
                        "type": "string",
                        "description": (
                            'JSON string with zones and optionally total_hours and days. '
                            'Example: {"zones": [{"name": "Z1 Recovery", "percent": 15}, '
                            '{"name": "Z2 Endurance", "percent": 42}], "total_hours": 12, "days": 28}'
                        ),
                    },
                },
                "required": ["zones_json"],
            },
        },
        handler=lambda args, **kw: render_zone_distribution_chart(**args),
    )
