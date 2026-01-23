from stats.mongo import server_metrics
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
import time
import math
from datetime import timezone


DEFAULT_PUSH_INTERVAL_SECONDS = 10
GAP_MULTIPLIER = 2.2

DARK_BG = "#0B0B0C"
AX_BG = "#111113"
GRID_COLOR = "#26262A"
LINE_COLOR = "#ff8524"
FILL_COLOR = "#E97112"
TEXT_COLOR = "#E6E6E6"


BYTES_TO_GB = 1 / (1024**3)


def _label(metric: str) -> str:
    return metric.replace("_", " ").title()


def plot_metric(metric, minutes=60, ylabel=None, scale=1.0, clamp=None):
    """
    Plot for provided metric.

    Args:
        metric: The datatype to plot
        minutes: How far back to plot
        ylabel: The metric label
        scale: Normaliziing factor
        clamp: Minimum and maximum values on Y axis
    """

    since = datetime.utcnow() - timedelta(minutes=minutes)

    cursor = server_metrics.find(
        {"timestamp": {"$gte": since}},
        {"timestamp": 1, metric: 1},
    ).sort("timestamp", 1)

    times = []
    values = []

    last_ts = None
    gap_threshold = timedelta(seconds=DEFAULT_PUSH_INTERVAL_SECONDS * GAP_MULTIPLIER)

    for doc in cursor:
        if metric not in doc:
            continue

        ts = doc["timestamp"]
        val = doc[metric] * scale

        if clamp:
            val = max(clamp[0], min(clamp[1], val))

        if last_ts and (ts - last_ts) > gap_threshold:
            times.append(ts)
            values.append(float("nan"))

        times.append(ts)
        values.append(val)
        last_ts = ts

    if not times:
        return None

    clean_times = []
    clean_values = []
    baseline = []

    for t, v in zip(times, values):
        clean_times.append(t)
        clean_values.append(v)
        baseline.append(0.0)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(AX_BG)

    ax.plot(
        times,
        values,
        color=LINE_COLOR,
        linewidth=2.8,
        solid_capstyle="round",
        zorder=3,
    )

    ax.fill_between(
        times,
        values,
        0,
        where=[not math.isnan(v) for v in values],
        color=FILL_COLOR,
        alpha=0.90,
        interpolate=False,
        zorder=2,
    )

    ax.grid(
        True,
        linestyle="--",
        linewidth=0.6,
        color=GRID_COLOR,
        alpha=0.45,
    )

    ax.set_xlabel("Time", color=TEXT_COLOR, labelpad=8)
    ax.set_ylabel(ylabel or _label(metric), color=TEXT_COLOR, labelpad=8)

    ax.tick_params(
        colors=TEXT_COLOR,
        labelsize=9,
        length=0,
    )

    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
        spine.set_linewidth(1.0)

    ax.set_title(
        f"{_label(metric)} · last {minutes} min",
        color=TEXT_COLOR,
        fontsize=12,
        pad=12,
        loc="left",
        fontweight="bold",
    )

    ax.plot(
        times,
        values,
        color="#FF8C2A",
        linewidth=5.0,
        zorder=1,
    )

    plt.tight_layout()

    path = f"/tmp/{metric}_{int(time.time())}.png"
    plt.savefig(
        path,
        dpi=140,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)

    return path
