"""Generate HTML viewer for OCR results verification with correction capability."""

import base64
import json
from pathlib import Path


def image_to_base64(image_path: Path) -> str:
    """Convert image to base64 data URI."""
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{data}"


def generate_html(readings_path: Path, output_path: Path | None = None) -> Path:
    """Generate HTML viewer for OCR results with editable corrections."""
    with open(readings_path) as f:
        data = json.load(f)

    readings = data.get("readings", [])
    batch_id = data.get("batch_id", "unknown")

    if output_path is None:
        output_path = readings_path.with_suffix(".html")

    total = len(readings)
    ok_count = sum(1 for r in readings if r["reading"]["status"] == "ok")
    fail_count = total - ok_count

    readings_json = json.dumps(readings)

    html_parts = [
        """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OCR Results Viewer</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: #333;
            color: white;
            padding: 20px;
            margin: -20px -20px 20px -20px;
        }
        .header h1 { margin: 0 0 10px 0; }
        .stats {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .stat {
            background: rgba(255,255,255,0.1);
            padding: 10px 20px;
            border-radius: 5px;
        }
        .stat-value { font-size: 24px; font-weight: bold; }
        .stat-label { font-size: 12px; opacity: 0.8; }
        .filters {
            margin-bottom: 20px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .filters label {
            margin-right: 20px;
            cursor: pointer;
        }
        .export-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        .export-btn:hover { background: #0056b3; }
        .card {
            background: white;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .card.hidden { display: none; }
        .card.corrected { border-left: 4px solid #28a745; }
        .card-header {
            padding: 10px 15px;
            background: #f8f8f8;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-header h3 { margin: 0; font-size: 14px; }
        .status {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-ok { background: #d4edda; color: #155724; }
        .status-display_unreadable { background: #fff3cd; color: #856404; }
        .status-meter_not_found { background: #f8d7da; color: #721c24; }
        .status-other { background: #e2e3e5; color: #383d41; }
        .card-body {
            display: flex;
            padding: 15px;
            gap: 20px;
        }
        .image-container {
            flex: 0 0 150px;
        }
        .image-container img {
            width: 150px;
            height: auto;
            border-radius: 4px;
        }
        .annotation {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .reading {
            font-size: 48px;
            font-weight: bold;
            color: #333;
        }
        .reading.null { color: #999; font-size: 24px; }
        .confidence {
            font-size: 14px;
            color: #666;
            margin-top: 10px;
        }
        .correction {
            margin-top: 15px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
        }
        .correction label {
            font-size: 12px;
            color: #666;
            display: block;
            margin-bottom: 5px;
        }
        .correction input {
            width: 100px;
            padding: 8px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .correction input:focus {
            outline: none;
            border-color: #007bff;
        }
        .correction input.has-value {
            border-color: #28a745;
            background: #f0fff4;
        }
        .metadata {
            font-size: 12px;
            color: #999;
            margin-top: 15px;
        }
        .metadata div { margin: 3px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>OCR Results Viewer</h1>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">""",
        str(total),
        """</div>
                <div class="stat-label">Total</div>
            </div>
            <div class="stat">
                <div class="stat-value">""",
        str(ok_count),
        """</div>
                <div class="stat-label">OK</div>
            </div>
            <div class="stat">
                <div class="stat-value">""",
        str(fail_count),
        """</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="corrected-count">0</div>
                <div class="stat-label">Corrected</div>
            </div>
        </div>
    </div>

    <div class="filters">
        <div>
            <strong>Filter:</strong>
            <label><input type="checkbox" checked onchange="filterCards()" id="filter-ok"> OK</label>
            <label><input type="checkbox" checked onchange="filterCards()" id="filter-failed"> Failed</label>
        </div>
        <div>
            <button class="export-btn" onclick="exportCorrections('json')">Export JSON</button>
            <button class="export-btn" onclick="exportCorrections('csv')">Export CSV</button>
        </div>
    </div>

    <div id="cards">
""",
    ]

    for i, r in enumerate(readings):
        reading = r["reading"]
        status = reading["status"]
        decibel = reading["decibel"]
        confidence = reading["confidence"]
        video_id = r.get("video_id", "unknown")
        frame_num = r.get("frame_number", 0)
        frame_path = r.get("frame_path", "")

        # Try to load image
        img_path = Path(frame_path)
        if img_path.exists():
            img_data = image_to_base64(img_path)
        else:
            img_data = ""

        status_class = f"status-{status}" if status in ["ok", "display_unreadable", "meter_not_found"] else "status-other"
        is_ok = status == "ok"

        if decibel is not None:
            reading_display = f"{decibel} dB"
            reading_class = ""
        else:
            reading_display = f"[{status}]"
            reading_class = "null"

        gps = r.get("gps", {})
        lat = gps.get("latitude", "N/A")
        lon = gps.get("longitude", "N/A")

        html_parts.append(f"""
        <div class="card" data-status="{'ok' if is_ok else 'failed'}" data-index="{i}">
            <div class="card-header">
                <h3>#{i+1} - {video_id} (frame {frame_num})</h3>
                <span class="status {status_class}">{status}</span>
            </div>
            <div class="card-body">
                <div class="image-container">
                    <img src="{img_data}" alt="Frame {frame_num}">
                </div>
                <div class="annotation">
                    <div class="reading {reading_class}">{reading_display}</div>
                    <div class="confidence">Confidence: {confidence:.0%}</div>
                    <div class="correction">
                        <label>Correct reading (dB):</label>
                        <input type="number" step="0.1" placeholder="e.g. 72.5"
                               data-index="{i}" onchange="markCorrected(this)">
                    </div>
                    <div class="metadata">
                        <div>Video: {video_id}</div>
                        <div>Frame: {frame_num}</div>
                        <div>GPS: {lat:.6f}, {lon:.6f}</div>
                    </div>
                </div>
            </div>
        </div>
""")

    html_parts.append(
        """
    </div>

    <script>
        const originalReadings = """
        + readings_json
        + """;

        function filterCards() {
            const showOk = document.getElementById('filter-ok').checked;
            const showFailed = document.getElementById('filter-failed').checked;

            document.querySelectorAll('.card').forEach(card => {
                const status = card.dataset.status;
                const show = (status === 'ok' && showOk) || (status === 'failed' && showFailed);
                card.classList.toggle('hidden', !show);
            });
        }

        function markCorrected(input) {
            const card = input.closest('.card');
            if (input.value && input.value.trim() !== '') {
                input.classList.add('has-value');
                card.classList.add('corrected');
            } else {
                input.classList.remove('has-value');
                card.classList.remove('corrected');
            }
            updateCorrectedCount();
        }

        function updateCorrectedCount() {
            const count = document.querySelectorAll('.correction input.has-value').length;
            document.getElementById('corrected-count').textContent = count;
        }

        function exportCorrections(format) {
            const corrections = [];
            document.querySelectorAll('.correction input').forEach(input => {
                const idx = parseInt(input.dataset.index);
                const correctedValue = input.value.trim();
                const original = originalReadings[idx];

                if (correctedValue !== '') {
                    corrections.push({
                        frame_path: original.frame_path,
                        video_id: original.video_id,
                        frame_number: original.frame_number,
                        timestamp_seconds: original.timestamp_seconds,
                        latitude: original.gps ? original.gps.latitude : null,
                        longitude: original.gps ? original.gps.longitude : null,
                        ocr_decibel: original.reading ? original.reading.decibel : null,
                        ocr_status: original.reading ? original.reading.status : null,
                        ocr_confidence: original.reading ? original.reading.confidence : null,
                        corrected_decibel: parseFloat(correctedValue)
                    });
                }
            });

            if (corrections.length === 0) {
                alert('No corrections entered yet.');
                return;
            }

            const dateStr = new Date().toISOString().slice(0,10);

            if (format === 'csv') {
                const headers = ['frame_path', 'video_id', 'frame_number', 'timestamp_seconds',
                                'latitude', 'longitude', 'ocr_decibel', 'ocr_status',
                                'ocr_confidence', 'corrected_decibel'];
                const rows = corrections.map(c =>
                    headers.map(h => c[h] === null ? '' : c[h]).join(',')
                );
                const csv = headers.join(',') + '\\n' + rows.join('\\n');

                const blob = new Blob([csv], {type: 'text/csv'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'corrections_' + dateStr + '.csv';
                a.click();
                URL.revokeObjectURL(url);
            } else {
                const output = {
                    export_time: new Date().toISOString(),
                    correction_count: corrections.length,
                    corrections: corrections
                };

                const blob = new Blob([JSON.stringify(output, null, 2)], {type: 'application/json'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'corrections_' + dateStr + '.json';
                a.click();
                URL.revokeObjectURL(url);
            }
        }
    </script>
</body>
</html>
"""
    )

    html = "".join(html_parts)

    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def process(
    readings_path: Path,
    output_path: Path | None = None,
) -> Path:
    """Generate HTML viewer."""
    output = generate_html(readings_path, output_path)
    print(f"Generated viewer: {output}")
    return output
