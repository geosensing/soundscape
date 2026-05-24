"""Noise exposure analysis for soundscape data.

Produces publication-ready tables (LaTeX) and figures (PDF) analyzing
decibel readings against WHO/NIOSH health thresholds.
"""

import json
from pathlib import Path

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

NIOSH_THRESHOLDS = {
    85: 8 * 60,
    88: 4 * 60,
    91: 2 * 60,
    94: 1 * 60,
    97: 30,
    100: 15,
}


def load_readings(path: Path, db_min: float = 30.0, db_max: float = 130.0) -> pd.DataFrame:
    """Load readings JSON into a DataFrame with flattened structure.

    Filters out physically implausible readings (outside db_min to db_max range).
    Default range 30-130 dB covers all realistic sound meter readings.
    """
    with open(path) as f:
        data = json.load(f)

    records = []
    for r in data["readings"]:
        records.append(
            {
                "frame_path": r["frame_path"],
                "video_id": r["video_id"],
                "frame_number": r["frame_number"],
                "timestamp_seconds": r["timestamp_seconds"],
                "latitude": r["gps"]["latitude"] if r.get("gps") else None,
                "longitude": r["gps"]["longitude"] if r.get("gps") else None,
                "decibel": r["reading"]["decibel"],
                "status": r["reading"]["status"],
                "confidence": r["reading"]["confidence"],
            }
        )
    df = pd.DataFrame(records)

    n_before = len(df[df["status"] == "ok"])
    df.loc[(df["decibel"] < db_min) | (df["decibel"] > db_max), "status"] = "out_of_range"
    n_after = len(df[df["status"] == "ok"])
    if n_before > n_after:
        click.echo(f"  Filtered {n_before - n_after} readings outside {db_min}-{db_max} dB range")

    return df


def compute_max_consecutive_above(series: pd.Series, threshold: float) -> int:
    """Count max consecutive readings above threshold."""
    above = (series >= threshold).astype(int)
    if above.sum() == 0:
        return 0
    groups = (above != above.shift()).cumsum()
    return above.groupby(groups).sum().max()


def compute_per_stop_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute comprehensive per-stop (video) statistics."""
    valid = df[df["status"] == "ok"].copy()
    valid = valid.sort_values(["video_id", "timestamp_seconds"])

    def stop_agg(g):
        db = g["decibel"]
        return pd.Series(
            {
                "n_readings": len(db),
                "mean_db": db.mean(),
                "median_db": db.median(),
                "std_db": db.std(),
                "min_db": db.min(),
                "max_db": db.max(),
                "p10_db": db.quantile(0.10),
                "p25_db": db.quantile(0.25),
                "p75_db": db.quantile(0.75),
                "p90_db": db.quantile(0.90),
                "pct_above_70": 100 * (db >= 70).mean(),
                "pct_above_75": 100 * (db >= 75).mean(),
                "pct_above_80": 100 * (db >= 80).mean(),
                "pct_above_85": 100 * (db >= 85).mean(),
                "pct_above_88": 100 * (db >= 88).mean(),
                "pct_above_91": 100 * (db >= 91).mean(),
                "max_consec_above_85": compute_max_consecutive_above(db, 85),
                "max_consec_above_88": compute_max_consecutive_above(db, 88),
                "latitude": g["latitude"].iloc[0],
                "longitude": g["longitude"].iloc[0],
                "duration_seconds": g["timestamp_seconds"].max() - g["timestamp_seconds"].min(),
            }
        )

    stats = valid.groupby("video_id").apply(stop_agg, include_groups=False).reset_index()
    return stats


def compute_summary_stats(df: pd.DataFrame) -> dict:
    """Compute summary statistics for the dataset."""
    valid = df[df["status"] == "ok"]
    db = valid["decibel"]

    return {
        "n_total": len(df),
        "n_valid": len(valid),
        "pct_valid": 100 * len(valid) / len(df),
        "n_stops": df["video_id"].nunique(),
        "mean": db.mean(),
        "median": db.median(),
        "std": db.std(),
        "iqr": db.quantile(0.75) - db.quantile(0.25),
        "min": db.min(),
        "max": db.max(),
        "q25": db.quantile(0.25),
        "q75": db.quantile(0.75),
    }


def make_table1_summary(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 1: Summary Statistics (LaTeX)."""
    stats = compute_summary_stats(df)

    latex = r"""\begin{table}[htbp]
\centering
\caption{Summary Statistics of Decibel Readings}
\label{tab:summary}
\begin{tabular}{lr}
\toprule
Statistic & Value \\
\midrule
Total readings & """ + f"{stats['n_total']:,}" + r""" \\
Valid readings (status = ok) & """ + f"{stats['n_valid']:,}" + r""" \\
Valid percentage & """ + f"{stats['pct_valid']:.1f}\\%" + r""" \\
Number of stops (videos) & """ + f"{stats['n_stops']:,}" + r""" \\
\midrule
Mean (dB) & """ + f"{stats['mean']:.1f}" + r""" \\
Median (dB) & """ + f"{stats['median']:.1f}" + r""" \\
Standard deviation & """ + f"{stats['std']:.1f}" + r""" \\
IQR (Q75 - Q25) & """ + f"{stats['iqr']:.1f}" + r""" \\
25th percentile & """ + f"{stats['q25']:.1f}" + r""" \\
75th percentile & """ + f"{stats['q75']:.1f}" + r""" \\
Minimum & """ + f"{stats['min']:.1f}" + r""" \\
Maximum & """ + f"{stats['max']:.1f}" + r""" \\
\bottomrule
\end{tabular}
\end{table}
"""
    output_path = output_dir / "table1_summary.tex"
    output_path.write_text(latex)
    click.echo(f"  Created {output_path}")


