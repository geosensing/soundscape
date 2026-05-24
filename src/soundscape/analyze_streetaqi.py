"""Street air quality analysis for rider-collected pollution data.

Produces publication-ready tables (LaTeX) and figures (PDF/HTML) analyzing
PM2.5 and CO2 readings against EPA/WHO health thresholds.
"""

import json
from pathlib import Path

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# EPA 2024 PM2.5 AQI Thresholds (μg/m³)
PM25_THRESHOLDS = {
    "Good": (0, 9.0),
    "Moderate": (9.1, 35.4),
    "Unhealthy for Sensitive Groups": (35.5, 55.4),
    "Unhealthy": (55.5, 125.4),
    "Very Unhealthy": (125.5, 225.4),
    "Hazardous": (225.5, float("inf")),
}

# AQI color scheme
AQI_COLORS = {
    "Good": "#00e400",
    "Moderate": "#ffff00",
    "Unhealthy for Sensitive Groups": "#ff7e00",
    "Unhealthy": "#ff0000",
    "Very Unhealthy": "#8f3f97",
    "Hazardous": "#7e0023",
}


def load_pollution_readings(path: Path) -> pd.DataFrame:
    """Load pollution CSV data into a DataFrame.

    Note: The 'co' column from the meter is actually CO2 (ppm), not CO.
    The meter displays CO2 in the 400-1500 ppm range, while CO shows 0 ppm.
    """
    df = pd.read_csv(path)
    df["captured_at"] = pd.to_datetime(df["captured_at"])
    df = df.rename(columns={"co": "co2"})
    df = df.dropna(subset=["pm25", "co2"])
    return df


def get_pm25_category(pm25: float) -> str:
    """Get EPA AQI category for PM2.5 value."""
    for category, (low, high) in PM25_THRESHOLDS.items():
        if low <= pm25 <= high:
            return category
    return "Hazardous"


def compute_summary_stats(df: pd.DataFrame) -> dict:
    """Compute overall summary statistics for pollution data."""
    return {
        "n_readings": len(df),
        "n_days": df["day"].nunique(),
        "n_itineraries": df["itinerary_id"].nunique(),
        "pm25_mean": df["pm25"].mean(),
        "pm25_median": df["pm25"].median(),
        "pm25_std": df["pm25"].std(),
        "pm25_min": df["pm25"].min(),
        "pm25_max": df["pm25"].max(),
        "pm25_q25": df["pm25"].quantile(0.25),
        "pm25_q75": df["pm25"].quantile(0.75),
        "pm25_iqr": df["pm25"].quantile(0.75) - df["pm25"].quantile(0.25),
        "co2_mean": df["co2"].mean(),
        "co2_median": df["co2"].median(),
        "co2_std": df["co2"].std(),
        "co2_min": df["co2"].min(),
        "co2_max": df["co2"].max(),
        "co2_q25": df["co2"].quantile(0.25),
        "co2_q75": df["co2"].quantile(0.75),
        "co2_iqr": df["co2"].quantile(0.75) - df["co2"].quantile(0.25),
    }


def compute_per_stop_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-stop (itinerary) statistics."""

    def stop_agg(g):
        return pd.Series(
            {
                "n_readings": len(g),
                "pm25_mean": g["pm25"].mean(),
                "pm25_median": g["pm25"].median(),
                "pm25_std": g["pm25"].std(),
                "pm25_min": g["pm25"].min(),
                "pm25_max": g["pm25"].max(),
                "co2_mean": g["co2"].mean(),
                "co2_median": g["co2"].median(),
                "latitude": g["latitude"].iloc[0] if len(g) > 0 else None,
                "longitude": g["longitude"].iloc[0] if len(g) > 0 else None,
                "pct_above_good": 100 * (g["pm25"] > 9.0).mean(),
                "pct_above_moderate": 100 * (g["pm25"] > 35.4).mean(),
                "pct_above_usg": 100 * (g["pm25"] > 55.4).mean(),
                "pct_above_unhealthy": 100 * (g["pm25"] > 125.4).mean(),
            }
        )

    stats = (
        df.groupby(["day", "itinerary_id"]).apply(stop_agg, include_groups=False).reset_index()
    )
    stats["stop_id"] = stats["day"].astype(str) + "_" + stats["itinerary_id"].astype(str)
    return stats


def make_table1_summary(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 1: Summary Statistics (LaTeX)."""
    stats = compute_summary_stats(df)

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Summary Statistics of Air Quality Readings}
\label{tab:streetaqi_summary}
\begin{tabular}{lr}
\toprule
Statistic & Value \\
\midrule
Total readings & """
        + f"{stats['n_readings']:,}"
        + r""" \\
