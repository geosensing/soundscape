# Soundscape

Extract frames and OCR sound meter readings from GoPro video recordings.

## Requirements

- Python 3.11+
- ffmpeg (`brew install ffmpeg`)
- exiftool (`brew install exiftool`)
- Anthropic API key (for OCR)

## Installation

```bash
uv sync
```

## Quick Start

### Full Pipeline

```bash
# Extract everything and build manifest
make all

# Run OCR on all frames (requires ANTHROPIC_API_KEY)
make ocr
```

### Step-by-Step

```bash
# 1. Extract frames (1 per second at 50fps)
uv run soundscape extract-frames --input data/

# 2. Extract video metadata
uv run soundscape extract-exif --input data/

# 3. Extract GPS coordinates
uv run soundscape extract-gps --input data/

# 4. Build manifest combining all data
uv run soundscape build-manifest

# 5. Sample frames for manual verification
uv run soundscape sample-frames --frames-per-video 1 --seed 42

# 6. Run OCR on frames (batch API - 50% cheaper)
export ANTHROPIC_API_KEY=your_key
uv run soundscape ocr-readings --manifest output/manifest.json

# 7. Merge readings into manifest
uv run soundscape merge-readings
```

### Process Single Video

```bash
make single VIDEO=data/delhi/04_30_2026/GX011906.MP4
```

## Commands

| # | Command | Description |
|---|---------|-------------|
| 1 | `extract-frames` | Extract JPEG frames at specified intervals |
| 2 | `extract-exif` | Extract video metadata (duration, fps, camera) |
| 3 | `extract-gps` | Extract GPS coordinates from GoPro telemetry |
| 4 | `build-manifest` | Combine all metadata into manifest.json |
| 5 | `sample-frames` | Sample random frames for manual annotation |
| 6 | `ocr-readings` | OCR sound meter values using Claude batch API |
| 7 | `merge-readings` | Merge OCR results into manifest |

## Output Structure

```
output/
├── frames/                 # Extracted JPEG frames
│   └── {city}_{date}_{video}_{frame}.jpg
├── exif/                   # Video metadata
│   └── {city}_{date}_{video}_exif.json
├── gps/                    # GPS telemetry
│   └── {city}_{date}_{video}_gps.json
├── samples/                # Sampled frames for verification
│   ├── *.jpg
│   └── sample_manifest.json
├── readings/               # OCR results
│   └── readings.json
├── manifest.json           # All metadata combined
└── manifest_with_readings.json  # Manifest + OCR readings
```

## Configuration

Edit `config.yaml`:

```yaml
data_dir: data
output_dir: output

frames:
  interval: 50    # Extract every 50th frame (1fps at 50fps)
  quality: 95     # JPEG quality

gps:
  max_spread_meters: 50  # Warn if GPS points spread > 50m

processing:
  skip_existing: true
```

## Sampling for Manual Verification

Sample random frames to verify OCR quality:

```bash
# Sample 2 frames per video, skip first 10s and last 5s
uv run soundscape sample-frames \
    --frames-per-video 2 \
    --seed 42 \
    --start-skip 10.0 \
    --end-skip 5.0
```

Frames are saved to `output/samples/` with `sample_manifest.json` tracking which videos they came from.

## OCR with Batch API

The OCR uses Anthropic's Message Batches API for 50% cost savings:

```bash
# Process all frames (creates batch, polls until done)
uv run soundscape ocr-readings --model claude-haiku-4-5

# Process only sampled frames
uv run soundscape ocr-readings --sample-manifest output/samples/sample_manifest.json

# Resume/check existing batch
uv run soundscape ocr-readings --batch-id msgbatch_abc123
```

Output format (`readings.json`):
```json
{
  "batch_id": "msgbatch_...",
  "reading_count": 5483,
  "readings": [
    {
      "frame_path": "output/frames/delhi_04_30_2026_GX011906_000050.jpg",
      "video_id": "delhi_04_30_2026_GX011906",
      "frame_number": 50,
      "timestamp_seconds": 1.0,
      "gps": {"latitude": 28.5497, "longitude": 77.1979},
      "reading": {"value": 72.3, "unit": "dB", "confidence": 0.95}
    }
  ]
}
```

If reading is not visible: `{"value": null, "unit": null, "confidence": 0.0}`

## Data Directory Structure

Expected input structure:
```
data/
└── {city}/
    └── {MM_DD_YYYY}/
        └── *.MP4
```

Example:
```
data/
└── delhi/
    ├── 04_30_2026/
    │   ├── GX011906.MP4
    │   └── GX011907.MP4
    └── 05_01_2026/
        └── GX011917.MP4
```
