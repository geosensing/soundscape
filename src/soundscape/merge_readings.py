"""Merge OCR readings into manifest."""

import json
from pathlib import Path

from .utils import load_config


def load_readings(readings_path: Path) -> dict[str, dict]:
    """Load readings and index by frame path."""
    with open(readings_path) as f:
        data = json.load(f)

    return {r["frame_path"]: r["reading"] for r in data.get("readings", [])}


def merge_readings_into_manifest(
    manifest_path: Path,
    readings_path: Path,
    output_path: Path | None = None,
) -> Path:
    """Merge readings into manifest, adding reading field to each frame."""
    readings = load_readings(readings_path)

    with open(manifest_path) as f:
        manifest = json.load(f)

    merged_count = 0
    for video in manifest.get("videos", []):
        for frame in video.get("frames", []):
            frame_path = frame.get("path")
            if frame_path in readings:
                frame["reading"] = readings[frame_path]
                merged_count += 1
            else:
                frame["reading"] = {"value": None, "unit": None, "confidence": 0.0}

    manifest["readings_merged"] = True
    manifest["readings_count"] = merged_count

    if output_path is None:
        output_path = manifest_path.parent / "manifest_with_readings.json"

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return output_path


def process(
    manifest_path: Path | None = None,
    readings_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Merge readings into manifest."""
    config = load_config()
    output_dir = Path(config["output_dir"])

    if manifest_path is None:
        manifest_path = output_dir / "manifest.json"
    if readings_path is None:
        readings_path = output_dir / "readings" / "readings.json"

    if not readings_path.exists():
        raise FileNotFoundError(f"Readings file not found: {readings_path}")

    print(f"Merging readings from {readings_path}...")
    result_path = merge_readings_into_manifest(manifest_path, readings_path, output_path)
    print(f"  -> {result_path}")

    return result_path
