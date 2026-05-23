"""Extract EXIF metadata from GoPro videos using exiftool."""

import json
import subprocess
from pathlib import Path

from .utils import (build_output_prefix, ensure_output_dirs, find_videos,
                    load_config)


def extract_exif_from_video(video_path: Path) -> dict:
    """Extract ALL EXIF metadata from a single video using exiftool.

    Uses -ee flag to extract embedded metadata (GPS tracks, etc.) and
    returns complete raw exiftool output at top level.
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

    exif = data[0]
    exif["source_file"] = str(video_path)

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
    """Process all videos and extract EXIF metadata.

    Outputs:
    - Individual JSON files per video in output/exif/
    - Combined JSONL file with all metadata: output/exif.jsonl
    """
    config = load_config()
    if output_dir is None:
        output_dir = Path(config["output_dir"])

    ensure_output_dirs(output_dir)
    videos = find_videos(input_path)
    output_files = []
    all_exif = []

    for video in videos:
        prefix = build_output_prefix(video)
        output_path = output_dir / "exif" / f"{prefix}_exif.json"

        if skip_existing and output_path.exists():
            print(f"Skipping {video.name} (EXIF already exists)")
            output_files.append(output_path)
            with open(output_path) as f:
                all_exif.append(json.load(f))
            continue

        print(f"Extracting EXIF from {video.name}...")
        exif_data = extract_exif_from_video(video)
        save_exif(exif_data, output_path)
        output_files.append(output_path)
        all_exif.append(exif_data)
        print(f"  -> {output_path}")

    jsonl_path = output_dir / "exif.jsonl"
    with open(jsonl_path, "w") as f:
        for exif in all_exif:
            f.write(json.dumps(exif) + "\n")
    print(f"Combined JSONL: {jsonl_path} ({len(all_exif)} records)")

    return output_files