def make_table2_stop_distribution(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 2: Distribution of Per-Stop Summary Statistics (LaTeX)."""
    stop_stats = compute_per_stop_stats(df)

    metrics = [
        ("mean_db", "Mean dB"),
        ("median_db", "Median dB"),
        ("max_db", "Max dB"),
        ("pct_above_85", "\\% readings $\\geq$85 dB"),
        ("pct_above_88", "\\% readings $\\geq$88 dB"),
        ("max_consec_above_85", "Max consecutive $\\geq$85 dB"),
    ]

    rows = []
    for col, label in metrics:
        data = stop_stats[col]
        rows.append(
            f"{label} & {data.min():.1f} & {data.quantile(0.25):.1f} & "
            f"{data.median():.1f} & {data.quantile(0.75):.1f} & {data.max():.1f} \\\\"
        )

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Distribution of Per-Stop Summary Statistics (N="""
        + str(len(stop_stats))
        + r""" stops)}
\label{tab:stop_distribution}
\begin{tabular}{lrrrrr}
\toprule
Metric & Min & P25 & Median & P75 & Max \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    )

    output_path = output_dir / "table2_stop_distribution.tex"
    output_path.write_text(latex)
    click.echo(f"  Created {output_path}")


def make_table3_threshold_exceedance(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 3: Threshold Exceedance with Per-Stop Distribution (LaTeX)."""
    stop_stats = compute_per_stop_stats(df)
    valid = df[df["status"] == "ok"]
    n_total = len(valid)

    thresholds = [70, 75, 80, 85, 88, 91]
    rows = []
    for thresh in thresholds:
        n_above = (valid["decibel"] >= thresh).sum()
        pct_col = f"pct_above_{thresh}"
        pct_dist = stop_stats[pct_col]
        n_stops_majority = (pct_dist >= 50).sum()

        iqr_str = f"[{pct_dist.quantile(0.25):.1f}, {pct_dist.quantile(0.75):.1f}]"
        rows.append(
            f"$\\geq${thresh} dB & {n_above:,} & {100*n_above/n_total:.1f}\\% & "
            f"{pct_dist.median():.1f}\\% & {iqr_str} & {n_stops_majority} \\\\"
        )

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Noise Threshold Exceedance}
\label{tab:thresholds}
\begin{tabular}{lrrrrl}
\toprule
Threshold & N Readings & Overall \% & Median Stop \% & IQR & Stops $\geq$50\% \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item Note: ``Median Stop \%'' shows the median of per-stop percentages above threshold.
\item NIOSH REL is 85 dBA for 8-hour TWA exposure.
\end{tablenotes}
\end{table}
"""
    )

    output_path = output_dir / "table3_threshold_exceedance.tex"
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


def make_fig1_map_locations(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 1: Interactive map of data collection locations (Folium HTML)."""
    try:
        import folium
    except ImportError:
        click.echo("  Skipping fig1 (install folium)")
        return

    stop_stats = compute_per_stop_stats(df)
    stop_stats = stop_stats.dropna(subset=["latitude", "longitude"])
    stop_stats = stop_stats[
        (stop_stats["latitude"] > 28.0) & (stop_stats["latitude"] < 29.0) &
        (stop_stats["longitude"] > 76.5) & (stop_stats["longitude"] < 78.0)
    ]

    if len(stop_stats) == 0:
        click.echo("  Skipping fig1 map (no valid coordinates in Delhi bounds)")
        return

    center_lat = stop_stats["latitude"].mean()
    center_lon = stop_stats["longitude"].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB Positron")

    for _, row in stop_stats.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6,
            color="#3182bd",
            weight=2,
            fill=True,
            fill_color="#3182bd",
            fill_opacity=0.6,
            popup=(
                f"<b>{row['video_id']}</b><br>"
                f"N readings: {int(row['n_readings'])}<br>"
                f"Duration: {row['duration_seconds']:.0f}s<br>"
                f"Mean: {row['mean_db']:.1f} dB<br>"
                f"Max: {row['max_db']:.1f} dB"
            ),
        ).add_to(m)

    html_path = output_dir / "fig1_map_locations.html"
    m.save(str(html_path))
    click.echo(f"  Created {html_path}")


