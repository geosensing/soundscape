# Soundscape

Pipeline to extract, OCR, and analyze sound meter readings from GoPro video recordings for street-level noise exposure research.

## Delhi Street Noise Study

We collected street-level noise measurements across 190 locations in Delhi using a handheld sound meter recorded on GoPro. The analysis covers **3.4 hours of observation** (12,159 valid readings sampled at 1 per second).

### Key Findings

| Metric | Value |
|--------|-------|
| Locations sampled | 190 stops |
| Total observation time | 3.4 hours |
| Mean noise level | 70.2 dB |
| Median noise level | 70.3 dB |

**Threshold Exceedance:**

| Threshold | % of readings | Interpretation |
|-----------|---------------|----------------|
| ≥70 dB | 51.6% | Louder than conversation |
| ≥75 dB | 28.3% | Requires raised voice |
| ≥80 dB | 11.4% | Potential hearing damage with prolonged exposure |
| ≥85 dB | 4.3% | NIOSH 8-hour exposure limit |
| ≥91 dB | 1.4% | NIOSH 2-hour exposure limit |

**Per-Location Analysis:**
- 131 of 190 stops (69%) had at least one reading ≥85 dB
- 23 stops (12%) recorded peaks ≥100 dB
- Median peak noise across stops: 89.3 dB
- Only 1 stop had majority (>50%) of readings above 85 dB

The data shows Delhi streets are consistently noisy (median 70 dB) with frequent spikes above safe occupational limits. Most locations experience brief exposures to harmful noise levels, though sustained high exposure is rare.

### Analysis Outputs

Run `soundscape analyze` to generate publication-ready tables and figures:

```
output/analysis/
├── figs/
│   ├── fig1_map_locations.html    # Interactive map of collection points
│   ├── fig2_map_static.pdf        # Static map for print
│   ├── fig3_histogram.pdf         # Distribution with NIOSH thresholds
│   ├── fig4_stop_distributions.pdf # Per-stop summary statistics
│   ├── fig5_all_data_by_stop.pdf  # All readings ordered by stop
│   ├── fig6_per_stop_boxplot.pdf  # Boxplots for each location
│   ├── fig7_exceedance_curves.pdf # Per-stop exceedance curves
│   └── fig8_temporal_pattern.pdf  # Noise by position in recording
├── tabs/
│   ├── table1_summary.tex         # Overall summary statistics
│   ├── table2_stop_distribution.tex # Distribution of per-stop metrics
│   └── table3_threshold_exceedance.tex # Threshold analysis
├── analysis_data.parquet          # Processed readings
└── stop_stats.parquet             # Per-stop summary statistics
```

---

## Installation

**Requirements:**
- Python 3.13+
- ffmpeg (`brew install ffmpeg`)
- exiftool (`brew install exiftool`)
- API key for OCR (Anthropic or Google)

```bash
# Install with core dependencies
uv sync

# Install with mapping libraries (for analyze command)
uv pip install -e ".[maps]"
```

## Pipeline Commands

| # | Command | Description |
|---|---------|-------------|
| 1 | `extract-frames` | Extract JPEG frames at specified intervals |
| 2 | `downsample` | Resize frames for efficient OCR processing |
| 3 | `extract-exif` | Extract video metadata (duration, fps, camera) |
| 4 | `extract-gps` | Extract GPS coordinates from GoPro telemetry |
| 5 | `build-manifest` | Combine all metadata into manifest.json |
| 6 | `sample-frames` | Sample random frames for manual verification |
| 7 | `ocr-readings` | OCR sound meter values using Claude/Gemini |
| 8 | `merge-readings` | Merge OCR results into manifest |
| 9 | `create-archives` | Create tar.gz archives for data sharing |
| 10 | `validate` | Validate pipeline outputs match inputs |
| 11 | `viewer` | Generate HTML viewer for OCR verification |
| 12 | `analyze` | Generate publication-ready tables and figures |

## Quick Start

### Full Pipeline

```bash
# Extract everything and build manifest
make all

# Run OCR on all frames
export ANTHROPIC_API_KEY=your_key  # or GOOGLE_API_KEY
uv run soundscape ocr-readings --manifest output/manifest.json

# Generate analysis
uv run soundscape analyze --readings output/readings/readings.json
```

### Step-by-Step

```bash
# 1. Extract frames (1 per second from 50fps video)
uv run soundscape extract-frames --input data/

# 2. Downsample to 720p for efficient OCR
uv run soundscape downsample

# 3. Extract video metadata
uv run soundscape extract-exif --input data/

# 4. Extract GPS coordinates from GoPro telemetry
uv run soundscape extract-gps --input data/

# 5. Build manifest combining all metadata
uv run soundscape build-manifest

# 6. Run OCR (supports Claude and Gemini models)
uv run soundscape ocr-readings --model gemini-2.5-flash

# 7. Generate HTML viewer to verify OCR quality
uv run soundscape viewer --readings output/readings/readings.json

# 8. Run analysis
uv run soundscape analyze --readings output/readings/readings.json
```

## OCR Models

The pipeline supports multiple models for OCR:

| Model | Provider | Notes |
|-------|----------|-------|
| `claude-haiku-4-5` | Anthropic | Default, good accuracy |
| `claude-sonnet-4-5` | Anthropic | Higher accuracy |
| `gemini-2.0-flash` | Google | Fast, cost-effective |
| `gemini-2.5-flash` | Google | Good balance |
| `gemini-2.5-flash-lite` | Google | Fastest |
| `gemini-3-flash-preview` | Google | Latest |

```bash
# Use Gemini (requires GOOGLE_API_KEY)
uv run soundscape ocr-readings --model gemini-2.5-flash

# Use Claude batch API (50% cheaper, requires ANTHROPIC_API_KEY)
uv run soundscape ocr-readings --model claude-haiku-4-5
```

## Output Structure

```
output/
├── frames/                 # Full-resolution extracted frames
├── frames_720p/            # Downsampled frames for OCR
├── exif/                   # Video metadata JSON files
├── gps/                    # GPS telemetry JSON files
├── samples/                # Sampled frames for verification
├── readings/               # OCR results
│   ├── *.json              # Raw readings
│   └── *.html              # Verification viewer
├── analysis/               # Analysis outputs
│   ├── figs/               # PDF figures + HTML maps
│   ├── tabs/               # LaTeX tables
│   └── *.parquet           # Processed data
└── manifest.json           # Combined metadata
```

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

## License

MIT
