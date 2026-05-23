"""Extract GPS telemetry from GoPro videos using exiftool."""

import json
import math
import re
import statistics
import subprocess
from pathlib import Path

from .utils import (build_output_prefix, ensure_output_dirs, find_videos,
                    load_config)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two GPS coordinates."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_dms_to_decimal(dms_str: str) -> float | None:
    """Convert DMS coordinate string to decimal degrees.

    Handles formats like:
    - "28 deg 34' 47.76\" N"
    - "77 deg 13' 50.26\" E"
    """
    if not dms_str:
        return None

    pattern = r"(\d+)\s*deg\s*(\d+)'\s*([\d.]+)\"\s*([NSEW])"
    match = re.match(pattern, dms_str.strip())
    if not match:
        return None

    degrees = float(match.group(1))
    minutes = float(match.group(2))
    seconds = float(match.group(3))
    direction = match.group(4)

    decimal = degrees + minutes / 60 + seconds / 3600
    if direction in ("S", "W"):
        decimal = -decimal

    return decimal


def parse_altitude(alt_str: str) -> float | None:
    """Parse altitude string like '209.607 m' to float."""
    if not alt_str:
        return None

    match = re.match(r"([\d.]+)\s*m", alt_str.strip())
    if match:
        return float(match.group(1))
    return None


def extract_gps_telemetry(video_path: Path) -> list[dict]:
    """Extract full GPS timeseries from GoPro video using raw exiftool output.

    Uses -G flag for grouped output and parses GoPro GPS blocks with regex
    to extract all GPS points (typically ~10 per second of video).
    """
    result = subprocess.run(
        [
            "exiftool",
            "-G",
            "-ee",
            "-api",
            "LargeFileSupport=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    raw_output = result.stdout
    points = []

    gps_pattern = re.compile(
        r"\[GoPro\]\s+GPS Latitude\s+:\s+(.+?)\n"
        r"\[GoPro\]\s+GPS Longitude\s+:\s+(.+?)\n"
        r"\[GoPro\]\s+GPS Altitude\s+:\s+(.+?)\n"
        r"\[GoPro\]\s+GPS Speed\s+:\s+(.+?)\n"
        r"\[GoPro\]\s+GPS Speed 3D\s+:\s+(.+?)\n"
        r"\[GoPro\]\s+GPS Date Time\s+:\s+(.+?)\n",
        re.MULTILINE,
    )

    for match in gps_pattern.finditer(raw_output):
        lat_str, lon_str, alt_str, speed_str, speed_3d_str, datetime_str = (
            match.groups()
        )

        lat = parse_dms_to_decimal(lat_str)
        lon = parse_dms_to_decimal(lon_str)

        if lat is None or lon is None:
            continue

        alt = parse_altitude(alt_str)

        try:
            speed = float(speed_str) if speed_str else None
        except ValueError:
            speed = None

        try:
            speed_3d = float(speed_3d_str) if speed_3d_str else None
        except ValueError:
            speed_3d = None

        points.append(
            {
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "datetime": datetime_str.strip() if datetime_str else None,
                "speed": speed,
                "speed_3d": speed_3d,
            }
        )

    return points


def compute_gps_stats(points: list[dict], max_spread_meters: float = 50) -> dict:
    """Compute GPS statistics and median location."""
    if not points:
        return {
            "point_count": 0,
            "median_latitude": None,
            "median_longitude": None,
            "median_altitude": None,
            "max_spread_meters": None,
            "spread_valid": None,
        }

    lats = [p["latitude"] for p in points if p["latitude"] is not None]
    lons = [p["longitude"] for p in points if p["longitude"] is not None]
    alts = [p["altitude"] for p in points if p.get("altitude") is not None]

    if not lats or not lons:
        return {
            "point_count": 0,
            "median_latitude": None,
            "median_longitude": None,
            "median_altitude": None,
            "max_spread_meters": None,
            "spread_valid": None,
        }

    median_lat = statistics.median(lats)
    median_lon = statistics.median(lons)
    median_alt = statistics.median(alts) if alts else None

    max_dist = 0.0
    for p in points:
        if p["latitude"] is not None and p["longitude"] is not None:
            dist = haversine_distance(
                median_lat, median_lon, p["latitude"], p["longitude"]
            )
            max_dist = max(max_dist, dist)

    return {
        "point_count": len(points),
        "median_latitude": median_lat,
        "median_longitude": median_lon,
        "median_altitude": median_alt,
        "max_spread_meters": round(max_dist, 2),
        "spread_valid": max_dist <= max_spread_meters,
    }


def save_gps(gps_data: dict, output_path: Path) -> None:
    """Save GPS data to JSON file."""
    with open(output_path, "w") as f:
        json.dump(gps_data, f, indent=2)


def process_videos(
    input_path: Path,
    output_dir: Path | None = None,
    max_spread_meters: float = 50,
    skip_existing: bool = True,
) -> list[Path]:
    """Process all videos and extract GPS telemetry."""
    config = load_config()
    if output_dir is None:
        output_dir = Path(config["output_dir"])

    if max_spread_meters is None:
        max_spread_meters = config.get("gps", {}).get("max_spread_meters", 50)

    ensure_output_dirs(output_dir)
    videos = find_videos(input_path)
    output_files = []

    for video in videos:
        prefix = build_output_prefix(video)
        output_path = output_dir / "gps" / f"{prefix}_gps.json"

        if skip_existing and output_path.exists():
            print(f"Skipping {video.name} (GPS already exists)")
            output_files.append(output_path)
            continue

        print(f"Extracting GPS from {video.name}...")
        points = extract_gps_telemetry(video)
        stats = compute_gps_stats(points, max_spread_meters)

        gps_data = {
            "source_file": str(video),
            "telemetry_points": points,
            **stats,
        }

        save_gps(gps_data, output_path)
        output_files.append(output_path)

        status = "OK" if stats.get("spread_valid") else "WARNING: spread exceeds limit"
        print(f"  -> {output_path} ({stats.get('point_count', 0)} points, {status})")

    return output_files
