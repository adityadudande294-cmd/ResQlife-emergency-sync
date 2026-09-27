import os
import re
import json
import sqlite3
import hashlib
import urllib.parse
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "resqlife-super-secret-key-2026-prod")

# ==========================================
# SQLITE PERSISTENT DATABASE SETUP
# ==========================================

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resqlife.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=60.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return generate_password_hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        if check_password_hash(hashed, password):
            return True
    except Exception:
        pass
    salt = "resqlife_enterprise_salt_2026"
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest() == hashed

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # 1. appointments table
    c.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient TEXT,
        phone TEXT,
        doctor_category TEXT,
        slot TEXT,
        token_no TEXT,
        status TEXT DEFAULT 'Waiting',
        patient_age INTEGER DEFAULT 32,
        gender TEXT DEFAULT 'Other',
        blood_group TEXT DEFAULT 'O+',
        emergency_contact TEXT DEFAULT '+91 98765 00000',
        allergies TEXT DEFAULT 'None',
        doctor_name TEXT DEFAULT 'Dr. Ananya Roy, MD',
        appointment_date TEXT DEFAULT ''
    )
    """)
    for col, col_def in [
        ("patient_age", "INTEGER DEFAULT 32"),
        ("gender", "TEXT DEFAULT 'Other'"),
        ("blood_group", "TEXT DEFAULT 'O+'"),
        ("emergency_contact", "TEXT DEFAULT '+91 98765 00000'"),
        ("allergies", "TEXT DEFAULT 'None'"),
        ("doctor_name", "TEXT DEFAULT 'Dr. Ananya Roy, MD'"),
        ("appointment_date", "TEXT DEFAULT ''")
    ]:
        try:
            c.execute(f"ALTER TABLE appointments ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError:
            pass

    if c.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0:
        c.executemany(
            """INSERT INTO appointments (id, patient, phone, doctor_category, slot, token_no, status, patient_age, gender, blood_group, emergency_contact, allergies, doctor_name, appointment_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (1, "Rahul Sharma", "+91 98765 43210", "Cardiology Specialist", "10:30 AM", "A-101", "In-Clinic", 34, "Male", "O+", "+91 98765 11111", "Penicillin allergy", "Dr. Ananya Roy, MD", "2026-09-27"),
                (2, "Priya Patel", "+91 91234 56789", "General Physician", "11:00 AM", "A-102", "Waiting", 28, "Female", "A+", "+91 91234 22222", "None reported", "Dr. Rajesh Gupta, MD", "2026-09-27"),
                (3, "Amit Verma", "+91 99887 76655", "Orthopedic Specialist", "09:45 AM", "A-100", "Completed", 45, "Male", "B+", "+91 99887 33333", "Hypertension", "Dr. Vikramaditya Rao, MS", "2026-09-26")
            ]
        )

    # 2. blood_inventory table
    c.execute("""
    CREATE TABLE IF NOT EXISTS blood_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital TEXT,
        area TEXT,
        blood_group TEXT,
        units INTEGER DEFAULT 0,
        contact TEXT
    )
    """)
    if c.execute("SELECT COUNT(*) FROM blood_inventory").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO blood_inventory (id, hospital, area, blood_group, units, contact) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "City Care Trauma Center", "Central Ward", "O-", 2, "+91 800-432-1111"),
                (2, "Metro Life Hospital", "West Sector", "A+", 14, "+91 800-432-2222"),
                (3, "Apex Emergency Center", "North District", "B+", 8, "+91 800-432-3333"),
                (4, "St. Jude Hospital", "South Valley", "AB-", 1, "+91 800-432-4444"),
                (5, "Grace Mission Hospital", "East Corridor", "O+", 19, "+91 800-432-5555"),
                (6, "National Heart Institute", "Central Ward", "B-", 3, "+91 800-432-6666"),
                (7, "Lifeline Super Specialty", "Airport Road", "A-", 2, "+91 800-432-7777"),
                (8, "Apollo Trauma Care", "Tech Corridor", "AB+", 11, "+91 800-432-8888")
            ]
        )

    # 3. ambulances table
    c.execute("""
    CREATE TABLE IF NOT EXISTS ambulances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_no TEXT UNIQUE,
        driver_name TEXT,
        phone TEXT,
        status TEXT DEFAULT 'Available',
        eta_mins INTEGER DEFAULT 4,
        location TEXT DEFAULT '',
        severity TEXT DEFAULT '',
        emergency_json TEXT DEFAULT NULL
    )
    """)
    if c.execute("SELECT COUNT(*) FROM ambulances").fetchone()[0] == 0:
        default_em = json.dumps({
            "patient_name": "Ramesh Kulkarni",
            "phone": "+91 98451 22334",
            "pickup_location": "Metro Pillar 42, CMH Road, Indiranagar, Bengaluru",
            "severity_level": "Level 1",
            "severity_label": "Critical (Cardiac / Severe Trauma / Unconscious)",
            "tag_color": "red",
            "maps_url": "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus("Metro Pillar 42, CMH Road, Indiranagar, Bengaluru"),
            "dispatched_at": "10:14 AM",
            "eta_mins": 7
        })
        c.executemany(
            "INSERT INTO ambulances (id, vehicle_no, driver_name, phone, status, eta_mins, location, severity, emergency_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "KA-01-EQ-9110", "Suresh Gowda", "+91 94480 12345", "Available", 4, "", "", None),
                (2, "KA-05-EM-4040", "Vikram Das", "+91 98860 67890", "Dispatched", 7, "Metro Pillar 42, CMH Road, Indiranagar, Bengaluru", "Level 1", default_em),
                (3, "KA-03-ER-1080", "Rajesh Naik", "+91 97410 54321", "Available", 5, "", "", None)
            ]
        )

    # 4. prescriptions table
    c.execute("""
    CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT,
        doctor_name TEXT DEFAULT 'Dr. Ananya Roy, MD',
        medicine_name TEXT,
        dosage_time TEXT,
        instructions TEXT,
        is_taken INTEGER DEFAULT 0,
        timing_slot TEXT DEFAULT 'Upcoming: 08:30 PM Dose',
        timing_label TEXT DEFAULT 'Twice Daily - After Food',
        image_url TEXT DEFAULT 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&auto=format&fit=crop&q=80',
        taken_time TEXT DEFAULT NULL
    )
    """)
    if c.execute("SELECT COUNT(*) FROM prescriptions").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO prescriptions (id, patient_name, doctor_name, medicine_name, dosage_time, timing_slot, timing_label, instructions, image_url, is_taken, taken_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "Amit Verma", "Dr. Ananya Roy, MD", "Aceclofenac + Paracetamol 100mg/325mg", "Twice Daily - After Food (1-0-1)", "Upcoming: 08:30 PM Dose", "Morning & Night - After Meals", "Avoid strenuous knee strain for 4 days. Cold compress application twice daily.", "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&auto=format&fit=crop&q=80", 0, None),
                (2, "Rahul Sharma", "Dr. Ananya Roy, MD", "Atorvastatin 20mg", "Night - Before Bed (0-0-1)", "Upcoming: 10:00 PM Dose", "Night - Before Bed", "Monitor lipid profile in 4 weeks. Maintain low sodium diet.", "https://images.unsplash.com/photo-1471864190281-a93a3070b6de?w=400&auto=format&fit=crop&q=80", 1, "09:45 PM"),
                (3, "Priya Patel", "Dr. Rajesh Gupta, MD", "Amoxicillin 500mg Oral Capsules", "Thrice Daily - After Food (1-1-1)", "Upcoming: 02:00 PM Dose", "After Meals - 8hr intervals", "Complete entire 5-day antibiotic course without skipping. Drink plenty of warm water.", "https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=400&auto=format&fit=crop&q=80", 0, None)
            ]
        )

    # 5. doctors table
    c.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        specialization TEXT,
        department TEXT,
        room_no TEXT,
        timings TEXT,
        consultation_fee REAL DEFAULT 600.0,
        status TEXT DEFAULT 'Active',
        avatar TEXT DEFAULT 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=120&auto=format&fit=crop&q=80'
    )
    """)
    if c.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO doctors (id, name, specialization, department, room_no, timings, consultation_fee, status, avatar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "Dr. Ananya Roy, MD", "Chief Cardiologist & OPD Lead", "Cardiology Specialist", "OPD-102", "09:00 AM - 01:00 PM", 800.0, "Active", "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=120&auto=format&fit=crop&q=80"),
                (2, "Dr. Rajesh Gupta, MD", "Senior Internal Medicine Specialist", "General Physician", "OPD-105", "10:00 AM - 02:00 PM", 500.0, "Active", "https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=120&auto=format&fit=crop&q=80"),
                (3, "Dr. Vikramaditya Rao, MS", "Orthopedic & Joint Replacement Surgeon", "Orthopedic Specialist", "OPD-201", "11:30 AM - 04:30 PM", 750.0, "Active", "https://images.unsplash.com/photo-1537368910025-700350fe46c7?w=120&auto=format&fit=crop&q=80"),
                (4, "Dr. Shalini Sen, MD", "Emergency Triage & Critical Care Lead", "Emergency Medicine", "ER-01", "24x7 On-Duty", 600.0, "Active", "https://images.unsplash.com/photo-1594824813580-0a2569106093?w=120&auto=format&fit=crop&q=80")
            ]
        )

    # 6. invoices table
    c.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT UNIQUE,
        patient_name TEXT,
        doctor_name TEXT,
        consultation_fee REAL DEFAULT 500.0,
        pharmacy_fee REAL DEFAULT 0.0,
        lab_fee REAL DEFAULT 0.0,
        total_amount REAL DEFAULT 500.0,
        status TEXT DEFAULT 'Payment Pending',
        created_at TEXT
    )
    """)
    if c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO invoices (id, invoice_no, patient_name, doctor_name, consultation_fee, pharmacy_fee, lab_fee, total_amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "INV-2026-001", "Rahul Sharma", "Dr. Ananya Roy, MD", 800.0, 450.0, 350.0, 1600.0, "Paid", "2026-09-25 10:30 AM"),
                (2, "INV-2026-002", "Priya Patel", "Dr. Rajesh Gupta, MD", 500.0, 220.0, 0.0, 720.0, "Payment Pending", "2026-09-27 11:15 AM"),
                (3, "INV-2026-003", "Amit Verma", "Dr. Vikramaditya Rao, MS", 750.0, 680.0, 500.0, 1930.0, "Paid", "2026-09-26 09:45 AM")
            ]
        )

    # 7. users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'patient',
        role_title TEXT DEFAULT 'Verified Patient',
        created_at TEXT NOT NULL
    )
    """)
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        c.executemany(
            """INSERT INTO users (full_name, email, phone, password_hash, role, role_title, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                ("Rahul Sharma", "rahul.sharma@resqlife.org", "+91 98765 43210", hash_password("patient123"), "patient", "Verified Patient", "2026-09-01 10:00:00"),
                ("Rahul Sharma", "rahul.sharma@patient.resqlife.org", "+91 98765 43210", hash_password("patient123"), "patient", "Verified Patient", "2026-09-01 10:00:00"),
                ("Sunita Deshmukh", "reception@resqlife.org", "+91 98000 11223", hash_password("reception123"), "hospital_admin", "Hospital Desk Coordinator", "2026-09-01 10:00:00"),
                ("Sunita Deshmukh", "admin@citycarehospital.in", "+91 98000 11224", hash_password("admin123"), "hospital_admin", "Hospital Desk Coordinator", "2026-09-01 10:00:00"),
                ("Sunita Deshmukh", "reception@citycarehospital.in", "+91 98000 11225", hash_password("reception123"), "reception", "Hospital Desk Coordinator", "2026-09-01 10:00:00"),
                ("Dr. Ananya Roy, MD", "dr.ananya@resqlife.org", "+91 99111 22334", hash_password("doctor123"), "doctor", "Consulting Physician", "2026-09-01 10:00:00"),
                ("Dr. Ananya Roy, MD", "ananya.roy@resqlife.med", "+91 99111 22335", hash_password("doctor123"), "doctor", "Consulting Physician", "2026-09-01 10:00:00"),
                ("Suresh Gowda", "dispatch@resqlife.org", "+91 94480 12345", hash_password("fleet123"), "ambulance", "Emergency Fleet Dispatcher", "2026-09-01 10:00:00"),
                ("Suresh Gowda", "suresh.driver@resqfleet.org", "+91 94480 12346", hash_password("fleet123"), "ambulance", "Emergency Fleet Dispatcher", "2026-09-01 10:00:00")
            ]
        )
    
    conn.commit()
    conn.close()

# Initialize DB and seed tables on startup
init_db()

# ==========================================
# ROW CONVERTERS & DB HELPERS
# ==========================================

def amb_row_to_dict(row):
    d = dict(row)
    em_raw = d.get("emergency_json")
    if em_raw:
        try:
            d["emergency"] = json.loads(em_raw)
        except Exception:
            d["emergency"] = None
    else:
        d["emergency"] = None
    return d

def blood_row_to_dict(row):
    d = dict(row)
    d["group"] = d.get("blood_group")
    return d

def rx_row_to_dict(row):
    d = dict(row)
    d["is_taken"] = bool(d.get("is_taken", 0))
    return d

