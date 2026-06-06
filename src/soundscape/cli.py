"""Click CLI entry point for soundscape pipeline."""

from pathlib import Path

import click

from . import (
    analyze,
    analyze_rider,
    archive,
    build_manifest,
    compare_locations,
    downsample,
    extract_exif,
    extract_frames,
    extract_gps,
    geocode_gopro,
    merge_readings,
    ocr_readings,
    sample_frames,
    upload,
    validate,
    viewer,
)


@click.group()
@click.version_option()
def main():
    """Soundscape: Extract frames and metadata from GoPro sound meter recordings."""
    pass


# =============================================================================
# 1. Extract Frames
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
# 2. Downsample Frames
# =============================================================================


@main.command("downsample")
@click.option(
    "--input",
    "input_dir",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Input frames directory (default: output/frames)",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: output/frames_720p)",
)
@click.option(
    "--width",
    type=int,
    default=1280,
    help="Target width in pixels (default: 1280)",
)
@click.option(
    "--height",
    type=int,
    default=720,
    help="Target height in pixels (default: 720)",
)
@click.option(
    "--quality",
    type=int,
    default=85,
    help="JPEG quality 1-100 (default: 85)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing files",
)
def downsample_cmd(input_dir, output_dir, width, height, quality, force):
    """2. Downsample frames for efficient OCR processing."""
    downsample.process(
        input_dir=input_dir,
        output_dir=output_dir,
        target_width=width,
        target_height=height,
        quality=quality,
        skip_existing=not force,
    )


# =============================================================================
# 3. Extract EXIF
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
    """3. Extract EXIF metadata from video files."""
    extract_exif.process_videos(
        input_path=input_path,
        output_dir=output_dir,
        skip_existing=not force,
    )


# =============================================================================
# 4. Extract GPS
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
    """4. Extract GPS telemetry from video files."""
    extract_gps.process_videos(
        input_path=input_path,
        output_dir=output_dir,
        max_spread_meters=max_spread_meters,
        skip_existing=not force,
    )


# =============================================================================
# 5. Build Manifest
# =============================================================================


@main.command("build-manifest")
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: from config.yaml)",
)
@click.option(
    "--frames-dir",
    "frames_dir",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Frames directory to use (default: output/frames_720p)",
)
def build_manifest_cmd(output_dir, frames_dir):
    """5. Build manifest.json aggregating all metadata and frames."""
    build_manifest.process(output_dir=output_dir, frames_dir=frames_dir)


# =============================================================================
# 6. Sample Frames
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
    """6. Sample random frames for manual annotation verification."""
    sample_frames.process(
        manifest_path=manifest_path,
        output_dir=output_dir,
        frames_per_video=frames_per_video,
        seed=seed,
        start_skip_seconds=start_skip,
        end_skip_seconds=end_skip,
    )


# =============================================================================
# 7. OCR Readings
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
    type=click.Choice(
        [
            "claude-haiku-4-5",
            "claude-sonnet-4-5",
            "gemini-2.0-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-3-flash-preview",
        ]
    ),
    default="claude-haiku-4-5",
    help="Model to use (default: claude-haiku-4-5)",
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
    """7. OCR sound meter readings using Claude or Gemini API."""
    ocr_readings.process(
        manifest_path=manifest_path,
        output_dir=output_dir,
        model=model,
        sample_manifest=sample_manifest,
        batch_id=batch_id,
        poll_interval=poll_interval,
    )


# =============================================================================
# 8. Merge Readings
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
    """8. Merge OCR readings into manifest."""
    merge_readings.process(
        manifest_path=manifest_path,
        readings_path=readings_path,
        output_path=output_path,
    )


# =============================================================================
# 9. Create Archives
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
    """9. Create tar.gz archives of video folders for Harvard Dataverse."""
    archive.process_city_folder(
        city_dir=input_dir,
        output_dir=output_dir,
        prefix=prefix,
    )


# =============================================================================
# 9b. Upload Archives to Harvard Dataverse
# =============================================================================


