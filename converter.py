import requests
import json
from datetime import date

# HAPI FHIR server URL
FHIR_BASE_URL = "http://localhost:8080/fhir"

def parse_834_file(filename):
    """Parse 834 file and extract key segments"""
    with open(filename, 'r') as f:
        content = f.read()
    
    # Remove line breaks and split by segment terminator
    content = content.replace('\n', '').replace('\r', '')
    segments = content.strip().split('~')
    
    # Extract key data
    data = {
        'nm1_il': None,
        'dmg': None,
        'ref_0f': None,
        'n3': None,
        'n4': None,
        'per': None,
        'hd_segments': [],
        'dtp_348': []
    }
    
    for segment in segments:
        if not segment:
            continue
            
        fields = segment.split('*')
        seg_id = fields[0]
        
        if seg_id == 'NM1' and len(fields) > 3 and fields[1] == 'IL':
            data['nm1_il'] = fields
        elif seg_id == 'DMG':
            data['dmg'] = fields
        elif seg_id == 'REF' and len(fields) > 1 and fields[1] == '0F':
            data['ref_0f'] = fields[2] if len(fields) > 2 else None
        elif seg_id == 'N3':
            data['n3'] = fields
        elif seg_id == 'N4':
            data['n4'] = fields
        elif seg_id == 'PER':
            data['per'] = fields
        elif seg_id == 'HD':
            data['hd_segments'].append(fields)
        elif seg_id == 'DTP' and len(fields) > 1 and fields[1] == '348':
            data['dtp_348'].append(fields[3] if len(fields) > 3 else None)
    
    return data

def find_existing_patient(ssn):
    """Search for existing Patient by SSN to avoid duplicates"""
    if not ssn:
        return None
    
    try:
        # Search for Patient with matching SSN identifier
        search_url = f"{FHIR_BASE_URL}/Patient?identifier=http://hl7.org/fhir/sid/us-ssn|{ssn}"
        response = requests.get(search_url)
        
        if response.status_code == 200:
            bundle = response.json()
            if bundle.get('total', 0) > 0:
                # Found existing patient
                patient_id = bundle['entry'][0]['resource']['id']
                print(f"ℹ️  Found existing Patient/{patient_id} with SSN {ssn}")
                return patient_id
    except Exception as e:
        print(f"⚠️  Error searching for existing patient: {e}")
    
    return None

def create_patient(data):
    """Create FHIR Patient resource from 834 data with edge case handling"""
    
    # EDGE CASE: Missing NM1 segment
    if not data['nm1_il']:
        print("❌ CRITICAL: NM1*IL segment missing - cannot create Patient")
        return None
    
    nm1 = data['nm1_il']
    
    # EDGE CASE: Missing name fields
    family_name = nm1[3] if len(nm1) > 3 and nm1[3] else "UNKNOWN"
    given_name = nm1[4] if len(nm1) > 4 and nm1[4] else "UNKNOWN"
    
    if family_name == "UNKNOWN" or given_name == "UNKNOWN":
        print(f"⚠️  WARNING: Incomplete name data - Family: {family_name}, Given: {given_name}")
    
    ssn = nm1[9] if len(nm1) > 9 and nm1[9] else None
    
    # EDGE CASE: Check for duplicate by SSN
    if ssn:
        existing_patient_id = find_existing_patient(ssn)
        if existing_patient_id:
            print(f"✅ Using existing Patient/{existing_patient_id}")
            return existing_patient_id
    else:
        print("⚠️  WARNING: No SSN provided - cannot check for duplicates")
    
    # Extract demographics
    dmg = data['dmg']
    birth_date = None
    gender = "unknown"
    
    if dmg and len(dmg) > 2:
        birth_date_raw = dmg[2]
        # EDGE CASE: Validate DOB format
        if birth_date_raw and len(birth_date_raw) == 8:
            try:
                birth_date = f"{birth_date_raw[0:4]}-{birth_date_raw[4:6]}-{birth_date_raw[6:8]}"
                # Validate it's a real date
                year, month, day = int(birth_date_raw[0:4]), int(birth_date_raw[4:6]), int(birth_date_raw[6:8])
                date(year, month, day)  # This will raise ValueError if invalid
            except ValueError:
                print(f"⚠️  WARNING: Invalid DOB format: {birth_date_raw} - setting to None")
                birth_date = None
        else:
            print(f"⚠️  WARNING: DOB not in expected format (YYYYMMDD): {birth_date_raw}")
    else:
        print("⚠️  WARNING: DMG segment missing - no birth date or gender")
    
    if dmg and len(dmg) > 3:
        gender_code = dmg[3]
        gender = "male" if gender_code == "M" else "female" if gender_code == "F" else "unknown"
    
    # Build Patient resource
    patient = {
        "resourceType": "Patient",
        "identifier": [],
        "name": [{
            "use": "official",
            "family": family_name,
            "given": [given_name]
        }],
        "gender": gender
    }
    
    if birth_date:
        patient["birthDate"] = birth_date
    
    # Add identifiers with edge case handling
    if ssn:
        patient["identifier"].append({
            "system": "http://hl7.org/fhir/sid/us-ssn",
            "value": ssn
        })
    
    # EDGE CASE: Missing subscriber ID
    if data['ref_0f']:
        patient["identifier"].append({
            "system": "http://acme-health-plan.com/member-id",
            "value": data['ref_0f']
        })
    else:
        print("⚠️  WARNING: REF*0F subscriber ID missing - Patient will have SSN only")
    
    # EDGE CASE: Check if we have at least ONE identifier
    if len(patient["identifier"]) == 0:
        print("❌ CRITICAL: No identifiers (SSN or Member ID) - cannot create Patient")
        return None
    
    # Add address (optional)
    if data['n3'] and data['n4']:
        n3 = data['n3']
        n4 = data['n4']
        patient["address"] = [{
            "use": "home",
            "line": [n3[1]] if len(n3) > 1 else [],
            "city": n4[1] if len(n4) > 1 else None,
            "state": n4[2] if len(n4) > 2 else None,
            "postalCode": n4[3] if len(n4) > 3 else None
        }]
        if len(n3) > 2:
            patient["address"][0]["line"].append(n3[2])
    
    # Add telecom (optional)
    if data['per'] and len(data['per']) > 4:
        patient["telecom"] = [{
            "system": "phone",
            "value": data['per'][4],
            "use": "mobile"
        }]
    
    # POST to HAPI FHIR
    try:
        response = requests.post(f"{FHIR_BASE_URL}/Patient", json=patient)
        
        if response.status_code in [200, 201]:
            patient_resource = response.json()
            patient_id = patient_resource['id']
            print(f"✅ Created Patient/{patient_id} - {given_name} {family_name}")
            return patient_id
        else:
            print(f"❌ Failed to create Patient: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error creating Patient: {e}")
        return None