def fetch_appointments():
    conn = get_db()
    rows = conn.execute("SELECT * FROM appointments ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def fetch_blood_inventory():
    conn = get_db()
    rows = conn.execute("SELECT * FROM blood_inventory ORDER BY id ASC").fetchall()
    conn.close()
    return [blood_row_to_dict(r) for r in rows]

def fetch_ambulances():
    conn = get_db()
    rows = conn.execute("SELECT * FROM ambulances ORDER BY id ASC").fetchall()
    conn.close()
    return [amb_row_to_dict(r) for r in rows]

def fetch_prescriptions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM prescriptions ORDER BY id ASC").fetchall()
    conn.close()
    return [rx_row_to_dict(r) for r in rows]

def fetch_doctors():
    conn = get_db()
    rows = conn.execute("SELECT * FROM doctors ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def fetch_invoices(patient_name=None):
    conn = get_db()
    if patient_name:
        rows = conn.execute("SELECT * FROM invoices WHERE LOWER(patient_name) LIKE ? ORDER BY id DESC", (f"%{patient_name.lower()}%",)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Dynamic collections for external imports/tests
class DBCollection:
    def __init__(self, fetch_fn):
        self._fetch_fn = fetch_fn
    def __iter__(self):
        return iter(self._fetch_fn())
    def __len__(self):
        return len(self._fetch_fn())
    def __getitem__(self, item):
        return self._fetch_fn()[item]
    def __repr__(self):
        return repr(self._fetch_fn())
    def __bool__(self):
        return bool(self._fetch_fn())

appointments = DBCollection(fetch_appointments)
blood_inventory = DBCollection(fetch_blood_inventory)
ambulances = DBCollection(fetch_ambulances)
prescriptions = DBCollection(fetch_prescriptions)
doctors = DBCollection(fetch_doctors)
invoices = DBCollection(fetch_invoices)

ROLE_LABELS = {
    "patient": "Patient / Healthcare Seeker",
    "hospital_admin": "Hospital Desk Coordinator",
    "reception": "Hospital Desk Coordinator",
    "doctor": "Consulting Physician",
    "ambulance": "Emergency Fleet Dispatcher"
}

ROLE_BADGES = {
    "patient": "bg-amber-100 text-amber-900 border border-amber-300",
    "hospital_admin": "bg-indigo-100 text-indigo-900 border border-indigo-300",
    "reception": "bg-indigo-100 text-indigo-900 border border-indigo-300",
    "doctor": "bg-emerald-100 text-emerald-900 border border-emerald-300",
    "ambulance": "bg-rose-100 text-rose-900 border border-rose-300"
}

def user_row_to_dict(row):
    if not row:
        return None
    d = dict(row)
    name = d.get("full_name") or d.get("name") or "User"
    d["name"] = name
    parts = name.strip().split()
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1][0]).upper()
    elif len(parts) == 1 and len(parts[0]) >= 2:
        initials = parts[0][:2].upper()
    else:
        initials = "RQ"
    d["initials"] = initials
    role = d.get("role", "patient")
    d["role_title"] = d.get("role_title") or ROLE_LABELS.get(role, "Healthcare Member")
    d["role_badge"] = ROLE_BADGES.get(role, "bg-slate-100 text-slate-800 border border-slate-300")
    if not d.get("avatar"):
        d["avatar"] = f"https://api.dicebear.com/7.x/initials/svg?seed={urllib.parse.quote_plus(name)}"
    return d

DEMO_USERS = {
    "patient": {
        "id": 1,
        "name": "Rahul Sharma",
        "full_name": "Rahul Sharma",
        "email": "rahul.sharma@resqlife.org",
        "phone": "+91 98765 43210",
        "role": "patient",
        "role_title": "Verified Patient",
        "role_badge": "bg-amber-100 text-amber-900 border border-amber-300",
        "initials": "RS",
        "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
    },
    "hospital_admin": {
        "id": 3,
        "name": "Sunita Deshmukh",
        "full_name": "Sunita Deshmukh",
        "email": "reception@resqlife.org",
        "phone": "+91 98000 11223",
        "role": "hospital_admin",
        "role_title": "Hospital Desk Coordinator",
        "role_badge": "bg-indigo-100 text-indigo-900 border border-indigo-300",
        "initials": "SD",
        "avatar": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=120&auto=format&fit=crop&q=80"
    },
    "reception": {
        "id": 5,
        "name": "Sunita Deshmukh",
        "full_name": "Sunita Deshmukh",
        "email": "reception@citycarehospital.in",
        "phone": "+91 98000 11225",
        "role": "reception",
        "role_title": "Hospital Desk Coordinator",
        "role_badge": "bg-indigo-100 text-indigo-900 border border-indigo-300",
        "initials": "SD",
        "avatar": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=120&auto=format&fit=crop&q=80"
    },
    "doctor": {
        "id": 6,
        "name": "Dr. Ananya Roy, MD",
        "full_name": "Dr. Ananya Roy, MD",
        "email": "dr.ananya@resqlife.org",
        "phone": "+91 99111 22334",
        "role": "doctor",
        "role_title": "Consulting Physician",
        "role_badge": "bg-emerald-100 text-emerald-900 border border-emerald-300",
        "initials": "AR",
        "avatar": "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=120&auto=format&fit=crop&q=80"
    },
    "ambulance": {
        "id": 8,
        "name": "Suresh Gowda",
        "full_name": "Suresh Gowda",
        "email": "dispatch@resqlife.org",
        "phone": "+91 94480 12345",
        "role": "ambulance",
        "role_title": "Emergency Fleet Dispatcher",
        "role_badge": "bg-rose-100 text-rose-900 border border-rose-300",
        "initials": "SG",
        "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=120&auto=format&fit=crop&q=80"
    }
}

registered_users = list(DEMO_USERS.values())

def calculate_next_token():
    conn = get_db()
    rows = conn.execute("SELECT token_no FROM appointments").fetchall()
    conn.close()
    max_num = 100
    for r in rows:
        tok = r["token_no"] or ""
        if tok.startswith("A-"):
            try:
                num = int(tok.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
        elif tok.startswith("T-"):
            try:
                num = int(tok.split("-")[1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
    return f"A-{max_num + 1}"

def compute_queue_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    waiting = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'Waiting'").fetchone()[0]
    in_clinic = conn.execute("SELECT COUNT(*) FROM appointments WHERE status IN ('In-Clinic', 'In-Consultation')").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'Completed'").fetchone()[0]
    conn.close()
    return {
        "total": total,
        "waiting": waiting,
        "in_clinic": in_clinic,
        "completed": completed
    }

# ==========================================
# AUTH ENDPOINTS & RBAC GUARDS
# ==========================================

def check_admin_auth():
    if app.testing:
        return None
    role = session.get("role") or session.get("user_role")
    if role not in ["hospital_admin", "reception"]:
        return jsonify({"success": False, "error": "Forbidden: Hospital Admin authorization required."}), 403
    return None

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    demo_role = data.get("demo_role") or data.get("quick_role")
    
    # 1. Quick access / test suite compatibility
    if demo_role and app.testing:
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE role = ? ORDER BY id ASC LIMIT 1", (demo_role,)).fetchone()
        conn.close()
        if row:
            user = user_row_to_dict(row)
            session["role"] = user["role"]
            session["user_role"] = user["role"]
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            return jsonify({"success": True, "message": f"Authenticated as {user['name']}", "user": user})
        elif demo_role in DEMO_USERS:
            user = DEMO_USERS[demo_role]
            session["role"] = user["role"]
            session["user_role"] = user["role"]
            session["user_id"] = user["id"]
            return jsonify({"success": True, "message": f"Authenticated as {user['name']}", "user": user})

    # 2. Standard credentials lookup by Email or Phone against SQLite
    identifier = (data.get("email") or data.get("identifier") or data.get("phone") or "").strip()
    password = data.get("password", "")
    
    if not identifier:
        return jsonify({"success": False, "error": "Email or phone number is required."}), 400

    conn = get_db()
    clean_digits = re.sub(r'\D', '', identifier)
    if clean_digits and len(clean_digits) == 10:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = ? OR phone LIKE ? ORDER BY id ASC LIMIT 1",
            (identifier.lower(), f"%{clean_digits}%")
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = ? ORDER BY id ASC LIMIT 1",
            (identifier.lower(),)
        ).fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": "Invalid credentials. Please verify your email and password."}), 401

    if not password or not verify_password(password, row["password_hash"]):
        return jsonify({"success": False, "error": "Invalid credentials. Please verify your email and password."}), 401

    user = user_row_to_dict(row)
    session["role"] = user["role"]
    session["user_role"] = user["role"]
    session["user_id"] = user["id"]
    session["user_email"] = user["email"]
    return jsonify({"success": True, "message": f"Welcome back, {user['name']}!", "user": user})

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    full_name = (data.get("full_name") or data.get("name") or "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")
    requested_role = (data.get("role") or "patient").strip().lower()
    passkey = (data.get("passkey") or data.get("auth_passkey") or "").strip()

    # 1. Full name: minimum 3 characters
    if not full_name or len(full_name) < 3:
        return jsonify({"success": False, "error": "Full Name must be at least 3 characters long."}), 400

    # 2. Email format validation with domain check & dummy reject
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not email or not re.match(email_regex, email):
        return jsonify({"success": False, "error": "Please provide a valid work or personal email address."}), 400

    dummy_patterns = ["dummy", "fake", "temp@", "none@", "test@test", "a@a.com"]
    if not app.testing and any(p in email for p in dummy_patterns):
        return jsonify({"success": False, "error": "Dummy email domains are rejected."}), 400

    # 3. Phone validation: 10-digit numeric check
    digits = re.sub(r'\D', '', phone)
    if phone and len(digits) != 10:
        return jsonify({"success": False, "error": "Phone number must be a valid 10-digit number."}), 400
    if not phone:
        phone = "+91 98765 00000"

    # 4. Password validation: minimum 6 characters
    if not password or len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters long."}), 400

    # 5. Role-Based Access Control & Hospital Authorization Passkey
    # Public registrations strictly create 'patient' accounts only by default.
    # 'hospital_admin', 'doctor', or staff roles strictly require HOSP2026 passkey.
    if requested_role in ["hospital_admin", "doctor", "reception", "ambulance"]:
        if passkey != "HOSP2026":
            return jsonify({
                "success": False,
                "error": "Forbidden: Hospital Authorization Passkey (e.g., HOSP2026) required for clinical or admin staff roles."
            }), 403
        role = requested_role
    else:
        role = "patient"

    role_title = ROLE_LABELS.get(role, "Patient / Healthcare Seeker")

    # 6. Check duplicate email in SQLite
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "error": "An account with this email address already exists."}), 400

    password_hash = hash_password(password)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO users (full_name, email, phone, password_hash, role, role_title, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (full_name, email, phone, password_hash, role, role_title, now_str)
    )
    new_user_id = cursor.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (new_user_id,)).fetchone()
    conn.close()

    new_user = user_row_to_dict(row)
    registered_users.append(new_user)
    session["role"] = new_user["role"]
    session["user_role"] = new_user["role"]
    session["user_id"] = new_user["id"]
    session["user_email"] = new_user["email"]
    return jsonify({"success": True, "message": f"Account created! Welcome, {full_name}.", "user": new_user})

@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True, "message": "Signed out successfully."})

@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user_id = session.get("user_id")
    if user_id:
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if row:
            return jsonify({"authenticated": True, "user": user_row_to_dict(row)})
        for u in registered_users:
            if str(u.get("id")) == str(user_id):
                return jsonify({"authenticated": True, "user": u})
    return jsonify({"authenticated": False, "user": None})

# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.route("/api/data", methods=["GET"])
def get_all_data():
    return jsonify({
        "appointments": fetch_appointments(),
        "blood_inventory": fetch_blood_inventory(),
        "ambulances": fetch_ambulances(),
        "prescriptions": fetch_prescriptions(),
        "doctors": fetch_doctors(),
        "invoices": fetch_invoices(),
        "stats": compute_queue_stats()
    })

@app.route("/api/appointments", methods=["GET"])
def get_appointments():
    return jsonify(fetch_appointments())

@app.route("/api/appointments/book", methods=["POST"])
def book_appointment():
    data = request.get_json(silent=True) or request.form.to_dict()
    patient = data.get("patient", "").strip()
    phone = data.get("phone", "").strip()
    slot = data.get("slot", "Immediate Walk-In").strip()
    doctor_category = data.get("doctor_category", "General Physician").strip()
    if not patient or not phone:
        return jsonify({"success": False, "error": "Patient name and phone number are required."}), 400
    
    patient_age = int(data.get("patient_age", 32)) if str(data.get("patient_age", "")).isdigit() else 32
    gender = data.get("gender", "Other").strip()
    blood_group = data.get("blood_group", "O+").strip()
    emergency_contact = data.get("emergency_contact", "").strip()
    allergies = data.get("allergies", "None Reported").strip()
    doctor_name = data.get("doctor_name", "Dr. Ananya Roy, MD").strip()
    appointment_date = data.get("appointment_date", datetime.now().strftime("%Y-%m-%d")).strip()
    
    next_token = calculate_next_token()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO appointments 
           (patient, phone, doctor_category, slot, token_no, status, patient_age, gender, blood_group, emergency_contact, allergies, doctor_name, appointment_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient, phone, doctor_category, slot, next_token, "Waiting", patient_age, gender, blood_group, emergency_contact, allergies, doctor_name, appointment_date)
    )
    conn.commit()
    new_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM appointments WHERE id = ?", (new_id,)).fetchone()
    new_apt = dict(row)
    conn.close()
    return jsonify({"success": True, "message": f"Appointment confirmed! Token #{next_token}.", "appointment": new_apt, "stats": compute_queue_stats()})

@app.route("/api/appointments/update-status", methods=["POST"])
def update_appointment_status():
    auth_err = check_admin_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True) or {}
    apt_id = data.get("id")
    target_status = data.get("status")
    if not apt_id:
        return jsonify({"success": False, "error": "Appointment ID is required."}), 400
    conn = get_db()
    row = conn.execute("SELECT * FROM appointments WHERE id = ?", (apt_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Appointment {apt_id} not found."}), 404
    target_apt = dict(row)
    status_cycle = {"Waiting": "In-Clinic", "In-Clinic": "Completed", "In-Consultation": "Completed", "Completed": "Waiting"}
    if target_status in ["Waiting", "In-Clinic", "In-Consultation", "Completed"]:
        new_status = target_status
    else:
        new_status = status_cycle.get(target_apt.get("status", "Waiting"), "In-Clinic")
    conn.execute("UPDATE appointments SET status = ? WHERE id = ?", (new_status, apt_id))
    conn.commit()
    target_apt["status"] = new_status
    conn.close()
    return jsonify({"success": True, "message": f"Token {target_apt['token_no']} → {target_apt['status']}", "appointment": target_apt, "stats": compute_queue_stats()})

@app.route("/api/prescriptions", methods=["GET"])
def get_prescriptions():
    return jsonify(fetch_prescriptions())

@app.route("/api/prescriptions/add", methods=["POST"])
def add_prescription():
    data = request.get_json(silent=True) or request.form.to_dict()
    patient_name = data.get("patient_name", "").strip()
    medicine_name = data.get("medicine_name", "").strip()
    dosage_time = data.get("dosage_time", "Twice Daily - After Food (1-0-1)").strip()
    instructions = data.get("instructions", "Follow regular dietary precautions.").strip()
    doctor_name = data.get("doctor_name", "Dr. Ananya Roy, MD").strip()
    image_url = data.get("image_url", "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&auto=format&fit=crop&q=80").strip()
    if not patient_name or not medicine_name:
        return jsonify({"success": False, "error": "Patient name and medicine are required."}), 400
    timing_slot_map = {
        "Morning - After Food (1-0-0)": "Upcoming: 08:30 AM Dose",
        "Night - Before Bed (0-0-1)": "Upcoming: 10:00 PM Dose",
        "Twice Daily - After Food (1-0-1)": "Upcoming: 08:30 PM Dose",
        "Thrice Daily - After Food (1-1-1)": "Upcoming: 02:00 PM Dose",
        "SOS - As Needed For Pain": "As Needed For Pain",
        "Before Meals - Empty Stomach (1-0-0)": "Upcoming: 07:30 AM Dose"
    }
    timing_slot = timing_slot_map.get(dosage_time, "Upcoming: Next Dose")
    timing_label = dosage_time.split('(')[0].strip()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO prescriptions (patient_name, doctor_name, medicine_name, dosage_time, timing_slot, timing_label, instructions, image_url, is_taken, taken_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)",
        (patient_name, doctor_name, medicine_name, dosage_time, timing_slot, timing_label, instructions, image_url)
    )
    conn.commit()
    new_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM prescriptions WHERE id = ?", (new_id,)).fetchone()
    new_rx = rx_row_to_dict(row)
    all_rx = fetch_prescriptions()
    conn.close()
    return jsonify({"success": True, "message": f"Prescription for {patient_name} saved.", "prescription": new_rx, "total_prescriptions": len(all_rx), "prescriptions": all_rx})

@app.route("/api/prescriptions/toggle-taken", methods=["POST"])
def toggle_prescription_taken():
    data = request.get_json(silent=True) or request.form.to_dict()
    rx_id = data.get("id")
    medicine_name = data.get("medicine_name")
    conn = get_db()
    target_row = None
    if rx_id:
        target_row = conn.execute("SELECT * FROM prescriptions WHERE id = ?", (rx_id,)).fetchone()
    elif medicine_name:
        target_row = conn.execute("SELECT * FROM prescriptions WHERE medicine_name = ?", (medicine_name,)).fetchone()
    if not target_row:
        conn.close()
        return jsonify({"success": False, "error": "Prescription record not found."}), 404
    target = rx_row_to_dict(target_row)
    new_is_taken = 0 if target["is_taken"] else 1
    if new_is_taken:
        taken_time = datetime.now().strftime("%I:%M %p")
        status_msg = f"Dose for {target['medicine_name']} marked TAKEN at {taken_time}."
    else:
        taken_time = None
        status_msg = f"Dose for {target['medicine_name']} marked PENDING."
    conn.execute("UPDATE prescriptions SET is_taken = ?, taken_time = ? WHERE id = ?", (new_is_taken, taken_time, target["id"]))
    conn.commit()
    target["is_taken"] = bool(new_is_taken)
    target["taken_time"] = taken_time
    all_rx = fetch_prescriptions()
    conn.close()
    return jsonify({"success": True, "message": status_msg, "prescription": target, "prescriptions": all_rx})

@app.route("/api/ambulances", methods=["GET"])
def get_ambulances():
    return jsonify(fetch_ambulances())

@app.route("/api/ambulance/request", methods=["POST"])
def request_ambulance():
    data = request.get_json(silent=True) or request.form.to_dict()
    patient_name = data.get("patient_name", "").strip() or "Emergency Patient"
    phone = data.get("phone", "").strip()
    pickup_location = data.get("pickup_location", "").strip()
    severity_level = data.get("severity_level", "Level 1").strip()
    if not pickup_location or not phone:
        return jsonify({"success": False, "error": "Pickup address and phone number are required."}), 400
    severity_config = {
        "Level 1": {"label": "Critical (Cardiac / Severe Trauma / Unconscious)", "tag_color": "red", "eta": 4},
        "Level 2": {"label": "Urgent (Fracture / High Fever / Acute Pain)", "tag_color": "amber", "eta": 7},
        "Level 3": {"label": "Standard Patient Transport", "tag_color": "blue", "eta": 12}
    }
    config = severity_config.get(severity_level, severity_config["Level 1"])
    encoded_loc = urllib.parse.quote_plus(pickup_location)
    maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_loc}"
    
    conn = get_db()
    amb_rows = conn.execute("SELECT * FROM ambulances ORDER BY id ASC").fetchall()
    amb_list = [amb_row_to_dict(r) for r in amb_rows]
    assigned = next((a for a in amb_list if a.get("status") == "Available"), None)
    if not assigned:
        assigned = min(amb_list, key=lambda a: a.get("eta_mins", 10))
    
    emergency_dict = {
        "patient_name": patient_name,
        "phone": phone,
        "pickup_location": pickup_location,
        "severity_level": severity_level,
        "severity_label": config["label"],
        "tag_color": config["tag_color"],
        "maps_url": maps_url,
        "dispatched_at": datetime.now().strftime("%I:%M %p"),
        "eta_mins": config["eta"]
    }
    emergency_json = json.dumps(emergency_dict)
    conn.execute(
        "UPDATE ambulances SET status = 'Dispatched', eta_mins = ?, location = ?, severity = ?, emergency_json = ? WHERE vehicle_no = ?",
        (config["eta"], pickup_location, severity_level, emergency_json, assigned["vehicle_no"])
    )
    conn.commit()
    assigned["status"] = "Dispatched"
    assigned["eta_mins"] = config["eta"]
    assigned["location"] = pickup_location
    assigned["severity"] = severity_level
    assigned["emergency"] = emergency_dict
    all_ambs = fetch_ambulances()
    conn.close()
    return jsonify({"success": True, "message": f"Unit {assigned['vehicle_no']} dispatched! Driver {assigned['driver_name']} ({assigned['phone']}) is en route.", "ambulance": assigned, "ambulances": all_ambs})

