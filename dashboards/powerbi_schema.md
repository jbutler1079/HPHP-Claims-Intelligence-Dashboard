# Power BI Data Schema – HPHP Claims Intelligence Platform

## Overview

The Power BI data model follows a **star schema** connecting three fact/dimension CSV files
that are continuously updated by the Python ingestion pipeline.

---

## Data Sources

| File | Description |
|------|-------------|
| `data/processed/medical_claims_master.csv` | Normalized medical claims with calculated metrics |
| `data/processed/pharmacy_claims_master.csv` | Normalized pharmacy claims with calculated metrics |
| `data/processed/members_master.csv` | Deduplicated member dimension table |

---

## Table Schemas

### medical_claims_master

| Column | Type | Description |
|--------|------|-------------|
| claim_number | Text | Unique claim identifier |
| member_id | Text | Member identifier (FK → members) |
| service_date | Date | Date of service |
| paid_date | Date | Date claim was paid |
| procedure_code | Text | CPT / procedure code |
| diagnosis_code | Text | ICD diagnosis code |
| place_of_service | Text | Place of service code |
| billed_amount | Decimal | Amount billed by provider |
| allowed_amount | Decimal | Contracted allowed amount |
| paid_amount | Decimal | Amount paid by plan |
| employer_group | Text | Plan sponsor / employer group name |
| age | Integer | Member age at service date |
| gender | Text | Member gender |
| tpa_source | Text | TPA data source label |
| report_month | Text | Reporting period (YYYY-MM) |
| service_to_paid_lag | Integer | Days between service and payment |
| discount_percent | Decimal | (Billed − Allowed) / Billed |
| plan_paid_ratio | Decimal | Paid / Allowed |
| high_cost_flag | Boolean | Paid amount > $10,000 |
| very_high_cost_flag | Boolean | Paid amount > $50,000 |

---

### pharmacy_claims_master

| Column | Type | Description |
|--------|------|-------------|
| rx_number | Text | Prescription number |
| member_id | Text | Member identifier (FK → members) |
| fill_date | Date | Date prescription was filled |
| ndc | Text | National Drug Code |
| drug_name | Text | Medication name |
| days_supply | Integer | Days supply dispensed |
| quantity | Decimal | Quantity dispensed |
| ingredient_cost | Decimal | Drug ingredient cost |
| plan_paid | Decimal | Amount paid by plan |
| member_paid | Decimal | Member cost share (copay/coinsurance) |
| employer_group | Text | Plan sponsor / employer group name |
| age | Integer | Member age |
| gender | Text | Member gender |
| tpa_source | Text | PBM / TPA source label |
| report_month | Text | Reporting period (YYYY-MM) |
| total_rx_cost | Decimal | ingredient_cost + member_paid |
| member_cost_share_ratio | Decimal | member_paid / total_rx_cost |
| high_cost_flag | Boolean | Plan paid > $10,000 |
| very_high_cost_flag | Boolean | Plan paid > $50,000 |

---

### members_master

| Column | Type | Description |
|--------|------|-------------|
| member_id | Text | Unique member identifier (PK) |
| age | Integer | Member age |
| gender | Text | Member gender |
| employer_group | Text | Associated employer group |
| first_seen_date | Date | First date member appeared in claims |
| last_seen_date | Date | Most recent date member appeared |

---

## Relationships (Star Schema)

```
members_master (member_id)
    ├──< medical_claims_master (member_id)
    └──< pharmacy_claims_master (member_id)

Date Table (Date)
    ├──< medical_claims_master (service_date)
    └──< pharmacy_claims_master (fill_date)

Employer Dimension (employer_group)
    ├──< medical_claims_master (employer_group)
    └──< pharmacy_claims_master (employer_group)
```

---

## Date Table (DAX)

```dax
Date Table =
ADDCOLUMNS(
    CALENDAR(DATE(2020,1,1), DATE(2030,12,31)),
    "Year",          YEAR([Date]),
    "Month Number",  MONTH([Date]),
    "Month Name",    FORMAT([Date], "MMMM"),
    "Quarter",       "Q" & QUARTER([Date]),
    "Year-Month",    FORMAT([Date], "YYYY-MM")
)
```

---

## Dashboard Pages

### 1. Executive Overview
- Total medical paid YTD
- Total pharmacy paid YTD
- Total members served
- PMPM (Per Member Per Month) cost
- Medical vs pharmacy cost split (donut)
- Monthly spend trend (line)

### 2. Financial Performance
- Billed vs Allowed vs Paid (waterfall)
- Average discount percent by employer group
- Plan paid ratio trend
- Top 10 employer groups by total cost

### 3. Clinical Risk Analysis
- Top diagnosis codes by frequency and cost
- High-cost claimant count
- Cost per episode by procedure code
- Service-to-paid lag distribution

### 4. Pharmacy Spend Insights
- Top 20 drugs by plan paid
- Generic vs brand fill rate
- Specialty drug spend (NDC-based flag)
- Days supply analysis

### 5. Cost Leakage Detection
- Claims where paid_amount > allowed_amount
- High discount variance by TPA
- Procedure code anomaly flags

### 6. Large Claim Volatility
- Very high cost claims (>$50K) over time
- Employer group volatility index
- Catastrophic claim trend

### 7. Operational Metrics
- Ingestion volume by TPA source
- Claims by report month
- Duplicate rejection rate
- Validation failure rate

---

## Key DAX Measures

```dax
Total Medical Paid = SUM(medical_claims_master[paid_amount])

Total Pharmacy Paid = SUM(pharmacy_claims_master[plan_paid])

Total Claims Cost = [Total Medical Paid] + [Total Pharmacy Paid]

Avg Discount % = AVERAGE(medical_claims_master[discount_percent])

PMPM = DIVIDE([Total Claims Cost], [Total Member Months])

High Cost Claimants =
CALCULATE(
    COUNTROWS(members_master),
    FILTER(
        medical_claims_master,
        medical_claims_master[very_high_cost_flag] = TRUE()
    )
)
```
