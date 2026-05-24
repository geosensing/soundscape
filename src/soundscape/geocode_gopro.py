"""Reverse geocoding for GoPro stop locations.

Queries Nominatim API to add road type metadata to GoPro readings,
enabling road-type-based analysis without requiring matched rider data.
"""

import glob as glob_module
import json
import time
from pathlib import Path

import click
import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "soundscape-research/1.0 (https://github.com/in-rolls/soundscape)"
RATE_LIMIT_SECONDS = 1.1


def geocode_location(lat: float, lon: float) -> dict:
    """Query Nominatim for road type at given coordinates.

    Returns dict with road_type, road_name, and address.
    Rate limited to respect Nominatim usage policy.
    """
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1,
        "zoom": 18,
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(
            NOMINATIM_URL, params=params, headers=headers, timeout=10
        )
        response.raise_for_status()
        data = response.json()

        address = data.get("address", {})
        road_type = address.get("road_type") or data.get("type")
        road_name = address.get("road") or data.get("name", "")
        display_name = data.get("display_name", "")

        osm_class = data.get("class", "")
        osm_type = data.get("type", "")
        if osm_class == "highway":
            road_type = osm_type

        return {
            "road_type": road_type,
            "road_name": road_name,
            "address": display_name,
        }
    except Exception as e:
        click.echo(f"    Geocoding error: {e}")
        return {
            "road_type": None,
            "road_name": None,
            "address": None,
        }


def load_readings(path: Path) -> dict:
    """Load GoPro readings JSON."""
    with open(path) as f:
        return json.load(f)


def get_unique_stops(data: dict) -> dict:
    """Extract unique stops (by video_id) with their GPS coordinates."""
    stops = {}
    for r in data["readings"]:
        vid = r["video_id"]
        if vid not in stops and r.get("gps"):
            stops[vid] = {
                "latitude": r["gps"]["latitude"],
                "longitude": r["gps"]["longitude"],
            }
    return stops


def geocode_stops(stops: dict, cache_path: Path | None = None) -> dict:
    """Geocode all unique stops with rate limiting and caching.

    Args:
        stops: Dict mapping video_id to {latitude, longitude}
        cache_path: Optional path to load/save cache

    Returns:
        Dict mapping video_id to geocoding results
    """
    cache = {}
    if cache_path and cache_path.exists():
        try:
            with open(cache_path) as f:
                cache = json.load(f)
            click.echo(f"  Loaded cache with {len(cache)} entries")
        except Exception:
            cache = {}

    results = {}
    to_geocode = [vid for vid in stops if vid not in cache]

    if to_geocode:
        click.echo(f"  Geocoding {len(to_geocode)} stops (rate limited to 1/sec)...")
        with click.progressbar(to_geocode, show_pos=True) as progress:
            for vid in progress:
                coords = stops[vid]
                result = geocode_location(coords["latitude"], coords["longitude"])
                cache[vid] = result
                time.sleep(RATE_LIMIT_SECONDS)

        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(cache, f, indent=2)
            click.echo(f"  Saved cache to {cache_path}")

    for vid in stops:
        results[vid] = cache.get(
            vid, {"road_type": None, "road_name": None, "address": None}
        )

    return results


def enrich_readings(data: dict, geocode_results: dict) -> dict:
    """Add road_type, road_name, address to each reading based on video_id."""
    enriched = data.copy()
    enriched["readings"] = []

    for r in data["readings"]:
        new_r = r.copy()
        vid = r["video_id"]
        geo = geocode_results.get(vid, {})

        if "metadata" not in new_r:
            new_r["metadata"] = {}
        new_r["metadata"]["road_type"] = geo.get("road_type")
        new_r["metadata"]["road_name"] = geo.get("road_name")
        new_r["metadata"]["address"] = geo.get("address")

        enriched["readings"].append(new_r)

    return enriched


def process(
    readings_pattern: str,
    output_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> None:
    """Geocode GoPro readings and save enriched versions.

    Args:
        readings_pattern: Glob pattern for input JSON files
        output_dir: Where to save geocoded files (default: same directory)
        cache_dir: Where to store geocoding cache (default: output/.geocache)
    """
    paths = sorted([Path(p) for p in glob_module.glob(readings_pattern)])
    if not paths:
        click.echo(f"No files found matching {readings_pattern}")
        return

    if cache_dir is None:
        cache_dir = Path("output/.geocache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    for path in paths:
        click.echo(f"\nProcessing {path.name}")

        data = load_readings(path)
        click.echo(
            f"  Loaded {data.get('reading_count', len(data['readings']))} readings"
        )

        stops = get_unique_stops(data)
        click.echo(f"  Found {len(stops)} unique stops")

        cache_path = cache_dir / f"{path.stem}_geocache.json"
        geocode_results = geocode_stops(stops, cache_path)

        road_types = {}
        for geo in geocode_results.values():
            rt = geo.get("road_type") or "unknown"
            road_types[rt] = road_types.get(rt, 0) + 1

        click.echo("  Road type distribution:")
        for rt, count in sorted(road_types.items(), key=lambda x: -x[1]):
            click.echo(f"    {rt}: {count}")

        enriched = enrich_readings(data, geocode_results)

        if output_dir is None:
            out_path = path.parent / f"{path.stem}_geocoded.json"
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"{path.stem}_geocoded.json"

        with open(out_path, "w") as f:
            json.dump(enriched, f, indent=2)
        click.echo(f"  Saved enriched data to {out_path}")

    click.echo("\nGeocoding complete!")
