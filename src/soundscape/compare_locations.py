"""Compare rider and GoPro data collection locations.

Finds spatial overlap between rider-collected stops and GoPro stops,
enabling analysis of noise by road type and traffic conditions.
"""

import glob as glob_module
import json
from pathlib import Path

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CITY = "delhi"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in meters."""
    R = 6371000
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)

    a = (
        np.sin(delta_phi / 2) ** 2
        + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    )
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c


def load_rider_stops(path: Path) -> pd.DataFrame:
    """Load rider readings and return one row per stop."""
    with open(path) as f:
        data = json.load(f)

    records = []
    for r in data["readings"]:
        reading = r.get("reading", {})
        metadata = r.get("metadata", {})
        if r.get("gps"):
            records.append(
                {
                    "rider_stop_id": r.get("id"),
                    "rider_timestamp": r.get("timestamp"),
                    "rider_lat": r["gps"]["latitude"],
                    "rider_lon": r["gps"]["longitude"],
                    "rider_min_db": reading.get("min_db"),
                    "rider_max_db": reading.get("max_db"),
                    "rider_status": reading.get("status", "ok"),
                    "road_type": metadata.get("road_type"),
                    "road_name": metadata.get("road_name"),
                    "is_traffic_stop": metadata.get("is_traffic_stop", False),
                    "is_traffic_jam": metadata.get("is_traffic_jam", False),
                    "address": metadata.get("address"),
                    "day": metadata.get("day"),
                    "itinerary": metadata.get("itinerary"),
                }
            )

    return pd.DataFrame(records)


def load_gopro_stops(paths: list[Path]) -> pd.DataFrame:
    """Load GoPro readings and compute per-stop statistics."""
    all_readings = []

    for path in paths:
        with open(path) as f:
            data = json.load(f)

        for r in data["readings"]:
            if r.get("gps") and r["reading"]["status"] == "ok":
                all_readings.append(
                    {
                        "video_id": r["video_id"],
                        "latitude": r["gps"]["latitude"],
                        "longitude": r["gps"]["longitude"],
                        "decibel": r["reading"]["decibel"],
                        "timestamp_seconds": r["timestamp_seconds"],
                    }
                )

    df = pd.DataFrame(all_readings)

    if len(df) == 0:
        return pd.DataFrame()

    stop_stats = (
        df.groupby("video_id")
        .agg(
            gopro_lat=("latitude", "first"),
            gopro_lon=("longitude", "first"),
            gopro_n_readings=("decibel", "count"),
            gopro_mean_db=("decibel", "mean"),
            gopro_median_db=("decibel", "median"),
            gopro_max_db=("decibel", "max"),
            gopro_min_db=("decibel", "min"),
            gopro_std_db=("decibel", "std"),
            gopro_pct_above_85=("decibel", lambda x: 100 * (x >= 85).mean()),
        )
        .reset_index()
    )
    stop_stats.rename(columns={"video_id": "gopro_stop_id"}, inplace=True)

    return stop_stats


def find_nearby_stops(
    rider_df: pd.DataFrame, gopro_df: pd.DataFrame, max_distance_m: float
) -> pd.DataFrame:
    """Find GoPro stops within max_distance_m of each rider stop."""
    matches = []

    for _, rider_row in rider_df.iterrows():
        rider_lat = float(rider_row["rider_lat"])
        rider_lon = float(rider_row["rider_lon"])

        for _, gopro_row in gopro_df.iterrows():
            dist = haversine_distance(
                rider_lat,
                rider_lon,
                float(gopro_row["gopro_lat"]),
                float(gopro_row["gopro_lon"]),
            )

            if dist <= max_distance_m:
                match = {
                    **rider_row.to_dict(),
                    **gopro_row.to_dict(),
                    "distance_m": dist,
                }
                matches.append(match)

    return pd.DataFrame(matches)


def make_fig1_map(
    rider_df: pd.DataFrame,
    gopro_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Generate Figure 1: Interactive map showing both datasets with matches."""
    try:
        import folium
    except ImportError:
        click.echo("  Skipping fig1 (install folium)")
        return

    valid_rider = rider_df.dropna(subset=["rider_lat", "rider_lon"])
    valid_gopro = gopro_df.dropna(subset=["gopro_lat", "gopro_lon"])

    all_lats = list(valid_rider["rider_lat"]) + list(valid_gopro["gopro_lat"])
    all_lons = list(valid_rider["rider_lon"]) + list(valid_gopro["gopro_lon"])

    if not all_lats:
        click.echo("  Skipping fig1 map (no coordinates)")
        return

    center_lat = float(np.mean(all_lats))
    center_lon = float(np.mean(all_lons))

    m = folium.Map(
        location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB Positron"
    )

    matched_rider_ids = (
        set(matches_df["rider_stop_id"]) if len(matches_df) > 0 else set()
    )
    matched_gopro_ids = (
        set(matches_df["gopro_stop_id"]) if len(matches_df) > 0 else set()
    )

    for _, row in valid_rider.iterrows():
        is_matched = row["rider_stop_id"] in matched_rider_ids
        color = "#e41a1c" if is_matched else "#377eb8"
        folium.CircleMarker(
            location=[float(row["rider_lat"]), float(row["rider_lon"])],
            radius=6,
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=(
                f"<b>Rider Stop</b><br>"
                f"Max: {row['rider_max_db']:.1f} dB<br>"
                f"Min: {row['rider_min_db']:.1f} dB<br>"
                f"Road: {row['road_type']}<br>"
                f"{'<b>MATCHED</b>' if is_matched else 'No match'}"
            ),
        ).add_to(m)

    for _, row in valid_gopro.iterrows():
        is_matched = row["gopro_stop_id"] in matched_gopro_ids
        color = "#4daf4a" if is_matched else "#984ea3"
        folium.CircleMarker(
            location=[float(row["gopro_lat"]), float(row["gopro_lon"])],
            radius=5,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.5,
            popup=(
                f"<b>GoPro Stop</b><br>"
                f"Mean: {row['gopro_mean_db']:.1f} dB<br>"
                f"Max: {row['gopro_max_db']:.1f} dB<br>"
                f"N readings: {int(row['gopro_n_readings'])}<br>"
                f"{'<b>MATCHED</b>' if is_matched else 'No match'}"
            ),
        ).add_to(m)

    if len(matches_df) > 0:
        for _, row in matches_df.iterrows():
            folium.PolyLine(
                locations=[
                    [float(row["rider_lat"]), float(row["rider_lon"])],
                    [float(row["gopro_lat"]), float(row["gopro_lon"])],
                ],
                color="#ff7f00",
                weight=2,
                opacity=0.5,
            ).add_to(m)

    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background-color: white; padding: 10px; border: 2px solid gray;
                border-radius: 5px;">
        <b>Legend</b><br>
        <i style="background: #e41a1c; border-radius: 50%; width: 12px;
           height: 12px; display: inline-block;"></i> Rider (matched)<br>
        <i style="background: #377eb8; border-radius: 50%; width: 12px;
           height: 12px; display: inline-block;"></i> Rider (unmatched)<br>
        <i style="background: #4daf4a; border-radius: 50%; width: 12px;
           height: 12px; display: inline-block;"></i> GoPro (matched)<br>
        <i style="background: #984ea3; border-radius: 50%; width: 12px;
           height: 12px; display: inline-block;"></i> GoPro (unmatched)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    html_path = output_dir / f"{CITY}_compare_fig1_map.html"
    m.save(str(html_path))
    click.echo(f"  Created {html_path}")


