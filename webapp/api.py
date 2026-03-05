"""
api.py
Flask REST API for the HPHP Claims Intelligence Platform.
Deployed on Render (python environment).
"""

import os
import sys

# Ensure project root is on the path so sibling packages resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin

from webapp.upload_handler import handle_upload

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(__name__)

# Read allowed origins from the environment so the WordPress domain can be
# locked in via the Render dashboard without changing code.
# CORS_ORIGINS accepts "*" or a comma-separated list of origins, e.g.:
#   https://yourwordpresssite.com,https://www.yourwordpresssite.com
_raw_origins = os.environ.get("CORS_ORIGINS", "*").strip()
_cors_origins = "*" if _raw_origins == "*" else [o.strip() for o in _raw_origins.split(",")]
CORS(app, origins=_cors_origins)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    embed_path = os.path.join(FRONTEND_DIR, "wordpress_upload_embed.html")
    with open(embed_path, "r", encoding="utf-8") as fh:
        embed = fh.read()
    full_page = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>HPHP Claims Intelligence Platform</title>"
        "</head><body style='margin:0;background:#0b1e28;'>"
        + embed +
        "</body></html>"
    )
    return full_page, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/frontend/<path:filename>", methods=["GET"])
def frontend_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/static/<path:filename>", methods=["GET"])
def static_files(filename):
    static_dir = os.path.join(FRONTEND_DIR, "static")
    return send_from_directory(static_dir, filename)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})


@app.route("/upload", methods=["POST"])
@cross_origin(origins="*")
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
        try:
            result = handle_upload(
                file_bytes=file_bytes,
                filename=file.filename,
                tpa_source=tpa_source,
                report_month=report_month,
            )
        except Exception as exc:
            result = {
                "status": "rejected",
                "filename": file.filename,
                "validation": {
                    "file_name": file.filename,
                    "rows_processed": 0,
                    "missing_columns": [],
                    "invalid_fields": [f"server_error:{exc}"],
                    "detected_file_type": "unknown",
                    "validation_status": "failed",
                    "phi_columns_removed": [],
                },
            }
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
