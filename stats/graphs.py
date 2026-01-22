from stats.mongo import server_metrics
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
import time
import math


DEFAULT_PUSH_INTERVAL_SECONDS = 10
GAP_MULTIPLIER = 2.2

DARK_BG = "#0f1117"
AX_BG = "#161b22"
GRID_COLOR = "#30363d"
LINE_COLOR = "#58a6ff"
FILL_COLOR = "#58a6ff"

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
    # doc = server_metrics.find_one(sort=[("timestamp", -1)])
    # print(doc.keys())

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

    fig, ax = plt.subplots(figsize=(9, 4.5))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(AX_BG)

    ax.plot(
        times,
        values,
        color=LINE_COLOR,
        linewidth=2.2,
        solid_capstyle="round",
    )

    ax.fill_between(
        times,
        values,
        where=[not math.isnan(v) for v in values],
        color=FILL_COLOR,
        alpha=0.25,
        interpolate=False,
    )

    ax.grid(
        True,
        linestyle="--",
        linewidth=0.6,
        color=GRID_COLOR,
        alpha=0.6,
    )

    ax.set_xlabel("Time", color="white", labelpad=8)
    ax.set_ylabel(ylabel or _label(metric), color="white", labelpad=8)

    ax.tick_params(colors="white", labelsize=9)

    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)

    ax.set_title(
        f"{_label(metric)}: last {minutes} min",
        color="white",
        fontsize=12,
        pad=12,
        loc="left",
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
