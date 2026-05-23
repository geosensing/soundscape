"""OCR sound meter readings from frames using Claude batch inference API."""

import base64
import hashlib
import json
import time
from pathlib import Path

import anthropic

from .utils import load_config

OCR_SYSTEM_PROMPT = """You are analyzing images of a sound level meter (decibel meter) display.
Your task is to read the numerical value shown on the display.

Look for:
1. The main numerical reading (usually the largest numbers on screen)
2. The unit (typically dB, dBA, or dBC)

Respond with ONLY a JSON object in this exact format:
{"value": <number or null>, "unit": "<string or null>", "confidence": <0.0-1.0>}

If the reading is not visible, unclear, or the image doesn't show a sound meter:
{"value": null, "unit": null, "confidence": 0.0}

Do not include any other text or explanation."""


def encode_image_base64(image_path: Path) -> str:
    """Encode image to base64 string."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def path_to_custom_id(frame_path: str) -> str:
    """Convert frame path to valid custom_id (alphanumeric, max 64 chars)."""
    return hashlib.sha256(frame_path.encode()).hexdigest()[:64]


def create_batch_request(
    frame_info: dict, custom_id: str, model: str = "claude-haiku-4-5"
) -> dict:
    """Create a single batch request for a frame."""
    image_path = Path(frame_info["frame_path"])
    if not image_path.exists():
        image_path = Path(frame_info.get("original_path", frame_info["frame_path"]))

    if not image_path.exists():
        raise FileNotFoundError(f"Frame image not found: {image_path}")

    image_data = encode_image_base64(image_path)

    return {
        "custom_id": custom_id,
        "params": {
            "model": model,
            "max_tokens": 100,
            "system": OCR_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Read the sound meter value from this image.",
                        },
                    ],
                }
            ],
        },
    }


def submit_batch(
    frames: list[dict],
    model: str = "claude-haiku-4-5",
    api_key: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Submit a batch of frames for OCR processing.

    Returns tuple of (batch_id, id_to_path_mapping).
    """
    client = anthropic.Anthropic(api_key=api_key)

    requests = []
    id_to_path = {}

    for frame in frames:
        try:
            frame_path = frame["frame_path"]
            custom_id = path_to_custom_id(frame_path)
            id_to_path[custom_id] = frame_path
            req = create_batch_request(frame, custom_id, model)
            requests.append(req)
        except Exception as e:
            print(f"Warning: Failed to create request for {frame.get('frame_path')}: {e}")

    if not requests:
        raise ValueError("No valid requests to submit")

    print(f"Submitting batch with {len(requests)} requests...")
    batch = client.messages.batches.create(requests=requests)

    return batch.id, id_to_path


def poll_batch_status(
    batch_id: str,
    api_key: str | None = None,
    poll_interval: int = 30,
) -> dict:
    """Poll batch status until completion.

    Returns the final batch status.
    """
    client = anthropic.Anthropic(api_key=api_key)

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        status = batch.processing_status
        counts = batch.request_counts

        print(
            f"Batch {batch_id}: {status} "
            f"(succeeded={counts.succeeded}, processing={counts.processing}, "
            f"errored={counts.errored})"
        )

        if status == "ended":
            return {
                "id": batch.id,
                "status": status,
                "results_url": batch.results_url,
                "request_counts": {
                    "succeeded": counts.succeeded,
                    "errored": counts.errored,
                    "canceled": counts.canceled,
                    "expired": counts.expired,
                    "processing": counts.processing,
                },
            }

        time.sleep(poll_interval)


