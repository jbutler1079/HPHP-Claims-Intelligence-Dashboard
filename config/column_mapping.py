"""
Column mapping configuration for normalizing TPA/PBM export column names
to the HPHP standard schema.
"""

COLUMN_MAPPING = {
    # Claim identifier
    "Claim Number": "claim_number",
    "Claim_ID": "claim_number",
    "ClaimID": "claim_number",
    "claim_id": "claim_number",
    "Claim ID": "claim_number",

    # Member identifier
    "Member ID": "member_id",
    "MemberID": "member_id",
    "Member_ID": "member_id",
    "Subscriber ID": "member_id",
    "SubscriberID": "member_id",

    # Service date
    "Date of Service": "service_date",
    "DOS": "service_date",
    "Service Date": "service_date",
    "ServiceDate": "service_date",
    "Date_of_Service": "service_date",

    # Paid date
    "Paid Date": "paid_date",
    "Date_Paid": "paid_date",
    "PaidDate": "paid_date",
    "Payment Date": "paid_date",

    # Financial fields
    "Charge": "billed_amount",
    "Billed": "billed_amount",
    "Billed Amount": "billed_amount",
    "Billed_Amount": "billed_amount",
    "Total Billed": "billed_amount",

    "Allowed": "allowed_amount",
    "Allowed Amount": "allowed_amount",
    "Allowed_Amount": "allowed_amount",
    "Eligible Amount": "allowed_amount",

    "Paid": "paid_amount",
    "Paid Amount": "paid_amount",
    "Paid_Amount": "paid_amount",
    "Plan Paid": "paid_amount",

    # Procedure / diagnosis
    "Procedure": "procedure_code",
    "CPT_Code": "procedure_code",
    "CPT Code": "procedure_code",
    "Procedure Code": "procedure_code",
    "Procedure_Code": "procedure_code",

    "Diagnosis": "diagnosis_code",
    "Dx_Code": "diagnosis_code",
    "Dx Code": "diagnosis_code",
    "ICD Code": "diagnosis_code",
    "Diagnosis Code": "diagnosis_code",
    "Diagnosis_Code": "diagnosis_code",

    # Place of service
    "Place of Service": "place_of_service",
    "POS": "place_of_service",
    "Place_of_Service": "place_of_service",

    # Employer / group
    "Employer": "employer_group",
    "Group_Name": "employer_group",
    "Group Name": "employer_group",
    "Employer Group": "employer_group",
    "Plan Sponsor": "employer_group",

    # Demographics
    "Age": "age",
    "Member Age": "age",
    "Gender": "gender",
    "Sex": "gender",
    "Member Gender": "gender",

    # Pharmacy-specific
    "Rx Number": "rx_number",
    "RxNumber": "rx_number",
    "Rx_Number": "rx_number",
    "Prescription Number": "rx_number",

    "Fill Date": "fill_date",
    "FillDate": "fill_date",
    "Date Filled": "fill_date",
    "Date_Filled": "fill_date",

    "NDC": "ndc",
    "Drug NDC": "ndc",
    "NDC Code": "ndc",

    "Drug Name": "drug_name",
    "DrugName": "drug_name",
    "Drug_Name": "drug_name",
    "Medication Name": "drug_name",

    "Days Supply": "days_supply",
    "DaysSupply": "days_supply",
    "Days_Supply": "days_supply",

    "Quantity": "quantity",
    "Qty": "quantity",
    "Quantity Dispensed": "quantity",

    "Ingredient Cost": "ingredient_cost",
    "Drug Cost": "ingredient_cost",
    "Ingredient_Cost": "ingredient_cost",

    "Plan Paid Amount": "plan_paid",
    "Plan_Paid": "plan_paid",

    "Member Paid": "member_paid",
    "Copay": "member_paid",
    "Member_Paid": "member_paid",
    "Member Copay": "member_paid",

    # Source / report fields
    "TPA Source": "tpa_source",
    "TPA": "tpa_source",
    "Source": "tpa_source",

    "Report Month": "report_month",
    "ReportMonth": "report_month",
    "Report_Month": "report_month",
}

# Fields that must be removed to satisfy PHI de-identification requirements
PHI_FIELDS = {
    "name",
    "address",
    "date_of_birth",
    "social_security_number",
    "phone_number",
    "email",
    # Common raw variants
    "Name",
    "Full Name",
    "FullName",
    "Address",
    "DOB",
    "Date of Birth",
    "DateOfBirth",
    "SSN",
    "Social Security Number",
    "Phone",
    "Phone Number",
    "PhoneNumber",
    "Email",
    "Email Address",
    "EmailAddress",
}

MEDICAL_INDICATORS = {"procedure_code", "diagnosis_code", "place_of_service"}

PHARMACY_INDICATORS = {"ndc", "drug_name", "days_supply", "quantity"}

REQUIRED_MEDICAL_COLUMNS = {
    "member_id",
    "service_date",
    "billed_amount",
    "paid_amount",
}

REQUIRED_PHARMACY_COLUMNS = {
    "member_id",
    "fill_date",
    "ndc",
    "plan_paid",
}
