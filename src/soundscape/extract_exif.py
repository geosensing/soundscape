"""Extract EXIF metadata from GoPro videos using exiftool."""

import json
import subprocess
from pathlib import Path

from .utils import build_output_prefix, ensure_output_dirs, find_videos, load_config


def extract_exif_from_video(video_path: Path) -> dict:
    """Extract EXIF metadata from a single video using exiftool."""
    result = subprocess.run(
        ["exiftool", "-json", "-n", str(video_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    if not data:
        return {}

    raw = data[0]

    exif = {
        "source_file": str(video_path),
        "file_name": raw.get("FileName"),
        "file_size_bytes": raw.get("FileSize"),
        "create_date": raw.get("CreateDate"),
        "modify_date": raw.get("ModifyDate"),
        "duration_seconds": raw.get("Duration"),
        "frame_rate": raw.get("VideoFrameRate"),
        "frame_count": raw.get("FrameCount"),
        "image_width": raw.get("ImageWidth"),
        "image_height": raw.get("ImageHeight"),
        "video_codec": raw.get("CompressorID") or raw.get("VideoCodec"),
        "audio_codec": raw.get("AudioFormat"),
        "camera_model": raw.get("Model"),
        "camera_serial": raw.get("SerialNumber"),
        "firmware": raw.get("FirmwareVersion"),
    }

    if exif.get("frame_rate") and exif.get("duration_seconds") and not exif.get("frame_count"):
        exif["frame_count"] = int(exif["frame_rate"] * exif["duration_seconds"])

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
