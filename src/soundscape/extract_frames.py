"""Extract frames from GoPro videos using ffmpeg."""

import re
import subprocess
import tempfile
from pathlib import Path

from .utils import (build_output_prefix, ensure_output_dirs, find_videos,
                    load_config)


def extract_frames_from_video(
    video_path: Path,
    output_dir: Path,
    prefix: str,
    interval: int = 50,
    quality: int = 95,
) -> list[Path]:
    """Extract frames from a video at specified intervals.

    Uses ffmpeg with select filter to pick every Nth frame.
    Frame numbers in filenames are original video frame numbers.
    """
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        output_pattern = str(tmp_path / f"{prefix}_%06d.jpg")

        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            f"select=not(mod(n\\,{interval}))",
            "-vsync",
            "vfr",
            "-q:v",
            str(max(1, min(31, (100 - quality) * 31 // 100 + 1))),
            "-start_number",
            "1",
            output_pattern,
            "-y",
        ]

        subprocess.run(cmd, capture_output=True, check=True)

        raw_frames = sorted(tmp_path.glob(f"{prefix}_*.jpg"))
        renamed_frames = []

        for frame in raw_frames:
            match = re.search(r"_(\d{6})\.jpg$", frame.name)
            if match:
                seq_num = int(match.group(1))
                original_frame_num = (seq_num - 1) * interval
                new_name = frames_dir / f"{prefix}_{original_frame_num:06d}.jpg"
                frame.rename(new_name)
                renamed_frames.append(new_name)

    return renamed_frames


def process_videos(
    input_path: Path,
    output_dir: Path | None = None,
    interval: int | None = None,
    quality: int | None = None,
    skip_existing: bool = True,
) -> list[Path]:
    """Process all videos and extract frames."""
    config = load_config()
    if output_dir is None:
        output_dir = Path(config["output_dir"])

    frames_config = config.get("frames", {})
    if interval is None:
        interval = frames_config.get("interval", 50)
    if quality is None:
        quality = frames_config.get("quality", 95)

    ensure_output_dirs(output_dir)
    videos = find_videos(input_path)
    all_frames = []

    for video in videos:
        prefix = build_output_prefix(video)
        frames_dir = output_dir / "frames"

        existing_frames = list(frames_dir.glob(f"{prefix}_*.jpg"))
        if skip_existing and existing_frames:
            print(
                f"Skipping {video.name} (frames already exist: {len(existing_frames)} files)"
            )
            all_frames.extend(existing_frames)
            continue

        print(
            f"Extracting frames from {video.name} (interval={interval}, quality={quality})..."
        )
        frames = extract_frames_from_video(video, output_dir, prefix, interval, quality)
        all_frames.extend(frames)
        print(f"  -> Extracted {len(frames)} frames")

    return all_frames
