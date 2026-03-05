/**
 * upload.js
 * Handles drag-and-drop file selection, form submission, progress feedback,
 * and rendering of ingestion reports for the HPHP Claims Upload Portal.
 */

(function () {
  "use strict";

  // ── Configuration ───────────────────────────────────────────────────────────
  // Override this by setting window.HPHP_API_BASE before this script loads, e.g.:
  //   <script>window.HPHP_API_BASE = "https://your-render-service.onrender.com";</script>
  // If running locally for development, set it to "http://localhost:5000".
  const API_BASE =
    window.HPHP_API_BASE ||
    "https://your-render-service.onrender.com";

  const UPLOAD_ENDPOINT = `${API_BASE}/upload`;

  // ── DOM references ───────────────────────────────────────────────────────────
  const form = document.getElementById("upload-form");
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const fileList = document.getElementById("file-list");
  const submitBtn = document.getElementById("submit-btn");
  const clearBtn = document.getElementById("clear-btn");
  const progressWrap = document.getElementById("progress-wrap");
  const progressBar = document.getElementById("progress-bar");
  const progressLabel = document.getElementById("progress-label");
  const ingestionReport = document.getElementById("ingestion-report");

  // Metric card counters
  const statFiles = document.getElementById("stat-files");
  const statRecords = document.getElementById("stat-records");
  const statLast = document.getElementById("stat-last");
  const statStatus = document.getElementById("stat-status");

  // Session counters
  let sessionFiles = 0;
  let sessionRecords = 0;

  // Accumulated selected files
  let selectedFiles = [];

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function sanitizeFilename(name) {
    return name.replace(/[^a-zA-Z0-9._\-]/g, "_");
  }

  function setProgress(pct) {
    const clamped = Math.min(100, Math.max(0, pct));
    progressBar.style.width = `${clamped}%`;
    progressBar.setAttribute("aria-valuenow", clamped);
    progressLabel.textContent = `${clamped}%`;
  }

  function showProgress() {
    progressWrap.hidden = false;
    setProgress(0);
  }

  function hideProgress() {
    progressWrap.hidden = true;
    setProgress(0);
  }

  // ── File list management ─────────────────────────────────────────────────────

  function renderFileList() {
    fileList.innerHTML = "";
    selectedFiles.forEach(function (file, idx) {
      const li = document.createElement("li");
      li.className = "file-list-item";
      li.innerHTML = `
        <span class="file-icon">📄</span>
        <span class="file-name" title="${sanitizeFilename(file.name)}">${file.name}</span>
        <span class="file-size">${formatBytes(file.size)}</span>
        <button class="file-remove" data-idx="${idx}" aria-label="Remove ${file.name}">✕</button>
      `;
      fileList.appendChild(li);
    });

    submitBtn.disabled = selectedFiles.length === 0;
  }

  function addFiles(newFiles) {
    Array.from(newFiles).forEach(function (f) {
      const alreadyAdded = selectedFiles.some(
        (existing) => existing.name === f.name && existing.size === f.size
      );
      if (!alreadyAdded) {
        selectedFiles.push(f);
      }
    });
    renderFileList();
  }

  function removeFile(idx) {
    selectedFiles.splice(idx, 1);
    renderFileList();
  }

  function clearFiles() {
    selectedFiles = [];
    fileInput.value = "";
    renderFileList();
    hideProgress();
    ingestionReport.innerHTML =
      '<p class="report-placeholder">No uploads yet. Submit files above to see results.</p>';
  }

  // ── Event: drop zone click / keyboard ────────────────────────────────────────

  dropZone.addEventListener("click", function () {
    fileInput.click();
  });

  dropZone.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener("change", function () {
    addFiles(fileInput.files);
  });

  // ── Event: drag-and-drop ─────────────────────────────────────────────────────

  ["dragenter", "dragover"].forEach(function (evt) {
    dropZone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropZone.classList.add("drop-zone--active");
    });
  });

  ["dragleave", "drop"].forEach(function (evt) {
    dropZone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropZone.classList.remove("drop-zone--active");
    });
  });

  dropZone.addEventListener("drop", function (e) {
    const files = e.dataTransfer.files;
    addFiles(files);
  });

  // ── Event: remove file ───────────────────────────────────────────────────────

  fileList.addEventListener("click", function (e) {
    const btn = e.target.closest(".file-remove");
    if (btn) {
      removeFile(parseInt(btn.dataset.idx, 10));
    }
  });

  // ── Event: clear button ──────────────────────────────────────────────────────

  clearBtn.addEventListener("click", clearFiles);

  // ── Ingestion report renderer ────────────────────────────────────────────────

  function statusBadge(status) {
    const cls = status === "accepted" ? "badge badge--success" : "badge badge--error";
    return `<span class="${cls}">${status.toUpperCase()}</span>`;
  }

  function renderReport(data) {
    if (!data || !data.results) {
      ingestionReport.innerHTML = '<p class="report-error">Unexpected server response.</p>';
      return;
    }

    let totalRows = 0;
    let html = `<p class="report-overall">Overall status: <strong>${data.overall_status}</strong></p>`;

    data.results.forEach(function (r) {
      const isAccepted = r.status === "accepted";
      html += `
        <div class="report-card ${isAccepted ? "report-card--success" : "report-card--error"}">
          <div class="report-card-header">
            <span class="report-filename">${r.filename || "Unknown file"}</span>
            ${statusBadge(r.status || "error")}
            ${r.file_type ? `<span class="badge badge--info">${r.file_type}</span>` : ""}
          </div>`;

      if (r.validation) {
        const v = r.validation;
        html += `
          <table class="report-table">
            <tr><th>Rows Processed</th><td>${v.rows_processed}</td></tr>
            <tr><th>Detected Type</th><td>${v.detected_file_type}</td></tr>
            <tr><th>Validation</th><td>${v.validation_status}</td></tr>
            ${v.missing_columns && v.missing_columns.length ? `<tr><th>Missing Columns</th><td class="text-warn">${v.missing_columns.join(", ")}</td></tr>` : ""}
            ${v.invalid_fields && v.invalid_fields.length ? `<tr><th>Invalid Fields</th><td class="text-error">${v.invalid_fields.join(", ")}</td></tr>` : ""}
            ${v.phi_columns_removed && v.phi_columns_removed.length ? `<tr><th>PHI Removed</th><td class="text-info">${v.phi_columns_removed.join(", ")}</td></tr>` : ""}
          </table>`;
      }

      if (isAccepted && r.processing) {
        const p = r.processing;
        totalRows += p.rows_out || 0;
        html += `
          <table class="report-table">
            <tr><th>Rows In</th><td>${p.rows_in}</td></tr>
            <tr><th>Rows Out</th><td>${p.rows_out}</td></tr>
            <tr><th>Duplicates Removed</th><td>${p.duplicates_removed}</td></tr>
          </table>`;
      }

      if (r.error) {
        html += `<p class="text-error">${r.error}</p>`;
      }

      html += `</div>`;
    });

    ingestionReport.innerHTML = html;

    // Update metric cards
    sessionFiles += data.results.length;
    sessionRecords += totalRows;
    statFiles.textContent = sessionFiles;
    statRecords.textContent = sessionRecords.toLocaleString();
    statLast.textContent = new Date().toLocaleTimeString();
    statStatus.textContent = data.overall_status === "success" ? "✅ Passed" : "⚠️ Check Log";
  }

  // ── Event: form submit ───────────────────────────────────────────────────────

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    if (selectedFiles.length === 0) return;

    const tpaSource = document.getElementById("tpa-source").value;
    const reportMonth = document.getElementById("report-month").value;

    const formData = new FormData();
    selectedFiles.forEach(function (f) {
      formData.append("files[]", f, f.name);
    });
    if (tpaSource) formData.append("tpa_source", tpaSource);
    if (reportMonth) formData.append("report_month", reportMonth);

    submitBtn.disabled = true;
    showProgress();
    setProgress(20);

    try {
      setProgress(50);
      const response = await fetch(UPLOAD_ENDPOINT, {
        method: "POST",
        body: formData,
      });

      setProgress(80);

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setProgress(100);

      setTimeout(function () {
        hideProgress();
        renderReport(data);
        clearFiles();
      }, 600);

    } catch (err) {
      hideProgress();
      ingestionReport.innerHTML = `
        <div class="report-card report-card--error">
          <p class="text-error"><strong>Upload failed:</strong> ${err.message}</p>
          <p>Please check your network connection and try again.</p>
        </div>`;
      submitBtn.disabled = false;
    }
  });

})();
