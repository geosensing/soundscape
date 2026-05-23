"""Validate pipeline outputs against video inputs."""

from pathlib import Path

from .utils import find_videos, load_config


def validate_pipeline(
    input_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Validate that pipeline outputs match video inputs.

    Returns:
        Dictionary with validation results and any issues found
    """
    config = load_config()

    if input_path is None:
        input_path = Path(config.get("input_dir", "data"))

    if output_dir is None:
        output_dir = Path(config["output_dir"])

    videos = find_videos(input_path)
    video_stems = {v.stem for v in videos}

    gps_dir = output_dir / "gps"
    exif_dir = output_dir / "exif"
    frames_dir = output_dir / "frames"

    gps_files = list(gps_dir.glob("*_gps.json")) if gps_dir.exists() else []
    exif_files = list(exif_dir.glob("*_exif.json")) if exif_dir.exists() else []
    frame_files = list(frames_dir.glob("*.jpg")) if frames_dir.exists() else []

    gps_stems = set()
    for f in gps_files:
        parts = f.stem.replace("_gps", "").split("_")
        if len(parts) >= 3:
            gps_stems.add(parts[-1])

    exif_stems = set()
    for f in exif_files:
        parts = f.stem.replace("_exif", "").split("_")
        if len(parts) >= 3:
            exif_stems.add(parts[-1])

    frame_stems = set()
    for f in frame_files:
        parts = f.stem.split("_")
        if len(parts) >= 3:
            frame_stems.add(parts[2])

    results = {
        "video_count": len(videos),
        "gps_file_count": len(gps_files),
        "exif_file_count": len(exif_files),
        "frame_file_count": len(frame_files),
        "issues": [],
    }

    missing_gps = video_stems - gps_stems
    missing_exif = video_stems - exif_stems
    missing_frames = video_stems - frame_stems

    if missing_gps:
        results["issues"].append(
            {
                "type": "missing_gps",
                "count": len(missing_gps),
                "videos": sorted(missing_gps)[:10],
            }
        )

    if missing_exif:
        results["issues"].append(
            {
                "type": "missing_exif",
                "count": len(missing_exif),
                "videos": sorted(missing_exif)[:10],
            }
        )

    if missing_frames:
        results["issues"].append(
            {
                "type": "missing_frames",
                "count": len(missing_frames),
                "videos": sorted(missing_frames)[:10],
            }
        )

    extra_gps = gps_stems - video_stems
    extra_exif = exif_stems - video_stems

    if extra_gps:
        results["issues"].append(
            {
                "type": "extra_gps",
                "count": len(extra_gps),
                "files": sorted(extra_gps)[:10],
            }
        )

    if extra_exif:
        results["issues"].append(
            {
                "type": "extra_exif",
                "count": len(extra_exif),
                "files": sorted(extra_exif)[:10],
            }
        )

    results["valid"] = len(results["issues"]) == 0

    return results


def print_validation_report(results: dict) -> None:
    """Print a human-readable validation report."""
    print("\n" + "=" * 60)
    print("PIPELINE VALIDATION REPORT")
    print("=" * 60)

    print(f"\nVideo files found: {results['video_count']}")
    print(f"GPS files: {results['gps_file_count']}")
    print(f"EXIF files: {results['exif_file_count']}")
    print(f"Frame files: {results['frame_file_count']}")

    if results["valid"]:
        print("\n✓ All outputs match inputs")
    else:
        print(f"\n✗ Found {len(results['issues'])} issue(s):")

        for issue in results["issues"]:
            issue_type = issue["type"]
            count = issue["count"]

            if issue_type == "missing_gps":
                print(f"\n  Missing GPS files: {count}")
                print(f"    Videos: {', '.join(issue['videos'][:5])}...")
            elif issue_type == "missing_exif":
                print(f"\n  Missing EXIF files: {count}")
                print(f"    Videos: {', '.join(issue['videos'][:5])}...")
            elif issue_type == "missing_frames":
                print(f"\n  Missing frames: {count}")
                print(f"    Videos: {', '.join(issue['videos'][:5])}...")
            elif issue_type == "extra_gps":
                print(f"\n  Extra GPS files (no matching video): {count}")
                print(f"    Files: {', '.join(issue['files'][:5])}...")
            elif issue_type == "extra_exif":
                print(f"\n  Extra EXIF files (no matching video): {count}")
                print(f"    Files: {', '.join(issue['files'][:5])}...")

    print("\n" + "=" * 60)


def process(input_path: Path | None = None, output_dir: Path | None = None) -> dict:
    """Run validation and print report."""
    results = validate_pipeline(input_path, output_dir)
    print_validation_report(results)
    return results