def make_fig2_static_map(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 2: Static PDF map of data collection locations."""
    try:
        import contextily as cx
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError:
        click.echo("  Skipping fig2 static map (install contextily, geopandas, shapely)")
        return

    stop_stats = compute_per_stop_stats(df)
    stop_stats = stop_stats.dropna(subset=["latitude", "longitude"])
    stop_stats = stop_stats[
        (stop_stats["latitude"] > 28.0) & (stop_stats["latitude"] < 29.0) &
        (stop_stats["longitude"] > 76.5) & (stop_stats["longitude"] < 78.0)
    ]

    if len(stop_stats) == 0:
        click.echo("  Skipping fig2 static map (no valid coordinates in Delhi bounds)")
        return

    geometry = [Point(xy) for xy in zip(stop_stats["longitude"], stop_stats["latitude"])]
    gdf = gpd.GeoDataFrame(stop_stats, geometry=geometry, crs="EPSG:4326")
    gdf_web = gdf.to_crs(epsg=3857)

    fig, ax = plt.subplots(figsize=(10, 10))
    gdf_web.plot(ax=ax, color="#e41a1c", markersize=60, alpha=0.8, edgecolor="white", linewidth=0.8)

    try:
        cx.add_basemap(ax, source=cx.providers.CartoDB.Positron, zoom=12)
    except Exception:
        pass

    ax.set_axis_off()
    ax.set_title(f"Data Collection Locations in Delhi (N={len(gdf)} stops)", fontsize=14, pad=10)

    output_path = output_dir / "fig2_map_static.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig3_histogram(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 3: Histogram of decibel readings with threshold lines."""
    valid = df[df["status"] == "ok"]
    db = valid["decibel"]

    fig, ax = plt.subplots(figsize=(8, 5))

    bins = np.arange(50, 105, 2)
    ax.hist(db, bins=bins, color="#3182bd", alpha=0.7, edgecolor="white", linewidth=0.5)

    thresholds = [85, 88, 91, 94, 97]
    colors = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#ffffbf"]
    for thresh, color in zip(thresholds, colors):
        pct_above = 100 * (db >= thresh).mean()
        ax.axvline(
            thresh,
            color=color,
            linestyle="--",
            linewidth=2,
            label=f"{thresh} dB ({pct_above:.1f}% above)",
        )

    ax.axvline(85, color="#d73027", linestyle="-", linewidth=3, alpha=0.5)
    ax.annotate(
        "NIOSH REL\n(85 dB)",
        xy=(85, ax.get_ylim()[1] * 0.95),
        xytext=(78, ax.get_ylim()[1] * 0.85),
        fontsize=9,
        ha="center",
        arrowprops=dict(arrowstyle="->", color="#d73027"),
    )

    ax.set_xlabel("Decibel Level (dBA)")
    ax.set_ylabel("Number of Readings")
    ax.set_title("Distribution of All Noise Readings (N={:,})".format(len(db)))
    ax.legend(loc="upper right", fontsize=8)
    ax.set_xlim(50, 105)

    output_path = output_dir / "fig3_histogram.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig4_stop_distributions(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 4: Distribution of per-stop summary statistics."""
    stop_stats = compute_per_stop_stats(df)

    fig, axes = plt.subplots(2, 3, figsize=(12, 8))

    metrics = [
        ("mean_db", "Mean dB per Stop", "dB"),
        ("median_db", "Median dB per Stop", "dB"),
        ("std_db", "Std Dev per Stop", "dB"),
        ("pct_above_85", "% Readings ≥85 dB per Stop", "%"),
        ("max_consec_above_85", "Max Consecutive ≥85 dB", "readings"),
        ("max_db", "Max dB per Stop", "dB"),
    ]

    for ax, (col, title, unit) in zip(axes.flat, metrics):
        data = stop_stats[col].dropna()
        ax.hist(data, bins=20, color="#3182bd", alpha=0.7, edgecolor="white")
        ax.axvline(data.median(), color="#d73027", linestyle="--", linewidth=2, label="Median")
        ax.axvline(data.mean(), color="#2ca02c", linestyle=":", linewidth=2, label="Mean")
        ax.set_xlabel(unit)
        ax.set_ylabel("Number of Stops")
        ax.set_title(title)
        ax.legend(fontsize=7)

    plt.tight_layout()
    output_path = output_dir / "fig4_stop_distributions.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig5_all_data_by_stop(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 5: All data points showing within/between stop variation."""
    valid = df[df["status"] == "ok"].copy()

    stop_medians = valid.groupby("video_id")["decibel"].median().sort_values()
    valid["stop_rank"] = valid["video_id"].map(
        {vid: rank for rank, vid in enumerate(stop_medians.index)}
    )

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.scatter(
        valid["stop_rank"],
        valid["decibel"],
        alpha=0.1,
        s=3,
        c="#3182bd",
        rasterized=True,
    )

    stop_summary = valid.groupby("stop_rank")["decibel"].agg(["median", "mean"]).reset_index()
    ax.plot(
        stop_summary["stop_rank"],
        stop_summary["median"],
        color="#d73027",
        linewidth=1.5,
        label="Stop median",
    )

    ax.axhline(85, color="#d73027", linestyle="--", linewidth=2, alpha=0.7, label="NIOSH 85 dB")
    ax.axhline(70, color="#1a9850", linestyle=":", linewidth=1.5, alpha=0.7, label="70 dB")

    ax.set_xlabel("Stop (ordered by median dB)")
    ax.set_ylabel("Decibel Level (dBA)")
    ax.set_title("All Readings by Stop (stops ordered by median noise level)")
    ax.legend(loc="upper left")
    ax.set_xlim(-1, valid["stop_rank"].max() + 1)

    output_path = output_dir / "fig5_all_data_by_stop.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig6_boxplot(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 6: Per-stop distribution boxplots (all stops)."""
    valid = df[df["status"] == "ok"]

    stop_medians = valid.groupby("video_id")["decibel"].median().sort_values(ascending=False)
    ordered_stops = stop_medians.index.tolist()

    n_stops = len(ordered_stops)
    if n_stops > 50:
        fig, ax = plt.subplots(figsize=(16, 6))
    else:
        fig, ax = plt.subplots(figsize=(12, 6))

    plot_data = [valid[valid["video_id"] == vid]["decibel"].values for vid in ordered_stops]

    bp = ax.boxplot(
        plot_data,
        vert=True,
        patch_artist=True,
        widths=0.7,
        showfliers=False,
    )

    for patch, vid in zip(bp["boxes"], ordered_stops):
        median = stop_medians[vid]
        if median >= 85:
            patch.set_facecolor("#d73027")
        elif median >= 80:
            patch.set_facecolor("#fc8d59")
        elif median >= 75:
            patch.set_facecolor("#fee08b")
        else:
            patch.set_facecolor("#91cf60")
        patch.set_alpha(0.7)

    ax.axhline(85, color="#d73027", linestyle="--", linewidth=2, label="NIOSH 85 dB REL")
    ax.axhline(70, color="#1a9850", linestyle=":", linewidth=1.5, label="70 dB")

    ax.set_xlabel(f"Stop (N={n_stops}, ordered by median dB, highest first)")
    ax.set_ylabel("Decibel Level (dBA)")
    ax.set_title("Noise Distribution by Stop")
    ax.legend(loc="lower right")
    ax.set_xticklabels([])

    output_path = output_dir / "fig6_per_stop_boxplot.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig7_exceedance(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 7: Exceedance curves showing per-stop variation."""
    valid = df[df["status"] == "ok"]

    thresholds = np.arange(50, 100, 1)

    overall_exceed = [100 * (valid["decibel"] >= t).mean() for t in thresholds]

    stop_exceed = []
    for t in thresholds:
        exc = valid.groupby("video_id")["decibel"].apply(lambda x: 100 * (x >= t).mean())
        stop_exceed.append(exc)

    stop_exceed_df = pd.DataFrame(stop_exceed, index=thresholds).T

    fig, ax = plt.subplots(figsize=(10, 6))

    for vid in stop_exceed_df.index:
        ax.plot(thresholds, stop_exceed_df.loc[vid], color="#3182bd", alpha=0.15, linewidth=0.5)

    ax.plot(thresholds, overall_exceed, color="#d73027", linewidth=3, label="Overall")

    p25 = [stop_exceed_df[t].quantile(0.25) for t in thresholds]
    p75 = [stop_exceed_df[t].quantile(0.75) for t in thresholds]
    ax.fill_between(thresholds, p25, p75, alpha=0.3, color="#2ca02c", label="IQR across stops")

    for t in [85, 88, 91]:
        overall = 100 * (valid["decibel"] >= t).mean()
        ax.plot(t, overall, "o", color="#d73027", markersize=8, zorder=5)
        ax.annotate(f"{t}dB: {overall:.0f}%", xy=(t, overall), xytext=(t + 1, overall + 3))

    ax.axvline(85, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Decibel Threshold (dBA)")
    ax.set_ylabel("% Readings Above Threshold")
    ax.set_title("Exceedance Curves (each line = one stop)")
    ax.legend(loc="upper right")
    ax.set_xlim(50, 100)
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)

    output_path = output_dir / "fig7_exceedance_curves.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig8_temporal(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 8: Temporal pattern within videos."""
    valid = df[df["status"] == "ok"].copy()

    max_ts = valid.groupby("video_id")["timestamp_seconds"].transform("max")
    valid["normalized_time"] = valid["timestamp_seconds"] / max_ts.replace(0, 1)

    bins = np.linspace(0, 1, 21)
    valid["time_bin"] = pd.cut(valid["normalized_time"], bins=bins, labels=False)

    temporal = valid.groupby("time_bin")["decibel"].agg(["mean", "std", "count"]).reset_index()
    temporal["se"] = temporal["std"] / np.sqrt(temporal["count"])
    temporal["time_pct"] = (temporal["time_bin"] + 0.5) * 5

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.fill_between(
        temporal["time_pct"],
        temporal["mean"] - 1.96 * temporal["se"],
        temporal["mean"] + 1.96 * temporal["se"],
        alpha=0.3,
        color="#3182bd",
    )
    ax.plot(temporal["time_pct"], temporal["mean"], color="#3182bd", linewidth=2)

    ax.axhline(85, color="#d73027", linestyle="--", linewidth=1.5, label="NIOSH 85 dB REL")

    ax.set_xlabel("Position Within Video (%)")
    ax.set_ylabel("Mean Decibel Level (dBA)")
    ax.set_title("Noise Level by Position Within Recording")
    ax.set_xlim(0, 100)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    output_path = output_dir / "fig8_temporal_pattern.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def process(readings_path: Path, output_dir: Path | None = None) -> None:
    """Run the full analysis pipeline."""
    if output_dir is None:
        output_dir = Path("output/analysis")

    figs_dir = output_dir / "figs"
    tabs_dir = output_dir / "tabs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    tabs_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Loading readings from {readings_path}")
    df = load_readings(readings_path)
    click.echo(f"  Loaded {len(df):,} readings from {df['video_id'].nunique()} videos")

    valid = df[df["status"] == "ok"]
    click.echo(f"  Valid readings: {len(valid):,} ({100*len(valid)/len(df):.1f}%)")
    click.echo(f"  Decibel range: {valid['decibel'].min():.1f} - {valid['decibel'].max():.1f} dB")

    parquet_path = output_dir / "analysis_data.parquet"
    df.to_parquet(parquet_path)
    click.echo(f"  Saved analysis dataset to {parquet_path}")

    stop_stats = compute_per_stop_stats(df)
    stop_parquet_path = output_dir / "stop_stats.parquet"
    stop_stats.to_parquet(stop_parquet_path)
    click.echo(f"  Saved per-stop statistics to {stop_parquet_path}")

    setup_matplotlib()

    click.echo("\nGenerating tables...")
    make_table1_summary(df, tabs_dir)
    make_table2_stop_distribution(df, tabs_dir)
    make_table3_threshold_exceedance(df, tabs_dir)

    click.echo("\nGenerating figures...")
    make_fig1_map_locations(df, figs_dir)
    make_fig2_static_map(df, figs_dir)
    make_fig3_histogram(df, figs_dir)
    make_fig4_stop_distributions(df, figs_dir)
    make_fig5_all_data_by_stop(df, figs_dir)
    make_fig6_boxplot(df, figs_dir)
    make_fig7_exceedance(df, figs_dir)
    make_fig8_temporal(df, figs_dir)

    click.echo("\nAnalysis complete!")
    click.echo(f"  Tables: {tabs_dir}")
    click.echo(f"  Figures: {figs_dir}")
