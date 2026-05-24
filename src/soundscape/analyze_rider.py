"""Rider-collected noise data analysis.

Produces publication-ready tables (LaTeX) and figures (PDF/HTML) analyzing
rider form data with min/max dB readings and road type metadata.
"""

import json
from pathlib import Path

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CITY = "delhi"


def load_rider_readings(path: Path) -> pd.DataFrame:
    """Load rider readings JSON into a DataFrame with flattened structure."""
    with open(path) as f:
        data = json.load(f)

    if data.get("source") != "rider_form":
        raise ValueError(f"Expected rider_form source, got {data.get('source')}")

    records = []
    for r in data["readings"]:
        reading = r.get("reading", {})
        metadata = r.get("metadata", {})
        records.append(
            {
                "stop_id": r.get("id"),
                "timestamp": r.get("timestamp"),
                "latitude": r["gps"]["latitude"] if r.get("gps") else None,
                "longitude": r["gps"]["longitude"] if r.get("gps") else None,
                "min_db": reading.get("min_db"),
                "max_db": reading.get("max_db"),
                "status": reading.get("status", "ok"),
                "day": metadata.get("day"),
                "itinerary": metadata.get("itinerary"),
                "is_traffic_stop": metadata.get("is_traffic_stop", False),
                "is_traffic_jam": metadata.get("is_traffic_jam", False),
                "address": metadata.get("address"),
                "road_type": metadata.get("road_type"),
                "road_name": metadata.get("road_name"),
                "frame_path": r.get("frame_path"),
            }
        )

    df = pd.DataFrame(records)
    return df


def compute_summary_stats(df: pd.DataFrame) -> dict:
    """Compute overall summary statistics for rider data."""
    valid = df[df["status"] == "ok"]

    return {
        "n_total": len(df),
        "n_valid": len(valid),
        "pct_valid": 100 * len(valid) / len(df) if len(df) > 0 else 0,
        "mean_max_db": valid["max_db"].mean(),
        "median_max_db": valid["max_db"].median(),
        "std_max_db": valid["max_db"].std(),
        "min_max_db": valid["max_db"].min(),
        "max_max_db": valid["max_db"].max(),
        "mean_min_db": valid["min_db"].mean(),
        "median_min_db": valid["min_db"].median(),
        "std_min_db": valid["min_db"].std(),
        "min_min_db": valid["min_db"].min(),
        "max_min_db": valid["min_db"].max(),
        "n_traffic_stops": valid["is_traffic_stop"].sum(),
        "n_traffic_jams": valid["is_traffic_jam"].sum(),
    }


def compute_stats_by_road_type(df: pd.DataFrame) -> pd.DataFrame:
    """Compute statistics grouped by road type."""
    valid = df[df["status"] == "ok"].copy()
    valid["road_type"] = valid["road_type"].fillna("unknown")

    def agg_stats(g):
        return pd.Series(
            {
                "n": len(g),
                "mean_max_db": g["max_db"].mean(),
                "median_max_db": g["max_db"].median(),
                "std_max_db": g["max_db"].std(),
                "mean_min_db": g["min_db"].mean(),
                "median_min_db": g["min_db"].median(),
                "pct_above_85": 100 * (g["max_db"] >= 85).mean(),
                "pct_above_88": 100 * (g["max_db"] >= 88).mean(),
            }
        )

    stats = (
        valid.groupby("road_type").apply(agg_stats, include_groups=False).reset_index()
    )
    stats = stats.sort_values("n", ascending=False)
    return stats


