"""Extract EXIF metadata from GoPro videos using exiftool."""

import json
import subprocess
from pathlib import Path

from .utils import build_output_prefix, ensure_output_dirs, find_videos, load_config


def extract_gps_track(video_path: Path) -> list[dict]:
    """Extract full GPS track from embedded metadata.

    Uses exiftool -p format to get all GPS points, not just the first one.
    Returns list of dicts with lat, lon, altitude, speed, datetime.
    """
    result = subprocess.run(
        [
            "exiftool",
            "-ee",
            "-p",
            "$GPSLatitude,$GPSLongitude,$GPSAltitude,$GPSSpeed,$GPSDateTime",
            "-n",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )

    gps_track = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) < 5:
            continue
        try:
            lat = float(parts[0]) if parts[0] else None
            lon = float(parts[1]) if parts[1] else None
            altitude = float(parts[2]) if parts[2] else None
            speed = float(parts[3]) if parts[3] else None
            datetime_str = parts[4] if parts[4] else None

            if lat is not None and lon is not None:
                gps_track.append(
                    {
                        "lat": lat,
                        "lon": lon,
                        "altitude": altitude,
                        "speed": speed,
                        "datetime": datetime_str,
                    }
                )
        except ValueError:
            continue

    return gps_track


def extract_exif_from_video(video_path: Path) -> dict:
    """Extract ALL EXIF metadata from a single video using exiftool.

    Uses -ee flag to extract embedded metadata (GPS tracks, etc.) and
    returns complete raw exiftool output with commonly-used fields
    normalized at the top level for convenience.
    """
    result = subprocess.run(
        ["exiftool", "-ee", "-json", "-n", str(video_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        msg = f"exiftool returned invalid JSON for {video_path}: {e}"
        raise ValueError(msg) from e
    if not data:
        return {}

    raw = data[0]

    duration = raw.get("Duration")
    frame_rate = raw.get("VideoFrameRate")
    frame_count = raw.get("FrameCount")
    if frame_rate and duration and not frame_count:
        frame_count = int(frame_rate * duration)

    gps_track = extract_gps_track(video_path)

    exif = {
        "source_file": str(video_path),
        "duration_seconds": duration,
        "frame_rate": frame_rate,
        "frame_count": frame_count,
        "gps_track": gps_track,
        "raw": raw,
    }

    return exif


def save_exif(exif_data: dict, output_path: Path) -> None:
    """Save EXIF data to JSON file."""
    with open(output_path, "w") as f:
        json.dump(exif_data, f, indent=2)


def process_videos(
    input_path: Path,
    output_dir: Path | None = None,
    skip_existing: bool = True,
) -> list[Path]:
    """Process all videos and extract EXIF metadata."""
    config = load_config()
    if output_dir is None:
        output_dir = Path(config["output_dir"])

    ensure_output_dirs(output_dir)
    videos = find_videos(input_path)
    output_files = []

    for video in videos:
        prefix = build_output_prefix(video)
        output_path = output_dir / "exif" / f"{prefix}_exif.json"

        if skip_existing and output_path.exists():
            print(f"Skipping {video.name} (EXIF already exists)")
            output_files.append(output_path)
            continue

        print(f"Extracting EXIF from {video.name}...")
        exif_data = extract_exif_from_video(video)
        save_exif(exif_data, output_path)
        output_files.append(output_path)
        print(f"  -> {output_path}")

    return output_files
