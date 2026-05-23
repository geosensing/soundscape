"""Sample random frames from extracted frames for manual annotation."""

import json
import random
import shutil
from pathlib import Path

from .utils import load_config


def load_manifest(manifest_path: Path) -> dict:
    """Load manifest.json."""
    with open(manifest_path) as f:
        return json.load(f)


def get_eligible_frames(
    video: dict, frame_rate: float, start_skip_seconds: float, end_skip_seconds: float
) -> list[dict]:
    """Get frames that fall within the valid time window.

    Excludes frames from first start_skip_seconds and last end_skip_seconds.
    """
    duration = video.get("exif", {}).get("duration_seconds")
    if not duration or not frame_rate:
        return video.get("frames", [])

    start_frame = int(start_skip_seconds * frame_rate)
    end_frame = int((duration - end_skip_seconds) * frame_rate)

    eligible = []
    for frame in video.get("frames", []):
        frame_num = frame.get("frame_number", 0)
        if start_frame <= frame_num <= end_frame:
            eligible.append(frame)

    return eligible


def sample_frames(
    manifest_path: Path,
    output_dir: Path,
    frames_per_video: int = 1,
    seed: int = 42,
    start_skip_seconds: float = 10.0,
    end_skip_seconds: float = 5.0,
) -> list[dict]:
    """Sample random frames from each video and copy to output directory.

    Returns list of sampled frame info with video metadata attached.
    """
    random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(manifest_path)
    sampled = []

    for video in manifest.get("videos", []):
        video_id = video.get("video_id", "unknown")
        frame_rate = video.get("exif", {}).get("frame_rate", 50)

        eligible_frames = get_eligible_frames(
            video, frame_rate, start_skip_seconds, end_skip_seconds
        )

        if not eligible_frames:
            print(f"Warning: No eligible frames for {video_id}")
            continue

        n_samples = min(frames_per_video, len(eligible_frames))
        selected = random.sample(eligible_frames, n_samples)

        for frame in selected:
            src_path = Path(frame["path"])
            if not src_path.exists():
                print(f"Warning: Frame not found: {src_path}")
                continue

            dst_path = output_dir / frame["filename"]
            shutil.copy2(src_path, dst_path)

            sampled.append(
                {
                    "video_id": video_id,
                    "frame_path": str(dst_path),
                    "original_path": frame["path"],
                    "frame_number": frame["frame_number"],
                    "timestamp_seconds": frame["frame_number"] / frame_rate if frame_rate else None,
                    "gps": {
                        "latitude": video.get("gps", {}).get("median_latitude"),
                        "longitude": video.get("gps", {}).get("median_longitude"),
                    },
                }
            )

    return sampled


def save_sample_manifest(sampled: list[dict], output_path: Path, seed: int) -> None:
    """Save sampled frames manifest."""
    manifest = {
        "seed": seed,
        "sample_count": len(sampled),
        "samples": sampled,
    }
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)


def process(
    manifest_path: Path | None = None,
    output_dir: Path | None = None,
    frames_per_video: int = 1,
    seed: int = 42,
    start_skip_seconds: float = 10.0,
    end_skip_seconds: float = 5.0,
) -> Path:
    """Sample frames and save to output directory."""
    config = load_config()

    if manifest_path is None:
        manifest_path = Path(config["output_dir"]) / "manifest.json"
    if output_dir is None:
        output_dir = Path(config["output_dir"]) / "samples"

    print(f"Sampling {frames_per_video} frame(s) per video (seed={seed})...")
    print(f"Skipping first {start_skip_seconds}s and last {end_skip_seconds}s")

    sampled = sample_frames(
        manifest_path=manifest_path,
        output_dir=output_dir,
        frames_per_video=frames_per_video,
        seed=seed,
        start_skip_seconds=start_skip_seconds,
        end_skip_seconds=end_skip_seconds,
    )

    sample_manifest_path = output_dir / "sample_manifest.json"
    save_sample_manifest(sampled, sample_manifest_path, seed)

    print(f"Sampled {len(sampled)} frames -> {output_dir}")
    print(f"Sample manifest -> {sample_manifest_path}")

    return sample_manifest_path