@main.command("upload-dataverse")
@click.option(
    "--input",
    "input_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("data/archives"),
    help="Directory of .tar.gz archives (default: data/archives)",
)
@click.option(
    "--doi",
    type=str,
    required=True,
    help="Dataset persistent identifier (e.g. doi:10.7910/DVN/S8ZBLX)",
)
@click.option(
    "--server",
    type=str,
    default=upload.DEFAULT_SERVER,
    help=f"Dataverse base URL (default: {upload.DEFAULT_SERVER})",
)
@click.option(
    "--token",
    type=str,
    default=None,
    envvar="DATAVERSE_API_TOKEN",
    help="Dataverse API token (default: from DATAVERSE_API_TOKEN env var)",
)
@click.option(
    "--no-skip-existing",
    is_flag=True,
    help="Re-upload files even if a file of the same name is already in the dataset",
)
@click.option(
    "--file",
    "files",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    multiple=True,
    help="Specific archive(s) to upload instead of scanning --input (repeatable)",
)
def upload_dataverse_cmd(input_dir, doi, server, token, no_skip_existing, files):
    """9b. Upload tar.gz archives to a Harvard Dataverse dataset via the API."""
    if not token:
        raise click.UsageError(
            "No API token provided. Pass --token or set DATAVERSE_API_TOKEN."
        )
    upload.upload_archives(
        archives_dir=input_dir,
        doi=doi,
        token=token,
        server=server,
        skip_existing=not no_skip_existing,
        files=list(files) or None,
    )


# =============================================================================
# 10. Validate Pipeline
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
    """10. Validate pipeline outputs match video inputs."""
    validate.process(input_path=input_path, output_dir=output_dir)


# =============================================================================
# 11. Viewer
# =============================================================================


@main.command("viewer")
@click.option(
    "--readings",
    "readings_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to readings JSON file",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output HTML path (default: same as readings with .html extension)",
)
def viewer_cmd(readings_path, output_path):
    """11. Generate HTML viewer for verifying and correcting OCR results."""
    viewer.process(readings_path=readings_path, output_path=output_path)


# =============================================================================
# 12. Analyze
# =============================================================================


@main.command("analyze")
@click.option(
    "--readings",
    "readings_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to readings JSON file",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: output/analysis)",
)
def analyze_cmd(readings_path, output_dir):
    """12. Generate publication-ready analysis tables and figures."""
    analyze.process(readings_path=readings_path, output_dir=output_dir)


# =============================================================================
# 13. Analyze Rider Data
# =============================================================================


@main.command("analyze-rider")
@click.option(
    "--readings",
    "readings_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to rider readings JSON file",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: <readings_dir>/analysis)",
)
def analyze_rider_cmd(readings_path, output_dir):
    """13. Analyze rider-collected noise data with road type metadata."""
    analyze_rider.process(readings_path=readings_path, output_dir=output_dir)


# =============================================================================
# 14. Compare Locations
# =============================================================================


@main.command("compare-locations")
@click.option(
    "--rider",
    "rider_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to rider readings JSON file",
)
@click.option(
    "--gopro",
    "gopro_pattern",
    type=str,
    required=True,
    help="Glob pattern for GoPro readings JSON files (e.g., 'output/readings/delhi_*.json')",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: output/comparison)",
)
@click.option(
    "--max-distance",
    "max_distance_m",
    type=float,
    default=100.0,
    help="Maximum match distance in meters (default: 100)",
)
def compare_locations_cmd(rider_path, gopro_pattern, output_dir, max_distance_m):
    """14. Compare rider and GoPro collection locations for overlap analysis."""
    compare_locations.process(
        rider_path=rider_path,
        gopro_pattern=gopro_pattern,
        output_dir=output_dir,
        max_distance_m=max_distance_m,
    )


# =============================================================================
# 15. Geocode GoPro Data
# =============================================================================


@main.command("geocode-gopro")
@click.option(
    "--readings",
    "readings_pattern",
    type=str,
    required=True,
    help="Glob pattern for GoPro readings JSON files (e.g., 'output/readings/delhi_*.json')",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for geocoded files (default: same as input)",
)
@click.option(
    "--cache-dir",
    "cache_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory for geocoding cache (default: output/.geocache)",
)
def geocode_gopro_cmd(readings_pattern, output_dir, cache_dir):
    """15. Add road type metadata to GoPro data via reverse geocoding."""
    geocode_gopro.process(
        readings_pattern=readings_pattern,
        output_dir=output_dir,
        cache_dir=cache_dir,
    )


if __name__ == "__main__":
    main()