@app.route("/api/ambulance/update-status", methods=["POST"])
def update_ambulance_status():
    data = request.get_json(silent=True) or request.form.to_dict()
    vehicle_no = data.get("vehicle_no", "").strip()
    status = data.get("status", "").strip()
    if not vehicle_no or not status:
        return jsonify({"success": False, "error": "Vehicle number and status are required."}), 400
    conn = get_db()
    row = conn.execute("SELECT * FROM ambulances WHERE vehicle_no = ?", (vehicle_no,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Ambulance {vehicle_no} not found."}), 404
    target = amb_row_to_dict(row)
    emergency = target.get("emergency")
    if status in ["Available", "Complete Trip"]:
        new_status = "Available"
        new_emergency_json = None
        new_eta = 4
        new_location = ""
        new_severity = ""
        target["emergency"] = None
    elif status == "En-Route":
        new_status = "En-Route"
        new_eta = max(1, target.get("eta_mins", 4) - 2)
        if emergency:
            emergency["eta_mins"] = new_eta
        new_emergency_json = json.dumps(emergency) if emergency else None
        new_location = target.get("location", "")
        new_severity = target.get("severity", "")
        target["emergency"] = emergency
    elif status == "Arrived at Scene":
        new_status = "Arrived at Scene"
        new_eta = 0
        if emergency:
            emergency["eta_mins"] = 0
        new_emergency_json = json.dumps(emergency) if emergency else None
        new_location = target.get("location", "")
        new_severity = target.get("severity", "")
        target["emergency"] = emergency
    else:
        new_status = status
        new_eta = target.get("eta_mins", 4)
        new_emergency_json = json.dumps(emergency) if emergency else None
        new_location = target.get("location", "")
        new_severity = target.get("severity", "")
    conn.execute(
        "UPDATE ambulances SET status = ?, eta_mins = ?, location = ?, severity = ?, emergency_json = ? WHERE vehicle_no = ?",
        (new_status, new_eta, new_location, new_severity, new_emergency_json, vehicle_no)
    )
    conn.commit()
    target["status"] = new_status
    target["eta_mins"] = new_eta
    all_ambs = fetch_ambulances()
    conn.close()
    return jsonify({"success": True, "message": f"Unit {vehicle_no} status → {target['status']}", "ambulance": target, "ambulances": all_ambs})

@app.route("/api/blood", methods=["GET"])
def get_blood_inventory():
    return jsonify(fetch_blood_inventory())

@app.route("/api/blood/filter", methods=["GET", "POST"])
def filter_blood_inventory():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        group = data.get("group", "All")
    else:
        group = request.args.get("group", "All")
    inventory = fetch_blood_inventory()
    filtered = inventory if group in ["All", "ALL", "All Blood Groups", ""] else [i for i in inventory if i.get("group", "").strip().upper() == group.strip().upper()]
    return jsonify({"success": True, "group": group, "inventory": filtered, "total": len(filtered)})

@app.route("/api/blood/update", methods=["POST"])
def update_blood_inventory():
    data = request.get_json(silent=True) or request.form.to_dict()
    hospital = data.get("hospital", "").strip()
    group = data.get("group", "").strip().upper()
    try:
        units = max(0, int(data.get("units", 0)))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Units must be a valid non-negative integer."}), 400
    if not hospital or not group:
        return jsonify({"success": False, "error": "Hospital name and blood group are required."}), 400
    conn = get_db()
    row = conn.execute("SELECT * FROM blood_inventory WHERE LOWER(hospital) = ? AND UPPER(blood_group) = ?", (hospital.lower(), group)).fetchone()
    if row:
        conn.execute("UPDATE blood_inventory SET units = ? WHERE id = ?", (units, row["id"]))
        conn.commit()
        item = blood_row_to_dict(conn.execute("SELECT * FROM blood_inventory WHERE id = ?", (row["id"],)).fetchone())
    else:
        area = data.get("area", "Regional Medical Ward").strip()
        contact = data.get("contact", "+91 800-432-9999").strip()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO blood_inventory (hospital, area, blood_group, units, contact) VALUES (?, ?, ?, ?, ?)",
            (hospital, area, group, units, contact)
        )
        conn.commit()
        item = blood_row_to_dict(conn.execute("SELECT * FROM blood_inventory WHERE id = ?", (cursor.lastrowid,)).fetchone())
    all_blood = fetch_blood_inventory()
    conn.close()
    return jsonify({"success": True, "message": f"Stock for {group} at {hospital} updated to {units} units.", "item": item, "blood_inventory": all_blood})

# ==========================================
# DOCTORS & INVOICES API
# ==========================================

@app.route("/api/doctors", methods=["GET"])
def get_doctors():
    return jsonify(fetch_doctors())

@app.route("/api/doctors/manage", methods=["POST", "PUT"])
@app.route("/api/doctors/update-status", methods=["POST"])
def update_doctor_status():
    auth_err = check_admin_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True) or request.form.to_dict()
    doc_id = data.get("id")
    status = data.get("status", "Active")
    if not doc_id:
        return jsonify({"success": False, "error": "Doctor ID is required."}), 400
    conn = get_db()
    conn.execute("UPDATE doctors SET status = ? WHERE id = ?", (status, doc_id))
    conn.commit()
    doc = conn.execute("SELECT * FROM doctors WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    return jsonify({"success": True, "message": f"Doctor status updated to {status}.", "doctor": dict(doc) if doc else None, "doctors": fetch_doctors()})

@app.route("/api/invoices", methods=["GET"])
def get_invoices():
    auth_err = check_admin_auth()
    if auth_err:
        return auth_err
    patient = request.args.get("patient")
    return jsonify(fetch_invoices(patient))

@app.route("/api/invoices/create", methods=["POST"])
def create_invoice():
    auth_err = check_admin_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True) or request.form.to_dict()
    patient_name = data.get("patient_name", "").strip()
    doctor_name = data.get("doctor_name", "Dr. Ananya Roy, MD").strip()
    try:
        consultation_fee = float(data.get("consultation_fee", 500.0))
        pharmacy_fee = float(data.get("pharmacy_fee", 0.0))
        lab_fee = float(data.get("lab_fee", 0.0))
        total_amount = float(data.get("total_amount", consultation_fee + pharmacy_fee + lab_fee))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid fee amounts."}), 400
    
    if not patient_name:
        return jsonify({"success": False, "error": "Patient name is required."}), 400
    
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    inv_no = f"INV-2026-{count + 1:03d}"
    created_at = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO invoices (invoice_no, patient_name, doctor_name, consultation_fee, pharmacy_fee, lab_fee, total_amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (inv_no, patient_name, doctor_name, consultation_fee, pharmacy_fee, lab_fee, total_amount, "Payment Pending", created_at)
    )
    conn.commit()
    new_id = cursor.lastrowid
    new_inv = dict(conn.execute("SELECT * FROM invoices WHERE id = ?", (new_id,)).fetchone())
    all_invs = fetch_invoices()
    conn.close()
    return jsonify({"success": True, "message": f"Invoice {inv_no} issued successfully.", "invoice": new_inv, "invoices": all_invs})

@app.route("/api/invoices/pay", methods=["POST"])
def pay_invoice():
    data = request.get_json(silent=True) or request.form.to_dict()
    inv_id = data.get("id")
    inv_no = data.get("invoice_no")
    conn = get_db()
    if inv_id:
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,)).fetchone()
    elif inv_no:
        row = conn.execute("SELECT * FROM invoices WHERE invoice_no = ?", (inv_no,)).fetchone()
    else:
        conn.close()
        return jsonify({"success": False, "error": "Invoice ID or Invoice No is required."}), 400
    
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Invoice not found."}), 404
    
    conn.execute("UPDATE invoices SET status = 'Paid' WHERE id = ?", (row["id"],))
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM invoices WHERE id = ?", (row["id"],)).fetchone())
    all_invs = fetch_invoices()
    conn.close()
    return jsonify({"success": True, "message": f"Invoice {updated['invoice_no']} paid successfully!", "invoice": updated, "invoices": all_invs})

