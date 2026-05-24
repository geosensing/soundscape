"""Downsample frames for more efficient OCR processing."""

from pathlib import Path

from PIL import Image

from .utils import load_config


def downsample_image(
    input_path: Path,
    output_path: Path,
    target_size: tuple[int, int] = (1280, 720),
    quality: int = 85,
) -> None:
    """Downsample a single image to target size."""
    img = Image.open(input_path)
    img_resized = img.resize(target_size, Image.Resampling.LANCZOS)
    img_resized.save(output_path, "JPEG", quality=quality)


def process(
    input_dir: Path | None = None,
    output_dir: Path | None = None,
    target_width: int = 1280,
    target_height: int = 720,
    quality: int = 85,
    skip_existing: bool = True,
) -> list[Path]:
    """Downsample all frames in input directory.

    Args:
        input_dir: Directory containing frames (default: output/frames)
        output_dir: Output directory (default: output/frames_720p)
        target_width: Target width in pixels
        target_height: Target height in pixels
        quality: JPEG quality (1-100)
        skip_existing: Skip if output file exists

    Returns:
        List of output file paths
    """
    config = load_config()

    if input_dir is None:
        input_dir = Path(config["output_dir"]) / "frames"

    if output_dir is None:
        output_dir = Path(config["output_dir"]) / "frames_720p"

    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = sorted(input_dir.glob("*.jpg"))
    if not input_files:
        print(f"No JPG files found in {input_dir}")
        return []

    print(f"Downsampling {len(input_files)} images to {target_width}x{target_height}...")

    output_files = []
    target_size = (target_width, target_height)

    for i, input_path in enumerate(input_files):
        output_path = output_dir / input_path.name

        if skip_existing and output_path.exists():
            output_files.append(output_path)
            continue

        downsample_image(input_path, output_path, target_size, quality)
        output_files.append(output_path)

        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(input_files)}")

    print(f"Done. {len(output_files)} images -> {output_dir}")
    return output_files