def create_coverage(patient_id, hd_segment, effective_date, end_date=None):
    """Create FHIR Coverage resource with edge case handling"""
    
    # Extract coverage type
    coverage_code = hd_segment[3] if len(hd_segment) > 3 and hd_segment[3] else "HLT"
    coverage_name = hd_segment[4] if len(hd_segment) > 4 and hd_segment[4] else "Health Coverage"
    
    # Map codes
    coverage_type_map = {
        "HLT": "HIP",
        "DEN": "DENTPRG",
        "VIS": "VISPOL"
    }
    
    fhir_type = coverage_type_map.get(coverage_code, "HIP")
    
    # EDGE CASE: Missing effective date - use today
    if not effective_date:
        effective_date = date.today().strftime("%Y%m%d")
        print(f"⚠️  WARNING: No effective date (DTP*348) - using today: {effective_date}")
    
    # Format dates
    if effective_date and len(effective_date) == 8:
        effective_date = f"{effective_date[0:4]}-{effective_date[4:6]}-{effective_date[6:8]}"
    
    # Build Coverage
    coverage = {
        "resourceType": "Coverage",
        "status": "active",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": fhir_type,
                "display": coverage_name
            }]
        },
        "subscriber": {
            "reference": f"Patient/{patient_id}"
        },
        "beneficiary": {
            "reference": f"Patient/{patient_id}"
        },
        "period": {
            "start": effective_date
        }
    }
    
    if end_date and len(end_date) == 8:
        coverage["period"]["end"] = f"{end_date[0:4]}-{end_date[4:6]}-{end_date[6:8]}"
    
    # POST to HAPI FHIR
    try:
        response = requests.post(f"{FHIR_BASE_URL}/Coverage", json=coverage)
        
        if response.status_code in [200, 201]:
            coverage_resource = response.json()
            coverage_id = coverage_resource['id']
            print(f"✅ Created Coverage/{coverage_id} - {coverage_name} ({coverage_code})")
            return coverage_id
        else:
            print(f"❌ Failed to create Coverage: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error creating Coverage: {e}")
        return None

def main():
    print("🚀 Starting 834 to FHIR Conversion (with Edge Case Handling)...")
    print()
    
    # Parse 834 file
    print("📄 Parsing 834 file...")
    data = parse_834_file('sample_834.txt')
    print(f"   Found {len(data['hd_segments'])} coverage plan(s)")
    print()
    
    # Create Patient
    print("👤 Creating Patient resource...")
    patient_id = create_patient(data)
    
    if not patient_id:
        print("❌ Conversion failed - could not create Patient")
        return
    
    print()
    
    # Create Coverage resources
    print("🏥 Creating Coverage resource(s)...")
    for i, hd_segment in enumerate(data['hd_segments']):
        effective_date = data['dtp_348'][i] if i < len(data['dtp_348']) else None
        create_coverage(patient_id, hd_segment, effective_date, "20251231")
    
    print()
    print("✅ Conversion complete!")
    print(f"   Patient ID: {patient_id}")
    print(f"   Coverages created: {len(data['hd_segments'])}")
    print()
    print(f"🔍 View in browser: http://localhost:8080/fhir/Patient/{patient_id}")

if __name__ == "__main__":
    main()