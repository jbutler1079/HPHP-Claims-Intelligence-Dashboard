(function () {
  "use strict";

  var API_URL = "https://hphp-claims-api.onrender.com/upload";

  // Wait for DOM ready — WordPress can execute external scripts before the
  // Custom HTML block is parsed, so getElementById would return null if we
  // ran immediately. We retry until the elements exist.
  function init() {
    var form      = document.getElementById("hci-form");
    var fileInput = document.getElementById("hci-files");
    if (!form || !fileInput) { setTimeout(init, 150); return; }

    var source     = document.getElementById("hci-source");
    var month      = document.getElementById("hci-month");
    var drop       = document.getElementById("hci-drop");
    var fileList   = document.getElementById("hci-file-list");
    var submitBtn  = document.getElementById("hci-submit");
    var clearBtn   = document.getElementById("hci-clear");
    var progressEl = document.getElementById("hci-progress");
    var barEl      = document.getElementById("hci-bar");
    var statusEl   = document.getElementById("hci-status");
    var statusText = document.getElementById("hci-status-text");
    var reportEl   = document.getElementById("hci-report");
    var tsEl       = document.getElementById("hci-timestamp");
    var sFiles     = document.getElementById("hci-s-files");
    var sRows      = document.getElementById("hci-s-rows");
    var sDupes     = document.getElementById("hci-s-dupes");
    var sPhi       = document.getElementById("hci-s-phi");

    var files  = [];
    var totals = { files: 0, rows: 0, dupes: 0, phi: 0 };
    var MAX_FILES = 4;
    var MAX_SIZE  = 50 * 1024 * 1024;
    var ALLOWED   = ["csv", "xlsx", "xls"];

    function fmtBytes(n) {
      if (n < 1024) return n + " B";
      if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
      return (n / 1048576).toFixed(1) + " MB";
    }
    function extOf(name) { return (name.split(".").pop() || "").toLowerCase(); }
    function setBar(pct) {
      barEl.style.width = Math.max(0, Math.min(100, pct)) + "%";
      progressEl.setAttribute("aria-valuenow", pct);
    }
    function showBar() { progressEl.style.display = "block"; setBar(0); }
    function hideBar() { progressEl.style.display = "none";  setBar(0); }
    function setStatus(text, tone) {
      statusText.textContent = text;
      statusEl.setAttribute("data-tone", tone || "");
    }
    function updateSubmit() { submitBtn.disabled = files.length === 0; }
    function stampTime() { tsEl.textContent = "Last activity: " + new Date().toLocaleString(); }

    function renderFiles() {
      fileList.innerHTML = "";
      files.forEach(function (file, idx) {
        var ext = extOf(file.name);
        var iconCls = ext === "csv" ? "hci-file__icon--csv" : "hci-file__icon--xlsx";
        var li = document.createElement("li");
        li.className = "hci-file";
        li.innerHTML =
          '<span class="hci-file__icon ' + iconCls + '">' + ext.toUpperCase() + '</span>' +
          '<span class="hci-file__name" title="' + file.name + '">' + file.name + '</span>' +
          '<span class="hci-file__size">' + fmtBytes(file.size) + '</span>' +
          '<button type="button" class="hci-file__remove" data-i="' + idx + '" aria-label="Remove">&#215;</button>';
        fileList.appendChild(li);
      });
      updateSubmit();
    }

    function addFiles(incoming) {
      var warnings = [];
      Array.from(incoming).forEach(function (f) {
        var ext = extOf(f.name);
        if (ALLOWED.indexOf(ext) === -1) { warnings.push(f.name + ": unsupported format"); return; }
        if (f.size > MAX_SIZE) { warnings.push(f.name + ": exceeds 50 MB"); return; }
        if (files.length >= MAX_FILES) { warnings.push(f.name + ": batch limit reached (4)"); return; }
        if (files.some(function (e) { return e.name === f.name && e.size === f.size; })) return;
        files.push(f);
      });
      renderFiles();
      if (warnings.length) {
        setStatus("Skipped: " + warnings.join("; "), "warn");
      } else if (files.length) {
        setStatus(files.length + " file" + (files.length > 1 ? "s" : "") + " staged for upload.", "");
      }
    }

    function clearAll() {
      files = [];
      fileInput.value = "";
      renderFiles();
      hideBar();
      reportEl.innerHTML = "";
      setStatus("Awaiting file upload.", "");
    }

    function renderReport(data) {
      reportEl.innerHTML = "";
      if (!data || !Array.isArray(data.results)) { setStatus("Unexpected API response.", "bad"); return; }
      var accepted = 0, rows = 0, dupes = 0, phi = 0;
      data.results.forEach(function (item) {
        var ok = item.status === "accepted";
        if (ok) accepted += 1;
        var card = document.createElement("div");
        card.className = "hci-rpt";
        var headHTML =
          '<div class="hci-rpt__head"><span>' + (item.filename || "Unknown") + '</span><span>' +
          (item.file_type ? '<span class="hci-badge hci-badge--info">' + item.file_type + '</span> ' : '') +
          '<span class="hci-badge ' + (ok ? "hci-badge--ok" : "hci-badge--bad") + '">' + (item.status || "error").toUpperCase() + '</span></span></div>';
        var detailHTML = '<div class="hci-rpt__details">';
        if (item.validation) {
          detailHTML += '<div class="hci-rpt__detail"><span>Rows in file</span><strong>' + (item.validation.rows_processed || 0) + '</strong></div>';
          detailHTML += '<div class="hci-rpt__detail"><span>Validation</span><strong>' + item.validation.validation_status + '</strong></div>';
          if (item.validation.phi_columns_removed && item.validation.phi_columns_removed.length) {
            phi += item.validation.phi_columns_removed.length;
            detailHTML += '<div class="hci-rpt__detail"><span>PHI Stripped</span><strong>' + item.validation.phi_columns_removed.join(", ") + '</strong></div>';
          }
        }
        if (ok && item.processing) {
          rows  += Number(item.processing.rows_out) || 0;
          dupes += Number(item.processing.duplicates_removed) || 0;
          detailHTML += '<div class="hci-rpt__detail"><span>Rows ingested</span><strong>' + (item.processing.rows_out || 0) + '</strong></div>';
          detailHTML += '<div class="hci-rpt__detail"><span>Duplicates removed</span><strong>' + (item.processing.duplicates_removed || 0) + '</strong></div>';
        }
        if (item.storage) {
          detailHTML += '<div class="hci-rpt__detail"><span>Master total</span><strong>' + (item.storage.records_after || "—") + '</strong></div>';
        }
        detailHTML += '</div>';
        var errHTML = "";
        if (item.validation) {
          var issues = [];
          if (item.validation.missing_columns && item.validation.missing_columns.length)
            issues.push("Missing: " + item.validation.missing_columns.join(", "));
          if (item.validation.invalid_fields && item.validation.invalid_fields.length)
            issues.push("Invalid: " + item.validation.invalid_fields.join(", "));
          if (issues.length) errHTML = '<div class="hci-rpt__errors">' + issues.join("<br>") + '</div>';
        }
        card.innerHTML = headHTML + detailHTML + errHTML;
        reportEl.appendChild(card);
      });
      totals.files += data.results.length; totals.rows += rows; totals.dupes += dupes; totals.phi += phi;
      sFiles.textContent = String(totals.files);
      sRows.textContent  = totals.rows.toLocaleString();
      sDupes.textContent = String(totals.dupes);
      sPhi.textContent   = String(totals.phi);
      if (accepted === data.results.length) setStatus("Batch accepted — " + rows.toLocaleString() + " rows ingested.", "ok");
      else if (accepted > 0) setStatus("Partial acceptance — review rejected files.", "warn");
      else setStatus("Batch rejected — see validation details.", "bad");
      stampTime();
    }

    // File selection: label for="hci-files" opens dialog natively (no JS .click needed).
    // Listener attached directly on the live fileInput element — init() only runs
    // once the element is confirmed to exist, so this is always a live reference.
    fileInput.addEventListener("change", function () {
      if (fileInput.files && fileInput.files.length) addFiles(fileInput.files);
    });

    // Drag-and-drop
    drop.addEventListener("dragenter", function (e) { e.preventDefault(); drop.classList.add("is-active"); });
    drop.addEventListener("dragover",  function (e) { e.preventDefault(); });
    drop.addEventListener("dragleave", function (e) {
      if (!e.relatedTarget || !drop.contains(e.relatedTarget)) drop.classList.remove("is-active");
    });
    drop.addEventListener("drop", function (e) {
      e.preventDefault();
      drop.classList.remove("is-active");
      if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
    });

    fileList.addEventListener("click", function (e) {
      var btn = e.target.closest(".hci-file__remove");
      if (!btn) return;
      files.splice(Number(btn.getAttribute("data-i")), 1);
      renderFiles();
      setStatus(files.length ? files.length + " file(s) staged." : "Awaiting file upload.", "");
    });

    clearBtn.addEventListener("click", clearAll);

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!files.length) { setStatus("Add at least one claims file.", "bad"); return; }
      if (!source.value) { setStatus("Select a TPA/PBM source.", "bad"); return; }
      if (!month.value)  { setStatus("Select a report month.", "bad"); return; }
      var payload = new FormData();
      files.forEach(function (f) { payload.append("files[]", f, f.name); });
      payload.append("tpa_source", source.value);
      payload.append("report_month", month.value);
      submitBtn.disabled = true;
      showBar(); setBar(12);
      setStatus("Uploading " + files.length + " file(s) to pipeline...", "");
      reportEl.innerHTML = "";
      fetch(API_URL, { method: "POST", body: payload })
        .then(function (res) {
          setBar(55);
          if (!res.ok) return res.text().then(function (b) { throw new Error("Server " + res.status + ": " + b.substring(0, 200)); });
          return res.json();
        })
        .then(function (data) {
          setBar(100);
          setTimeout(function () { hideBar(); renderReport(data); files = []; fileInput.value = ""; renderFiles(); }, 400);
        })
        .catch(function (err) {
          hideBar();
          var msg = err.message || "Unknown error";
          if (msg.indexOf("Failed to fetch") !== -1 || msg.indexOf("NetworkError") !== -1)
            msg = "Cannot reach the API server. Check your connection or try again.";
          setStatus("Upload failed — " + msg, "bad");
          stampTime(); submitBtn.disabled = false; updateSubmit();
        });
    });
  } // end init()

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

})();
