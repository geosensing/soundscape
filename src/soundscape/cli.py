"""Click CLI entry point for soundscape pipeline."""

from pathlib import Path

import click

from . import (archive, build_manifest, extract_exif, extract_frames,
               extract_gps, merge_readings, ocr_readings, sample_frames,
               validate)


@click.group()
@click.version_option()
def main():
    """Soundscape: Extract frames and metadata from GoPro sound meter recordings."""
    pass


# =============================================================================
# 1. Frame Extraction
# =============================================================================


@main.command("extract-frames")
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Input video file or directory containing videos",
)
@click.option(
    "--frame-interval",
    type=int,
    default=None,
    help="Extract every Nth frame (default: 50, i.e., 1 fps at 50fps video)",
)
@click.option(
    "--quality",
    type=int,
    default=None,
    help="JPEG quality 1-100 (default: 95)",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: from config.yaml)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing files",
)
def extract_frames_cmd(input_path, frame_interval, quality, output_dir, force):
    """1. Extract frames from video files at specified intervals."""
    extract_frames.process_videos(
        input_path=input_path,
        output_dir=output_dir,
        interval=frame_interval,
        quality=quality,
        skip_existing=not force,
    )


# =============================================================================
# 2. EXIF Extraction
# =============================================================================


@main.command("extract-exif")
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Input video file or directory containing videos",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: from config.yaml)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing files",
)
def extract_exif_cmd(input_path, output_dir, force):
    """2. Extract EXIF metadata from video files."""
    extract_exif.process_videos(
        input_path=input_path,
        output_dir=output_dir,
        skip_existing=not force,
    )


# =============================================================================
# 3. GPS Extraction
# =============================================================================


@main.command("extract-gps")
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Input video file or directory containing videos",
)
@click.option(
    "--max-spread-meters",
    type=float,
    default=None,
    help="Maximum allowed GPS spread in meters (default: 50)",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: from config.yaml)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing files",
)
def extract_gps_cmd(input_path, max_spread_meters, output_dir, force):
    """3. Extract GPS telemetry from video files."""
    extract_gps.process_videos(
        input_path=input_path,
        output_dir=output_dir,
        max_spread_meters=max_spread_meters,
        skip_existing=not force,
    )


# =============================================================================
# 4. Build Manifest
# =============================================================================


@main.command("build-manifest")
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: from config.yaml)",
)
def build_manifest_cmd(output_dir):
    """4. Build manifest.json aggregating all metadata and frames."""
    build_manifest.process(output_dir=output_dir)


# =============================================================================
# 5. Sample Frames
# =============================================================================


@main.command("sample-frames")
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to manifest.json (default: output/manifest.json)",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for sampled frames (default: output/samples)",
)
@click.option(
    "--frames-per-video",
    type=int,
    default=1,
    help="Number of frames to sample per video (default: 1)",
)
@click.option(
    "--seed",
    type=int,
    default=42,
    help="Random seed for reproducibility (default: 42)",
)
@click.option(
    "--start-skip",
    type=float,
    default=10.0,
    help="Skip frames in first N seconds (default: 10.0)",
)
@click.option(
    "--end-skip",
    type=float,
    default=5.0,
    help="Skip frames in last N seconds (default: 5.0)",
)
def sample_frames_cmd(
    manifest_path, output_dir, frames_per_video, seed, start_skip, end_skip
):
    """5. Sample random frames for manual annotation verification."""
    sample_frames.process(
        manifest_path=manifest_path,
        output_dir=output_dir,
        frames_per_video=frames_per_video,
        seed=seed,
        start_skip_seconds=start_skip,
        end_skip_seconds=end_skip,
    )


# =============================================================================
# 6. OCR Readings (Batch API)
# =============================================================================


@main.command("ocr-readings")
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to manifest.json (default: output/manifest.json)",
)
@click.option(
    "--sample-manifest",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to sample_manifest.json for processing sampled frames only",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for readings (default: output/readings)",
)
@click.option(
    "--model",
    type=click.Choice(["claude-haiku-4-5", "claude-sonnet-4-5"]),
    default="claude-haiku-4-5",
    help="Claude model to use (default: claude-haiku-4-5)",
)
@click.option(
    "--batch-id",
    type=str,
    default=None,
    help="Retrieve results from existing batch ID instead of submitting new batch",
)
@click.option(
    "--poll-interval",
    type=int,
    default=30,
    help="Seconds between status polls (default: 30)",
)
def ocr_readings_cmd(
    manifest_path, sample_manifest, output_dir, model, batch_id, poll_interval
):
    """6. OCR sound meter readings using Claude batch API."""
    ocr_readings.process(
        manifest_path=manifest_path,
        output_dir=output_dir,
        model=model,
        sample_manifest=sample_manifest,
        batch_id=batch_id,
        poll_interval=poll_interval,
    )


# =============================================================================
# 7. Merge Readings
# =============================================================================


@main.command("merge-readings")
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to manifest.json (default: output/manifest.json)",
)
@click.option(
    "--readings",
    "readings_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to readings.json (default: output/readings/readings.json)",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path for merged manifest (default: output/manifest_with_readings.json)",
)
def merge_readings_cmd(manifest_path, readings_path, output_path):
    """7. Merge OCR readings into manifest."""
    merge_readings.process(
        manifest_path=manifest_path,
        readings_path=readings_path,
        output_path=output_path,
    )


# =============================================================================
# 8. Create Archives
# =============================================================================


@main.command("create-archives")
@click.option(
    "--input",
    "input_dir",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="City directory containing date folders (e.g., data/delhi)",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for archives (default: data/archives)",
)
@click.option(
    "--prefix",
    type=str,
    default=None,
    help="Prefix for archive names (default: city folder name)",
)
def create_archives_cmd(input_dir, output_dir, prefix):
    """8. Create tar.gz archives of video folders for Harvard Dataverse."""
    archive.process_city_folder(
        city_dir=input_dir,
        output_dir=output_dir,
        prefix=prefix,
    )


# =============================================================================
# 9. Validate Pipeline
# =============================================================================


@main.command("validate")
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Input video directory (default: from config.yaml)",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: from config.yaml)",
)
def validate_cmd(input_path, output_dir):
    """9. Validate pipeline outputs match video inputs."""
    validate.process(input_path=input_path, output_dir=output_dir)


if __name__ == "__main__":
    main()
