.PHONY: all frames exif gps manifest sample ocr merge single clean setup lint test

all: frames exif gps manifest

setup:
	uv sync
	@echo "Checking for required external tools..."
	@command -v ffmpeg >/dev/null 2>&1 || (echo "ffmpeg not found. Install with: brew install ffmpeg" && exit 1)
	@command -v exiftool >/dev/null 2>&1 || (echo "exiftool not found. Install with: brew install exiftool" && exit 1)
	@echo "All dependencies installed."

frames:
	uv run soundscape extract-frames --input data/

exif:
	uv run soundscape extract-exif --input data/

gps:
	uv run soundscape extract-gps --input data/

manifest:
	uv run soundscape build-manifest

sample:
	uv run soundscape sample-frames

ocr:
	uv run soundscape ocr-readings

merge:
	uv run soundscape merge-readings

single:
ifndef VIDEO
	$(error VIDEO is not set. Usage: make single VIDEO=path/to/video.MP4)
endif
	uv run soundscape extract-exif --input $(VIDEO)
	uv run soundscape extract-gps --input $(VIDEO)
	uv run soundscape extract-frames --input $(VIDEO)
	uv run soundscape build-manifest

clean:
	rm -rf output/frames/* output/exif/* output/gps/* output/samples/* output/readings/*
	rm -f output/manifest.json output/manifest_with_readings.json

lint:
	uv run ruff check src/
	uv run ruff format --check src/

test:
	uv run pytest
