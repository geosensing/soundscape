"""Build manifest.json aggregating all EXIF, GPS, and frame data."""

import json
import re
from pathlib import Path

from .utils import load_config


def parse_frame_filename(filename: str) -> dict | None:
    """Parse frame filename to extract video ID and frame number.

    Pattern: {city}_{date}_{vidname}_{frame:06d}.jpg
    Example: delhi_04_30_2026_GX011906_000050.jpg
    """
    match = re.match(r"^(.+)_(\d{6})\.jpg$", filename)
    if not match:
        return None

    prefix = match.group(1)
    frame_number = int(match.group(2))

    return {
        "video_id": prefix,
        "frame_number": frame_number,
    }


def build_manifest(output_dir: Path | None = None) -> dict:
    """Build manifest aggregating all metadata and frame paths."""
    config = load_config()
    if output_dir is None:
        output_dir = Path(config["output_dir"])

    frames_dir = output_dir / "frames"
    exif_dir = output_dir / "exif"
    gps_dir = output_dir / "gps"

    videos = {}

    for exif_file in sorted(exif_dir.glob("*_exif.json")):
        video_id = exif_file.stem.replace("_exif", "")
        with open(exif_file) as f:
            exif_data = json.load(f)

        videos[video_id] = {
            "video_id": video_id,
            "exif": exif_data,
            "exif_file": str(exif_file),
            "gps": None,
            "gps_file": None,
            "frames": [],
            "frame_count": 0,
        }

    for gps_file in sorted(gps_dir.glob("*_gps.json")):
        video_id = gps_file.stem.replace("_gps", "")
        with open(gps_file) as f:
            gps_data = json.load(f)

        if video_id in videos:
            videos[video_id]["gps"] = gps_data
            videos[video_id]["gps_file"] = str(gps_file)
        else:
            videos[video_id] = {
                "video_id": video_id,
                "exif": None,
                "exif_file": None,
                "gps": gps_data,
                "gps_file": str(gps_file),
                "frames": [],
                "frame_count": 0,
            }

    for frame_file in sorted(frames_dir.glob("*.jpg")):
        parsed = parse_frame_filename(frame_file.name)
        if not parsed:
            continue

        video_id = parsed["video_id"]
        frame_info = {
            "path": str(frame_file),
            "filename": frame_file.name,
            "frame_number": parsed["frame_number"],
        }

        if video_id in videos:
            videos[video_id]["frames"].append(frame_info)
        else:
            videos[video_id] = {
                "video_id": video_id,
                "exif": None,
                "exif_file": None,
                "gps": None,
                "gps_file": None,
                "frames": [frame_info],
                "frame_count": 0,
            }

    for video_id in videos:
        videos[video_id]["frame_count"] = len(videos[video_id]["frames"])

    manifest = {
        "version": "1.0",
        "video_count": len(videos),
        "total_frame_count": sum(v["frame_count"] for v in videos.values()),
        "videos": list(videos.values()),
    }

    return manifest


def save_manifest(manifest: dict, output_path: Path) -> None:
    """Save manifest to JSON file."""
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)


def process(output_dir: Path | None = None) -> Path:
    """Build and save manifest."""
    config = load_config()
    if output_dir is None:
        output_dir = Path(config["output_dir"])

    manifest = build_manifest(output_dir)
    output_path = output_dir / "manifest.json"
    save_manifest(manifest, output_path)

    print(f"Built manifest: {manifest['video_count']} videos, {manifest['total_frame_count']} frames")
    print(f"  -> {output_path}")

    return output_path