def make_table1_summary(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 1: Overall rider data summary (LaTeX)."""
    stats = compute_summary_stats(df)

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Summary Statistics of Rider-Collected Noise Readings}
\label{tab:rider_summary}
\begin{tabular}{lr}
\toprule
Statistic & Value \\
\midrule
Total stops & """
        + f"{stats['n_total']:,}"
        + r""" \\
Valid readings & """
        + f"{stats['n_valid']:,}"
        + r""" \\
Traffic stops & """
        + f"{int(stats['n_traffic_stops']):,}"
        + r""" \\
Traffic jams & """
        + f"{int(stats['n_traffic_jams']):,}"
        + r""" \\
\midrule
\multicolumn{2}{l}{\textbf{Maximum dB per Stop}} \\
Mean & """
        + f"{stats['mean_max_db']:.1f}"
        + r""" \\
Median & """
        + f"{stats['median_max_db']:.1f}"
        + r""" \\
Std Dev & """
        + f"{stats['std_max_db']:.1f}"
        + r""" \\
Range & """
        + f"{stats['min_max_db']:.1f}--{stats['max_max_db']:.1f}"
        + r""" \\
\midrule
\multicolumn{2}{l}{\textbf{Minimum dB per Stop}} \\
Mean & """
        + f"{stats['mean_min_db']:.1f}"
        + r""" \\
Median & """
        + f"{stats['median_min_db']:.1f}"
        + r""" \\
Std Dev & """
        + f"{stats['std_min_db']:.1f}"
        + r""" \\
Range & """
        + f"{stats['min_min_db']:.1f}--{stats['max_min_db']:.1f}"
        + r""" \\
\bottomrule
\end{tabular}
\end{table}
"""
    )
    output_path = output_dir / f"{CITY}_rider_table1_summary.tex"
    output_path.write_text(latex)
    click.echo(f"  Created {output_path}")


def make_table2_road_type(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 2: Statistics by road type (LaTeX)."""
    stats = compute_stats_by_road_type(df)

    rows = []
    for _, row in stats.iterrows():
        road_type = row["road_type"].replace("_", " ").title()
        rows.append(
            f"{road_type} & {int(row['n'])} & {row['mean_max_db']:.1f} & "
            f"{row['mean_min_db']:.1f} & {row['pct_above_85']:.1f}\\% \\\\"
        )

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Noise Levels by Road Type}
\label{tab:rider_road_type}
\begin{tabular}{lrrrr}
\toprule
Road Type & N & Mean Max dB & Mean Min dB & \% $\geq$85 dB \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    )

    output_path = output_dir / f"{CITY}_rider_table2_road_type.tex"
    output_path.write_text(latex)
    click.echo(f"  Created {output_path}")


def make_table3_threshold(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 3: Threshold exceedance for max_db (LaTeX)."""
    valid = df[df["status"] == "ok"]
    n_total = len(valid)

    thresholds = [70, 75, 80, 85, 88, 91]
    rows = []
    for thresh in thresholds:
        n_above = (valid["max_db"] >= thresh).sum()
        pct = 100 * n_above / n_total if n_total > 0 else 0
        rows.append(f"$\\geq${thresh} dB & {n_above:,} & {pct:.1f}\\% \\\\")

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Threshold Exceedance (Maximum dB per Stop)}
\label{tab:rider_threshold}
\begin{tabular}{lrr}
\toprule
Threshold & N Stops & Percentage \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item NIOSH REL is 85 dBA for 8-hour TWA exposure.
\end{tablenotes}
\end{table}
"""
    )

    output_path = output_dir / f"{CITY}_rider_table3_threshold.tex"
    output_path.write_text(latex)
    click.echo(f"  Created {output_path}")


def setup_matplotlib():
    """Configure matplotlib for publication-quality figures."""
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.figsize": (6, 4),
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.1,
        }
    )


def make_fig1_map(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 1: Interactive map of rider stops (Folium HTML)."""
    try:
        import folium
    except ImportError:
        click.echo("  Skipping fig1 (install folium)")
        return

    valid = df[df["status"] == "ok"].dropna(subset=["latitude", "longitude"])
    valid = valid[
        (valid["latitude"] > 28.0)
        & (valid["latitude"] < 29.0)
        & (valid["longitude"] > 76.5)
        & (valid["longitude"] < 78.0)
    ]

    if len(valid) == 0:
        click.echo("  Skipping fig1 map (no valid coordinates in Delhi bounds)")
        return

    center_lat = valid["latitude"].mean()
    center_lon = valid["longitude"].mean()

    m = folium.Map(
        location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB Positron"
    )

    def get_color(max_db):
        if max_db >= 91:
            return "#d73027"
        elif max_db >= 85:
            return "#fc8d59"
        elif max_db >= 80:
            return "#fee08b"
        elif max_db >= 75:
            return "#d9ef8b"
        else:
            return "#91cf60"

    for _, row in valid.iterrows():
        color = get_color(row["max_db"])
        road_type = row["road_type"] if row["road_type"] else "unknown"
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6,
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=(
                f"<b>Max: {row['max_db']:.1f} dB</b><br>"
                f"Min: {row['min_db']:.1f} dB<br>"
                f"Road: {road_type}<br>"
                f"Traffic stop: {row['is_traffic_stop']}<br>"
                f"Traffic jam: {row['is_traffic_jam']}"
            ),
        ).add_to(m)

    html_path = output_dir / f"{CITY}_rider_fig1_map.html"
    m.save(str(html_path))
    click.echo(f"  Created {html_path}")


