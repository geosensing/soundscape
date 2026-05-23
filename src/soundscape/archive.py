"""Create tar.gz archives of video folders for Harvard Dataverse upload."""

import subprocess
from pathlib import Path


def create_archive(
    input_dir: Path,
    output_dir: Path,
    prefix: str = "delhi",
) -> Path:
    """Create a tar.gz archive of a video folder.

    Args:
        input_dir: Directory containing video files (e.g., data/delhi/05_03_2026)
        output_dir: Where to save the archive
        prefix: Prefix for archive name (default: "delhi")

    Returns:
        Path to created archive
    """
    folder_name = input_dir.name
    archive_name = f"{prefix}_{folder_name}.tar.gz"
    archive_path = output_dir / archive_name

    output_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "tar",
            "-czvf",
            str(archive_path),
            "-C",
            str(input_dir.parent),
            folder_name,
        ],
        check=True,
    )

    return archive_path


def process_city_folder(
    city_dir: Path,
    output_dir: Path | None = None,
    prefix: str | None = None,
) -> list[Path]:
    """Create tar.gz archives for all date folders in a city directory.

    Args:
        city_dir: Directory containing date folders (e.g., data/delhi)
        output_dir: Where to save archives (default: archives/ alongside city_dir)
        prefix: Prefix for archive names (default: city folder name)

    Returns:
        List of created archive paths
    """
    if not city_dir.is_dir():
        raise ValueError(f"Not a directory: {city_dir}")

    if output_dir is None:
        output_dir = city_dir.parent / "archives"

    if prefix is None:
        prefix = city_dir.name

    output_dir.mkdir(parents=True, exist_ok=True)

    date_folders = sorted(
        d for d in city_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )

    if not date_folders:
        print(f"No date folders found in {city_dir}")
        return []

    archives = []
    for folder in date_folders:
        print(f"Creating archive for {folder.name}...")
        archive_path = create_archive(folder, output_dir, prefix)
        size_mb = archive_path.stat().st_size / (1024 * 1024)
        print(f"  -> {archive_path.name} ({size_mb:.1f} MB)")
        archives.append(archive_path)

    print(f"\nCreated {len(archives)} archives in {output_dir}")
    return archives
