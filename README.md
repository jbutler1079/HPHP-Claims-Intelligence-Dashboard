# HPHP Claims Intelligence Platform

> Production-ready healthcare claims analytics platform for **High Plains Health Plan (HPHP)**.

---

## Overview

The HPHP Claims Intelligence Platform ingests medical and pharmacy claims data from multiple
Third-Party Administrators (TPAs) and Pharmacy Benefit Managers (PBMs), validates and normalizes
the data, maintains a growing historical claims dataset, and powers executive dashboards used for
consulting, employer reporting, and financial oversight.

---

## Architecture

```
WordPress Upload Portal
        ↓
Render-Hosted Python API  (webapp/api.py)
        ↓
Claims Validation Layer   (scripts/validate_claim_file.py)
        ↓
Claims Processing Pipeline
   ├── scripts/normalize_columns.py
   ├── scripts/process_medical_claims.py
   ├── scripts/process_pharmacy_claims.py
   ├── scripts/calculate_metrics.py
   └── scripts/deduplicate_claims.py
        ↓
Historical Claims Data Warehouse  (data/processed/)
        ↓
Power BI Analytics Dashboard      (dashboards/)
        ↓
Dashboard Embedded Into WordPress
```

---

## Repository Structure

```
hphp-claims-intelligence/
├── data/
│   ├── raw/                        # Timestamped raw file archives
│   └── processed/
│       ├── medical_claims_master.csv
│       ├── pharmacy_claims_master.csv
│       └── members_master.csv
├── scripts/
│   ├── validate_claim_file.py
│   ├── normalize_columns.py
│   ├── process_medical_claims.py
│   ├── process_pharmacy_claims.py
│   ├── calculate_metrics.py
│   ├── deduplicate_claims.py
│   └── append_to_master_dataset.py
├── config/
│   └── column_mapping.py
├── webapp/
│   ├── api.py
│   └── upload_handler.py
├── frontend/
│   ├── upload_portal.html
│   ├── upload.js
│   └── styles/
│       ├── base.css
│       ├── layout.css
│       ├── components.css
│       ├── dashboard.css
│       └── theme.css
├── dashboards/
│   ├── powerbi_schema.md
│   └── powerbi_theme.json
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
pip install -r requirements.txt
```

### Running the API Locally

```bash
python webapp/api.py
```

The API starts on `http://localhost:5000`.

### Uploading Claims

```bash
curl -X POST http://localhost:5000/upload \
  -F "files[]=@TPA_A_MEDICAL_CLAIMS.csv" \
  -F "tpa_source=TPA_A" \
  -F "report_month=2024-01"
```

### WordPress Drop-In Upload Block

Use `frontend/wordpress_upload_embed.html` when you need a single HTML/CSS block that can be pasted into a WordPress `Custom HTML` block.

1. Copy the full contents of `frontend/wordpress_upload_embed.html`.
2. Paste into a WordPress page using a `Custom HTML` block.
3. Update the form `action` URL to your deployed API endpoint, for example:

```html
https://your-render-service.onrender.com/upload
```

The block submits multipart form data using the same field names expected by the API:
`files[]`, `tpa_source`, and `report_month`.

---

## Upload Workflow

Each ingestion cycle accepts up to four files:

| File | Type |
|------|------|
| `TPA_A_MEDICAL_CLAIMS` | Medical |
| `TPA_A_PHARMACY_CLAIMS` | Pharmacy |
| `TPA_B_MEDICAL_CLAIMS` | Medical |
| `TPA_B_PHARMACY_CLAIMS` | Pharmacy |

Files are uploaded via `POST /upload` and processed independently.

---

## Data Privacy

All uploaded datasets are automatically de-identified. The following PHI fields are
**removed on ingestion** if detected:

`name` · `address` · `date_of_birth` · `social_security_number` · `phone_number` · `email`

---

## Validation

Every file passes a validation layer that checks:

- File type (`.csv` or `.xlsx` only)
- Required column presence
- Column mapping compatibility
- Date field parseability
- Numeric value validity
- Duplicate file detection (SHA-256 hash)

---

## Calculated Metrics

| Metric | Formula |
|--------|---------|
| `service_to_paid_lag` | `paid_date − service_date` (days) |
| `discount_percent` | `(billed − allowed) / billed` |
| `plan_paid_ratio` | `paid / allowed` |
| `high_cost_flag` | `paid_amount > $10,000` |
| `very_high_cost_flag` | `paid_amount > $50,000` |

---

## Power BI Integration

See [`dashboards/powerbi_schema.md`](dashboards/powerbi_schema.md) for the full data model,
DAX measures, and dashboard page specifications.

Apply the HPHP brand theme using [`dashboards/powerbi_theme.json`](dashboards/powerbi_theme.json).

---

## Deployment (Render)

| Setting | Value |
|---------|-------|
| Environment | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python webapp/api.py` |

---

## Brand Colors

| Token | Hex |
|-------|-----|
| Primary Teal | `#1BACB2` |
| Accent Blue | `#5B7BFF` |
| Accent Orange | `#FD6D06` |
| Accent Magenta | `#CF18AA` |
| Alert Red | `#FF0000` |

---

## License

Proprietary – High Plains Health Plan. All rights reserved.
