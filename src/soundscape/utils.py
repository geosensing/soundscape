"""Utility functions for soundscape pipeline."""

import re
from pathlib import Path

import yaml


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path("config.yaml")
    if not config_path.exists():
        return get_default_config()
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_default_config() -> dict:
    """Return default configuration."""
    return {
        "data_dir": "data",
        "output_dir": "output",
        "frames": {"interval": 50, "quality": 95},
        "gps": {"max_spread_meters": 50, "location_method": "median"},
        "processing": {"skip_existing": True},
    }


def find_videos(input_path: Path) -> list[Path]:
    """Find all MP4 video files in the given path."""
    if input_path.is_file():
        if input_path.suffix.upper() == ".MP4":
            return [input_path]
        return []
    return sorted(input_path.rglob("*.MP4"))


def parse_video_path(video_path: Path) -> dict:
    """Parse video path to extract city and date information.

    Expected structure: data/{city}/{date}/VIDEO.MP4
    Date format: MM_DD_YYYY (e.g., 04_30_2026)
    """
    parts = video_path.parts
    video_name = video_path.stem

    city = None
    date = None

    for i, part in enumerate(parts):
        if part == "data" and i + 2 < len(parts):
            city = parts[i + 1]
            date_candidate = parts[i + 2]
            if re.match(r"\d{2}_\d{2}_\d{4}", date_candidate):
                date = date_candidate
            break

    return {
        "city": city or "unknown",
        "date": date or "unknown",
        "video_name": video_name,
    }


def build_output_prefix(video_path: Path) -> str:
    """Build the output filename prefix for a video.

    Format: {city}_{date}_{vidname}
    Example: delhi_04_30_2026_GX011906
    """
    info = parse_video_path(video_path)
    return f"{info['city']}_{info['date']}_{info['video_name']}"


def ensure_output_dirs(output_dir: Path) -> None:
    """Ensure all output directories exist."""
    (output_dir / "frames").mkdir(parents=True, exist_ok=True)
    (output_dir / "exif").mkdir(parents=True, exist_ok=True)
    (output_dir / "gps").mkdir(parents=True, exist_ok=True)


def get_city_from_manifest(manifest: dict) -> str:
    """Extract city from manifest video_ids."""
    for video in manifest.get("videos", []):
        video_id = video.get("video_id", "")
        if "_" in video_id:
            return video_id.split("_")[0]
    return "unknown"


def get_city_from_sample_manifest(sample_manifest: dict) -> str:
    """Extract city from sample manifest."""
    for sample in sample_manifest.get("samples", []):
        video_id = sample.get("video_id", "")
        if "_" in video_id:
            return video_id.split("_")[0]
    return "unknown"
