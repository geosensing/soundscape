"""Offline checks for the image and manifest pipeline."""

import json

import pytest
from PIL import Image

from soundscape.downsample import downsample_image, process
from soundscape.merge_readings import merge_readings_into_manifest
from soundscape.utils import build_output_prefix, find_videos


def test_video_discovery_accepts_both_extensions(tmp_path):
    upper = tmp_path / "one.MP4"
    lower = tmp_path / "nested" / "two.mp4"
    lower.parent.mkdir()
    upper.touch()
    lower.touch()
    (tmp_path / "notes.txt").touch()
    (tmp_path / "directory.MP4").mkdir()

    assert set(find_videos(tmp_path)) == {upper, lower}
    assert find_videos(lower) == [lower]
    assert find_videos(tmp_path / "notes.txt") == []


def test_output_prefix_retains_city_date_and_video(tmp_path):
    video = tmp_path / "data" / "delhi" / "04_30_2026" / "GX011906.MP4"
    assert build_output_prefix(video) == "delhi_04_30_2026_GX011906"


def test_merge_preserves_unmatched_frames_and_source_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    readings = tmp_path / "readings.json"
    original = {"videos": [{"frames": [{"path": "one.jpg"}, {"path": "two.jpg"}]}]}
    reading = {"value": 65.5, "unit": "dB", "confidence": 0.9}
    manifest.write_text(json.dumps(original))
    readings.write_text(json.dumps({"readings": [{"frame_path": "one.jpg", "reading": reading}]}))

    output = merge_readings_into_manifest(manifest, readings)
    merged = json.loads(output.read_text())

    assert merged["readings_count"] == 1
    assert merged["readings_merged"] is True
    assert merged["videos"][0]["frames"][0]["reading"] == reading
    assert merged["videos"][0]["frames"][1]["reading"] == {
        "value": None,
        "unit": None,
        "confidence": 0.0,
    }
    assert json.loads(manifest.read_text()) == original


def test_merge_rejects_malformed_readings(tmp_path):
    readings = tmp_path / "readings.json"
    readings.write_text("not JSON")
    with pytest.raises(json.JSONDecodeError):
        merge_readings_into_manifest(tmp_path / "manifest.json", readings)


def test_downsample_writes_decodable_jpeg_at_requested_size(tmp_path):
    source, target = tmp_path / "source.png", tmp_path / "target.jpg"
    Image.new("RGB", (100, 50), "red").save(source)

    downsample_image(source, target, target_size=(40, 20))

    with Image.open(target) as result:
        assert result.size == (40, 20)
        assert result.format == "JPEG"
        assert result.getpixel((20, 10))[0] > 240


def test_batch_downsample_preserves_existing_output(tmp_path):
    source, target = tmp_path / "frames", tmp_path / "resized"
    source.mkdir()
    target.mkdir()
    Image.new("RGB", (20, 10), "red").save(source / "one.jpg")
    existing = target / "one.jpg"
    existing.write_bytes(b"existing output")

    assert process(source, target, target_width=10, target_height=5) == [existing]
    assert existing.read_bytes() == b"existing output"
    process(source, target, target_width=10, target_height=5, skip_existing=False)
    with Image.open(existing) as result:
        assert result.size == (10, 5)
