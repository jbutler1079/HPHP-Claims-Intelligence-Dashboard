"""
api.py
Flask REST API for the HPHP Claims Intelligence Platform.
Deployed on Render (python environment).
"""

import os
import sys

# Ensure project root is on the path so sibling packages resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS

from webapp.upload_handler import handle_upload

app = Flask(__name__)
CORS(app)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    return jsonify({"service": "HPHP Claims Intelligence API", "status": "running"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})


@app.route("/upload", methods=["POST"])
def upload():
    """
    Accept one or more claims files.

    Form fields:
      files[]     – one or more file uploads
      tpa_source  – optional TPA/PBM label
      report_month – optional report month label (YYYY-MM)

    Returns JSON ingestion report for each file.
    """
    if "files[]" not in request.files and "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file_list = request.files.getlist("files[]") or [request.files.get("file")]
    tpa_source = request.form.get("tpa_source", "")
    report_month = request.form.get("report_month", "")

    reports = []
    for file in file_list:
        if file.filename == "":
            reports.append({"error": "empty filename"})
            continue

        if not _allowed_file(file.filename):
            reports.append({"error": f"unsupported file type: {file.filename}"})
            continue

        file_bytes = file.read()
        result = handle_upload(
            file_bytes=file_bytes,
            filename=file.filename,
            tpa_source=tpa_source,
            report_month=report_month,
        )
        reports.append(result)

    accepted = sum(1 for r in reports if r.get("status") == "accepted")
    if accepted == len(reports):
        overall_status = "success"
    elif accepted > 0:
        overall_status = "partial"
    else:
        overall_status = "failed"
    return jsonify({"overall_status": overall_status, "results": reports})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
