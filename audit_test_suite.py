import re
import json
import urllib.parse
from app import app, appointments, blood_inventory, ambulances, prescriptions, HTML_TEMPLATE, DB_PATH

def run_system_audit():
    app.testing = True
    client = app.test_client()
    audit_results = {
        "perspective_1_patient": {},
        "perspective_2_reception": {},
        "perspective_3_doctor": {},
        "perspective_4_ambulance": {},
        "dom_id_audit": {},
        "api_integrity": {},
        "errors": []
    }

    print("=" * 60)
    print("STARTING RESQLIFE FULL-SYSTEM COMPREHENSIVE AUDIT")
    print("=" * 60)

    # Clean up prior test runs from SQLite so tests are idempotent
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        try:
            conn.execute("DELETE FROM appointments WHERE patient = 'Audit Patient Test'")
            conn.execute("DELETE FROM prescriptions WHERE patient_name = 'Audit Patient Test'")
            conn.execute("DELETE FROM users WHERE email = 'audit.dr@med.org'")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
    except Exception:
        pass

    # ---------------------------------------------------------
    # 0. DOM & STATIC TEMPLATE INTEGRITY AUDIT
    # ---------------------------------------------------------
    print("\n[PHASE 0] Auditing DOM Element IDs & JavaScript Handlers...")
    # Find all document.getElementById('XYZ') in template
    js_ids = set(re.findall(r"document\.getElementById\(['\"]([a-zA-Z0-9_\-]+)['\"]\)", HTML_TEMPLATE))
    # Find all id="XYZ" in HTML
    html_ids = set(re.findall(r'id=["\']([a-zA-Z0-9_\-]+)["\']', HTML_TEMPLATE))

    # Note: Some IDs are generated dynamically in loops (e.g., status-badge-${apt.id}, rx-vault-card-${rx.id}, etc.)
    missing_static_ids = []
    dynamic_prefixes = ('status-badge-', 'patient-token-card-', 'doc-apt-', 'reception-row-', 'blood-row-', 'rx-vault-card-', 'rx-img-')
    for jid in js_ids:
        if not jid.startswith(dynamic_prefixes) and jid not in html_ids:
            missing_static_ids.append(jid)

    audit_results["dom_id_audit"]["total_js_ids_checked"] = len(js_ids)
    audit_results["dom_id_audit"]["total_html_ids_found"] = len(html_ids)
    audit_results["dom_id_audit"]["missing_ids"] = missing_static_ids

    if missing_static_ids:
        print(f"⚠️ Warning: Found missing DOM IDs referenced in JS: {missing_static_ids}")
    else:
        print(f"✅ DOM Integrity: All {len(js_ids)} JavaScript element selectors match existing HTML IDs!")

    # ---------------------------------------------------------
    # 1. PERSPECTIVE 1: PATIENT / PUBLIC VIEW
    # ---------------------------------------------------------
    print("\n[PHASE 1] Auditing Perspective 1: Patient / Public View...")
    
    # 1.1 Index View
    res = client.get('/')
    assert res.status_code == 200
    assert b"ResQLife" in res.data
    audit_results["perspective_1_patient"]["index_page_status"] = "PASSED (200 OK)"

    # 1.2 Appointment Booking Flow & Incremental Token
    init_total_apts = len(appointments)
    book_payload = {
        "patient": "Audit Patient Test",
        "phone": "+91 99999 11111",
        "slot": "04:00 PM",
        "doctor_category": "Cardiology Specialist"
    }
    res_book = client.post('/api/appointments/book', json=book_payload)
    assert res_book.status_code == 200
    data_book = res_book.get_json()
    assert data_book["success"] is True
    assert data_book["appointment"]["patient"] == "Audit Patient Test"
    assigned_token = data_book["appointment"]["token_no"]
    assert assigned_token.startswith("A-")
    audit_results["perspective_1_patient"]["booking_and_token_generation"] = f"PASSED (Assigned Token: {assigned_token})"

    # 1.3 Validation on Missing Fields for Booking
    res_invalid_book = client.post('/api/appointments/book', json={"patient": ""})
    assert res_invalid_book.status_code == 400
    audit_results["perspective_1_patient"]["booking_validation"] = "PASSED (Rejected empty fields with 400)"

    # 1.4 Emergency SOS Dispatch Trigger & Google Maps URL
    sos_payload = {
        "patient_name": "Emergency Trauma Subject",
        "phone": "+91 98888 22222",
        "pickup_location": "Brigade Gateway, Malleshwaram, Bengaluru",
        "severity_level": "Level 1"
    }
    res_sos = client.post('/api/ambulance/request', json=sos_payload)
    assert res_sos.status_code == 200
    data_sos = res_sos.get_json()
    assert data_sos["success"] is True
    amb = data_sos["ambulance"]
    assert amb["status"] == "Dispatched"
    em = amb["emergency"]
    assert em["severity_level"] == "Level 1"
    assert em["tag_color"] == "red"
    assert "https://www.google.com/maps/search/?api=1&query=" in em["maps_url"]
    assert "Brigade+Gateway" in em["maps_url"]
    audit_results["perspective_1_patient"]["emergency_sos_dispatch"] = f"PASSED (Assigned {amb['vehicle_no']}, Maps URL generated)"

    # 1.5 Blood Inventory Group Filtering
    res_b_all = client.get('/api/blood/filter?group=All')
    assert res_b_all.status_code == 200
    assert len(res_b_all.get_json()["inventory"]) == len(blood_inventory)

    res_b_oneg = client.get('/api/blood/filter?group=O-')
    assert res_b_oneg.status_code == 200
    b_oneg_data = res_b_oneg.get_json()["inventory"]
    assert all(item["group"] == "O-" for item in b_oneg_data)
    audit_results["perspective_1_patient"]["blood_matrix_filtering"] = f"PASSED (O- group returned {len(b_oneg_data)} matching center(s))"

    # 1.6 Medicine Reminder List & "Mark as Taken"
    res_rx = client.get('/api/prescriptions')
    assert res_rx.status_code == 200
    rx_list = res_rx.get_json()
    target_rx = rx_list[0]
    initial_taken_state = target_rx.get("is_taken", False)
    
    res_tog = client.post('/api/prescriptions/toggle-taken', json={"id": target_rx["id"]})
    assert res_tog.status_code == 200
    new_taken_state = res_tog.get_json()["prescription"]["is_taken"]
    assert new_taken_state != initial_taken_state
    audit_results["perspective_1_patient"]["medicine_reminder_adherence"] = f"PASSED (Toggled Rx #{target_rx['id']} to is_taken={new_taken_state})"

    # ---------------------------------------------------------
    # 2. PERSPECTIVE 2: CLINIC RECEPTION DESK
    # ---------------------------------------------------------
    print("\n[PHASE 2] Auditing Perspective 2: Clinic Reception Desk...")
    
    # 2.1 Appointments Queue Table Data
    res_apts = client.get('/api/appointments')
    assert res_apts.status_code == 200
    all_apts = res_apts.get_json()
    assert len(all_apts) >= 4
    audit_results["perspective_2_reception"]["queue_table_feed"] = f"PASSED ({len(all_apts)} active records)"

    # 2.2 Status Cycle Transitions: Waiting -> In-Clinic -> Completed
    test_apt = next((a for a in appointments if a["patient"] == "Audit Patient Test"), appointments[-1])
    assert test_apt["status"] == "Waiting"

    # Transition 1: Waiting -> In-Clinic
    res_cyc1 = client.post('/api/appointments/update-status', json={"id": test_apt["id"]})
    assert res_cyc1.status_code == 200
    assert res_cyc1.get_json()["appointment"]["status"] == "In-Clinic"

    # Transition 2: In-Clinic -> Completed
    res_cyc2 = client.post('/api/appointments/update-status', json={"id": test_apt["id"]})
    assert res_cyc2.status_code == 200
    assert res_cyc2.get_json()["appointment"]["status"] == "Completed"

    # 2.3 Queue Counter Accuracy
    stats = res_cyc2.get_json()["stats"]
    assert stats["total"] == len(appointments)
    assert stats["completed"] == sum(1 for a in appointments if a["status"] == "Completed")
    assert stats["waiting"] == sum(1 for a in appointments if a["status"] == "Waiting")
    assert stats["in_clinic"] == sum(1 for a in appointments if a["status"] == "In-Clinic")
    audit_results["perspective_2_reception"]["status_cycle_and_counter_accuracy"] = "PASSED (Waiting -> In-Clinic -> Completed & stats verified)"

    # ---------------------------------------------------------
    # 3. PERSPECTIVE 3: DOCTOR PORTAL
    # ---------------------------------------------------------
    print("\n[PHASE 3] Auditing Perspective 3: Doctor Consultation Portal...")
    
    # 3.1 Patient Queue Availability for Consultation
    assigned_for_doc = [a for a in appointments if a["status"] in ["In-Clinic", "Waiting"]]
    assert len(assigned_for_doc) > 0
    audit_results["perspective_3_doctor"]["assigned_patient_filter"] = f"PASSED ({len(assigned_for_doc)} patients queued for consult)"

    # 3.2 Doctor Adding Prescription & Synchronizing to Patient Locker
    rx_payload = {
        "patient_name": "Audit Patient Test",
        "doctor_name": "Dr. Ananya Roy, MD",
        "medicine_name": "Telmisartan 40mg + Chlorthalidone",
        "dosage_time": "Morning - After Food (1-0-0)",
        "instructions": "Monitor blood pressure daily at 9:00 AM."
    }
    res_add_rx = client.post('/api/prescriptions/add', json=rx_payload)
    assert res_add_rx.status_code == 200
    data_add_rx = res_add_rx.get_json()
    assert data_add_rx["success"] is True
    created_rx = data_add_rx["prescription"]
    assert created_rx["medicine_name"] == "Telmisartan 40mg + Chlorthalidone"
    assert created_rx["timing_slot"] == "Upcoming: 08:30 AM Dose"
    assert created_rx["is_taken"] is False

    # Verify presence in GET /api/prescriptions
    res_verify_rx = client.get('/api/prescriptions')
    assert any(r["medicine_name"] == "Telmisartan 40mg + Chlorthalidone" for r in res_verify_rx.get_json())
    audit_results["perspective_3_doctor"]["prescription_creation_and_sync"] = "PASSED (Rx issued and verified in patient locker)"

    # ---------------------------------------------------------
    # 4. PERSPECTIVE 4: AMBULANCE DRIVER CONSOLE
    # ---------------------------------------------------------
    print("\n[PHASE 4] Auditing Perspective 4: Ambulance Driver Console...")
    
    # 4.1 Receiving Live SOS Dispatch Payload
    res_amb_fleet = client.get('/api/ambulances')
    assert res_amb_fleet.status_code == 200
    active_dispatched = [a for a in res_amb_fleet.get_json() if a.get("emergency") is not None and a["status"] != "Available"]
    assert len(active_dispatched) > 0
    test_amb = active_dispatched[0]
    audit_results["perspective_4_ambulance"]["radar_payload_detection"] = f"PASSED (Unit {test_amb['vehicle_no']} has active emergency mission)"

    # 4.2 Status Progression: En-Route -> Arrived at Scene -> Complete Trip (Available)
    target_vno = test_amb["vehicle_no"]
    
    # Step 1: En-Route
    res_s1 = client.post('/api/ambulance/update-status', json={"vehicle_no": target_vno, "status": "En-Route"})
    assert res_s1.status_code == 200
    assert res_s1.get_json()["ambulance"]["status"] == "En-Route"

    # Step 2: Arrived at Scene
    res_s2 = client.post('/api/ambulance/update-status', json={"vehicle_no": target_vno, "status": "Arrived at Scene"})
    assert res_s2.status_code == 200
    assert res_s2.get_json()["ambulance"]["status"] == "Arrived at Scene"
    assert res_s2.get_json()["ambulance"]["eta_mins"] == 0

    # Step 3: Complete Trip -> Sets vehicle back to Available
    res_s3 = client.post('/api/ambulance/update-status', json={"vehicle_no": target_vno, "status": "Complete Trip"})
    assert res_s3.status_code == 200
    completed_amb = res_s3.get_json()["ambulance"]
    assert completed_amb["status"] == "Available"
    assert completed_amb["emergency"] is None
    audit_results["perspective_4_ambulance"]["trip_status_progression"] = "PASSED (En-Route -> Arrived at Scene -> Complete Trip -> Available)"

    # ---------------------------------------------------------
    # 5. BLOOD BANK COORDINATOR UPDATE MODAL AUDIT
    # ---------------------------------------------------------
    print("\n[PHASE 5] Auditing Blood Bank Stock Coordinate / Need Reporting...")
    res_b_up = client.post('/api/blood/update', json={
        "hospital": "City Care Trauma Center",
        "group": "O-",
        "units": 5
    })
    assert res_b_up.status_code == 200
    assert res_b_up.get_json()["item"]["units"] == 5
    audit_results["api_integrity"]["blood_stock_update"] = "PASSED (City Care O- updated to 5 units)"

    # Error handling for invalid blood update
    res_b_err = client.post('/api/blood/update', json={"hospital": "", "group": ""})
    assert res_b_err.status_code == 400
    audit_results["api_integrity"]["blood_update_error_handling"] = "PASSED (400 on empty fields)"

    # ---------------------------------------------------------
    # 6. AUTHENTICATION & RBAC AUDIT
    # ---------------------------------------------------------
    print("\n[PHASE 6] Auditing Authentication & Role-Based Access Control...")
    for role_key in ["patient", "reception", "doctor", "ambulance"]:
        res_auth = client.post('/api/auth/login', json={"demo_role": role_key})
        assert res_auth.status_code == 200
        u_data = res_auth.get_json()
        assert u_data["success"] is True
        assert u_data["user"]["role"] == role_key
    
    # Register test (Hospital Authorization Passkey required for clinical roles)
    res_reg_fail = client.post('/api/auth/register', json={"name": "Audit Dr", "email": "audit.dr@med.org", "role": "doctor", "password": "password123"})
    assert res_reg_fail.status_code == 403
    
    res_reg = client.post('/api/auth/register', json={"name": "Audit Dr", "email": "audit.dr@med.org", "role": "doctor", "passkey": "HOSP2026", "password": "password123"})
    assert res_reg.status_code == 200
    assert res_reg.get_json()["user"]["role"] == "doctor"

    audit_results["api_integrity"]["rbac_authentication"] = "PASSED (RBAC Passkey enforcement + 1-Click demo logins for all 4 roles + registration verified)"

    print("\n" + "=" * 60)
    print("ALL TEST PHASES COMPLETED!")
    print("=" * 60)
    return audit_results

if __name__ == "__main__":
    results = run_system_audit()
    print("\nAUDIT SUMMARY DUMP:")
    print(json.dumps(results, indent=2))