Number of days & """
        + f"{stats['n_days']:,}"
        + r""" \\
Number of itineraries & """
        + f"{stats['n_itineraries']:,}"
        + r""" \\
\midrule
\multicolumn{2}{l}{\textbf{PM2.5 ($\mu$g/m$^3$)}} \\
\quad Mean & """
        + f"{stats['pm25_mean']:.1f}"
        + r""" \\
\quad Median & """
        + f"{stats['pm25_median']:.1f}"
        + r""" \\
\quad Standard deviation & """
        + f"{stats['pm25_std']:.1f}"
        + r""" \\
\quad IQR (Q75 - Q25) & """
        + f"{stats['pm25_iqr']:.1f}"
        + r""" \\
\quad Minimum & """
        + f"{stats['pm25_min']:.1f}"
        + r""" \\
\quad Maximum & """
        + f"{stats['pm25_max']:.1f}"
        + r""" \\
\midrule
\multicolumn{2}{l}{\textbf{CO$_2$ (ppm)}} \\
\quad Mean & """
        + f"{stats['co2_mean']:.0f}"
        + r""" \\
\quad Median & """
        + f"{stats['co2_median']:.0f}"
        + r""" \\
\quad Standard deviation & """
        + f"{stats['co2_std']:.0f}"
        + r""" \\
\quad IQR (Q75 - Q25) & """
        + f"{stats['co2_iqr']:.0f}"
        + r""" \\
\quad Minimum & """
        + f"{stats['co2_min']:.0f}"
        + r""" \\
\quad Maximum & """
        + f"{stats['co2_max']:.0f}"
        + r""" \\
