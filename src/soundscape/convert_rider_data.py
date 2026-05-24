"""Convert rider form data to soundscape readings format.

Transforms exports from the missing-women-rider-route-tool into the
standard soundscape readings JSON schema for analysis.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import click
import requests


def parse_note(note: str | None) -> dict:
    """Parse note field to extract stop_id and traffic annotations.

    Args:
        note: Raw note string like "1.2" or "2.1 traffic stop"

    Returns:
        Dictionary with stop_id, is_traffic_stop, is_traffic_jam
    """
    if not note:
        return {
            "stop_id": None,
            "is_traffic_stop": False,
            "is_traffic_jam": False,
        }

    note_lower = note.lower()
    is_traffic_stop = "traffic stop" in note_lower
    is_traffic_jam = "traffic jam" in note_lower

    parts = note.split()
    stop_id = parts[0] if parts else None

    return {
        "stop_id": stop_id,
        "is_traffic_stop": is_traffic_stop,
        "is_traffic_jam": is_traffic_jam,
    }


def reverse_geocode(
    lat: float, lng: float, cache: dict, session: requests.Session
) -> str | None:
    """Fetch address for coordinates using Nominatim.

    Args:
        lat: Latitude
        lng: Longitude
        cache: Address cache dict (modified in place)
        session: Requests session with headers set

    Returns:
        Address string or None if lookup fails
    """
    key = f"{lat:.6f},{lng:.6f}"
    if key in cache:
        return cache[key]

    url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?format=jsonv2&lat={lat}&lon={lng}&zoom=18&addressdetails=1"
    )

    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        address = data.get("display_name")
        if address:
            cache[key] = address
        return address
    except Exception:
        return None


IST = ZoneInfo("Asia/Kolkata")


def convert_timestamp_to_ist(ts_str: str | None) -> str | None:
    """Convert ISO timestamp to IST (India Standard Time).

    Args:
        ts_str: ISO format timestamp string (assumed UTC if no timezone)

    Returns:
        ISO format timestamp in IST, or None if input is None
    """
    if not ts_str:
        return None

    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_ist = dt.astimezone(IST)
    return dt_ist.isoformat()


def convert_reading(log: dict, export_dir: Path, address: str | None = None) -> dict:
    """Convert a single rider log to soundscape reading format.

    Args:
        log: Raw log dict from manifest
        export_dir: Path to export directory for constructing frame paths
        address: Optional reverse-geocoded address string

    Returns:
        Soundscape reading dict
    """
    note_parsed = parse_note(log.get("note"))

    itinerary = None
    if log.get("itinerary_id") and log.get("part"):
        itinerary = f"{log['itinerary_id']}-{log['part']}"

    frame_path = None
    if log.get("image") and log["image"].get("local_path"):
        frame_path = str(export_dir / log["image"]["local_path"])

    timestamp_ist = convert_timestamp_to_ist(log.get("captured_at"))

    image_data = None
    if log.get("image"):
        image_data = {
            "local_path": log["image"].get("local_path"),
            "original_name": log["image"].get("original_name"),
            "remote_url": log["image"].get("remote_url"),
        }

    reading = {
        "id": log.get("id"),
        "timestamp": timestamp_ist,
        "timestamp_utc": log.get("captured_at"),
        "gps": {
            "latitude": log.get("latitude"),
            "longitude": log.get("longitude"),
        },
        "reading": {
            "min_db": log.get("min_db"),
            "max_db": log.get("max_db"),
            "status": "ok",
        },
        "frame_path": frame_path,
        "image": image_data,
        "metadata": {
            "day": log.get("day"),
            "itinerary": itinerary,
            "title": log.get("title"),
            "stop_id": note_parsed["stop_id"],
            "is_traffic_stop": note_parsed["is_traffic_stop"],
            "is_traffic_jam": note_parsed["is_traffic_jam"],
            "note_raw": log.get("note"),
        },
    }

    if address:
        reading["metadata"]["address"] = address

    return reading


def process(
    manifest_path: Path,
    output_dir: Path | None = None,
    geocode: bool = True,
    geocode_delay: float = 1.1,
    address_cache_path: Path | None = None,
) -> None:
    """Convert rider manifest to soundscape readings JSON.

    Args:
        manifest_path: Path to rider manifest.json
        output_dir: Output directory (default: output/rider)
        geocode: Whether to reverse geocode coordinates to addresses
        geocode_delay: Delay between geocode requests (Nominatim policy: 1/sec)
        address_cache_path: Path to address_cache.json exported from dashboard
    """
    if output_dir is None:
        output_dir = Path("output/rider")
    output_dir.mkdir(parents=True, exist_ok=True)

    export_dir = manifest_path.parent

    click.echo(f"Loading manifest from {manifest_path}")
    with open(manifest_path) as f:
        manifest = json.load(f)

    noise_logs = manifest.get("noise_logs", [])
    click.echo(f"  Found {len(noise_logs)} noise logs")

    address_cache: dict[str, str] = {}
    if address_cache_path is None:
        default_cache = export_dir / "address_cache.json"
        if default_cache.exists():
            address_cache_path = default_cache
    if address_cache_path:
        click.echo(f"Loading address cache from {address_cache_path}")
        with open(address_cache_path) as f:
            address_cache = json.load(f)
        click.echo(f"  Loaded {len(address_cache)} cached addresses")

    session = requests.Session()
    session.headers["User-Agent"] = "soundscape/1.0 (research; contact@example.com)"

    readings = []
    geocoded_count = 0
    for i, log in enumerate(noise_logs):
        address = None
        if log.get("latitude") and log.get("longitude"):
            key = f"{log['latitude']:.5f},{log['longitude']:.5f}"
            if key in address_cache:
                address = address_cache[key]
            elif geocode:
                click.echo(f"\r  Geocoding: {i + 1}/{len(noise_logs)}", nl=False)
                address = reverse_geocode(
                    log["latitude"], log["longitude"], address_cache, session
                )
                geocoded_count += 1
                time.sleep(geocode_delay)

        reading = convert_reading(log, export_dir, address)
        readings.append(reading)

    if geocode and geocoded_count > 0:
        click.echo()
        click.echo(f"  Geocoded {geocoded_count} new locations")

    addresses_found = sum(1 for r in readings if r["metadata"].get("address"))
    click.echo(f"  Addresses resolved: {addresses_found}/{len(readings)}")

    traffic_stops = sum(1 for r in readings if r["metadata"]["is_traffic_stop"])
    traffic_jams = sum(1 for r in readings if r["metadata"]["is_traffic_jam"])
    regular = len(readings) - traffic_stops - traffic_jams

    click.echo(f"  Traffic stops: {traffic_stops}")
    click.echo(f"  Traffic jams: {traffic_jams}")
    click.echo(f"  Regular stops: {regular}")

    output = {
        "source": "rider_form",
        "export_date": manifest.get("export_date"),
        "reading_count": len(readings),
        "readings": readings,
    }

    output_path = output_dir / "readings.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    click.echo(f"\nWrote {output_path}")

    if geocode:
        cache_path = output_dir / "address_cache.json"
        with open(cache_path, "w") as f:
            json.dump(address_cache, f, indent=2)
        click.echo(f"Wrote {cache_path}")