def make_fig2_histogram(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 2: Histogram of max_db readings."""
    valid = df[df["status"] == "ok"]
    db = valid["max_db"]

    fig, ax = plt.subplots(figsize=(8, 5))

    bins = np.arange(50, 125, 2.5).tolist()
    ax.hist(db, bins=bins, color="#3182bd", alpha=0.7, edgecolor="white", linewidth=0.5)

    thresholds = [(85, "#d73027", "NIOSH 85 dB"), (70, "#1a9850", "70 dB")]
    for thresh, color, label in thresholds:
        pct_above = 100 * (db >= thresh).mean()
        ax.axvline(
            thresh,
            color=color,
            linestyle="--",
            linewidth=2,
            label=f"{label} ({pct_above:.1f}% above)",
        )

    ax.set_xlabel("Maximum Decibel Level (dBA)")
    ax.set_ylabel("Number of Stops")
    ax.set_title(f"Distribution of Maximum Noise Readings (N={len(db):,} stops)")
    ax.legend(loc="upper right", fontsize=8)

    output_path = output_dir / f"{CITY}_rider_fig2_histogram.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig3_histogram_min(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 3: Histogram of min_db readings."""
    valid = df[df["status"] == "ok"]
    db = valid["min_db"]

    fig, ax = plt.subplots(figsize=(8, 5))

    bins = np.arange(40, 100, 2.5).tolist()
    ax.hist(db, bins=bins, color="#2ca02c", alpha=0.7, edgecolor="white", linewidth=0.5)

    median_val = float(db.median())
    ax.axvline(
        median_val,
        color="#d73027",
        linestyle="--",
        linewidth=2,
        label=f"Median ({median_val:.1f} dB)",
    )

    ax.set_xlabel("Minimum Decibel Level (dBA)")
    ax.set_ylabel("Number of Stops")
    ax.set_title(f"Distribution of Minimum Noise Readings (N={len(db):,} stops)")
    ax.legend(loc="upper right", fontsize=8)

    output_path = output_dir / f"{CITY}_rider_fig3_histogram_min.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig4_boxplot(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 4: Boxplots of max_db by road type."""
    valid = df[df["status"] == "ok"].copy()
    valid["road_type"] = valid["road_type"].fillna("unknown")

    road_order = (
        valid.groupby("road_type")["max_db"]
        .median()
        .sort_values(ascending=False)
        .index.tolist()
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    plot_data = [valid[valid["road_type"] == rt]["max_db"].values for rt in road_order]
    counts = [len(d) for d in plot_data]
    labels = [f"{rt}\n(n={c})" for rt, c in zip(road_order, counts)]

    bp = ax.boxplot(
        plot_data, vert=True, patch_artist=True, widths=0.6, showfliers=True
    )

    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(road_order)))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.axhline(
        85, color="#d73027", linestyle="--", linewidth=2, label="NIOSH 85 dB REL"
    )
    ax.axhline(70, color="#1a9850", linestyle=":", linewidth=1.5, label="70 dB")

    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Maximum Decibel Level (dBA)")
    ax.set_title("Noise Levels by Road Type")
    ax.legend(loc="upper right")

    plt.tight_layout()
    output_path = output_dir / f"{CITY}_rider_fig4_boxplot.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig5_scatter(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 5: Scatter plot of min_db vs max_db."""
    valid = df[df["status"] == "ok"]

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.scatter(
        valid["min_db"],
        valid["max_db"],
        alpha=0.5,
        s=30,
        c="#3182bd",
        edgecolor="white",
        linewidth=0.5,
    )

    min_val = min(valid["min_db"].min(), valid["max_db"].min())
    max_val = max(valid["min_db"].max(), valid["max_db"].max())
    ax.plot([min_val, max_val], [min_val, max_val], "k--", alpha=0.3, label="1:1 line")

    corr = float(valid["min_db"].corr(valid["max_db"]))
    ax.text(
        0.05,
        0.95,
        f"r = {corr:.2f}",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
    )

    ax.axhline(
        85,
        color="#d73027",
        linestyle="--",
        linewidth=1.5,
        alpha=0.7,
        label="Max = 85 dB",
    )

    ax.set_xlabel("Minimum Decibel Level (dBA)")
    ax.set_ylabel("Maximum Decibel Level (dBA)")
    ax.set_title("Minimum vs Maximum Noise Readings")
    ax.legend(loc="lower right")

    output_path = output_dir / f"{CITY}_rider_fig5_scatter.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig6_temporal(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 6: Readings by collection day."""
    valid = df[df["status"] == "ok"].copy()

    if "day" not in valid.columns or valid["day"].isna().all():
        click.echo("  Skipping fig6 (no day information)")
        return

    day_stats = (
        valid.groupby("day")
        .agg(
            n=("max_db", "count"),
            mean_max=("max_db", "mean"),
            median_max=("max_db", "median"),
            mean_min=("min_db", "mean"),
        )
        .reset_index()
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax1 = axes[0]
    ax1.bar(day_stats["day"], day_stats["n"], color="#3182bd", alpha=0.7)
    ax1.set_xlabel("Collection Day")
    ax1.set_ylabel("Number of Stops")
    ax1.set_title("Stops per Day")

    ax2 = axes[1]
    ax2.plot(
        day_stats["day"],
        day_stats["mean_max"],
        "o-",
        color="#d73027",
        label="Mean Max dB",
        linewidth=2,
    )
    ax2.plot(
        day_stats["day"],
        day_stats["mean_min"],
        "s-",
        color="#2ca02c",
        label="Mean Min dB",
        linewidth=2,
    )
    ax2.axhline(85, color="#d73027", linestyle="--", linewidth=1, alpha=0.5)
    ax2.set_xlabel("Collection Day")
    ax2.set_ylabel("Decibel Level (dBA)")
    ax2.set_title("Noise Levels by Day")
    ax2.legend()

    plt.tight_layout()
    output_path = output_dir / f"{CITY}_rider_fig6_temporal.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def process(readings_path: Path, output_dir: Path | None = None) -> None:
    """Run the rider data analysis pipeline."""
    if output_dir is None:
        output_dir = readings_path.parent / "analysis"

    figs_dir = output_dir / "figs"
    tabs_dir = output_dir / "tabs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    tabs_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Loading rider readings from {readings_path}")
    df = load_rider_readings(readings_path)
    click.echo(f"  Loaded {len(df):,} stops")

    valid = df[df["status"] == "ok"]
    click.echo(f"  Valid readings: {len(valid):,} ({100*len(valid)/len(df):.1f}%)")
    click.echo(
        f"  Max dB range: {valid['max_db'].min():.1f} - {valid['max_db'].max():.1f}"
    )
    click.echo(
        f"  Min dB range: {valid['min_db'].min():.1f} - {valid['min_db'].max():.1f}"
    )

    road_counts = df["road_type"].value_counts(dropna=False)
    click.echo("\n  Road type distribution:")
    for rt, count in road_counts.items():
        click.echo(f"    {rt}: {count}")

    parquet_path = output_dir / f"{CITY}_rider_data.parquet"
    df.to_parquet(parquet_path)
    click.echo(f"\n  Saved rider dataset to {parquet_path}")

    setup_matplotlib()

    click.echo("\nGenerating tables...")
    make_table1_summary(df, tabs_dir)
    make_table2_road_type(df, tabs_dir)
    make_table3_threshold(df, tabs_dir)

    click.echo("\nGenerating figures...")
    make_fig1_map(df, figs_dir)
    make_fig2_histogram(df, figs_dir)
    make_fig3_histogram_min(df, figs_dir)
    make_fig4_boxplot(df, figs_dir)
    make_fig5_scatter(df, figs_dir)
    make_fig6_temporal(df, figs_dir)

    click.echo("\nRider analysis complete!")
    click.echo(f"  Tables: {tabs_dir}")
    click.echo(f"  Figures: {figs_dir}")
