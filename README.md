# Delhi Street Noise

Street-level noise measurements from 655 locations across Delhi.

## Results

We recorded sound meter readings while walking and riding Delhi streets over 20+ days in April-May 2026.

**Summary (GoPro continuous + Rider spot measurements):**
- **655 locations** across Delhi (190 GoPro, 465 Rider)
- **3.4+ hours** of continuous observation (12,159 GoPro readings at 1/second)
- **Median GoPro noise: 70 dB** | **Median Rider max: 81 dB**
- **4.3% of GoPro readings exceed 85 dB** (NIOSH occupational limit)
- **38% of Rider stops** recorded peaks ≥85 dB

### How noisy is Delhi?

| Noise Level | GoPro (% of Time) | Rider (% of Stops) | Reference |
|-------------|-------------------|---------------------|-----------|
| ≥70 dB | 52% | 82% | Louder than normal conversation |
| ≥80 dB | 11% | 52% | Hearing damage risk with prolonged exposure |
| ≥85 dB | 4.3% | 38% | NIOSH 8-hour occupational limit |
| ≥91 dB | 1.4% | 25% | NIOSH 2-hour limit |

### Comparison to Other Cities

How does Delhi compare to urban traffic noise elsewhere? At traffic stops and jams, you're largely hearing engine idling and slow-moving vehicles - conditions that should produce similar noise levels across cities.

| Location | Average dB | Peak Range | Source |
|----------|------------|------------|--------|
| **Delhi (this study)** | 70 dB (GoPro mean) | 49-128 dB | Continuous measurement |
| NYC streets | 73.4 dBA | 56-95 dB | [Neitzel et al. 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC4350859/) |
| NYC high traffic | 77.2 dBA | - | Same study |
| Manhattan | 74.6 dBA | - | Same study |
| US busy urban street | 70-80 dB | - | [CODOT](https://www.codot.gov/programs/environmental/noise/noise-faqs) |
| EU road traffic (67M exposed) | >55 dB Lden | - | [EEA 2024](https://www.eea.europa.eu/en/analysis/indicators/exposure-of-europe-population-to-noise) |

**Key finding:** Delhi's average street noise (~70 dB) is comparable to NYC and other busy urban environments. However, Delhi shows more extreme peaks - 38% of rider stops recorded ≥85 dB, and 25% exceeded 91 dB. This suggests Delhi's noise problem is less about average levels and more about frequent high-intensity spikes (horns, engines revving).

### Noise by Road Type (Rider Data)

| Road Type | N | Mean Max dB | % ≥85 dB |
|-----------|---|-------------|----------|
| Trunk (major highway) | 21 | 99.5 | 71% |
| Primary | 30 | 94.7 | 70% |
| Secondary | 65 | 92.3 | 65% |
| Tertiary | 110 | 84.7 | 36% |
| Residential | 194 | 77.3 | 18% |

### Location-level findings (GoPro continuous data)

- **69% of stops** (131/190) had at least one reading ≥85 dB
- **12% of stops** (23/190) hit peaks ≥100 dB
- **Median peak** across stops: 89 dB
- Only **1 stop** had sustained high noise (>50% of readings ≥85 dB)

Most locations experience brief spikes above safe levels, but sustained harmful exposure is rare.

### Rider data findings (465 spot measurements)

- **Mean max dB: 84** across all stops
- **Mean min dB: 66** (baseline noise level)
- **81 traffic stops** and **19 traffic jams** recorded
- Road type strongly predicts noise: trunk roads average 99.5 dB max vs 77.3 dB on residential streets

### Figures

**GoPro analysis** (`output/analysis/figs/`):
- `delhi_gopro_fig1_map.html` - Interactive map of measurement locations
- `delhi_gopro_fig2_histogram.pdf` - Distribution of all readings
- `delhi_gopro_fig3_stop_distributions.pdf` - Per-location summary statistics

**Rider analysis** (`output/rider/analysis/figs/`):
- `delhi_rider_fig1_map.html` - Interactive map of rider stops
- `delhi_rider_fig2_histogram.pdf` - Distribution of max dB readings
- `delhi_rider_fig4_boxplot.pdf` - Noise by road type
- `delhi_rider_fig5_scatter.pdf` - Min vs max dB correlation

**Comparison** (`output/comparison/figs/`):
- `delhi_compare_fig1_map.html` - Map showing both datasets with matches
- `delhi_compare_fig2_correlation.pdf` - Rider max dB vs GoPro mean dB
- `delhi_compare_fig4_road_type.pdf` - GoPro noise by road type

## Data

### Processed Data

| File | Description |
|------|-------------|
| `output/readings/*.json` | GoPro OCR'd decibel readings with GPS |
| `output/rider/readings.json` | Rider spot measurements with road type metadata |
| `output/analysis/delhi_gopro_data.parquet` | GoPro readings as DataFrame |
| `output/rider/analysis/delhi_rider_data.parquet` | Rider data with road type |
| `output/comparison/delhi_compare_matched.parquet` | GoPro-Rider location matches |
| `output/*/tabs/delhi_*.tex` | LaTeX tables |

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
| `analyze` | Generate GoPro analysis tables and figures |
| `analyze-rider` | Generate rider data analysis with road type breakdown |
| `compare-locations` | Compare rider and GoPro locations for overlap |
| `create-archives` | Create tar.gz for Dataverse |

## Rider Data Pipeline

For data collected via the [rider route tool](https://github.com/soodoku/missing-women-rider-route-tool), conversion scripts are in that repo:

```bash
cd ../missing-women-rider-route-tool

# Sound data -> soundscape
python3 export_sound.py \
    --manifest exports/2026-05-24/manifest.json \
    --output ../soundscape/output/rider \
    --geocode

# Pollution data -> streetaqi
python3 export_pollution.py \
    --manifest exports/2026-05-24/manifest.json \
    --output ../streetaqi/data/rider \
    --city delhi \
    --geocode
```

### Analyze Rider Data

```bash
# Generate rider-specific analysis (by road type, traffic conditions)
uv run soundscape analyze-rider --readings output/rider/readings.json

# Compare rider and GoPro locations for spatial overlap
uv run soundscape compare-locations \
    --rider output/rider/readings.json \
    --gopro "output/readings/delhi_full_*.json"
```

## License

MIT