def make_fig2_correlation(matches_df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 2: Scatter plot of rider max_db vs GoPro mean_db."""
    if len(matches_df) == 0:
        click.echo("  Skipping fig2 (no matches)")
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.scatter(
        matches_df["gopro_mean_db"],
        matches_df["rider_max_db"],
        alpha=0.6,
        s=50,
        c="#3182bd",
        edgecolor="white",
        linewidth=0.5,
    )

    corr = float(matches_df["gopro_mean_db"].corr(matches_df["rider_max_db"]))
    ax.text(
        0.05,
        0.95,
        f"r = {corr:.2f}\nn = {len(matches_df)}",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
    )

    min_val = min(matches_df["gopro_mean_db"].min(), matches_df["rider_max_db"].min())
    max_val = max(matches_df["gopro_mean_db"].max(), matches_df["rider_max_db"].max())
    ax.plot([min_val, max_val], [min_val, max_val], "k--", alpha=0.3, label="1:1 line")

    ax.axhline(85, color="#d73027", linestyle="--", linewidth=1.5, alpha=0.7)
    ax.axvline(85, color="#d73027", linestyle="--", linewidth=1.5, alpha=0.7)

    ax.set_xlabel("GoPro Mean dB (continuous)")
    ax.set_ylabel("Rider Max dB (spot reading)")
    ax.set_title("Noise Comparison at Matched Locations")
    ax.legend(loc="lower right")

    output_path = output_dir / f"{CITY}_compare_fig2_correlation.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig3_traffic(matches_df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 3: GoPro noise at traffic stops/jams vs not."""
    if len(matches_df) == 0:
        click.echo("  Skipping fig3 (no matches)")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax1 = axes[0]
    traffic_stop = matches_df["is_traffic_stop"].astype(bool)
    groups = [
        matches_df[~traffic_stop]["gopro_mean_db"],
        matches_df[traffic_stop]["gopro_mean_db"],
    ]
    labels = [f"No\n(n={len(groups[0])})", f"Yes\n(n={len(groups[1])})"]
    bp = ax1.boxplot(groups, labels=labels, patch_artist=True)
    bp["boxes"][0].set_facecolor("#91cf60")
    bp["boxes"][1].set_facecolor("#fc8d59")
    ax1.axhline(85, color="#d73027", linestyle="--", linewidth=1.5)
    ax1.set_xlabel("Traffic Stop")
    ax1.set_ylabel("GoPro Mean dB")
    ax1.set_title("GoPro Noise at Traffic Stops")

    ax2 = axes[1]
    traffic_jam = matches_df["is_traffic_jam"].astype(bool)
    groups = [
        matches_df[~traffic_jam]["gopro_mean_db"],
        matches_df[traffic_jam]["gopro_mean_db"],
    ]
    labels = [f"No\n(n={len(groups[0])})", f"Yes\n(n={len(groups[1])})"]
    bp = ax2.boxplot(groups, labels=labels, patch_artist=True)
    bp["boxes"][0].set_facecolor("#91cf60")
    bp["boxes"][1].set_facecolor("#fc8d59")
    ax2.axhline(85, color="#d73027", linestyle="--", linewidth=1.5)
    ax2.set_xlabel("Traffic Jam")
    ax2.set_ylabel("GoPro Mean dB")
    ax2.set_title("GoPro Noise at Traffic Jams")

    plt.tight_layout()
    output_path = output_dir / f"{CITY}_compare_fig3_traffic.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig4_road_type(matches_df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 4: GoPro noise by road type (from rider metadata)."""
    if len(matches_df) == 0:
        click.echo("  Skipping fig4 (no matches)")
        return

    df = matches_df.copy()
    df["road_type"] = df["road_type"].fillna("unknown")

    road_order = (
        df.groupby("road_type")["gopro_mean_db"]
        .median()
        .sort_values(ascending=False)
        .index.tolist()
    )

    if len(road_order) == 0:
        click.echo("  Skipping fig4 (no road types)")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    plot_data = [df[df["road_type"] == rt]["gopro_mean_db"].values for rt in road_order]
    counts = [len(d) for d in plot_data]
    labels = [f"{rt}\n(n={c})" for rt, c in zip(road_order, counts)]

    plot_data = [d for d in plot_data if len(d) > 0]
    labels = [
        label
        for label, d in zip(
            labels,
            [df[df["road_type"] == rt]["gopro_mean_db"].values for rt in road_order],
        )
        if len(d) > 0
    ]

    if not plot_data:
        click.echo("  Skipping fig4 (no data)")
        return

    bp = ax.boxplot(plot_data, vert=True, patch_artist=True, widths=0.6)

    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(plot_data)))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.axhline(
        85, color="#d73027", linestyle="--", linewidth=2, label="NIOSH 85 dB REL"
    )

    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("GoPro Mean dB")
    ax.set_title("GoPro Noise by Road Type (from Rider Metadata)")
    ax.legend(loc="upper right")

    plt.tight_layout()
    output_path = output_dir / f"{CITY}_compare_fig4_road_type.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_table2_validation(matches_df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 2: Validation metrics comparing GoPro vs Rider at matched stops."""
    if len(matches_df) == 0:
        click.echo("  Skipping table2 (no matches)")
        return

    valid = matches_df.dropna(
        subset=["gopro_min_db", "gopro_max_db", "rider_min_db", "rider_max_db"]
    )
    if len(valid) == 0:
        click.echo("  Skipping table2 (no valid data)")
        return

    min_corr = float(valid["gopro_min_db"].corr(valid["rider_min_db"]))
    max_corr = float(valid["gopro_max_db"].corr(valid["rider_max_db"]))

    min_diff = (valid["gopro_min_db"] - valid["rider_min_db"]).abs()
    max_diff = (valid["gopro_max_db"] - valid["rider_max_db"]).abs()

    min_mean_diff = float(min_diff.mean())
    max_mean_diff = float(max_diff.mean())

    min_within_5 = 100 * (min_diff < 5).mean()
    max_within_5 = 100 * (max_diff < 5).mean()

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Validation: GoPro vs Rider Measurements at Matched Locations}
\label{tab:validation}
\begin{tabular}{lrr}
\toprule
Metric & Min dB & Max dB \\
\midrule
N matched pairs & """
        + f"{len(valid)}"
        + r""" & """
        + f"{len(valid)}"
        + r""" \\
