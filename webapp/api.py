"""
api.py
Flask REST API for the HPHP Claims Intelligence Platform.
Deployed on Render (python environment).
"""

import os
import sys

# Ensure project root is on the path so sibling packages resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, send_from_directory, make_response

from webapp.upload_handler import handle_upload
from webapp.onedrive_sync import download_masters

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(__name__)

# Restore master CSVs from OneDrive on every cold start (Render filesystem is ephemeral).
download_masters()

# Manual CORS — inject headers on every response so the browser preflight succeeds.
# This bypasses flask-cors entirely and is guaranteed to work.
@app.after_request
def _add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"]       = "86400"
    return response

# Handle preflight OPTIONS requests for every route.
@app.before_request
def _handle_options():
    if request.method == "OPTIONS":
        resp = make_response("", 204)
        resp.headers["Access-Control-Allow-Origin"]  = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Max-Age"]       = "86400"
        return resp

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(FRONTEND_DIR, "wordpress_upload_embed.html")


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
