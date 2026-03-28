# X12 834 to FHIR R4 Enrollment Transformer

A Python-based converter that transforms X12 834 enrollment transactions into FHIR R4 Patient and Coverage resources, designed for healthcare payers implementing CMS Patient Access APIs.

## Business Problem

Healthcare payers have 18+ years of member enrollment data in X12 834 EDI format. The CMS Interoperability Final Rule (CMS-0057-F) requires payers to expose this data via FHIR-based Patient Access APIs by January 2027. This converter automates the transformation from legacy EDI to modern FHIR R4 resources.

## Features

- **834 Parser**: Extracts NM1, DMG, REF, HD, DTP segments from X12 enrollment files
- **Patient Mapping**: Maps subscriber demographics to FHIR Patient resources
- **Coverage Mapping**: Creates FHIR Coverage resources from HD segments
- **Multi-Plan Support**: Handles Medical + Dental + Vision in single transaction
- **Duplicate Detection**: Searches FHIR by SSN to prevent duplicate Patient records
- **Edge Case Handling**: Gracefully handles missing data, invalid formats, API errors

## Architecture
```
X12 834 File
    ↓
parse_834_file() → Extract segments
    ↓
find_existing_patient() → Check for duplicates by SSN
    ↓
create_patient() → NM1/DMG/REF → FHIR Patient
    ↓
create_coverage() → HD/DTP → FHIR Coverage (loops for multi-plan)
    ↓
HAPI FHIR Server → Stores Patient + Coverage resources
```

## Mapping Logic

| X12 Segment | X12 Field | FHIR Resource | FHIR Field |
|-------------|-----------|---------------|------------|
| NM1*IL | NM103 (Family) | Patient | name.family |
| NM1*IL | NM104 (Given) | Patient | name.given |
| NM1*IL | NM109 (SSN) | Patient | identifier (SSN system) |
| DMG | DMG02 (DOB) | Patient | birthDate |
| DMG | DMG03 (Gender) | Patient | gender |
| REF*0F | REF02 (Member ID) | Patient | identifier (Member ID system) |
| HD | HD03 (Coverage code) | Coverage | type.coding.code |
| DTP*348 | DTP03 (Effective date) | Coverage | period.start |
| DTP*349 | DTP03 (End date) | Coverage | period.end |

## Edge Cases Handled

1. **Duplicate Members**: Searches FHIR by SSN before creating Patient, reuses existing if found
2. **Missing Subscriber ID (REF*0F)**: Logs warning, creates Patient with SSN-only identification
3. **Missing Effective Date (DTP*348)**: Defaults to today's date, logs warning for review
4. **Invalid DOB Format**: Validates YYYYMMDD format, rejects malformed dates
5. **Missing Name Fields**: Uses "UNKNOWN" placeholder, logs for manual correction
6. **API Errors**: Try/catch blocks with informative error messages

## Prerequisites

- Python 3.7+
- Docker (for HAPI FHIR server)
- HAPI FHIR server running on localhost:8080

## Installation
```bash
# Clone repository
git clone https://github.com/[YOUR_USERNAME]/fhir-834-converter.git
cd fhir-834-converter

# Install dependencies
pip3 install -r requirements.txt

# Start HAPI FHIR server (if not running)
docker run -d -p 8080:8080 --name hapi-fhir hapiproject/hapi:latest
```

## Usage
```bash
# Run converter with sample 834 file
python3 converter.py

# Expected output:
# 🚀 Starting 834 to FHIR Conversion...
# 📄 Parsing 834 file...
#    Found 2 coverage plan(s)
# 👤 Creating Patient resource...
# ✅ Created Patient/1002 - VENKATESH THOTA
# 🏥 Creating Coverage resource(s)...
# ✅ Created Coverage/1003 - MEDICAL PLAN (HLT)
# ✅ Created Coverage/1004 - DENTAL PLAN (DEN)
# ✅ Conversion complete!
```

## Sample 834 File Format

The converter expects 834 files with segments on a single line separated by `~`:
```
ISA*00*...*~GS*BE*...*~ST*834*...*~NM1*IL*1*THOTA*VENKATESH~DMG*D8*19800115*M~REF*0F*MBR-2024-001~HD*025**HLT*MEDICAL~DTP*348*D8*20250101~...
```


## Technologies

- Python 3
- FHIR R4
- HAPI FHIR
- X12 EDI 834
- REST APIs
- Docker

## Development Approach

This project was developed using modern AI-assisted development practices. AI tools were used for baseline code generation and documentation. All business logic, mapping rules, and edge case handling were designed and validated against the Da Vinci PDex Implementation Guide. This approach mirrors how senior engineers use GitHub Copilot in production environments.

## License

MIT License - Feel free to use this for learning or adapt for your own projects.

## Author
Built as part of FHIR integration learning for healthcare payer interoperability projects.