def fetch_batch_results(
    batch_id: str,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch results from a completed batch."""
    client = anthropic.Anthropic(api_key=api_key)

    results = []
    for result in client.messages.batches.results(batch_id):
        results.append(result)

    return results


def parse_ocr_response(response_text: str) -> dict:
    """Parse OCR response JSON."""
    try:
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

        data = json.loads(text)
        return {
            "value": data.get("value"),
            "unit": data.get("unit"),
            "confidence": data.get("confidence", 0.0),
        }
    except (json.JSONDecodeError, KeyError):
        return {"value": None, "unit": None, "confidence": 0.0}


def process_batch_results(
    results: list,
    frame_lookup: dict[str, dict],
    id_to_path: dict[str, str],
) -> list[dict]:
    """Process batch results and merge with frame metadata."""
    readings = []

    for result in results:
        custom_id = result.custom_id
        frame_path = id_to_path.get(custom_id, custom_id)
        frame_info = frame_lookup.get(frame_path, {})

        if result.result.type == "succeeded":
            message = result.result.message
            response_text = ""
            for block in message.content:
                if block.type == "text":
                    response_text = block.text
                    break

            reading = parse_ocr_response(response_text)
        else:
            reading = {"value": None, "unit": None, "confidence": 0.0}

        readings.append(
            {
                "frame_path": frame_path,
                "video_id": frame_info.get("video_id", "unknown"),
                "frame_number": frame_info.get("frame_number", 0),
                "timestamp_seconds": frame_info.get("timestamp_seconds"),
                "gps": frame_info.get("gps", {}),
                "reading": reading,
            }
        )

    return readings


def load_frames_from_manifest(manifest_path: Path) -> list[dict]:
    """Load all frames from main manifest."""
    with open(manifest_path) as f:
        manifest = json.load(f)

    frames = []
    for video in manifest.get("videos", []):
        video_id = video.get("video_id", "unknown")
        frame_rate = video.get("exif", {}).get("frame_rate", 50)
        gps = {
            "latitude": video.get("gps", {}).get("median_latitude"),
            "longitude": video.get("gps", {}).get("median_longitude"),
        }

        for frame in video.get("frames", []):
            frame_num = frame.get("frame_number", 0)
            frames.append(
                {
                    "frame_path": frame["path"],
                    "video_id": video_id,
                    "frame_number": frame_num,
                    "timestamp_seconds": frame_num / frame_rate if frame_rate else None,
                    "gps": gps,
                }
            )

    return frames


def load_frames_from_sample_manifest(sample_manifest_path: Path) -> list[dict]:
    """Load frames from sample manifest."""
    with open(sample_manifest_path) as f:
        manifest = json.load(f)
    return manifest.get("samples", [])


def save_readings(readings: list[dict], output_path: Path, batch_id: str) -> None:
    """Save readings to JSON file."""
    output = {
        "batch_id": batch_id,
        "reading_count": len(readings),
        "readings": readings,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)


def save_id_mapping(id_to_path: dict[str, str], output_path: Path) -> None:
    """Save ID to path mapping for later retrieval."""
    with open(output_path, "w") as f:
        json.dump(id_to_path, f, indent=2)


def load_id_mapping(mapping_path: Path) -> dict[str, str]:
    """Load ID to path mapping."""
    with open(mapping_path) as f:
        return json.load(f)


def process(
    manifest_path: Path | None = None,
    output_dir: Path | None = None,
    model: str = "claude-haiku-4-5",
    sample_manifest: Path | None = None,
    batch_id: str | None = None,
    poll_interval: int = 30,
) -> Path:
    """Run OCR on frames using batch API.

    If batch_id is provided, retrieves results from existing batch.
    Otherwise, submits new batch and polls for completion.
    """
    config = load_config()

    if output_dir is None:
        output_dir = Path(config["output_dir"]) / "readings"
    output_dir.mkdir(parents=True, exist_ok=True)

    if sample_manifest:
        frames = load_frames_from_sample_manifest(sample_manifest)
        output_file = output_dir / "sample_readings.json"
        mapping_file = output_dir / "sample_id_mapping.json"
    else:
        if manifest_path is None:
            manifest_path = Path(config["output_dir"]) / "manifest.json"
        frames = load_frames_from_manifest(manifest_path)
        output_file = output_dir / "readings.json"
        mapping_file = output_dir / "id_mapping.json"

    frame_lookup = {f["frame_path"]: f for f in frames}

    if batch_id:
        print(f"Retrieving results for batch {batch_id}...")
        if mapping_file.exists():
            id_to_path = load_id_mapping(mapping_file)
        else:
            id_to_path = {path_to_custom_id(f["frame_path"]): f["frame_path"] for f in frames}
    else:
        batch_id, id_to_path = submit_batch(frames, model)
        print(f"Submitted batch: {batch_id}")

        save_id_mapping(id_to_path, mapping_file)
        print(f"Saved ID mapping -> {mapping_file}")

        print("Polling for completion...")
        status = poll_batch_status(batch_id, poll_interval=poll_interval)
        print(f"Batch completed: {status['request_counts']}")

    results = fetch_batch_results(batch_id)
    readings = process_batch_results(results, frame_lookup, id_to_path)
    save_readings(readings, output_file, batch_id)

    print(f"Saved {len(readings)} readings -> {output_file}")
    return output_file