\bottomrule
\end{tabular}
\end{table}
"""
    )
    output_path = output_dir / "table1_streetaqi_summary.tex"
    output_path.write_text(latex)
    click.echo(f"  Created {output_path}")


def make_table2_threshold_exceedance(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 2: PM2.5 Threshold Exceedance (LaTeX)."""
    n_total = len(df)

    thresholds = [
        (9.0, "Above Good ($>$9 $\\mu$g/m$^3$)"),
        (35.4, "Above Moderate ($>$35.4 $\\mu$g/m$^3$)"),
        (55.4, "Unhealthy for Sensitive ($>$55.4 $\\mu$g/m$^3$)"),
        (125.4, "Unhealthy ($>$125.4 $\\mu$g/m$^3$)"),
        (225.4, "Very Unhealthy ($>$225.4 $\\mu$g/m$^3$)"),
    ]

    rows = []
    for thresh, label in thresholds:
        n_above = (df["pm25"] > thresh).sum()
        pct = 100 * n_above / n_total
        rows.append(f"{label} & {n_above:,} & {pct:.1f}\\% \\\\")

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{PM2.5 Threshold Exceedance (EPA 2024 AQI Standards)}
\label{tab:streetaqi_thresholds}
\begin{tabular}{lrr}
\toprule
Threshold & N Readings & Percentage \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item Note: EPA 2024 lowered the annual PM2.5 standard from 12 to 9 $\mu$g/m$^3$.
\end{tablenotes}
\end{table}
"""
    )

    output_path = output_dir / "table2_streetaqi_threshold_exceedance.tex"
    output_path.write_text(latex)
    click.echo(f"  Created {output_path}")


def make_table3_category_distribution(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Table 3: AQI Category Distribution (LaTeX)."""
    df = df.copy()
    df["category"] = df["pm25"].apply(get_pm25_category)

    category_order = list(PM25_THRESHOLDS.keys())
    counts = df["category"].value_counts()

    rows = []
    for cat in category_order:
        n = counts.get(cat, 0)
        pct = 100 * n / len(df)
        low, high = PM25_THRESHOLDS[cat]
        if high == float("inf"):
            range_str = f"$>$225.4"
        else:
            range_str = f"{low}--{high}"
        rows.append(f"{cat} & {range_str} & {n:,} & {pct:.1f}\\% \\\\")

    latex = (
        r"""\begin{table}[htbp]
\centering
\caption{Distribution of Readings by EPA AQI Category}
\label{tab:streetaqi_categories}
\begin{tabular}{llrr}
\toprule
Category & PM2.5 Range ($\mu$g/m$^3$) & N Readings & Percentage \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    )

    output_path = output_dir / "table3_streetaqi_category_distribution.tex"
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
    """Generate Figure 1: Interactive map of readings color-coded by PM2.5 level."""
    try:
        import folium
    except ImportError:
        click.echo("  Skipping fig1 (install folium: pip install folium)")
        return

    df = df.dropna(subset=["latitude", "longitude"])
    df = df[
        (df["latitude"] > 28.0)
        & (df["latitude"] < 29.0)
        & (df["longitude"] > 76.5)
        & (df["longitude"] < 78.0)
    ]

    if len(df) == 0:
        click.echo("  Skipping fig1 map (no valid coordinates in Delhi bounds)")
        return

    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB Positron")

    for _, row in df.iterrows():
        category = get_pm25_category(row["pm25"])
        color = AQI_COLORS.get(category, "#808080")

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6,
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=(
                f"<b>PM2.5:</b> {row['pm25']:.0f} μg/m³<br>"
                f"<b>CO2:</b> {row['co2']:.0f} ppm<br>"
                f"<b>Category:</b> {category}<br>"
                f"<b>Day:</b> {row['day']}<br>"
                f"<b>Time:</b> {row['captured_at']}"
            ),
        ).add_to(m)

    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid grey; font-size: 12px;">
    <b>PM2.5 AQI Categories</b><br>
    """
    for cat, color in AQI_COLORS.items():
        low, high = PM25_THRESHOLDS[cat]
        if high == float("inf"):
            range_str = f">{low}"
        else:
            range_str = f"{low}-{high}"
        legend_html += (
            f'<i style="background:{color};width:12px;height:12px;'
            f'display:inline-block;margin-right:5px;"></i>{cat} ({range_str})<br>'
        )
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))

    html_path = output_dir / "fig1_streetaqi_map.html"
    m.save(str(html_path))
    click.echo(f"  Created {html_path}")