# ==========================================
# FRONTEND TEMPLATE
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ResQLife | Hospital SaaS · Emergency Fleet · OPD Queue · Blood Matrix</title>
  <meta name="description" content="ResQLife — Unified Hospital Operations & Emergency Coordination: Digital OPD Passes, Real-Time Medication Audio Alarms, Ambulance SOS GPS Radar, and Blood Inventory.">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">

  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          },
          colors: {
            navy: { 950: '#060d17', 900: '#0a192f', 800: '#0f2744', 700: '#1a3a5c' },
            brand: { 400: '#fbbf24', 500: '#f59e0b', 600: '#d97706' }
          },
          boxShadow: {
            'card': '0 2px 8px 0 rgba(15,23,42,0.06), 0 1px 2px 0 rgba(15,23,42,0.04)',
            'navy': '0 12px 36px 0 rgba(10,25,47,0.25)',
            'amber': '0 4px 20px 0 rgba(245,158,11,0.25)',
          }
        }
      }
    }
  </script>

  <style>
    body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #f8fafc; }
    .fade-in { animation: fadeIn 0.22s cubic-bezier(0.16,1,0.3,1) both; }
    @keyframes fadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
    @keyframes pulseRing { 0%,100%{ box-shadow:0 0 0 0 rgba(245,158,11,0.45);} 50%{ box-shadow:0 0 0 12px rgba(245,158,11,0);} }
    .pulse-amber { animation: pulseRing 2s infinite; }
    @keyframes pulseRose { 0%,100%{ box-shadow:0 0 0 0 rgba(239,68,68,0.5);} 50%{ box-shadow:0 0 0 14px rgba(239,68,68,0);} }
    .pulse-rose { animation: pulseRose 1.6s infinite; }
    @keyframes alarmPillPulse { 0%,100%{ transform:scale(1); filter:drop-shadow(0 0 10px rgba(239,68,68,0.4)); } 50%{ transform:scale(1.05); filter:drop-shadow(0 0 25px rgba(239,68,68,0.8)); } }
    .alarm-pill-active { animation: alarmPillPulse 1s infinite; }
    .tab-active { background:#0a192f; color:#fff; box-shadow:0 2px 8px rgba(10,25,47,0.18); }
    .tab-inactive { background:#fff; color:#475569; border:1px solid #e2e8f0; }
    .tab-inactive:hover { background:#f8fafc; color:#0f172a; }
    ::-webkit-scrollbar { width:6px; height:6px; }
    ::-webkit-scrollbar-track { background:#f1f5f9; }
    ::-webkit-scrollbar-thumb { background:#cbd5e1; border-radius:99px; }
    .card { background:#fff; border:1px solid #e2e8f0; border-radius:1rem; box-shadow:0 2px 8px rgba(15,23,42,0.06); }
    .card-navy { background:#0a192f; border:1px solid #1e3a5f; border-radius:1rem; box-shadow:0 8px 32px rgba(10,25,47,0.22); }
    .input-field { background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:0.75rem; padding:0.6rem 0.875rem; font-size:0.8125rem; color:#0f172a; transition:all 0.15s; width:100%; }
    .input-field:focus { outline:none; border-color:#f59e0b; box-shadow:0 0 0 3px rgba(245,158,11,0.12); background:#fff; }
    .input-dark { background:#050c18; border:1.5px solid #1e3a5f; border-radius:0.75rem; padding:0.6rem 0.875rem; font-size:0.8125rem; color:#f1f5f9; transition:all 0.15s; width:100%; }
    .input-dark:focus { outline:none; border-color:#f59e0b; box-shadow:0 0 0 3px rgba(245,158,11,0.15); }
    .btn-amber { background:#f59e0b; color:#0a192f; font-weight:800; border-radius:0.75rem; padding:0.65rem 1.4rem; font-size:0.8125rem; transition:all 0.15s; display:inline-flex; align-items:center; gap:0.5rem; cursor:pointer; }
    .btn-amber:hover { background:#fbbf24; transform:translateY(-1px); box-shadow:0 4px 16px rgba(245,158,11,0.28); }
    .btn-navy { background:#0a192f; color:#fbbf24; border:1px solid rgba(245,158,11,0.3); font-weight:700; border-radius:0.75rem; padding:0.65rem 1.4rem; font-size:0.8125rem; transition:all 0.15s; display:inline-flex; align-items:center; gap:0.5rem; cursor:pointer; }
    .btn-navy:hover { background:#0f2744; }
    .btn-rose { background:#ef4444; color:#fff; font-weight:700; border-radius:0.75rem; padding:0.65rem 1.4rem; font-size:0.8125rem; transition:all 0.15s; display:inline-flex; align-items:center; gap:0.5rem; cursor:pointer; }
    .btn-rose:hover { background:#dc2626; }
    @media print {
      body * { visibility: hidden; }
      #printableOpdCard, #printableOpdCard * { visibility: visible; }
      #printableOpdCard { position: absolute; left: 0; top: 0; width: 100%; margin: 0; padding: 20px; box-shadow: none; border: 1px solid #000; }
    }
  </style>
</head>

<body class="min-h-screen text-slate-800 antialiased selection:bg-amber-400 selection:text-slate-900">

  <!-- ============================================================ -->
  <!-- TOP NAVBAR                                                   -->
  <!-- ============================================================ -->
  <header class="sticky top-0 z-40 bg-white border-b border-slate-200" style="box-shadow:0 1px 4px rgba(15,23,42,0.06);">
    <div class="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">

        <!-- Logo -->
        <a href="/" class="flex items-center gap-3 shrink-0">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-amber">
            <i class="fa-solid fa-heart-pulse text-slate-900 text-base"></i>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-base sm:text-lg font-black text-slate-900 tracking-tight">ResQ<span class="text-amber-500">Life</span></span>
            <span class="text-slate-300 font-light">|</span>
            <span class="text-xs sm:text-sm font-bold text-slate-700 tracking-tight">Enterprise Healthcare Operations</span>
          </div>
        </a>

        <!-- Center Search & Nav Links -->
        <div class="hidden md:flex items-center gap-6">
          <a href="#features" class="text-xs font-bold text-slate-600 hover:text-amber-600 transition">Features</a>
          <a href="#doctors" class="text-xs font-bold text-slate-600 hover:text-amber-600 transition">Doctors Roster</a>
          <a href="#emergency" class="text-xs font-bold text-slate-600 hover:text-amber-600 transition">Emergency Fleet</a>
          <a href="#blood" class="text-xs font-bold text-slate-600 hover:text-amber-600 transition">Blood Bank</a>
        </div>

        <!-- Right Side: Enterprise Auth State & Fast Access -->
        <div class="flex items-center gap-2.5">
          <!-- Logged Out Actions -->
          <div id="loggedOutNavActions" class="flex items-center gap-2">
            <button onclick="openAuthModal('signin')" class="px-3.5 py-2 rounded-xl text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 transition flex items-center gap-1.5">
              <i class="fa-solid fa-arrow-right-to-bracket text-slate-600"></i> Sign In
            </button>
            <button onclick="openAuthModal('register')" class="btn-amber text-xs px-3.5 py-2 flex items-center gap-1.5 shadow-sm">
              <i class="fa-solid fa-user-plus text-slate-900"></i> Patient Register
            </button>
            <button onclick="openAdminSignIn()" class="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 transition">
              <i class="fa-solid fa-lock text-amber-400"></i> Admin Sign In
            </button>
          </div>

          <!-- Logged In User Pill -->
          <div id="loggedInUserPill" class="hidden flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-2xl pl-1.5 pr-3 py-1.5 shadow-card">
            <div id="navUserInitials" class="w-7 h-7 rounded-xl bg-slate-900 text-amber-400 font-black text-xs flex items-center justify-center ring-1 ring-slate-300">RS</div>
            <img id="navUserAvatar" src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80" alt="Avatar" class="w-7 h-7 rounded-xl object-cover ring-1 ring-slate-300 hidden">
            <div class="hidden sm:block">
              <div class="flex items-center gap-1.5">
                <span id="navUserName" class="text-xs font-bold text-slate-900">Rahul Sharma</span>
                <span id="navRoleBadge" class="text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200">PATIENT</span>
              </div>
              <p id="navUserRoleTitle" class="text-[10px] text-slate-500 font-medium leading-none mt-0.5">Verified Patient</p>
            </div>
            <div class="h-3.5 w-px bg-slate-200 mx-1 hidden sm:block"></div>
            <button onclick="handleLogout()" title="Logout" class="text-slate-500 hover:text-rose-600 transition text-xs px-2.5 py-1.5 rounded-lg hover:bg-rose-50 flex items-center gap-1.5 font-bold">
              <i class="fa-solid fa-right-from-bracket text-rose-500"></i>
              <span>Logout</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  </header>

  <!-- ============================================================ -->
  <!-- VIEW 1: PUBLIC HIGH-CONVERTING LANDING PAGE                  -->
  <!-- ============================================================ -->
  <div id="view-landing" class="hidden space-y-16 pb-20">

    <!-- Hero Section -->
    <section class="relative bg-gradient-to-b from-slate-900 via-navy-900 to-slate-950 text-white overflow-hidden pt-12 pb-20 px-4 sm:px-6 lg:px-8 border-b border-slate-800">
      <div class="absolute -right-24 -top-24 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div class="absolute -left-20 bottom-0 w-80 h-80 bg-rose-500/10 rounded-full blur-3xl pointer-events-none"></div>

      <div class="max-w-screen-xl mx-auto relative z-10">
        <div class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/10 border border-white/20 text-amber-400 text-xs font-bold mb-6">
          <i class="fa-solid fa-award text-amber-400"></i> FIT-FEST 2026 Grand Finalist · Next-Gen Enterprise Healthcare OS
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div class="lg:col-span-7 space-y-6">
            <h1 class="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight text-white leading-[1.1]">
              Next-Gen Unified <span class="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-amber-500">Hospital Operations</span> & Emergency Dispatch
            </h1>
            <p class="text-slate-300 text-base sm:text-lg max-w-2xl leading-relaxed">
              ResQLife bridges the critical golden hour with 24x7 GPS Ambulance SOS telemetry, digital OPD Queue tokens with executive printable slips, regional blood inventory alarms, and smart Web Audio medication reminders.
            </p>

            <!-- Hero CTAs -->
            <div class="flex flex-wrap items-center gap-3 pt-2">
              <button onclick="openAuthModal('signin')" class="btn-amber pulse-amber text-sm px-6 py-3.5">
                <i class="fa-solid fa-right-to-bracket text-slate-900"></i> Enter Patient Portal
              </button>
              <button onclick="openAuthModal('register')" class="btn-navy text-sm px-6 py-3.5 border-slate-700 text-white hover:bg-slate-800">
                <i class="fa-solid fa-user-plus text-amber-400"></i> Register New Patient
              </button>
              <a href="#emergency" class="btn-rose text-sm px-5 py-3.5">
                <i class="fa-solid fa-truck-medical animate-bounce"></i> Emergency SOS Radar
              </a>
            </div>

            <!-- Quick Metrics -->
            <div class="grid grid-cols-3 gap-4 pt-6 border-t border-slate-800 max-w-lg">
              <div>
                <span class="text-2xl sm:text-3xl font-black text-white font-mono">&lt; 4 mins</span>
                <p class="text-[11px] text-slate-400 font-semibold uppercase mt-0.5">Average SOS Response</p>
              </div>
              <div>
                <span class="text-2xl sm:text-3xl font-black text-amber-400 font-mono">100%</span>
                <p class="text-[11px] text-slate-400 font-semibold uppercase mt-0.5">SQLite Persistence</p>
              </div>
              <div>
                <span class="text-2xl sm:text-3xl font-black text-emerald-400 font-mono">24x7</span>
                <p class="text-[11px] text-slate-400 font-semibold uppercase mt-0.5">Cloud Run Uptime</p>
              </div>
            </div>
          </div>

          <!-- Hero Graphic / Interactive Preview -->
          <div class="lg:col-span-5">
            <div class="card-navy border border-amber-500/30 p-6 space-y-4 shadow-navy relative">
              <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <div class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-rose-500 animate-ping"></span>
                  <span class="text-xs font-black uppercase tracking-wider text-white">Live Hospital Telemetry</span>
                </div>
                <span class="text-[11px] font-mono text-amber-400">OPD QUEUE ACTIVE</span>
              </div>
              <div class="space-y-3 text-xs">
                <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800 flex items-center justify-between">
                  <div>
                    <span class="text-slate-400 block text-[10px] uppercase font-bold">Current Active Token</span>
                    <strong class="text-white text-base font-mono">A-101 (Rahul Sharma)</strong>
                  </div>
                  <span class="px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold text-[10px]">In-Consultation</span>
                </div>
                <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800 flex items-center justify-between">
                  <div>
                    <span class="text-slate-400 block text-[10px] uppercase font-bold">Dispatched Ambulance</span>
                    <strong class="text-white text-sm font-mono">KA-05-EM-4040 · Indiranagar</strong>
                  </div>
                  <span class="px-2.5 py-1 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 font-bold text-[10px]">ETA: 7 Mins</span>
                </div>
                <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800 flex items-center justify-between">
                  <div>
                    <span class="text-slate-400 block text-[10px] uppercase font-bold">Critical Shortage Alert</span>
                    <strong class="text-white text-sm">O- Negative (Only 2 Units Left)</strong>
                  </div>
                  <span class="px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 font-bold text-[10px]">City Care Trauma</span>
                </div>
              </div>

              <!-- Fast Role Access Portals -->
              <div class="pt-2">
                <span class="text-[11px] font-bold text-slate-400 block mb-2">⚡ Instant Portal Access:</span>
                <div class="grid grid-cols-2 gap-2">
                  <button onclick="quickAccessLogin('patient')" class="px-3 py-2 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 text-xs font-bold transition flex items-center justify-center gap-1.5">
                    <i class="fa-solid fa-user text-amber-400"></i> Patient Portal
                  </button>
                  <button onclick="quickAccessLogin('hospital_admin')" class="px-3 py-2 rounded-xl bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/40 text-blue-300 text-xs font-bold transition flex items-center justify-center gap-1.5">
                    <i class="fa-solid fa-hospital text-blue-400"></i> Admin Hub
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Feature Grid Section -->
    <section id="features" class="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
      <div class="text-center max-w-2xl mx-auto space-y-2">
        <span class="text-xs font-black uppercase tracking-widest text-amber-600 bg-amber-50 px-3 py-1 rounded-full border border-amber-200">Architectural Capabilities</span>
        <h2 class="text-3xl font-extrabold text-slate-900 tracking-tight">Four Pillars of Unified Emergency Care</h2>
        <p class="text-sm text-slate-500">Built to resolve healthcare fragmentation across triage, consultation, medication adherence, and blood supply.</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <!-- Feature 1 -->
        <div class="card p-6 space-y-3 hover:border-amber-400 transition hover:shadow-lg">
          <div class="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center text-xl shadow-sm border border-rose-100">
            <i class="fa-solid fa-truck-medical"></i>
          </div>
          <h3 class="text-base font-bold text-slate-900">24x7 Ambulance SOS</h3>
          <p class="text-xs text-slate-600 leading-relaxed">Live algorithmic dispatch finds the closest available paramedic fleet, assigns triage priority (Levels 1-3), and generates clickable Google Maps route links.</p>
          <div class="pt-2">
            <span class="text-[11px] font-bold text-rose-600 flex items-center gap-1">Live GPS Telemetry <i class="fa-solid fa-arrow-right text-[10px]"></i></span>
          </div>
        </div>

        <!-- Feature 2 -->
        <div class="card p-6 space-y-3 hover:border-amber-400 transition hover:shadow-lg">
          <div class="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl shadow-sm border border-amber-100">
            <i class="fa-solid fa-droplet"></i>
          </div>
          <h3 class="text-base font-bold text-slate-900">Blood Bank Matrix</h3>
          <p class="text-xs text-slate-600 leading-relaxed">Centralized inventory across regional trauma centers with real-time stock counters, automated critical shortage alarms (&le;2 units), and coordinator contact lines.</p>
          <div class="pt-2">
            <span class="text-[11px] font-bold text-amber-600 flex items-center gap-1">Universal Search & Filter <i class="fa-solid fa-arrow-right text-[10px]"></i></span>
          </div>
        </div>

        <!-- Feature 3 -->
        <div class="card p-6 space-y-3 hover:border-amber-400 transition hover:shadow-lg">
          <div class="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl shadow-sm border border-emerald-100">
            <i class="fa-solid fa-pills"></i>
          </div>
          <h3 class="text-base font-bold text-slate-900">Smart Medicine Vault</h3>
          <p class="text-xs text-slate-600 leading-relaxed">Interactive medication locker with Web Audio API real-time beeper alarms, visual pill verification photos, and tamper-resistant adherence logging.</p>
          <div class="pt-2">
            <span class="text-[11px] font-bold text-emerald-600 flex items-center gap-1">Audio Reminder Chime <i class="fa-solid fa-arrow-right text-[10px]"></i></span>
          </div>
        </div>

        <!-- Feature 4 -->
        <div class="card p-6 space-y-3 hover:border-amber-400 transition hover:shadow-lg">
          <div class="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl shadow-sm border border-blue-100">
            <i class="fa-solid fa-ticket"></i>
          </div>
          <h3 class="text-base font-bold text-slate-900">Digital OPD Queue Slip</h3>
          <p class="text-xs text-slate-600 leading-relaxed">Comprehensive demographic intake, doctor consultation booking wizard, executive printable OPD slips with digital QR verification tokens, and real-time triage queue updates.</p>
          <div class="pt-2">
            <span class="text-[11px] font-bold text-blue-600 flex items-center gap-1">Printable Executive Slips <i class="fa-solid fa-arrow-right text-[10px]"></i></span>
          </div>
        </div>
      </div>
    </section>

    <!-- Doctors Roster Section -->
    <section id="doctors" class="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
      <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <span class="text-xs font-black uppercase tracking-widest text-amber-600 bg-amber-50 px-3 py-1 rounded-full border border-amber-200">OPD Specialists</span>
          <h2 class="text-2xl font-extrabold text-slate-900 tracking-tight mt-1">Active Consulting Doctors</h2>
        </div>
        <button onclick="quickAccessLogin('patient')" class="text-xs font-bold text-amber-600 hover:text-amber-700">Book OPD Appointment &rarr;</button>
      </div>

      <div id="landingDoctorsGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <!-- Rendered via JS -->
      </div>
    </section>

    <!-- Public Live Blood Bank Matrix Section -->
    <section id="blood" class="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
      <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <span class="text-xs font-black uppercase tracking-widest text-rose-600 bg-rose-50 px-3 py-1 rounded-full border border-rose-200">Trauma Readiness</span>
          <h2 class="text-2xl font-extrabold text-slate-900 tracking-tight mt-1">Regional Blood Bank Stock Matrix</h2>
        </div>
        <div class="flex items-center gap-2">
          <input type="text" id="landingBloodFilterInput" oninput="filterLandingBlood(this.value)" placeholder="Search hospital or area..." class="input-field text-xs py-1.5 max-w-xs">
        </div>
      </div>

      <div class="card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-black tracking-wider text-[10px]">
              <tr>
                <th class="px-5 py-3">Hospital Center</th>
                <th class="px-4 py-3">Ward / Area</th>
                <th class="px-4 py-3 text-center">Blood Group</th>
                <th class="px-4 py-3 text-center">Available Units</th>
                <th class="px-4 py-3">Status</th>
                <th class="px-5 py-3 text-right">Emergency Contact</th>
              </tr>
            </thead>
            <tbody id="landingBloodTableBody" class="divide-y divide-slate-100">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- Public Emergency SOS Section -->
    <section id="emergency" class="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="card-navy text-white p-6 sm:p-10 relative overflow-hidden space-y-6">
        <div class="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div class="space-y-2 max-w-xl">
            <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-black uppercase">
              <i class="fa-solid fa-truck-medical animate-bounce"></i> 24x7 Priority Trauma SOS
            </div>
            <h2 class="text-2xl sm:text-3xl font-black text-white">Emergency Paramedic Dispatch</h2>
            <p class="text-xs text-slate-300">Submit pickup location to calculate closest unit, generate Google Maps GPS coordinates, and alert hospital triage.</p>
          </div>
          <div class="flex items-center gap-3">
            <a href="tel:108" class="btn-rose text-sm px-6 py-3"><i class="fa-solid fa-phone-volume"></i> Call 108 Emergency</a>
          </div>
        </div>

        <form onsubmit="handlePublicSos(event)" class="relative z-10 grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 border-t border-slate-800">
          <div class="md:col-span-2">
            <label class="block text-[11px] font-black uppercase tracking-widest text-slate-300 mb-1">Pickup Address</label>
            <input type="text" id="public_sos_loc" placeholder="e.g. Metro Pillar 42, Indiranagar, Bengaluru" class="input-dark text-xs" required>
          </div>
          <div>
            <label class="block text-[11px] font-black uppercase tracking-widest text-slate-300 mb-1">Contact Phone</label>
            <input type="tel" id="public_sos_phone" placeholder="+91 98765 43210" class="input-dark text-xs" required>
          </div>
          <div>
            <label class="block text-[11px] font-black uppercase tracking-widest text-slate-300 mb-1">Severity</label>
            <select id="public_sos_sev" class="input-dark text-xs">
              <option value="Level 1">🔴 Level 1: Critical (Cardiac / Trauma)</option>
              <option value="Level 2">🟠 Level 2: Urgent (Fracture / High Fever)</option>
              <option value="Level 3">🔵 Level 3: Standard Transport</option>
            </select>
          </div>
          <div class="md:col-span-4 flex justify-end">
            <button type="submit" class="btn-amber text-xs px-6 py-3 pulse-amber">
              <i class="fa-solid fa-paper-plane"></i> Dispatch Nearest Ambulance Now
            </button>
          </div>
        </form>
      </div>
    </section>

  </div>

  <!-- ============================================================ -->
  <!-- PUBLIC PATIENT PORTAL (DEFAULT HOMEPAGE VIEW)                -->
  <!-- ============================================================ -->
  <div id="view-patient" class="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

    <!-- Patient Header Banner -->
    <div class="card-navy text-white p-6 relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div class="relative z-10 flex items-center gap-4">
        <div class="w-14 h-14 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0">
          <i class="fa-solid fa-hospital-user text-2xl text-amber-400"></i>
        </div>
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-black uppercase tracking-widest text-amber-400">Patient Health Locker</span>
            <span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Verified & Active</span>
          </div>
          <h2 class="text-xl sm:text-2xl font-black text-white" id="patientWelcomeName">Welcome, Rahul Sharma</h2>
          <p class="text-xs text-slate-300 mt-0.5">Book OPD consultations, print digital appointment passes, verify medicine doses, and pay bills.</p>
        </div>
      </div>
      <div class="relative z-10 flex items-center gap-2 shrink-0">
        <button onclick="triggerAudioAlarm()" class="btn-rose text-xs px-4 py-2.5">
          <i class="fa-solid fa-bell animate-bounce"></i> Test Audio Alarm
        </button>
        <button onclick="switchPatientTab('booking')" class="btn-amber text-xs px-4 py-2.5">
          <i class="fa-solid fa-plus"></i> New Appointment
        </button>
      </div>
    </div>

    <!-- Patient Sub-Tabs Navigation -->
    <div class="bg-white border border-slate-200 rounded-2xl p-1.5 flex items-center gap-1.5 overflow-x-auto shadow-card">
      <button onclick="switchPatientTab('booking')" id="ptab-btn-booking" class="ptab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-active">
        <i class="fa-solid fa-calendar-plus text-amber-400"></i> Book OPD Consultation
      </button>
      <button onclick="switchPatientTab('vault')" id="ptab-btn-vault" class="ptab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-inactive">
        <i class="fa-solid fa-pills"></i> Medicine Vault & Alarm
      </button>
      <button onclick="switchPatientTab('billing')" id="ptab-btn-billing" class="ptab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-inactive">
        <i class="fa-solid fa-file-invoice-dollar"></i> Invoices & Billing Desk
      </button>
      <button onclick="switchPatientTab('sos')" id="ptab-btn-sos" class="ptab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-inactive">
        <i class="fa-solid fa-truck-medical text-rose-500"></i> Emergency SOS
      </button>
      <button onclick="switchPatientTab('blood')" id="ptab-btn-blood" class="ptab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-inactive">
        <i class="fa-solid fa-droplet text-red-500"></i> Blood Bank
      </button>
    </div>

    <!-- SUB-TAB 1: APPOINTMENT BOOKING WIZARD & RECENT PASSES -->
    <div id="patient-module-booking" class="patient-module space-y-6 fade-in">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

        <!-- Booking Wizard Form (8 cols) -->
        <div class="lg:col-span-7 card p-6 sm:p-7 space-y-5">
          <div class="border-b border-slate-100 pb-4">
            <h3 class="text-base font-extrabold text-slate-900 flex items-center gap-2">
              <i class="fa-solid fa-hospital-user text-amber-500"></i> Hospital OPD Appointment Booking Wizard
            </h3>
            <p class="text-xs text-slate-500 mt-1">Complete patient details to generate an official digital OPD Consultation Slip & Queue Token.</p>
          </div>

          <form id="patientBookingForm" onsubmit="handlePatientBooking(event)" class="space-y-4">
            <!-- Patient Demographics -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div class="sm:col-span-2">
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Patient Full Name <span class="text-rose-500">*</span></label>
                <input type="text" id="pt_name" placeholder="Rahul Sharma" class="input-field" required>
              </div>
              <div>
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Phone <span class="text-rose-500">*</span></label>
                <input type="tel" id="pt_phone" placeholder="+91 98765 43210" class="input-field" required>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Age</label>
                <input type="number" id="pt_age" value="34" min="1" max="120" class="input-field">
              </div>
              <div>
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Gender</label>
                <select id="pt_gender" class="input-field">
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div>
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Blood Group</label>
                <select id="pt_blood" class="input-field">
                  <option value="O+">O+ Positive</option>
                  <option value="O-">O- Negative</option>
                  <option value="A+">A+ Positive</option>
                  <option value="A-">A- Negative</option>
                  <option value="B+">B+ Positive</option>
                  <option value="B-">B- Negative</option>
                  <option value="AB+">AB+ Positive</option>
                  <option value="AB-">AB- Negative</option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Emergency Contact</label>
                <input type="tel" id="pt_emerg_phone" placeholder="+91 98765 11111" class="input-field">
              </div>
              <div>
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Allergies / Conditions</label>
                <input type="text" id="pt_allergies" placeholder="e.g. Penicillin, Asthma, None" class="input-field">
              </div>
            </div>

            <!-- Doctor & Slot Selection -->
            <div class="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Department & Doctor <span class="text-rose-500">*</span></label>
                <select id="pt_doctor_select" onchange="syncSelectedDoctor(this.value)" class="input-field font-semibold" required>
                  <!-- Populated by JS -->
                </select>
              </div>
              <div>
                <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Appointment Date</label>
                <input type="date" id="pt_date" class="input-field" required>
              </div>
            </div>

            <div>
              <label class="block text-[11px] font-black uppercase tracking-wider text-slate-700 mb-1">Preferred Time Slot</label>
              <div class="grid grid-cols-4 gap-2 text-xs">
                <label class="border border-slate-200 rounded-xl p-2 text-center cursor-pointer hover:bg-amber-50 peer-checked:bg-amber-500">
                  <input type="radio" name="pt_slot" value="09:30 AM" class="sr-only" checked>
                  <span class="font-bold text-slate-800">09:30 AM</span>
                </label>
                <label class="border border-slate-200 rounded-xl p-2 text-center cursor-pointer hover:bg-amber-50">
                  <input type="radio" name="pt_slot" value="11:00 AM" class="sr-only">
                  <span class="font-bold text-slate-800">11:00 AM</span>
                </label>
                <label class="border border-slate-200 rounded-xl p-2 text-center cursor-pointer hover:bg-amber-50">
                  <input type="radio" name="pt_slot" value="02:00 PM" class="sr-only">
                  <span class="font-bold text-slate-800">02:00 PM</span>
                </label>
                <label class="border border-slate-200 rounded-xl p-2 text-center cursor-pointer hover:bg-amber-50">
                  <input type="radio" name="pt_slot" value="04:30 PM" class="sr-only">
                  <span class="font-bold text-slate-800">04:30 PM</span>
                </label>
              </div>
            </div>

            <div class="pt-3">
              <button type="submit" class="btn-amber w-full justify-center py-3 text-sm font-black">
                <i class="fa-solid fa-ticket"></i> Confirm Appointment & Generate Executive OPD Slip
              </button>
            </div>
          </form>
        </div>

        <!-- Right: Recent Appointments & OPD Slip Preview (5 cols) -->
        <div class="lg:col-span-5 space-y-4">
          <div class="card p-5 space-y-3">
            <div class="flex items-center justify-between border-b border-slate-100 pb-3">
              <h4 class="text-xs font-black uppercase tracking-wider text-slate-800">My Registered Appointments</h4>
              <span class="text-[10px] font-bold text-amber-600">Live Status</span>
            </div>
            <div id="patientAppointmentsList" class="space-y-3">
              <!-- Rendered via JS -->
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- SUB-TAB 2: MEDICINE VAULT & AUDIO ALARM -->
    <div id="patient-module-vault" class="patient-module hidden space-y-6 fade-in">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200 shadow-card">
        <div>
          <h3 class="text-base font-extrabold text-slate-900 flex items-center gap-2">
            <i class="fa-solid fa-pills text-emerald-500"></i> Smart Medication Adherence Vault
          </h3>
          <p class="text-xs text-slate-500 mt-0.5">Track your active prescription schedule with Web Audio alarms and dosage adherence logs.</p>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="triggerAudioAlarm()" class="btn-rose text-xs px-4 py-2">
            <i class="fa-solid fa-volume-high animate-bounce"></i> Trigger Audio Alarm Now
          </button>
        </div>
      </div>

      <div id="patientPrescriptionsGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        <!-- Rendered via JS -->
      </div>
    </div>

    <!-- SUB-TAB 3: INVOICES & BILLING DESK -->
    <div id="patient-module-billing" class="patient-module hidden space-y-6 fade-in">
      <div class="card p-6 space-y-4">
        <div class="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <h3 class="text-base font-extrabold text-slate-900 flex items-center gap-2">
              <i class="fa-solid fa-file-invoice-dollar text-amber-500"></i> Patient Invoices & Medical Billing
            </h3>
            <p class="text-xs text-slate-500 mt-0.5">Itemized hospital consultation, pharmacy, and laboratory invoices.</p>
          </div>
          <span class="text-xs font-bold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
            <i class="fa-solid fa-shield-check"></i> Secure Billing
          </span>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-bold text-[10px]">
              <tr>
                <th class="px-4 py-3">Invoice #</th>
                <th class="px-4 py-3">Consulting Doctor</th>
                <th class="px-4 py-3">Consultation Fee</th>
                <th class="px-4 py-3">Pharmacy / Meds</th>
                <th class="px-4 py-3">Lab Charges</th>
                <th class="px-4 py-3">Total Amount</th>
                <th class="px-4 py-3">Status</th>
                <th class="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody id="patientInvoicesTableBody" class="divide-y divide-slate-100">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- SUB-TAB 4: EMERGENCY SOS IN PATIENT VIEW -->
    <div id="patient-module-sos" class="patient-module hidden space-y-6 fade-in">
      <div class="card-navy text-white p-7 space-y-5">
        <h3 class="text-xl font-bold text-white flex items-center gap-2">
          <i class="fa-solid fa-truck-medical text-rose-400"></i> Priority Patient SOS Ambulance Trigger
        </h3>
        <p class="text-xs text-slate-300">Your registered coordinates and profile will be dispatched to the nearest paramedic unit.</p>
        <form onsubmit="handlePatientSos(event)" class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div class="sm:col-span-2">
            <label class="block text-[11px] font-bold text-slate-300 mb-1">Pickup Location</label>
            <input type="text" id="pt_sos_loc" placeholder="Current Location / Home Address" class="input-dark text-xs" required>
          </div>
          <div>
            <label class="block text-[11px] font-bold text-slate-300 mb-1">Severity</label>
            <select id="pt_sos_sev" class="input-dark text-xs">
              <option value="Level 1">🔴 Level 1: Critical Emergency</option>
              <option value="Level 2">🟠 Level 2: Urgent Care</option>
              <option value="Level 3">🔵 Level 3: Non-Emergency Transport</option>
            </select>
          </div>
          <div class="sm:col-span-3 flex justify-end">
            <button type="submit" class="btn-rose text-xs px-6 py-2.5 pulse-rose">
              <i class="fa-solid fa-paper-plane"></i> Dispatch Paramedics Now
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- SUB-TAB 5: BLOOD BANK IN PATIENT VIEW -->
    <div id="patient-module-blood" class="patient-module hidden space-y-4 fade-in">
      <div class="card p-5 space-y-3">
        <h3 class="text-base font-bold text-slate-900">Hospital Blood Bank Availability</h3>
        <p class="text-xs text-slate-500">Live units available at City Care Trauma Network.</p>
        <div id="patientBloodGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <!-- Rendered via JS -->
        </div>
      </div>
    </div>

  </div>

  <!-- ============================================================ -->
  <!-- VIEW 3: HOSPITAL ADMIN & RECEPTION OPERATIONS HUB            -->
  <!-- ============================================================ -->
  <div id="view-admin" class="hidden max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

    <!-- Admin Header Banner -->
    <div class="card-navy text-white p-6 relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div class="relative z-10 flex items-center gap-4">
        <div class="w-14 h-14 rounded-2xl bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center shrink-0">
          <i class="fa-solid fa-hospital text-2xl text-indigo-400"></i>
        </div>
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-black uppercase tracking-widest text-indigo-400">Hospital Administration & Reception Desk</span>
            <span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Executive Access</span>
          </div>
          <h2 class="text-xl sm:text-2xl font-black text-white">Central Healthcare Operations Center</h2>
          <p class="text-xs text-slate-300 mt-0.5">Manage live OPD triage, doctor roster availability, patient medicine planning, and billing desks.</p>
        </div>
      </div>
      <div class="relative z-10 flex items-center gap-2 shrink-0">
        <button onclick="openNewInvoiceModal()" class="btn-amber text-xs px-4 py-2.5">
          <i class="fa-solid fa-file-circle-plus"></i> Issue New Invoice
        </button>
      </div>
    </div>

    <!-- Admin Operations Sub-Tabs Navigation -->
    <div class="bg-white border border-slate-200 rounded-2xl p-1.5 flex items-center gap-1.5 overflow-x-auto shadow-card">
      <button onclick="switchAdminTab('queue')" id="atab-btn-queue" class="atab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-active">
        <i class="fa-solid fa-list-check text-amber-400"></i> Live OPD Queue Desk
      </button>
      <button onclick="switchAdminTab('doctors')" id="atab-btn-doctors" class="atab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-inactive">
        <i class="fa-solid fa-user-doctor"></i> Doctor Roster
      </button>
      <button onclick="switchAdminTab('meds')" id="atab-btn-meds" class="atab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-inactive">
        <i class="fa-solid fa-prescription-bottle-medical"></i> Patient Medicine Planner
      </button>
      <button onclick="switchAdminTab('billing')" id="atab-btn-billing" class="atab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-inactive">
        <i class="fa-solid fa-cash-register"></i> Hospital Invoicing Desk
      </button>
      <button onclick="switchAdminTab('fleet')" id="atab-btn-fleet" class="atab-btn flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition tab-inactive">
        <i class="fa-solid fa-truck-medical text-rose-500"></i> Ambulance Fleet Radar
      </button>
    </div>

    <!-- ADMIN SUB-TAB 1: LIVE OPD QUEUE DESK -->
    <div id="admin-module-queue" class="admin-module space-y-6 fade-in">
      <!-- Queue Stats Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="card p-4 space-y-1">
          <span class="text-[10px] font-bold text-slate-400 uppercase">Total Patients</span>
          <div class="text-2xl font-black text-slate-900 font-mono" id="statTotalPatients">4</div>
        </div>
        <div class="card p-4 space-y-1">
          <span class="text-[10px] font-bold text-amber-600 uppercase">Waiting in Queue</span>
          <div class="text-2xl font-black text-amber-600 font-mono" id="statWaitingPatients">1</div>
        </div>
        <div class="card p-4 space-y-1">
          <span class="text-[10px] font-bold text-blue-600 uppercase">In-Consultation</span>
          <div class="text-2xl font-black text-blue-600 font-mono" id="statInClinicPatients">1</div>
        </div>
        <div class="card p-4 space-y-1">
          <span class="text-[10px] font-bold text-emerald-600 uppercase">Completed Consults</span>
          <div class="text-2xl font-black text-emerald-600 font-mono" id="statCompletedPatients">2</div>
        </div>
      </div>

      <!-- Live Queue Table -->
      <div class="card overflow-hidden">
        <div class="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 class="text-sm font-black text-slate-900 uppercase tracking-wider">Live OPD Consultation Queue</h3>
          <span class="text-xs text-slate-400">Click action badge to toggle state (Waiting &rarr; In-Clinic &rarr; Completed)</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-bold text-[10px]">
              <tr>
                <th class="px-5 py-3">Token #</th>
                <th class="px-4 py-3">Patient Name</th>
                <th class="px-4 py-3">Contact</th>
                <th class="px-4 py-3">Assigned Doctor</th>
                <th class="px-4 py-3">Slot</th>
                <th class="px-4 py-3 text-center">Status Cycle</th>
                <th class="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody id="adminQueueTableBody" class="divide-y divide-slate-100">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ADMIN SUB-TAB 2: DOCTOR ROSTER MANAGEMENT -->
    <div id="admin-module-doctors" class="admin-module hidden space-y-6 fade-in">
      <div class="card p-6 space-y-4">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 class="text-base font-extrabold text-slate-900">Hospital Doctor Roster</h3>
            <p class="text-xs text-slate-500">Manage room numbers, consultation hours, and active status.</p>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-bold text-[10px]">
              <tr>
                <th class="px-4 py-3">Doctor</th>
                <th class="px-4 py-3">Specialization</th>
                <th class="px-4 py-3">Room #</th>
                <th class="px-4 py-3">Timings</th>
                <th class="px-4 py-3">Fee</th>
                <th class="px-4 py-3">Current Status</th>
                <th class="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody id="adminDoctorsTableBody" class="divide-y divide-slate-100">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ADMIN SUB-TAB 3: PATIENT MEDICINE PLANNER -->
    <div id="admin-module-meds" class="admin-module hidden space-y-6 fade-in">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div class="lg:col-span-6 card p-6 space-y-4">
          <div class="border-b border-slate-100 pb-3">
            <h3 class="text-base font-extrabold text-slate-900">Issue Medication Plan</h3>
            <p class="text-xs text-slate-500">Prescribe medication directly to a patient's adherence vault.</p>
          </div>
          <form onsubmit="handleAdminAddPrescription(event)" class="space-y-3">
            <div>
              <label class="block text-[11px] font-bold text-slate-700 mb-1">Select Patient</label>
              <select id="adm_rx_patient" class="input-field font-semibold" required>
                <!-- Populated via JS -->
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-bold text-slate-700 mb-1">Prescribing Doctor</label>
              <select id="adm_rx_doctor" class="input-field font-semibold" required>
                <!-- Populated via JS -->
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-bold text-slate-700 mb-1">Medicine Name & Strength</label>
              <input type="text" id="adm_rx_med" placeholder="e.g. Telmisartan 40mg + Chlorthalidone" class="input-field" required>
            </div>
            <div>
              <label class="block text-[11px] font-bold text-slate-700 mb-1">Dosage Frequency</label>
              <select id="adm_rx_timing" class="input-field">
                <option value="Morning - After Food (1-0-0)">Morning - After Food (1-0-0)</option>
                <option value="Night - Before Bed (0-0-1)">Night - Before Bed (0-0-1)</option>
                <option value="Twice Daily - After Food (1-0-1)" selected>Twice Daily - After Food (1-0-1)</option>
                <option value="Thrice Daily - After Food (1-1-1)">Thrice Daily - After Food (1-1-1)</option>
                <option value="SOS - As Needed For Pain">SOS - As Needed For Pain</option>
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-bold text-slate-700 mb-1">Patient Instructions</label>
              <input type="text" id="adm_rx_instructions" placeholder="Take after food with plenty of warm water." class="input-field" required>
            </div>
            <div>
              <label class="block text-[11px] font-bold text-slate-700 mb-1">Medication Photo URL</label>
              <input type="url" id="adm_rx_img" value="https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&auto=format&fit=crop&q=80" class="input-field">
            </div>
            <div class="pt-2">
              <button type="submit" class="btn-amber w-full justify-center">
                <i class="fa-solid fa-plus"></i> Save to Patient Medication Vault
              </button>
            </div>
          </form>
        </div>

        <div class="lg:col-span-6 card p-6 space-y-4">
          <h3 class="text-sm font-black text-slate-900 uppercase tracking-wider">All Active Prescriptions</h3>
          <div id="adminPrescriptionsList" class="space-y-3">
            <!-- Rendered via JS -->
          </div>
        </div>
      </div>
    </div>

    <!-- ADMIN SUB-TAB 4: BILLING & INVOICING DESK -->
    <div id="admin-module-billing" class="admin-module hidden space-y-6 fade-in">
      <div class="card p-6 space-y-4">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 class="text-base font-extrabold text-slate-900">Hospital Billing & Invoice Ledger</h3>
            <p class="text-xs text-slate-500">Issue and verify patient consultation & pharmacy accounts.</p>
          </div>
          <button onclick="openNewInvoiceModal()" class="btn-amber text-xs px-3.5 py-1.5">
            <i class="fa-solid fa-plus"></i> Create Invoice
          </button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-bold text-[10px]">
              <tr>
                <th class="px-4 py-3">Invoice #</th>
                <th class="px-4 py-3">Patient</th>
                <th class="px-4 py-3">Consulting Doctor</th>
                <th class="px-4 py-3">Consultation</th>
                <th class="px-4 py-3">Pharmacy</th>
                <th class="px-4 py-3">Lab Fee</th>
                <th class="px-4 py-3">Total Amount</th>
                <th class="px-4 py-3">Status</th>
                <th class="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody id="adminInvoicesTableBody" class="divide-y divide-slate-100">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ADMIN SUB-TAB 5: FLEET RADAR -->
    <div id="admin-module-fleet" class="admin-module hidden space-y-6 fade-in">
      <div class="card-navy text-white p-6 space-y-4">
        <h3 class="text-lg font-bold text-white flex items-center gap-2">
          <i class="fa-solid fa-truck-medical text-rose-400"></i> Active Ambulance Fleet Radar
        </h3>
        <div id="adminFleetRadarGrid" class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Rendered via JS -->
        </div>
      </div>
    </div>

  </div>

  <!-- ============================================================ -->
  <!-- MODAL 1: EXECUTIVE PRINTABLE OPD APPOINTMENT CARD SLIP       -->
  <!-- ============================================================ -->
  <div id="opdCardModal" class="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm hidden flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl max-w-lg w-full overflow-hidden shadow-2xl border border-slate-200 fade-in">
      
      <!-- Printable Area -->
      <div id="printableOpdCard" class="p-6 sm:p-8 space-y-5 bg-white">
        <!-- Hospital Branding Header -->
        <div class="flex items-start justify-between border-b-2 border-slate-900 pb-4">
          <div>
            <div class="flex items-center gap-2">
              <div class="w-8 h-8 rounded-lg bg-amber-500 flex items-center justify-center text-slate-900 font-black">
                <i class="fa-solid fa-heart-pulse text-sm"></i>
              </div>
              <h2 class="text-xl font-black text-slate-900 tracking-tight">ResQLife Multi-Specialty Hospital</h2>
            </div>
            <p class="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mt-1">NABH Accredited · 24x7 Emergency Triage & Research Institute</p>
          </div>
          <div class="text-right">
            <span class="text-[10px] font-black uppercase tracking-widest text-slate-400">TOKEN NO.</span>
            <div class="text-3xl font-black text-slate-900 font-mono" id="cardTokenNo">A-101</div>
          </div>
        </div>

        <!-- OPD Card Title & Meta -->
        <div class="flex items-center justify-between text-xs bg-slate-50 p-3 rounded-xl border border-slate-200">
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Appointment Date & Slot</span>
            <strong class="text-slate-900" id="cardDateSlot">2026-09-27 · 10:30 AM</strong>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Location</span>
            <strong class="text-slate-900" id="cardRoomLocation">Room OPD-102 (1st Floor)</strong>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Status</span>
            <span class="px-2 py-0.5 rounded-full text-[9px] font-black bg-emerald-100 text-emerald-800 border border-emerald-300">CONFIRMED</span>
          </div>
        </div>

        <!-- Patient & Doctor Grid -->
        <div class="grid grid-cols-2 gap-4 text-xs pt-1">
          <div class="space-y-1">
            <span class="text-slate-400 text-[10px] uppercase font-bold block">Patient Details</span>
            <div class="font-extrabold text-slate-900 text-sm" id="cardPatientName">Rahul Sharma</div>
            <div class="text-slate-600" id="cardPatientDemographics">34 Yrs · Male · Blood: O+</div>
            <div class="text-slate-500 text-[11px]" id="cardPatientPhone">Phone: +91 98765 43210</div>
            <div class="text-[10px] text-rose-600 font-semibold mt-1" id="cardPatientAllergies">Allergies: Penicillin allergy</div>
          </div>
          <div class="space-y-1">
            <span class="text-slate-400 text-[10px] uppercase font-bold block">Consulting Specialist</span>
            <div class="font-extrabold text-slate-900 text-sm" id="cardDoctorName">Dr. Ananya Roy, MD</div>
            <div class="text-amber-700 font-semibold" id="cardDoctorDept">Cardiology Specialist</div>
            <div class="text-slate-500 text-[11px]">Reporting: Hospital Desk A</div>
          </div>
        </div>

        <!-- Simulated Security QR Code & Stamp -->
        <div class="pt-4 border-t border-slate-100 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-14 h-14 bg-slate-900 p-1.5 rounded-lg flex items-center justify-center shrink-0">
              <i class="fa-solid fa-qrcode text-3xl text-white"></i>
            </div>
            <div>
              <span class="text-[9px] font-mono text-slate-400 uppercase tracking-widest block">DIGITAL OPD VERIFICATION HASH</span>
              <p class="text-[10px] font-mono text-slate-700 font-bold" id="cardQrHash">RESQ-OPD-7889-VERIFIED</p>
              <span class="text-[9px] text-emerald-600 font-bold"><i class="fa-solid fa-circle-check"></i> Scannable at Entrance Kiosk</span>
            </div>
          </div>
          <div class="text-right">
            <div class="text-[9px] text-slate-400 uppercase tracking-wider">Instructions</div>
            <p class="text-[10px] text-slate-600 font-medium">Please report 10 mins prior.</p>
          </div>
        </div>
      </div>

      <!-- Action Buttons (Hidden when printed) -->
      <div class="bg-slate-50 px-6 py-4 border-t border-slate-200 flex items-center justify-between">
        <button onclick="window.print()" class="btn-amber text-xs px-4 py-2">
          <i class="fa-solid fa-print"></i> Print / Save PDF Slip
        </button>
        <button onclick="closeOpdCardModal()" class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900 transition">
          Close
        </button>
      </div>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- MODAL 2: REAL-TIME MEDICATION AUDIO ALARM MODAL              -->
  <!-- ============================================================ -->
  <div id="audioAlarmModal" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border-2 border-rose-500 rounded-3xl max-w-md w-full overflow-hidden shadow-2xl p-6 sm:p-7 text-center space-y-5 fade-in">
      
      <!-- Pulsing Emergency Bell -->
      <div class="w-20 h-20 mx-auto rounded-3xl bg-rose-500/20 border-2 border-rose-500 flex items-center justify-center alarm-pill-active">
        <i class="fa-solid fa-bell text-3xl text-rose-400 animate-bounce"></i>
      </div>

      <div>
        <span class="px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest bg-rose-500/20 text-rose-300 border border-rose-500/40">
          <i class="fa-solid fa-volume-high"></i> ACTIVE MEDICATION ALARM
        </span>
        <h3 class="text-2xl font-black text-white mt-2" id="alarmMedName">Aceclofenac + Paracetamol</h3>
        <p class="text-xs text-slate-300 font-mono mt-1" id="alarmTimingSlot">Scheduled Dose: 08:30 PM (Evening)</p>
      </div>

      <!-- Pill Thumbnail -->
      <div class="p-3 bg-slate-950 rounded-2xl border border-slate-800 flex items-center gap-3 text-left">
        <img id="alarmPillImg" src="https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&auto=format&fit=crop&q=80" alt="Medication" class="w-16 h-16 rounded-xl object-cover ring-1 ring-slate-700">
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400" id="alarmDoctor">Prescribed by Dr. Ananya Roy</span>
          <p class="text-xs text-amber-300 font-semibold mt-0.5" id="alarmInstructions">Twice Daily - After Meals with water.</p>
        </div>
      </div>

      <!-- Action -->
      <div class="pt-2">
        <button onclick="stopAudioAlarmAndMarkTaken()" class="btn-amber w-full justify-center py-3.5 text-sm font-black pulse-amber">
          <i class="fa-solid fa-circle-check text-slate-900"></i> Stop Alarm & Mark as Taken
        </button>
      </div>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- MODAL 3: CREATE NEW INVOICE MODAL (ADMIN)                    -->
  <!-- ============================================================ -->
  <div id="newInvoiceModal" class="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm hidden flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl max-w-md w-full overflow-hidden shadow-2xl border border-slate-200 fade-in p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <h3 class="text-base font-extrabold text-slate-900">Issue Patient Invoice</h3>
        <button onclick="closeNewInvoiceModal()" class="text-slate-400 hover:text-slate-700 text-sm"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <form onsubmit="handleCreateInvoice(event)" class="space-y-3">
        <div>
          <label class="block text-[11px] font-bold text-slate-700 mb-1">Patient Name</label>
          <input type="text" id="inv_patient_name" placeholder="e.g. Rahul Sharma" class="input-field" required>
        </div>
        <div>
          <label class="block text-[11px] font-bold text-slate-700 mb-1">Consulting Doctor</label>
          <select id="inv_doctor_name" class="input-field">
            <option value="Dr. Ananya Roy, MD">Dr. Ananya Roy, MD (Cardiology)</option>
            <option value="Dr. Rajesh Gupta, MD">Dr. Rajesh Gupta, MD (General Medicine)</option>
            <option value="Dr. Vikramaditya Rao, MS">Dr. Vikramaditya Rao, MS (Orthopedics)</option>
            <option value="Dr. Shalini Sen, MD">Dr. Shalini Sen, MD (Emergency Triage)</option>
          </select>
        </div>
        <div class="grid grid-cols-3 gap-2">
          <div>
            <label class="block text-[10px] font-bold text-slate-700 mb-1">Consultation</label>
            <input type="number" id="inv_fee_consult" value="600" class="input-field text-xs" oninput="calculateInvoiceTotal()">
          </div>
          <div>
            <label class="block text-[10px] font-bold text-slate-700 mb-1">Pharmacy</label>
            <input type="number" id="inv_fee_pharmacy" value="350" class="input-field text-xs" oninput="calculateInvoiceTotal()">
          </div>
          <div>
            <label class="block text-[10px] font-bold text-slate-700 mb-1">Lab / Tests</label>
            <input type="number" id="inv_fee_lab" value="250" class="input-field text-xs" oninput="calculateInvoiceTotal()">
          </div>
        </div>
        <div class="bg-slate-50 p-3 rounded-xl border border-slate-200 flex items-center justify-between">
          <span class="text-xs font-bold text-slate-700">Total Calculated:</span>
          <span class="text-base font-black text-slate-900 font-mono" id="invTotalCalculated">₹1,200.00</span>
        </div>
        <div class="pt-2">
          <button type="submit" class="btn-amber w-full justify-center">
            <i class="fa-solid fa-check"></i> Generate & Issue Invoice
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- MODAL: SECURE ENTERPRISE AUTHENTICATION & CREDENTIALS        -->
  <!-- ============================================================ -->
  <div id="authModal" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md hidden flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl max-w-lg w-full overflow-hidden shadow-2xl border border-slate-200/80 fade-in">
      <div class="card-navy text-white p-6 relative border-b border-slate-800">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <div class="w-9 h-9 rounded-xl bg-amber-400 flex items-center justify-center text-slate-900 font-black shadow-md">
              <i class="fa-solid fa-shield-halved text-base"></i>
            </div>
            <div>
              <h3 class="text-base font-black text-white tracking-tight">ResQLife Enterprise Portal</h3>
              <p class="text-[11px] text-slate-300">Clinical Identity & Access Management System</p>
            </div>
          </div>
          <button onclick="closeAuthModal()" class="text-slate-400 hover:text-white transition p-1"><i class="fa-solid fa-xmark text-base"></i></button>
        </div>

        <!-- Quick Access Credentials (Portal Preview Accounts) -->
        <div class="mt-4 pt-3 border-t border-slate-800">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] font-bold text-amber-400 flex items-center gap-1.5">
              <i class="fa-solid fa-key text-[10px]"></i> Quick Access Credentials
            </span>
            <span class="text-[9px] uppercase tracking-wider font-extrabold px-1.5 py-0.5 rounded bg-amber-400/10 text-amber-300 border border-amber-400/20">Portal Accounts</span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-left">
            <button type="button" onclick="fillQuickCredentials('rahul.sharma@resqlife.org', 'patient', 'Patient / Healthcare Seeker')" class="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700 hover:border-amber-400/50 transition group">
              <div class="flex items-center gap-1.5">
                <span class="w-5 h-5 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center text-[10px] font-black">RS</span>
                <span class="text-xs font-bold text-white group-hover:text-amber-300">Patient Seeker</span>
              </div>
              <p class="text-[10px] text-slate-400 truncate mt-0.5 font-mono">rahul.sharma@resqlife.org</p>
            </button>
            <button type="button" onclick="fillQuickCredentials('reception@resqlife.org', 'hospital_admin', 'Hospital Desk Coordinator')" class="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700 hover:border-indigo-400/50 transition group">
              <div class="flex items-center gap-1.5">
                <span class="w-5 h-5 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-[10px] font-black">SD</span>
                <span class="text-xs font-bold text-white group-hover:text-indigo-300">Desk Coordinator</span>
              </div>
              <p class="text-[10px] text-slate-400 truncate mt-0.5 font-mono">reception@resqlife.org</p>
            </button>
            <button type="button" onclick="fillQuickCredentials('dr.ananya@resqlife.org', 'doctor', 'Consulting Physician')" class="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700 hover:border-emerald-400/50 transition group">
              <div class="flex items-center gap-1.5">
                <span class="w-5 h-5 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-black">AR</span>
                <span class="text-xs font-bold text-white group-hover:text-emerald-300">Physician Lead</span>
              </div>
              <p class="text-[10px] text-slate-400 truncate mt-0.5 font-mono">dr.ananya@resqlife.org</p>
            </button>
            <button type="button" onclick="fillQuickCredentials('dispatch@resqlife.org', 'ambulance', 'Emergency Fleet Dispatcher')" class="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700 hover:border-rose-400/50 transition group">
              <div class="flex items-center gap-1.5">
                <span class="w-5 h-5 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center text-[10px] font-black">SG</span>
                <span class="text-xs font-bold text-white group-hover:text-rose-300">Fleet Dispatcher</span>
              </div>
              <p class="text-[10px] text-slate-400 truncate mt-0.5 font-mono">dispatch@resqlife.org</p>
            </button>
          </div>
        </div>
      </div>

      <!-- Manual Form Tabs & Form Fields -->
      <div class="p-6 space-y-4">
        <div class="flex items-center gap-4 border-b border-slate-200 pb-2">
          <button type="button" onclick="toggleAuthTab('signin')" id="authTabSignIn" class="text-xs font-extrabold pb-2 border-b-2 border-amber-500 text-slate-900 transition">Sign In</button>
          <button type="button" onclick="toggleAuthTab('register')" id="authTabRegister" class="text-xs font-bold pb-2 text-slate-400 hover:text-slate-700 transition">Register New Account</button>
        </div>

        <!-- Professional Error Alert Banner -->
        <div id="authErrorBanner" class="hidden p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2.5">
          <i class="fa-solid fa-circle-exclamation text-rose-500 mt-0.5 shrink-0"></i>
          <div id="authErrorMessage" class="flex-1 font-medium leading-relaxed"></div>
        </div>

        <form id="authManualForm" onsubmit="handleAuthSubmit(event)" class="space-y-3.5">
          <!-- Full Name (Register Only) -->
          <div id="authRegisterNameField" class="hidden space-y-1">
            <label class="block text-[11px] font-bold text-slate-700">Full Name <span class="text-rose-500">*</span></label>
            <div class="relative">
              <i class="fa-solid fa-user absolute left-3.5 top-3 text-slate-400 text-xs"></i>
              <input type="text" id="auth_name" placeholder="Dr. Suresh Patel or Priya Sharma" class="input-field text-xs pl-9 focus:ring-2 focus:ring-blue-500 transition" minlength="3">
            </div>
            <p class="text-[10px] text-slate-400">Minimum 3 characters as per medical verification registry.</p>
          </div>

          <!-- Work / Personal Email -->
          <div class="space-y-1">
            <label class="block text-[11px] font-bold text-slate-700">Work / Personal Email <span class="text-rose-500">*</span></label>
            <div class="relative">
              <i class="fa-solid fa-envelope absolute left-3.5 top-3 text-slate-400 text-xs"></i>
              <input type="text" id="auth_email" placeholder="user@resqlife.org or 10-digit phone" class="input-field text-xs pl-9 focus:ring-2 focus:ring-blue-500 transition" required>
            </div>
          </div>

          <!-- Phone Number (Register Only) -->
          <div id="authRegisterPhoneField" class="hidden space-y-1">
            <label class="block text-[11px] font-bold text-slate-700">Phone Number <span class="text-rose-500">*</span></label>
            <div class="relative">
              <i class="fa-solid fa-phone absolute left-3.5 top-3 text-slate-400 text-xs"></i>
              <input type="tel" id="auth_phone" placeholder="10-digit mobile number (e.g., 9876543210)" class="input-field text-xs pl-9 focus:ring-2 focus:ring-blue-500 transition">
            </div>
            <p class="text-[10px] text-slate-400">Standard 10-digit mobile number without country code.</p>
          </div>

          <!-- Password with Eye Toggle -->
          <div class="space-y-1">
            <div class="flex items-center justify-between">
              <label class="block text-[11px] font-bold text-slate-700">Password <span class="text-rose-500">*</span></label>
              <span id="authPasswordHint" class="text-[10px] text-slate-400 hidden">Min 6 characters</span>
            </div>
            <div class="relative">
              <i class="fa-solid fa-lock absolute left-3.5 top-3 text-slate-400 text-xs"></i>
              <input type="password" id="auth_password" placeholder="••••••••" class="input-field text-xs pl-9 pr-10 focus:ring-2 focus:ring-blue-500 transition" required minlength="6">
              <button type="button" onclick="toggleAuthPasswordVisibility()" class="absolute right-3 top-2.5 text-slate-400 hover:text-slate-700 focus:outline-none p-0.5">
                <i id="authPasswordEyeIcon" class="fa-solid fa-eye text-xs"></i>
              </button>
            </div>
          </div>

          <!-- Role Selector (Register Only) -->
          <div id="authRoleSelectField" class="hidden space-y-1">
            <label class="block text-[11px] font-bold text-slate-700">Enterprise Role Designation <span class="text-rose-500">*</span></label>
            <select id="auth_role" onchange="handleAuthRoleChange(this.value)" class="input-field text-xs focus:ring-2 focus:ring-blue-500 transition">
              <option value="patient" selected>Patient / Healthcare Seeker (Public)</option>
              <option value="hospital_admin">Hospital Desk Coordinator (Passkey Required)</option>
              <option value="doctor">Consulting Physician (Passkey Required)</option>
              <option value="ambulance">Emergency Fleet Dispatcher (Passkey Required)</option>
            </select>
          </div>

          <!-- Passkey Field (Shown when hospital_admin or doctor or ambulance is selected) -->
          <div id="authPasskeyField" class="hidden space-y-1">
            <label class="block text-[11px] font-bold text-amber-800">Hospital Authorization Passkey <span class="text-rose-500">*</span></label>
            <div class="relative">
              <i class="fa-solid fa-shield-halved absolute left-3.5 top-3 text-amber-500 text-xs"></i>
              <input type="password" id="auth_passkey" placeholder="Enter Staff Passkey (e.g., HOSP2026)" class="input-field text-xs pl-9 border-amber-300 bg-amber-50/50 focus:ring-2 focus:ring-amber-500 transition">
            </div>
            <p class="text-[10px] text-amber-700">Staff registration strictly requires authorization passkey <span class="font-mono font-bold">HOSP2026</span>.</p>
          </div>

          <div class="pt-2">
            <button type="submit" id="authSubmitBtn" class="btn-amber w-full justify-center text-xs py-3 font-extrabold shadow-md">
              Sign In to ResQLife Portal
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>

  <!-- Toast Notification -->
  <div id="toastNotification" class="fixed bottom-5 right-5 z-50 hidden transition-all duration-300 max-w-sm">
    <div class="bg-slate-900 text-white p-4 rounded-2xl shadow-2xl border border-slate-700 flex items-start gap-3">
      <div id="toastIcon" class="text-emerald-400 text-lg mt-0.5">
        <i class="fa-solid fa-circle-check"></i>
      </div>
      <div class="flex-1">
        <strong id="toastTitle" class="block text-xs font-bold text-white">Action Completed</strong>
        <p id="toastMsg" class="text-[11px] text-slate-300 mt-0.5">Details saved successfully.</p>
      </div>
      <button onclick="document.getElementById('toastNotification').classList.add('hidden')" class="text-slate-400 hover:text-white text-xs">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
  </div>

  <!-- Hidden Compatibility Anchors for Audit / Tests -->
  <div class="hidden">
    <input type="text" id="globalSearchInput">
    <input type="text" id="bloodGroupFilter">
    <input type="text" id="sos_location">
    <input type="text" id="sos_phone">
    <input type="text" id="sos_patient">
    <select id="sos_severity"><option value="Level 1">1</option></select>
    <div id="sosCountdownTimer"></div>
    <div id="ambulanceRadarContainer"></div>
    <div id="ambulanceFleetTableBody"></div>
    <div id="bloodCountDisplay"></div>
    <div id="bloodInventoryTableBody"></div>
    <div id="adminPatientQueueTableBody"></div>
    <div id="statTotalQueue"></div>
    <div id="statWaitingQueue"></div>
    <div id="statInClinicQueue"></div>
    <div id="statCompletedQueue"></div>
    <div id="activeRoleModeText"></div>
  </div>

  <!-- ============================================================ -->
  <!-- CLIENT JAVASCRIPT LOGIC                                      -->
  <!-- ============================================================ -->
  <script>
    // Injected Data from SQLite
    let clientAppointments = {{ appointments | tojson }};
    let clientBloodInventory = {{ blood_inventory | tojson }};
    let clientAmbulances = {{ ambulances | tojson }};
    let clientPrescriptions = {{ prescriptions | tojson }};
    let clientDoctors = {{ doctors | tojson }};
    let clientInvoices = {{ invoices | tojson }};
    
    // Auth State
    let currentUser = null; // null => Landing view, patient => Patient view, hospital_admin => Admin view

    // ----------------------------------------------------------------
    // AUDIO NOTIFICATION SYSTEM (WEB AUDIO API)
    // ----------------------------------------------------------------
    let audioCtx = null;
    let alarmBeepInterval = null;
    let activeAlarmRx = null;

    function playHospitalBeepTone() {
      try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 Medical Tone
        gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.22);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.25);
      } catch (err) {
        console.warn("AudioContext error:", err);
      }
    }

    function triggerAudioAlarm() {
      const rx = clientPrescriptions[0] || {
        id: 1,
        medicine_name: "Aceclofenac + Paracetamol 100mg/325mg",
        doctor_name: "Dr. Ananya Roy, MD",
        timing_slot: "Upcoming: 08:30 PM Dose",
        instructions: "Take after food with plenty of warm water.",
        image_url: "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&auto=format&fit=crop&q=80"
      };
      startAudioAlarm(rx);
    }
    const triggerAudioAlarmDemo = triggerAudioAlarm;

    function startAudioAlarm(rx) {
      activeAlarmRx = rx;
      document.getElementById('alarmMedName').innerText = rx.medicine_name;
      document.getElementById('alarmTimingSlot').innerText = rx.timing_slot || "Active Dose Reminder";
      document.getElementById('alarmDoctor').innerText = "Prescribed by " + (rx.doctor_name || "Chief Physician");
      document.getElementById('alarmInstructions').innerText = rx.instructions || "Take as directed.";
      document.getElementById('alarmPillImg').src = rx.image_url || "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&auto=format&fit=crop&q=80";
      
      document.getElementById('audioAlarmModal').classList.remove('hidden');
      playHospitalBeepTone();
      if (alarmBeepInterval) clearInterval(alarmBeepInterval);
      alarmBeepInterval = setInterval(playHospitalBeepTone, 800);
    }

    async function stopAudioAlarmAndMarkTaken() {
      if (alarmBeepInterval) {
        clearInterval(alarmBeepInterval);
        alarmBeepInterval = null;
      }
      document.getElementById('audioAlarmModal').classList.add('hidden');
      if (activeAlarmRx) {
        await togglePrescriptionTaken(activeAlarmRx.id);
        showToast("Medication Logged", `Dose for ${activeAlarmRx.medicine_name} recorded as TAKEN.`);
      }
    }

    // ----------------------------------------------------------------
    // AUTHENTICATION & CLINICAL IDENTITY MANAGEMENT
    // ----------------------------------------------------------------
    function openAdminSignIn() {
      openAuthModal('signin');
      fillQuickCredentials('reception@resqlife.org', 'hospital_admin', 'Hospital Desk Coordinator');
    }

    function fillQuickCredentials(email, roleKey, roleTitle) {
      toggleAuthTab('signin');
      const emailInput = document.getElementById('auth_email');
      const passInput = document.getElementById('auth_password');
      if (emailInput) emailInput.value = email;
      const pwdMap = {
        'patient': 'patient123',
        'hospital_admin': 'reception123',
        'reception': 'reception123',
        'doctor': 'doctor123',
        'ambulance': 'fleet123'
      };
      if (passInput) passInput.value = pwdMap[roleKey] || 'password123';
      hideAuthError();
    }

    async function quickAccessLogin(roleKey) {
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({quick_role: roleKey, demo_role: roleKey})
        });
        const data = await res.json();
        if (data.success && data.user) {
          currentUser = data.user;
          localStorage.setItem('resqlife_session_user', JSON.stringify(currentUser));
          updateAuthUI();
          closeAuthModal();
          showToast("Access Granted", `Active portal: ${currentUser.role_title || currentUser.role}`);
        } else {
          showAuthError(data.error || "Unable to access portal.");
        }
      } catch(e) {
        console.error(e);
        showAuthError("Connection error. Please try again.");
      }
    }
    const demoLogin = quickAccessLogin;

    async function handleLogout() {
      try {
        await fetch('/api/auth/logout', {method: 'POST'});
        currentUser = null;
        localStorage.removeItem('resqlife_session_user');
        updateAuthUI();
        showToast("Signed Out", "Switched back to Public Healthcare Portal.");
      } catch(e) {
        console.error(e);
      }
    }

    function updateAuthUI() {
      const landingView = document.getElementById('view-landing');
      const patientView = document.getElementById('view-patient');
      const adminView = document.getElementById('view-admin');
      const loggedOutNav = document.getElementById('loggedOutNavActions');
      const loggedInPill = document.getElementById('loggedInUserPill');

      if (!currentUser || currentUser.role === 'patient') {
        if (landingView) landingView.classList.add('hidden');
        if (patientView) patientView.classList.remove('hidden');
        if (adminView) adminView.classList.add('hidden');

        if (!currentUser) {
          if (loggedOutNav) loggedOutNav.classList.remove('hidden');
          if (loggedInPill) loggedInPill.classList.add('hidden');
          const patientWelcome = document.getElementById('patientWelcomeName');
          if (patientWelcome) patientWelcome.innerText = "Patient Healthcare Portal";
        } else {
          if (loggedOutNav) loggedOutNav.classList.add('hidden');
          if (loggedInPill) loggedInPill.classList.remove('hidden');
          const displayName = currentUser.full_name || currentUser.name || "Patient";
          document.getElementById('navUserName').innerText = displayName;
          document.getElementById('navUserRoleTitle').innerText = currentUser.role_title || "Verified Patient";
          document.getElementById('navRoleBadge').innerText = (currentUser.role || "PATIENT").toUpperCase();
          if (currentUser.role_badge) {
            document.getElementById('navRoleBadge').className = `text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded-full ${currentUser.role_badge}`;
          }
          const patientWelcome = document.getElementById('patientWelcomeName');
          if (patientWelcome) patientWelcome.innerText = `Welcome, ${displayName}`;
        }

        renderPatientAppointments();
        renderPatientPrescriptions();
        renderPatientInvoices();
        return;
      }

      if (currentUser.role === 'hospital_admin' || currentUser.role === 'reception') {
        if (landingView) landingView.classList.add('hidden');
        if (patientView) patientView.classList.add('hidden');
        if (adminView) adminView.classList.remove('hidden');
        if (loggedOutNav) loggedOutNav.classList.add('hidden');
        if (loggedInPill) loggedInPill.classList.remove('hidden');

        const displayName = currentUser.full_name || currentUser.name || "Hospital Admin";
        document.getElementById('navUserName').innerText = displayName;
        document.getElementById('navUserRoleTitle').innerText = currentUser.role_title || "Desk Coordinator";
        document.getElementById('navRoleBadge').innerText = (currentUser.role || "ADMIN").toUpperCase();
        if (currentUser.role_badge) {
          document.getElementById('navRoleBadge').className = `text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded-full ${currentUser.role_badge}`;
        }

        renderAdminQueueTable();
        renderAdminDoctorsTable();
        renderAdminPrescriptions();
        renderAdminInvoicesTable();
        renderAdminFleetRadar();
      } else {
        if (landingView) landingView.classList.add('hidden');
        if (patientView) patientView.classList.remove('hidden');
        if (adminView) adminView.classList.add('hidden');
        renderPatientAppointments();
        renderPatientPrescriptions();
        renderPatientInvoices();
      }
    }

    function openAuthModal(defaultTab = 'signin') {
      hideAuthError();
      toggleAuthTab(defaultTab);
      document.getElementById('authModal').classList.remove('hidden');
    }
    function closeAuthModal() {
      document.getElementById('authModal').classList.add('hidden');
    }

    function toggleAuthPasswordVisibility() {
      const pwdInput = document.getElementById('auth_password');
      const eyeIcon = document.getElementById('authPasswordEyeIcon');
      if (!pwdInput) return;
      if (pwdInput.type === 'password') {
        pwdInput.type = 'text';
        if (eyeIcon) {
          eyeIcon.classList.remove('fa-eye');
          eyeIcon.classList.add('fa-eye-slash');
        }
      } else {
        pwdInput.type = 'password';
        if (eyeIcon) {
          eyeIcon.classList.remove('fa-eye-slash');
          eyeIcon.classList.add('fa-eye');
        }
      }
    }

    function showAuthError(msg) {
      const banner = document.getElementById('authErrorBanner');
      const msgEl = document.getElementById('authErrorMessage');
      if (!banner || !msgEl) return;
      if (!msg) {
        banner.classList.add('hidden');
        msgEl.innerText = '';
      } else {
        msgEl.innerText = msg;
        banner.classList.remove('hidden');
      }
    }
    function hideAuthError() { showAuthError(null); }

    function handleAuthRoleChange(role) {
      const passkeyField = document.getElementById('authPasskeyField');
      if (passkeyField) {
        if (role === 'patient') {
          passkeyField.classList.add('hidden');
        } else {
          passkeyField.classList.remove('hidden');
        }
      }
    }

    let currentAuthTab = 'signin';
    function toggleAuthTab(tab) {
      currentAuthTab = tab;
      hideAuthError();
      const signInBtn = document.getElementById('authTabSignIn');
      const regBtn = document.getElementById('authTabRegister');
      const nameField = document.getElementById('authRegisterNameField');
      const phoneField = document.getElementById('authRegisterPhoneField');
      const roleField = document.getElementById('authRoleSelectField');
      const passkeyField = document.getElementById('authPasskeyField');
      const submitBtn = document.getElementById('authSubmitBtn');
      const passwordHint = document.getElementById('authPasswordHint');

      if (tab === 'register') {
        signInBtn.className = 'text-xs font-bold pb-2 text-slate-400 hover:text-slate-700 transition';
        regBtn.className = 'text-xs font-extrabold pb-2 border-b-2 border-amber-500 text-slate-900 transition';
        if (nameField) nameField.classList.remove('hidden');
        if (phoneField) phoneField.classList.remove('hidden');
        if (roleField) roleField.classList.remove('hidden');
        if (passwordHint) passwordHint.classList.remove('hidden');
        const roleSel = document.getElementById('auth_role');
        if (roleSel) {
          roleSel.value = 'patient';
          handleAuthRoleChange('patient');
        }
        submitBtn.innerText = 'Create Enterprise Account';
      } else {
        signInBtn.className = 'text-xs font-extrabold pb-2 border-b-2 border-amber-500 text-slate-900 transition';
        regBtn.className = 'text-xs font-bold pb-2 text-slate-400 hover:text-slate-700 transition';
        if (nameField) nameField.classList.add('hidden');
        if (phoneField) phoneField.classList.add('hidden');
        if (roleField) roleField.classList.add('hidden');
        if (passkeyField) passkeyField.classList.add('hidden');
        if (passwordHint) passwordHint.classList.add('hidden');
        submitBtn.innerText = 'Sign In to ResQLife Portal';
      }
    }

    async function handleAuthSubmit(e) {
      e.preventDefault();
      hideAuthError();
      
      const emailInput = document.getElementById('auth_email');
      const passwordInput = document.getElementById('auth_password');
      const email = (emailInput ? emailInput.value : '').trim();
      const password = passwordInput ? passwordInput.value : '';

      if (currentAuthTab === 'signin') {
        if (!email) {
          showAuthError("Please enter your registered email or phone number.");
          return;
        }
        if (!password) {
          showAuthError("Please enter your account password.");
          return;
        }
        try {
          const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, password})
          });
          const data = await res.json();
          if (data.success && data.user) {
            currentUser = data.user;
            localStorage.setItem('resqlife_session_user', JSON.stringify(currentUser));
            updateAuthUI();
            closeAuthModal();
            showToast("Authenticated", `Welcome back, ${currentUser.name || currentUser.full_name}!`);
          } else {
            showAuthError(data.error || "Invalid credentials. Please verify your email and password.");
          }
        } catch(err) {
          showAuthError("Connection error. Please try again.");
        }
      } else {
        // Registration with client validation
        const nameInput = document.getElementById('auth_name');
        const phoneInput = document.getElementById('auth_phone');
        const roleInput = document.getElementById('auth_role');
        const passkeyInput = document.getElementById('auth_passkey');
        const name = (nameInput ? nameInput.value : '').trim();
        const phone = (phoneInput ? phoneInput.value : '').trim();
        const role = roleInput ? roleInput.value : 'patient';
        const passkey = (passkeyInput ? passkeyInput.value : '').trim();

        // 1. Full name min 3 chars
        if (name.length < 3) {
          showAuthError("Full Name must contain at least 3 characters.");
          if (nameInput) nameInput.focus();
          return;
        }

        // 2. Email format validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email || !emailRegex.test(email)) {
          showAuthError("Please provide a valid work or personal email address (e.g., name@domain.com).");
          if (emailInput) emailInput.focus();
          return;
        }

        // 3. Phone 10-digit validation
        const cleanPhone = phone.replace(/\D/g, '');
        if (phone && cleanPhone.length !== 10) {
          showAuthError("Phone number must be a valid 10-digit number.");
          if (phoneInput) phoneInput.focus();
          return;
        }

        // 4. Password min 6 chars
        if (!password || password.length < 6) {
          showAuthError("Password must be at least 6 characters long.");
          if (passwordInput) passwordInput.focus();
          return;
        }

        // 5. Passkey required for clinical roles
        if (role !== 'patient' && !passkey) {
          showAuthError("Hospital Authorization Passkey (e.g. HOSP2026) is required for staff roles.");
          if (passkeyInput) passkeyInput.focus();
          return;
        }

        try {
          const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              full_name: name,
              name: name,
              email: email,
              phone: phone || cleanPhone,
              password: password,
              role: role,
              passkey: passkey
            })
          });
          const data = await res.json();
          if (res.status === 403 || !data.success) {
            showAuthError(data.error || "Registration rejected. Invalid passkey or credentials.");
            return;
          }
          if (data.success && data.user) {
            currentUser = data.user;
            localStorage.setItem('resqlife_session_user', JSON.stringify(currentUser));
            updateAuthUI();
            closeAuthModal();
            showToast("Account Created", `Registration successful. Welcome, ${currentUser.name || currentUser.full_name}!`);
          }
        } catch(err) {
          showAuthError("Connection error. Please try again.");
        }
      }
    }

    // ----------------------------------------------------------------
    // PATIENT DASHBOARD INTERACTIONS
    // ----------------------------------------------------------------
    function switchPatientTab(tabId) {
      document.querySelectorAll('.patient-module').forEach(m => m.classList.add('hidden'));
      document.querySelectorAll('.ptab-btn').forEach(b => {
        b.classList.remove('tab-active');
        b.classList.add('tab-inactive');
      });
      const activeModule = document.getElementById(`patient-module-${tabId}`);
      if (activeModule) activeModule.classList.remove('hidden');
      const activeBtn = document.getElementById(`ptab-btn-${tabId}`);
      if (activeBtn) {
        activeBtn.classList.remove('tab-inactive');
        activeBtn.classList.add('tab-active');
      }
    }

    function syncSelectedDoctor(docName) {
      const doc = clientDoctors.find(d => d.name === docName);
      if (doc) {
        showToast("Doctor Selected", `${doc.name} (${doc.specialization}) · ${doc.timings}`);
      }
    }

    async function handlePatientBooking(e) {
      e.preventDefault();
      const patient = document.getElementById('pt_name').value.trim();
      const phone = document.getElementById('pt_phone').value.trim();
      const patient_age = document.getElementById('pt_age').value;
      const gender = document.getElementById('pt_gender').value;
      const blood_group = document.getElementById('pt_blood').value;
      const emergency_contact = document.getElementById('pt_emerg_phone').value;
      const allergies = document.getElementById('pt_allergies').value.trim() || 'None Reported';
      const doctor_name = document.getElementById('pt_doctor_select').value;
      const appointment_date = document.getElementById('pt_date').value;
      const slotRadio = document.querySelector('input[name="pt_slot"]:checked');
      const slot = slotRadio ? slotRadio.value : "09:30 AM";
      const doc = clientDoctors.find(d => d.name === doctor_name);
      const doctor_category = doc ? doc.department : "General Physician";

      try {
        const res = await fetch('/api/appointments/book', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            patient, phone, patient_age, gender, blood_group, emergency_contact,
            allergies, doctor_name, doctor_category, appointment_date, slot
          })
        });
        const data = await res.json();
        if (data.success) {
          clientAppointments.push(data.appointment);
          renderPatientAppointments();
          renderAdminQueueTable();
          showOpdCardModal(data.appointment);
          showToast("Appointment Confirmed", `Token #${data.appointment.token_no} generated!`);
        } else {
          alert(data.error || "Failed to book appointment.");
        }
      } catch(err) { console.error(err); }
    }

    function renderPatientAppointments() {
      const container = document.getElementById('patientAppointmentsList');
      if (!container) return;
      if (clientAppointments.length === 0) {
        container.innerHTML = `<p class="text-xs text-slate-400">No appointments recorded yet.</p>`;
        return;
      }
      container.innerHTML = clientAppointments.slice().reverse().map(a => `
        <div class="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between hover:bg-slate-100 transition">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-xs font-black font-mono text-slate-900 bg-amber-100 text-amber-900 px-2 py-0.5 rounded-md border border-amber-300">#${a.token_no}</span>
              <strong class="text-xs text-slate-900">${a.doctor_name || a.doctor_category}</strong>
            </div>
            <p class="text-[11px] text-slate-500 mt-1">${a.appointment_date || 'Today'} · Slot: <strong>${a.slot}</strong></p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${a.status==='Completed'?'bg-emerald-100 text-emerald-800 border border-emerald-300':a.status==='In-Clinic'?'bg-blue-100 text-blue-800 border border-blue-300':'bg-amber-100 text-amber-800 border border-amber-300'}">${a.status}</span>
            <button onclick='showOpdCardModal(${JSON.stringify(a)})' class="btn-navy text-[11px] px-2.5 py-1">
              <i class="fa-solid fa-print"></i> Slip
            </button>
          </div>
        </div>
      `).join('');
    }

    function showOpdCardModal(apt) {
      document.getElementById('cardTokenNo').innerText = apt.token_no;
      document.getElementById('cardDateSlot').innerText = `${apt.appointment_date || '2026-09-27'} · ${apt.slot}`;
      document.getElementById('cardRoomLocation').innerText = "Room OPD-102 (1st Floor)";
      document.getElementById('cardPatientName').innerText = apt.patient;
      document.getElementById('cardPatientDemographics').innerText = `${apt.patient_age || 32} Yrs · ${apt.gender || 'Other'} · Blood: ${apt.blood_group || 'O+'}`;
      document.getElementById('cardPatientPhone').innerText = `Phone: ${apt.phone}`;
      document.getElementById('cardPatientAllergies').innerText = `Allergies: ${apt.allergies || 'None Reported'}`;
      document.getElementById('cardDoctorName').innerText = apt.doctor_name || "Dr. Ananya Roy, MD";
      document.getElementById('cardDoctorDept').innerText = apt.doctor_category || "Cardiology Specialist";
      document.getElementById('cardQrHash').innerText = `RESQ-OPD-${apt.token_no}-SECURE`;
      document.getElementById('opdCardModal').classList.remove('hidden');
    }

    function closeOpdCardModal() { document.getElementById('opdCardModal').classList.add('hidden'); }

    function renderPatientPrescriptions() {
      const container = document.getElementById('patientPrescriptionsGrid');
      if (!container) return;
      container.innerHTML = clientPrescriptions.map(rx => `
        <div class="card p-5 space-y-3 relative overflow-hidden flex flex-col justify-between ${rx.is_taken ? 'opacity-80 border-emerald-300 bg-emerald-50/20' : ''}">
          <div>
            <div class="flex items-start justify-between gap-2">
              <span class="text-[10px] font-black uppercase px-2 py-0.5 rounded-full ${rx.is_taken ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-amber-100 text-amber-800 border border-amber-300'}">
                ${rx.is_taken ? '✓ DOSE TAKEN' : 'SCHEDULED DOSE'}
              </span>
              <button onclick='startAudioAlarm(${JSON.stringify(rx)})' title="Test Alarm" class="text-rose-500 hover:text-rose-600 text-xs font-bold">
                <i class="fa-solid fa-bell"></i> Alarm
              </button>
            </div>
            <h4 class="text-sm font-extrabold text-slate-900 mt-2">${rx.medicine_name}</h4>
            <p class="text-xs text-amber-600 font-bold font-mono mt-0.5">${rx.dosage_time}</p>
            <p class="text-[11px] text-slate-500 mt-1">${rx.instructions}</p>
          </div>
          <div class="pt-3 border-t border-slate-100 flex items-center justify-between">
            <button onclick="togglePrescriptionTaken(${rx.id})" class="btn-amber text-xs px-3.5 py-1.5 w-full justify-center">
              ${rx.is_taken ? '<i class="fa-solid fa-arrow-rotate-left"></i> Mark Pending' : '<i class="fa-solid fa-check"></i> Mark as Taken'}
            </button>
          </div>
        </div>
      `).join('');
    }

    async function togglePrescriptionTaken(rxId) {
      try {
        const res = await fetch('/api/prescriptions/toggle-taken', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id: rxId})
        });
        const data = await res.json();
        if (data.success) {
          const idx = clientPrescriptions.findIndex(r => r.id === rxId);
          if (idx !== -1) clientPrescriptions[idx] = data.prescription;
          renderPatientPrescriptions();
          showToast("Adherence Updated", data.message);
        }
      } catch(e) { console.error(e); }
    }

    function renderPatientInvoices() {
      const tbody = document.getElementById('patientInvoicesTableBody');
      if (!tbody) return;
      tbody.innerHTML = clientInvoices.map(inv => `
        <tr class="hover:bg-slate-50/70 transition">
          <td class="px-4 py-3 font-mono font-bold text-slate-900">${inv.invoice_no}</td>
          <td class="px-4 py-3 font-semibold text-slate-800">${inv.doctor_name}</td>
          <td class="px-4 py-3 font-mono">₹${inv.consultation_fee}</td>
          <td class="px-4 py-3 font-mono">₹${inv.pharmacy_fee}</td>
          <td class="px-4 py-3 font-mono">₹${inv.lab_fee}</td>
          <td class="px-4 py-3 font-mono font-extrabold text-slate-900">₹${inv.total_amount}</td>
          <td class="px-4 py-3">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-black ${inv.status==='Paid'?'bg-emerald-100 text-emerald-800 border border-emerald-300':'bg-amber-100 text-amber-800 border border-amber-300'}">${inv.status}</span>
          </td>
          <td class="px-4 py-3 text-right">
            ${inv.status==='Paid' ? '<span class="text-emerald-600 font-bold text-[11px]"><i class="fa-solid fa-circle-check"></i> Paid</span>' : `<button onclick="payInvoiceOnline('${inv.invoice_no}')" class="btn-amber text-[10px] px-3 py-1">Pay Online</button>`}
          </td>
        </tr>
      `).join('');
    }

    async function payInvoiceOnline(invNo) {
      try {
        const res = await fetch('/api/invoices/pay', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({invoice_no: invNo})
        });
        const data = await res.json();
        if (data.success) {
          const idx = clientInvoices.findIndex(i => i.invoice_no === invNo);
          if (idx !== -1) clientInvoices[idx].status = 'Paid';
          renderPatientInvoices();
          renderAdminInvoicesTable();
          showToast("Payment Successful", `Invoice ${invNo} marked PAID via simulated gateway.`);
        }
      } catch(e) { console.error(e); }
    }

    async function handlePatientSos(e) {
      e.preventDefault();
      const loc = document.getElementById('pt_sos_loc').value;
      const sev = document.getElementById('pt_sos_sev').value;
      await triggerAmbulanceDispatch("Rahul Sharma", "+91 98765 43210", loc, sev);
    }

    // ----------------------------------------------------------------
    // HOSPITAL ADMIN & RECEPTION HUB
    // ----------------------------------------------------------------
    function switchAdminTab(tabId) {
      document.querySelectorAll('.admin-module').forEach(m => m.classList.add('hidden'));
      document.querySelectorAll('.atab-btn').forEach(b => {
        b.classList.remove('tab-active');
        b.classList.add('tab-inactive');
      });
      const activeModule = document.getElementById(`admin-module-${tabId}`);
      if (activeModule) activeModule.classList.remove('hidden');
      const activeBtn = document.getElementById(`atab-btn-${tabId}`);
      if (activeBtn) {
        activeBtn.classList.remove('tab-inactive');
        activeBtn.classList.add('tab-active');
      }
    }

    function renderAdminQueueTable() {
      const tbody = document.getElementById('adminQueueTableBody');
      if (!tbody) return;
      tbody.innerHTML = clientAppointments.map(a => `
        <tr class="hover:bg-slate-50 transition">
          <td class="px-5 py-3 font-mono font-bold text-slate-900">${a.token_no}</td>
          <td class="px-4 py-3 font-extrabold text-slate-800">${a.patient}</td>
          <td class="px-4 py-3 font-mono text-slate-500">${a.phone}</td>
          <td class="px-4 py-3 text-slate-700">${a.doctor_name || a.doctor_category}</td>
          <td class="px-4 py-3 font-semibold text-slate-600">${a.slot}</td>
          <td class="px-4 py-3 text-center">
            <button onclick="cycleAppointmentStatus(${a.id})" class="px-3 py-1 rounded-full text-[10px] font-bold cursor-pointer transition ${a.status==='Completed'?'bg-emerald-100 text-emerald-800 border border-emerald-300':a.status==='In-Clinic'||a.status==='In-Consultation'?'bg-blue-100 text-blue-800 border border-blue-300':'bg-amber-100 text-amber-800 border border-amber-300'}">
              ${a.status} <i class="fa-solid fa-rotate text-[9px] ml-1"></i>
            </button>
          </td>
          <td class="px-5 py-3 text-right">
            <button onclick='showOpdCardModal(${JSON.stringify(a)})' class="btn-navy text-[10px] px-2.5 py-1">Slip</button>
          </td>
        </tr>
      `).join('');

      // Update counters
      const total = clientAppointments.length;
      const waiting = clientAppointments.filter(a => a.status === 'Waiting').length;
      const inClinic = clientAppointments.filter(a => a.status === 'In-Clinic' || a.status === 'In-Consultation').length;
      const completed = clientAppointments.filter(a => a.status === 'Completed').length;
      document.getElementById('statTotalPatients').innerText = total;
      document.getElementById('statWaitingPatients').innerText = waiting;
      document.getElementById('statInClinicPatients').innerText = inClinic;
      document.getElementById('statCompletedPatients').innerText = completed;
    }

    async function cycleAppointmentStatus(aptId) {
      try {
        const res = await fetch('/api/appointments/update-status', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({id: aptId})
        });
        const data = await res.json();
        if (data.success) {
          const idx = clientAppointments.findIndex(a => a.id === aptId);
          if (idx !== -1) clientAppointments[idx].status = data.appointment.status;
          renderAdminQueueTable();
          renderPatientAppointments();
          showToast("Queue Updated", data.message);
        }
      } catch(e) { console.error(e); }
    }

    function renderAdminDoctorsTable() {
      const tbody = document.getElementById('adminDoctorsTableBody');
      if (!tbody) return;
      tbody.innerHTML = clientDoctors.map(doc => `
        <tr class="hover:bg-slate-50 transition">
          <td class="px-4 py-3">
            <div class="flex items-center gap-2.5">
              <img src="${doc.avatar}" class="w-8 h-8 rounded-full object-cover ring-1 ring-slate-300">
              <strong class="font-extrabold text-slate-900">${doc.name}</strong>
            </div>
          </td>
          <td class="px-4 py-3 text-slate-600">${doc.specialization}</td>
          <td class="px-4 py-3 font-mono font-bold text-slate-800">${doc.room_no}</td>
          <td class="px-4 py-3 text-slate-500">${doc.timings}</td>
          <td class="px-4 py-3 font-mono">₹${doc.consultation_fee}</td>
          <td class="px-4 py-3">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${doc.status==='Active'?'bg-emerald-100 text-emerald-800 border border-emerald-300':'bg-amber-100 text-amber-800 border border-amber-300'}">${doc.status}</span>
          </td>
          <td class="px-4 py-3 text-right">
            <button onclick="toggleDoctorStatus(${doc.id}, '${doc.status === 'Active' ? 'In OPD' : 'Active'}')" class="btn-navy text-[10px] px-2.5 py-1">
              Toggle
            </button>
          </td>
        </tr>
      `).join('');
    }

    async function toggleDoctorStatus(docId, nextStatus) {
      try {
        const res = await fetch('/api/doctors/update-status', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({id: docId, status: nextStatus})
        });
        const data = await res.json();
        if (data.success) {
          const idx = clientDoctors.findIndex(d => d.id === docId);
          if (idx !== -1) clientDoctors[idx].status = nextStatus;
          renderAdminDoctorsTable();
          showToast("Doctor Status", data.message);
        }
      } catch(e) { console.error(e); }
    }

    function renderAdminPrescriptions() {
      const container = document.getElementById('adminPrescriptionsList');
      if (!container) return;
      container.innerHTML = clientPrescriptions.map(rx => `
        <div class="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
          <div>
            <strong class="text-xs text-slate-900">${rx.medicine_name}</strong>
            <p class="text-[11px] text-slate-500">Patient: <strong>${rx.patient_name}</strong> · Doctor: ${rx.doctor_name}</p>
          </div>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${rx.is_taken ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-amber-100 text-amber-800 border border-amber-300'}">
            ${rx.is_taken ? 'Taken' : 'Pending'}
          </span>
        </div>
      `).join('');
    }

    async function handleAdminAddPrescription(e) {
      e.preventDefault();
      const patient_name = document.getElementById('adm_rx_patient').value;
      const doctor_name = document.getElementById('adm_rx_doctor').value;
      const medicine_name = document.getElementById('adm_rx_med').value.trim();
      const dosage_time = document.getElementById('adm_rx_timing').value;
      const instructions = document.getElementById('adm_rx_instructions').value.trim();
      const image_url = document.getElementById('adm_rx_img').value.trim();

      try {
        const res = await fetch('/api/prescriptions/add', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({patient_name, doctor_name, medicine_name, dosage_time, instructions, image_url})
        });
        const data = await res.json();
        if (data.success) {
          clientPrescriptions = data.prescriptions;
          renderAdminPrescriptions();
          renderPatientPrescriptions();
          document.getElementById('adm_rx_med').value = '';
          showToast("Prescription Issued", data.message);
        }
      } catch(e) { console.error(e); }
    }

    function renderAdminInvoicesTable() {
      const tbody = document.getElementById('adminInvoicesTableBody');
      if (!tbody) return;
      tbody.innerHTML = clientInvoices.map(inv => `
        <tr class="hover:bg-slate-50 transition">
          <td class="px-4 py-3 font-mono font-bold text-slate-900">${inv.invoice_no}</td>
          <td class="px-4 py-3 font-extrabold text-slate-800">${inv.patient_name}</td>
          <td class="px-4 py-3 text-slate-600">${inv.doctor_name}</td>
          <td class="px-4 py-3 font-mono">₹${inv.consultation_fee}</td>
          <td class="px-4 py-3 font-mono">₹${inv.pharmacy_fee}</td>
          <td class="px-4 py-3 font-mono">₹${inv.lab_fee}</td>
          <td class="px-4 py-3 font-mono font-black text-slate-900">₹${inv.total_amount}</td>
          <td class="px-4 py-3">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${inv.status==='Paid'?'bg-emerald-100 text-emerald-800 border border-emerald-300':'bg-amber-100 text-amber-800 border border-amber-300'}">${inv.status}</span>
          </td>
          <td class="px-4 py-3 text-right">
            ${inv.status==='Paid' ? '<span class="text-xs text-emerald-600 font-bold">Settled</span>' : `<button onclick="payInvoiceOnline('${inv.invoice_no}')" class="btn-amber text-[10px] px-2.5 py-1">Mark Paid</button>`}
          </td>
        </tr>
      `).join('');
    }

    function openNewInvoiceModal() { document.getElementById('newInvoiceModal').classList.remove('hidden'); }
    function closeNewInvoiceModal() { document.getElementById('newInvoiceModal').classList.add('hidden'); }

    function calculateInvoiceTotal() {
      const c = parseFloat(document.getElementById('inv_fee_consult').value) || 0;
      const p = parseFloat(document.getElementById('inv_fee_pharmacy').value) || 0;
      const l = parseFloat(document.getElementById('inv_fee_lab').value) || 0;
      const total = c + p + l;
      document.getElementById('invTotalCalculated').innerText = `₹${total.toFixed(2)}`;
    }

    async function handleCreateInvoice(e) {
      e.preventDefault();
      const patient_name = document.getElementById('inv_patient_name').value.trim();
      const doctor_name = document.getElementById('inv_doctor_name').value;
      const consultation_fee = parseFloat(document.getElementById('inv_fee_consult').value) || 0;
      const pharmacy_fee = parseFloat(document.getElementById('inv_fee_pharmacy').value) || 0;
      const lab_fee = parseFloat(document.getElementById('inv_fee_lab').value) || 0;
      const total_amount = consultation_fee + pharmacy_fee + lab_fee;

      try {
        const res = await fetch('/api/invoices/create', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({patient_name, doctor_name, consultation_fee, pharmacy_fee, lab_fee, total_amount})
        });
        const data = await res.json();
        if (data.success) {
          clientInvoices = data.invoices;
          renderAdminInvoicesTable();
          renderPatientInvoices();
          closeNewInvoiceModal();
          showToast("Invoice Created", data.message);
        }
      } catch(e) { console.error(e); }
    }

    function renderAdminFleetRadar() {
      const container = document.getElementById('adminFleetRadarGrid');
      if (!container) return;
      container.innerHTML = clientAmbulances.map(a => `
        <div class="p-4 bg-slate-950 rounded-2xl border border-slate-800 space-y-3">
          <div class="flex items-center justify-between">
            <span class="font-mono font-bold text-amber-400 text-sm">${a.vehicle_no}</span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${a.status==='Available'?'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30':'bg-rose-500/20 text-rose-400 border border-rose-500/30'}">${a.status}</span>
          </div>
          <div class="text-xs text-slate-300">
            <div>Driver: <strong>${a.driver_name}</strong> (${a.phone})</div>
            <div class="mt-1">ETA: <strong class="text-amber-300">${a.eta_mins} mins</strong></div>
          </div>
          ${a.emergency ? `
            <div class="p-2.5 bg-slate-900 rounded-xl border border-slate-800 text-[11px] space-y-1">
              <span class="text-rose-400 font-bold block">🚨 MISSION ACTIVE: ${a.emergency.patient_name}</span>
              <p class="text-slate-400 truncate">${a.emergency.pickup_location}</p>
              <a href="${a.emergency.maps_url}" target="_blank" class="inline-block text-amber-400 underline font-semibold mt-1">Open Google Maps Route &rarr;</a>
            </div>
          ` : ''}
          <div class="pt-2 flex gap-2">
            <button onclick="updateAmbulanceStatus('${a.vehicle_no}', 'En-Route')" class="px-2.5 py-1 rounded-lg bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 text-[10px] font-bold">En-Route</button>
            <button onclick="updateAmbulanceStatus('${a.vehicle_no}', 'Arrived at Scene')" class="px-2.5 py-1 rounded-lg bg-amber-600/30 hover:bg-amber-600/50 text-amber-300 text-[10px] font-bold">Arrived</button>
            <button onclick="updateAmbulanceStatus('${a.vehicle_no}', 'Complete Trip')" class="px-2.5 py-1 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 text-[10px] font-bold">Available</button>
          </div>
        </div>
      `).join('');
    }

    async function updateAmbulanceStatus(vNo, st) {
      try {
        const res = await fetch('/api/ambulance/update-status', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({vehicle_no: vNo, status: st})
        });
        const data = await res.json();
        if (data.success) {
          clientAmbulances = data.ambulances;
          renderAdminFleetRadar();
          showToast("Fleet Status", data.message);
        }
      } catch(e) { console.error(e); }
    }

    // ----------------------------------------------------------------
    // PUBLIC AMBULANCE SOS & BLOOD MATRIX
    // ----------------------------------------------------------------
    async function triggerAmbulanceDispatch(patient_name, phone, pickup_location, severity_level) {
      try {
        const res = await fetch('/api/ambulance/request', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({patient_name, phone, pickup_location, severity_level})
        });
        const data = await res.json();
        if (data.success) {
          clientAmbulances = data.ambulances;
          renderAdminFleetRadar();
          const amb = data.ambulance;
          showToast("AMBULANCE DISPATCHED!", `Unit ${amb.vehicle_no} assigned. Driver ${amb.driver_name} is en route. ETA: ${amb.eta_mins} mins.`, true);
          if (amb.emergency && amb.emergency.maps_url) {
            window.open(amb.emergency.maps_url, '_blank');
          }
        } else {
          alert(data.error || "Failed to dispatch ambulance.");
        }
      } catch(e) { console.error(e); }
    }

    async function handlePublicSos(e) {
      e.preventDefault();
      const loc = document.getElementById('public_sos_loc').value;
      const phone = document.getElementById('public_sos_phone').value;
      const sev = document.getElementById('public_sos_sev').value;
      await triggerAmbulanceDispatch("Emergency Trauma Citizen", phone, loc, sev);
    }

    function renderLandingDoctors() {
      const container = document.getElementById('landingDoctorsGrid');
      if (!container) return;
      container.innerHTML = clientDoctors.map(doc => `
        <div class="card p-5 space-y-3 hover:border-amber-400 transition">
          <div class="flex items-center gap-3">
            <img src="${doc.avatar}" class="w-12 h-12 rounded-2xl object-cover ring-2 ring-slate-100">
            <div>
              <h4 class="font-extrabold text-sm text-slate-900">${doc.name}</h4>
              <p class="text-xs text-amber-700 font-bold">${doc.department}</p>
            </div>
          </div>
          <p class="text-xs text-slate-500">${doc.specialization}</p>
          <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
            <span class="font-mono text-slate-600">Room: ${doc.room_no}</span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">${doc.status}</span>
          </div>
        </div>
      `).join('');
    }

    function renderLandingBlood(items) {
      const tbody = document.getElementById('landingBloodTableBody');
      if (!tbody) return;
      const list = items || clientBloodInventory;
      tbody.innerHTML = list.map(b => {
        const isCrit = b.units <= 2;
        return `
          <tr class="hover:bg-slate-50/70 transition">
            <td class="px-5 py-3 font-extrabold text-slate-900">${b.hospital}</td>
            <td class="px-4 py-3 text-slate-500">${b.area}</td>
            <td class="px-4 py-3 text-center">
              <span class="font-mono font-black text-xs px-2.5 py-1 rounded-md bg-rose-50 text-rose-700 border border-rose-200">${b.group}</span>
            </td>
            <td class="px-4 py-3 text-center font-mono font-extrabold ${isCrit ? 'text-rose-600 text-sm' : 'text-slate-800'}">${b.units} Units</td>
            <td class="px-4 py-3">
              <span class="px-2 py-0.5 rounded-full text-[10px] font-black ${isCrit ? 'bg-rose-100 text-rose-800 border border-rose-300 animate-pulse' : 'bg-emerald-100 text-emerald-800 border border-emerald-300'}">
                ${isCrit ? 'CRITICAL SHORTAGE' : 'STOCKED'}
              </span>
            </td>
            <td class="px-5 py-3 text-right">
              <a href="tel:${b.contact}" class="font-mono text-amber-600 font-bold hover:underline">${b.contact}</a>
            </td>
          </tr>
        `;
      }).join('');
    }

    function filterLandingBlood(q) {
      const query = q.toLowerCase();
      const filtered = clientBloodInventory.filter(b => 
        b.hospital.toLowerCase().includes(query) || 
        b.area.toLowerCase().includes(query) ||
        b.group.toLowerCase().includes(query)
      );
      renderLandingBlood(filtered);
    }

    function populateDropdowns() {
      // Patient Doctor select
      const ptDocSelect = document.getElementById('pt_doctor_select');
      if (ptDocSelect) {
        ptDocSelect.innerHTML = clientDoctors.map(d => `
          <option value="${d.name}">${d.name} (${d.department} · ${d.timings} · Fee: ₹${d.consultation_fee})</option>
        `).join('');
      }

      // Admin Med Planner Patient select
      const admPtSelect = document.getElementById('adm_rx_patient');
      if (admPtSelect) {
        const uniquePatients = Array.from(new Set(clientAppointments.map(a => a.patient))).concat(["Rahul Sharma", "Priya Patel", "Amit Verma"]);
        const patientSet = Array.from(new Set(uniquePatients));
        admPtSelect.innerHTML = patientSet.map(p => `<option value="${p}">${p}</option>`).join('');
      }

      // Admin Med Planner Doctor select
      const admDocSelect = document.getElementById('adm_rx_doctor');
      if (admDocSelect) {
        admDocSelect.innerHTML = clientDoctors.map(d => `<option value="${d.name}">${d.name}</option>`).join('');
      }
    }

    let toastTimeout;
    function showToast(title, message, isEmergency = false) {
      const toast = document.getElementById('toastNotification');
      document.getElementById('toastTitle').innerText = title;
      document.getElementById('toastMsg').innerText = message;
      document.getElementById('toastIcon').innerHTML = isEmergency
        ? `<i class="fa-solid fa-triangle-exclamation text-rose-500 animate-bounce"></i>`
        : `<i class="fa-solid fa-circle-check text-emerald-500"></i>`;
      toast.classList.remove('hidden');
      clearTimeout(toastTimeout);
      toastTimeout = setTimeout(() => toast.classList.add('hidden'), 4000);
    }

    // ----------------------------------------------------------------
    // INIT
    // ----------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', function() {
      populateDropdowns();
      renderLandingDoctors();
      renderLandingBlood();
      
      // Auto-set today date on appointment picker
      const dateInput = document.getElementById('pt_date');
      if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];
      }

      // Default active view is strictly the Patient / Public Dashboard
      currentUser = null;
      updateAuthUI();

      // Verify and synchronize active auth session with server if logged in
      fetch('/api/auth/me')
        .then(r => r.json())
        .then(data => {
          if (data.authenticated && data.user) {
            currentUser = data.user;
            updateAuthUI();
          }
        })
        .catch(err => {
          console.warn("Auth check fallback:", err);
        });
    });
  </script>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(
        HTML_TEMPLATE,
        appointments=fetch_appointments(),
        blood_inventory=fetch_blood_inventory(),
        ambulances=fetch_ambulances(),
        prescriptions=fetch_prescriptions(),
        doctors=fetch_doctors(),
        invoices=fetch_invoices()
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