Correlation (r) & """
        + f"{min_corr:.2f}"
        + r""" & """
        + f"{max_corr:.2f}"
        + r""" \\
Mean absolute difference & """
        + f"{min_mean_diff:.1f}"
        + r""" dB & """
        + f"{max_mean_diff:.1f}"
        + r""" dB \\
\% within 5 dB & """
        + f"{min_within_5:.1f}"
        + r"""\% & """
        + f"{max_within_5:.1f}"
        + r"""\% \\
\midrule
\multicolumn{3}{l}{\textbf{GoPro Statistics}} \\
Mean & """
        + f"{valid['gopro_min_db'].mean():.1f}"
        + r""" dB & """
        + f"{valid['gopro_max_db'].mean():.1f}"
        + r""" dB \\
Median & """
        + f"{valid['gopro_min_db'].median():.1f}"
        + r""" dB & """
        + f"{valid['gopro_max_db'].median():.1f}"
        + r""" dB \\
\midrule
\multicolumn{3}{l}{\textbf{Rider Statistics}} \\
Mean & """
        + f"{valid['rider_min_db'].mean():.1f}"
        + r""" dB & """
        + f"{valid['rider_max_db'].mean():.1f}"
        + r""" dB \\
Median & """
        + f"{valid['rider_min_db'].median():.1f}"
        + r""" dB & """
        + f"{valid['rider_max_db'].median():.1f}"
        + r""" dB \\
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item Matched within 100m radius. GoPro values are per-stop min/max from continuous readings.
\end{tablenotes}
\end{table}
"""
    )

    output_path = output_dir / f"{CITY}_compare_table2_validation.tex"
    output_path.write_text(latex)
    click.echo(f"  Created {output_path}")


def make_fig5_validation(matches_df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 5: Validation scatter plots GoPro vs Rider min/max."""
    if len(matches_df) == 0:
        click.echo("  Skipping fig5 (no matches)")
        return

    valid = matches_df.dropna(
        subset=["gopro_min_db", "gopro_max_db", "rider_min_db", "rider_max_db"]
    )
    if len(valid) == 0:
        click.echo("  Skipping fig5 (no valid data)")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax1 = axes[0]
    ax1.scatter(
        valid["rider_min_db"],
        valid["gopro_min_db"],
        alpha=0.6,
        s=50,
        c="#3182bd",
        edgecolor="white",
        linewidth=0.5,
    )
    min_corr = float(valid["rider_min_db"].corr(valid["gopro_min_db"]))
    min_mad = float((valid["gopro_min_db"] - valid["rider_min_db"]).abs().mean())
    ax1.text(
        0.05,
        0.95,
        f"r = {min_corr:.2f}\nMAD = {min_mad:.1f} dB",
        transform=ax1.transAxes,
        fontsize=10,
        verticalalignment="top",
    )
    min_val = min(valid["rider_min_db"].min(), valid["gopro_min_db"].min())
    max_val = max(valid["rider_min_db"].max(), valid["gopro_min_db"].max())
    ax1.plot([min_val, max_val], [min_val, max_val], "k--", alpha=0.3, label="1:1 line")
    ax1.set_xlabel("Rider Min dB")
    ax1.set_ylabel("GoPro Min dB")
    ax1.set_title("Minimum dB Comparison")
    ax1.legend(loc="lower right")

    ax2 = axes[1]
    ax2.scatter(
        valid["rider_max_db"],
        valid["gopro_max_db"],
        alpha=0.6,
        s=50,
        c="#e41a1c",
        edgecolor="white",
        linewidth=0.5,
    )
    max_corr = float(valid["rider_max_db"].corr(valid["gopro_max_db"]))
    max_mad = float((valid["gopro_max_db"] - valid["rider_max_db"]).abs().mean())
    ax2.text(
        0.05,
        0.95,
        f"r = {max_corr:.2f}\nMAD = {max_mad:.1f} dB",
        transform=ax2.transAxes,
        fontsize=10,
        verticalalignment="top",
    )
    min_val = min(valid["rider_max_db"].min(), valid["gopro_max_db"].min())
    max_val = max(valid["rider_max_db"].max(), valid["gopro_max_db"].max())
    ax2.plot([min_val, max_val], [min_val, max_val], "k--", alpha=0.3, label="1:1 line")
    ax2.axhline(85, color="#d73027", linestyle="--", linewidth=1.5, alpha=0.5)
    ax2.axvline(85, color="#d73027", linestyle="--", linewidth=1.5, alpha=0.5)
    ax2.set_xlabel("Rider Max dB")
    ax2.set_ylabel("GoPro Max dB")
    ax2.set_title("Maximum dB Comparison")
    ax2.legend(loc="lower right")

    plt.suptitle(
        f"Validation: GoPro vs Rider at Matched Locations (N={len(valid)})", y=1.02
    )
    plt.tight_layout()
    output_path = output_dir / f"{CITY}_compare_fig5_validation.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_table1_summary(matches_df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 1: Comparison summary statistics."""
    if len(matches_df) == 0:
        click.echo("  Skipping table1 (no matches)")
        return

    rows = []

    gopro_mean = matches_df["gopro_mean_db"].mean()
    rider_mean = matches_df["rider_max_db"].mean()
    dist_mean = matches_df["distance_m"].mean()
    rows.append(
        f"Overall & {len(matches_df)} & {gopro_mean:.1f} & "
        f"{rider_mean:.1f} & {dist_mean:.1f} \\\\"
    )

    rows.append("\\midrule")
    rows.append("\\multicolumn{5}{l}{\\textbf{By Traffic Stop}} \\\\")
    for is_stop, label in [(False, "No"), (True, "Yes")]:
        subset = matches_df[matches_df["is_traffic_stop"] == is_stop]
        if len(subset) > 0:
            g = subset["gopro_mean_db"].mean()
            r = subset["rider_max_db"].mean()
            d = subset["distance_m"].mean()
            rows.append(f"{label} & {len(subset)} & {g:.1f} & {r:.1f} & {d:.1f} \\\\")

    rows.append("\\midrule")
    rows.append("\\multicolumn{5}{l}{\\textbf{By Traffic Jam}} \\\\")
    for is_jam, label in [(False, "No"), (True, "Yes")]:
        subset = matches_df[matches_df["is_traffic_jam"] == is_jam]
        if len(subset) > 0:
            g = subset["gopro_mean_db"].mean()
            r = subset["rider_max_db"].mean()
            d = subset["distance_m"].mean()
            rows.append(f"{label} & {len(subset)} & {g:.1f} & {r:.1f} & {d:.1f} \\\\")

    rows.append("\\midrule")
    rows.append("\\multicolumn{5}{l}{\\textbf{By Road Type}} \\\\")
    road_stats = (
        matches_df.groupby("road_type")
        .agg(
            n=("gopro_mean_db", "count"),
            gopro_mean=("gopro_mean_db", "mean"),
            rider_mean=("rider_max_db", "mean"),
            dist_mean=("distance_m", "mean"),
        )
        .reset_index()
    )
    road_stats = road_stats.sort_values("n", ascending=False)

    for _, row in road_stats.iterrows():
        rt = row["road_type"]
        road_type = str(rt).replace("_", " ").title() if rt else "Unknown"
        n = int(row["n"])
        g = row["gopro_mean"]
        r = row["rider_mean"]
        d = row["dist_mean"]
        rows.append(f"{road_type} & {n} & {g:.1f} & {r:.1f} & {d:.1f} \\\\")

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Comparison of Matched Rider and GoPro Stops}
\label{tab:compare_summary}
\begin{tabular}{lrrrr}
\toprule
Category & N & GoPro Mean dB & Rider Max dB & Mean Dist (m) \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item Matches within 100m radius.
\end{tablenotes}
\end{table}
"""
    )

    output_path = output_dir / f"{CITY}_compare_table1_summary.tex"
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


def process(
    rider_path: Path,
    gopro_pattern: str,
    output_dir: Path | None = None,
    max_distance_m: float = 100.0,
) -> None:
    """Run the location comparison pipeline."""
    if output_dir is None:
        output_dir = Path("output/comparison")

    figs_dir = output_dir / "figs"
    tabs_dir = output_dir / "tabs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    tabs_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Loading rider data from {rider_path}")
    rider_df = load_rider_stops(rider_path)
    click.echo(f"  Loaded {len(rider_df):,} rider stops with GPS")

    gopro_paths = [Path(p) for p in glob_module.glob(gopro_pattern)]
    if not gopro_paths:
        click.echo(f"  No GoPro files found matching {gopro_pattern}")
        return

    click.echo(f"\nLoading GoPro data from {len(gopro_paths)} files")
    gopro_df = load_gopro_stops(gopro_paths)
    click.echo(f"  Loaded {len(gopro_df):,} GoPro stops")

    click.echo(f"\nFinding matches within {max_distance_m}m...")
    matches_df = find_nearby_stops(rider_df, gopro_df, max_distance_m)
    click.echo(f"  Found {len(matches_df):,} matches")

    if len(matches_df) > 0:
        n_unique_rider = matches_df["rider_stop_id"].nunique()
        n_unique_gopro = matches_df["gopro_stop_id"].nunique()
        click.echo(f"  Unique rider stops matched: {n_unique_rider}")
        click.echo(f"  Unique GoPro stops matched: {n_unique_gopro}")
        click.echo(f"  Mean match distance: {matches_df['distance_m'].mean():.1f}m")

    parquet_path = output_dir / f"{CITY}_compare_matched.parquet"
    matches_df.to_parquet(parquet_path)
    click.echo(f"\n  Saved matches to {parquet_path}")

    setup_matplotlib()

    click.echo("\nGenerating outputs...")
    make_fig1_map(rider_df, gopro_df, matches_df, figs_dir)
    make_fig2_correlation(matches_df, figs_dir)
    make_fig3_traffic(matches_df, figs_dir)
    make_fig4_road_type(matches_df, figs_dir)
    make_fig5_validation(matches_df, figs_dir)
    make_table1_summary(matches_df, tabs_dir)
    make_table2_validation(matches_df, tabs_dir)

    click.echo("\nLocation comparison complete!")
    click.echo(f"  Tables: {tabs_dir}")
    click.echo(f"  Figures: {figs_dir}")
