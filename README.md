# Delhi Street Noise

Street-level noise measurements from 190 locations across Delhi.

## Results

We recorded sound meter readings while walking Delhi streets over 11 days in April-May 2026. Each "stop" is a ~1 minute recording at a location.

**Summary:**
- **190 locations** across Delhi
- **3.4 hours** of total observation (12,159 readings at 1/second)
- **Median noise: 70 dB** (typical street level)
- **4.3% of readings exceed 85 dB** (NIOSH occupational limit)

### How noisy is Delhi?

| Noise Level | % of Time | What it means |
|-------------|-----------|---------------|
| ≥70 dB | 52% | Louder than normal conversation |
| ≥80 dB | 11% | Hearing damage risk with prolonged exposure |
| ≥85 dB | 4.3% | NIOSH 8-hour occupational limit |
| ≥91 dB | 1.4% | NIOSH 2-hour limit |

### Location-level findings

- **69% of stops** (131/190) had at least one reading ≥85 dB
- **12% of stops** (23/190) hit peaks ≥100 dB
- **Median peak** across stops: 89 dB
- Only **1 stop** had sustained high noise (>50% of readings ≥85 dB)

Most locations experience brief spikes above safe levels, but sustained harmful exposure is rare.

### Figures

![Histogram](output/analysis/figs/fig3_histogram.pdf)

See `output/analysis/figs/` for all figures:
- `fig1_map_locations.html` - Interactive map of measurement locations
- `fig3_histogram.pdf` - Distribution of all readings
- `fig4_stop_distributions.pdf` - Per-location summary statistics
- `fig6_per_stop_boxplot.pdf` - Boxplots for each location
- `fig7_exceedance_curves.pdf` - Exceedance curves by location

## Data

### Processed Data

| File | Description |
|------|-------------|
| `output/readings/*.json` | OCR'd decibel readings with GPS |
| `output/analysis/analysis_data.parquet` | All readings as DataFrame |
| `output/analysis/stop_stats.parquet` | Per-location summary stats |
| `output/analysis/tabs/*.tex` | LaTeX tables |

### Raw Video (Harvard Dataverse)

Raw GoPro recordings with embedded GPS telemetry:

| Archive | Size | Videos |
|---------|------|--------|
| `delhi_04_30_2026.tar.gz` | 1.9 GB | 8 |
| `delhi_05_01_2026.tar.gz` | 618 MB | 4 |
| `delhi_05_03_2026.tar.gz` | 2.0 GB | 18 |
| `delhi_05_04_2026.tar.gz` | 2.0 GB | 20 |
| `delhi_05_05_2026.tar.gz` | 2.0 GB | 22 |
| `delhi_05_06_2026.tar.gz` | 2.0 GB | 24 |
| `delhi_05_07_2026.tar.gz` | 416 MB | 3 |
| `delhi_05_08_2026.tar.gz` | 1.9 GB | 22 |
| `delhi_05_09_2026.tar.gz` | 1.9 GB | 24 |
| `delhi_05_13_2026.tar.gz` | 1.6 GB | 27 |
| `delhi_05_14_2026.tar.gz` | 1.9 GB | 17 |
| **Total** | **18 GB** | **192** |

---

## Reproduce the Analysis

### Requirements

- Python 3.13+
- ffmpeg, exiftool (`brew install ffmpeg exiftool`)
- Google API key (for OCR)

### Install

```bash
git clone https://github.com/soodoku/soundscape
cd soundscape
uv sync
uv pip install -e ".[maps]"
```

### Run Analysis

```bash
# Generate figures and tables from existing readings
uv run soundscape analyze --readings output/readings/delhi_full_12728_3-flash-preview_20260523_190001.json

# Open interactive map
open output/analysis/figs/fig1_map_locations.html
```

### Reprocess from Raw Video

If you download the raw videos from Dataverse:

```bash
# Extract frames, GPS, metadata
uv run soundscape extract-frames --input data/delhi
uv run soundscape extract-gps --input data/delhi
uv run soundscape extract-exif --input data/delhi
uv run soundscape downsample
uv run soundscape build-manifest

# OCR the sound meter readings
export GOOGLE_API_KEY=your_key
uv run soundscape ocr-readings --model gemini-2.5-flash

# Generate analysis
uv run soundscape analyze --readings output/readings/readings.json
```

## Methods

### Data Collection

- **Equipment:** Handheld sound level meter + GoPro Hero 12 (4K, 50fps, GPS enabled)
- **Protocol:** Walk to location, hold meter at arm's length, record ~1 minute
- **Dates:** April 30 - May 14, 2026
- **Locations:** 190 stops across Delhi (residential, commercial, roadside)

### Processing Pipeline

1. **Extract frames** - Sample 1 frame/second from 50fps video
2. **Downsample** - Resize to 720p for efficient OCR
3. **Extract GPS** - Pull coordinates from GoPro telemetry
4. **OCR readings** - Use Gemini to read decibel value from each frame
5. **Filter** - Remove readings outside 30-130 dB range (OCR errors)
6. **Analyze** - Generate tables and figures

### OCR Validation

- 95.5% of frames successfully OCR'd
- 5 readings filtered as physically implausible (<30 or >130 dB)
- Manual spot-check via HTML viewer (`soundscape viewer`)

## Pipeline Commands

| Command | Description |
|---------|-------------|
| `extract-frames` | Extract JPEG frames from video |
| `downsample` | Resize frames to 720p |
| `extract-exif` | Extract video metadata |
| `extract-gps` | Extract GPS from GoPro telemetry |
| `build-manifest` | Combine metadata into manifest.json |
| `ocr-readings` | OCR sound meter values |
| `viewer` | Generate HTML viewer for QC |
| `analyze` | Generate tables and figures |
| `create-archives` | Create tar.gz for Dataverse |

## License

MIT