def make_fig2_histogram(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 2: Histograms of PM2.5 and CO2 readings."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax1 = axes[0]
    bins_pm25 = np.arange(0, df["pm25"].max() + 20, 20)
    ax1.hist(df["pm25"], bins=bins_pm25, color="#3182bd", alpha=0.7, edgecolor="white")

    threshold_lines = [
        (9.0, "Good limit", "#00e400"),
        (35.4, "Moderate limit", "#ffff00"),
        (55.4, "USG limit", "#ff7e00"),
        (125.4, "Unhealthy limit", "#ff0000"),
    ]
    for thresh, label, color in threshold_lines:
        if thresh < df["pm25"].max():
            pct_above = 100 * (df["pm25"] > thresh).mean()
            ax1.axvline(
                thresh, color=color, linestyle="--", linewidth=2, label=f"{label} ({pct_above:.0f}% above)"
            )

    ax1.set_xlabel("PM2.5 (μg/m³)")
    ax1.set_ylabel("Number of Readings")
    ax1.set_title(f"Distribution of PM2.5 Readings (N={len(df):,})")
    ax1.legend(loc="upper right", fontsize=8)

    ax2 = axes[1]
    bins_co2 = np.arange(df["co2"].min() - 50, df["co2"].max() + 100, 50)
    ax2.hist(df["co2"], bins=bins_co2, color="#e6550d", alpha=0.7, edgecolor="white")

    ax2.axvline(420, color="#2ca02c", linestyle="--", linewidth=2, label="Outdoor ambient (~420)")
    ax2.axvline(1000, color="#d73027", linestyle="--", linewidth=2, label="Indoor limit (1000)")

    ax2.set_xlabel("CO₂ (ppm)")
    ax2.set_ylabel("Number of Readings")
    ax2.set_title(f"Distribution of CO₂ Readings (N={len(df):,})")
    ax2.legend(loc="upper right", fontsize=8)

    plt.tight_layout()
    output_path = output_dir / "fig2_streetaqi_histogram.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig3_boxplot_by_day(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 3: Box plots of PM2.5 by day."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    days = sorted(df["day"].unique())

    ax1 = axes[0]
    pm25_data = [df[df["day"] == d]["pm25"].values for d in days]
    bp1 = ax1.boxplot(pm25_data, patch_artist=True, showfliers=True)

    for patch in bp1["boxes"]:
        patch.set_facecolor("#3182bd")
        patch.set_alpha(0.7)

    ax1.axhline(9.0, color="#00e400", linestyle="--", linewidth=2, label="Good limit (9)")
    ax1.axhline(35.4, color="#ffff00", linestyle="--", linewidth=2, label="Moderate limit (35.4)")
    ax1.axhline(55.4, color="#ff7e00", linestyle="--", linewidth=2, label="USG limit (55.4)")

    ax1.set_xticklabels([f"Day {d}" for d in days])
    ax1.set_xlabel("Day")
    ax1.set_ylabel("PM2.5 (μg/m³)")
    ax1.set_title("PM2.5 Distribution by Day")
    ax1.legend(loc="upper right", fontsize=8)

    ax2 = axes[1]
    co2_data = [df[df["day"] == d]["co2"].values for d in days]
    bp2 = ax2.boxplot(co2_data, patch_artist=True, showfliers=True)

    for patch in bp2["boxes"]:
        patch.set_facecolor("#e6550d")
        patch.set_alpha(0.7)

    ax2.axhline(420, color="#2ca02c", linestyle="--", linewidth=2, label="Outdoor ambient (~420)")

    ax2.set_xticklabels([f"Day {d}" for d in days])
    ax2.set_xlabel("Day")
    ax2.set_ylabel("CO₂ (ppm)")
    ax2.set_title("CO₂ Distribution by Day")
    ax2.legend(loc="upper right", fontsize=8)

    plt.tight_layout()
    output_path = output_dir / "fig3_streetaqi_boxplot_by_day.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def make_fig4_scatter_pm_co2(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate Figure 4: Scatter plot of PM2.5 vs CO2."""
    fig, ax = plt.subplots(figsize=(8, 6))

    colors = [AQI_COLORS.get(get_pm25_category(pm), "#808080") for pm in df["pm25"]]

    ax.scatter(df["co2"], df["pm25"], c=colors, alpha=0.6, s=50, edgecolors="white", linewidth=0.5)

    corr = df["pm25"].corr(df["co2"])

    z = np.polyfit(df["co2"], df["pm25"], 1)
    p = np.poly1d(z)
    x_line = np.linspace(df["co2"].min(), df["co2"].max(), 100)
    ax.plot(x_line, p(x_line), "k--", linewidth=2, alpha=0.7, label=f"Trend (r={corr:.2f})")

    ax.set_xlabel("CO₂ (ppm)")
    ax.set_ylabel("PM2.5 (μg/m³)")
    ax.set_title(f"PM2.5 vs CO₂ Correlation (N={len(df):,})")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    output_path = output_dir / "fig4_streetaqi_pm_co2_scatter.pdf"
    fig.savefig(output_path)
    plt.close(fig)
    click.echo(f"  Created {output_path}")


def process(readings_path: Path, output_dir: Path | None = None) -> None:
    """Run the full streetaqi analysis pipeline."""
    if output_dir is None:
        output_dir = Path("output/streetaqi/analysis")

    figs_dir = output_dir / "figs"
    tabs_dir = output_dir / "tabs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    tabs_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Loading pollution readings from {readings_path}")
    df = load_pollution_readings(readings_path)
    click.echo(f"  Loaded {len(df):,} readings from {df['day'].nunique()} days")
    click.echo(f"  PM2.5 range: {df['pm25'].min():.1f} - {df['pm25'].max():.1f} μg/m³")
    click.echo(f"  CO2 range: {df['co2'].min():.0f} - {df['co2'].max():.0f} ppm")

    parquet_path = output_dir / "streetaqi_analysis_data.parquet"
    df.to_parquet(parquet_path)
    click.echo(f"  Saved analysis dataset to {parquet_path}")

    stop_stats = compute_per_stop_stats(df)
    stop_parquet_path = output_dir / "streetaqi_stop_stats.parquet"
    stop_stats.to_parquet(stop_parquet_path)
    click.echo(f"  Saved per-stop statistics to {stop_parquet_path}")

    setup_matplotlib()

    click.echo("\nGenerating tables...")
    make_table1_summary(df, tabs_dir)
    make_table2_threshold_exceedance(df, tabs_dir)
    make_table3_category_distribution(df, tabs_dir)

    click.echo("\nGenerating figures...")
    make_fig1_map(df, figs_dir)
    make_fig2_histogram(df, figs_dir)
    make_fig3_boxplot_by_day(df, figs_dir)
    make_fig4_scatter_pm_co2(df, figs_dir)

    click.echo("\n" + "=" * 50)
    click.echo("STREETAQI ANALYSIS SUMMARY")
    click.echo("=" * 50)
    stats = compute_summary_stats(df)
    click.echo(f"Total readings: {stats['n_readings']:,}")
    click.echo(f"Days sampled: {stats['n_days']}")
    click.echo(f"\nPM2.5 (μg/m³):")
    click.echo(f"  Mean: {stats['pm25_mean']:.1f}, Median: {stats['pm25_median']:.1f}")
    click.echo(f"  Range: {stats['pm25_min']:.1f} - {stats['pm25_max']:.1f}")

    pct_above_good = 100 * (df["pm25"] > 9.0).mean()
    pct_above_moderate = 100 * (df["pm25"] > 35.4).mean()
    pct_above_usg = 100 * (df["pm25"] > 55.4).mean()
    pct_above_unhealthy = 100 * (df["pm25"] > 125.4).mean()

    click.echo(f"\nThreshold exceedance:")
    click.echo(f"  Above Good (>9 μg/m³): {pct_above_good:.1f}%")
    click.echo(f"  Above Moderate (>35.4 μg/m³): {pct_above_moderate:.1f}%")
    click.echo(f"  Unhealthy for Sensitive (>55.4 μg/m³): {pct_above_usg:.1f}%")
    click.echo(f"  Unhealthy (>125.4 μg/m³): {pct_above_unhealthy:.1f}%")

    click.echo(f"\nCO2 (ppm):")
    click.echo(f"  Mean: {stats['co2_mean']:.0f}, Median: {stats['co2_median']:.0f}")
    click.echo(f"  Range: {stats['co2_min']:.0f} - {stats['co2_max']:.0f}")

    click.echo("\nAnalysis complete!")
    click.echo(f"  Tables: {tabs_dir}")
    click.echo(f"  Figures: {figs_dir}")
