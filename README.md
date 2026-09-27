# ResQLife — When Every Second Matters

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Google Cloud Run](https://img.shields.io/badge/Google_Cloud_Run-Ready-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-Modern_UI-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![FIT-FEST 2026](https://img.shields.io/badge/Hackathon-FIT--FEST_2026-E11D48?style=for-the-badge)](https://github.com)

> **ResQLife** is a unified, real-time emergency healthcare coordination and clinic queue synchronization engine designed to eliminate response latency during life-threatening medical events.

---

## 📌 Problem Statement & Solution Overview

### The Challenge
In emergency and outpatient healthcare, critical delays occur due to fragmented systems:
1. **Ambulance Dispatch Latency**: Emergency calls lack direct GPS routing, severity prioritization, and driver handoffs.
2. **Blood Shortage Crises**: Regional trauma care centers lack a unified, live view of emergency blood reserves.
3. **Overcrowded Outpatient Clinics**: Uncoordinated walk-in crowds cause long wait times and misrouted specialty consultations.
4. **Poor Prescription Adherence**: Discharged patients struggle with complex medication timing and confusing pill blister strips.

### The ResQLife Solution
ResQLife bridges patients, clinic reception desks, consulting doctors, and ambulance fleets into a synchronized single-page operations hub. 

> ⚠️ **Administrative & Logistics Compliance Notice (FIT-FEST 2026 Guidelines)**:  
> *ResQLife operates exclusively as an administrative routing, emergency triage coordination, and patient scheduling platform. It does NOT perform autonomous medical diagnosis, clinical treatment planning, or dispense controlled prescription drugs.*

---

## 🚀 Key Feature Matrix

| Feature Module | Audience / Role | Key Capabilities |
|---|---|---|
| **Emergency Ambulance SOS Dispatch Hub** | Patient / Bystander | One-tap emergency dispatch, Severity priority tagging (**Level 1: Critical Red**, **Level 2: Urgent Amber**, **Level 3: Transport Blue**), automatic nearest unit allocation, live GPS-encoded Google Maps navigation link, ticking countdown ETA banner. |
| **Ambulance Driver Telemetry Terminal** | Driver / Fleet Ops | Live Incoming SOS Radar card, direct **"Open Route in Google Maps"** navigation button, real-time action buttons (**"Mark En-Route"**, **"Arrived at Scene"**, **"Complete Trip"**), fleet status overview, and telemetry stream. |
| **Real-Time Blood Bank Stock Matrix** | ER / Triage / Public | Instant blood group filtering (`O-`, `O+`, `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`), dynamic **"CRITICAL SHORTAGE - DONORS NEEDED"** alarm for stock $\le 2$ units, direct click-to-dial hotline button, and **Quick Stock Update / Report Need** modal. |
| **Smart Specialty Router & Token Booking** | Outpatient Clinic | Rule-based triage router that directs symptoms to the right department (Cardiology, Orthopedics, Pediatrics, Dermatology, General Medicine, Ophthalmology), generates sequential tokens (`A-101`, `A-102`), and predicts wait times. |
| **Reception Desk & Queue Manager** | Front Desk Staff | Real-time overview of daily outpatient flow, walk-in patient registration modal, and single-click **"Next Stage"** status cycling (`Waiting` $\rightarrow$ `In-Clinic` $\rightarrow$ `Completed`). |
| **Doctor Consultation Portal** | Physicians | Real-time queue of assigned consultation patients, one-click **"Write Rx"** prepopulation, and a digital Prescription Pad that immediately archives instructions into the patient locker. |
| **Medicine Schedule & Reminder Vault** | Patient / Adherence | Daily medication cards with pulsing upcoming dose countdowns, physical pill strip / bottle photo verification simulator, and a one-tap **"Mark as Taken"** adherence checklist. |

---

## 🏗️ Technical Architecture

ResQLife is architected as a lightweight, production-grade cloud-native monolith built for sub-second response times:

```
                  ┌──────────────────────────────────────────────┐
                  │          Google Cloud Run (Port 8080)        │
                  │   Gunicorn Server (1 Worker, 8 Threads)      │
                  └──────────────────────┬───────────────────────┘
                                         │
             ┌───────────────────────────┴───────────────────────────┐
             │                   Flask Application                    │
             │           (In-Memory Real-Time State Engines)          │
             └──────┬──────────────┬──────────────┬──────────────┬───┘
                    │              │              │              │
                    ▼              ▼              ▼              ▼
              [Ambulances]   [Appointments]  [Blood Stock]  [Prescriptions]
                    │              │              │              │
                    └──────────────┼──────────────┼──────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    Client Single-Page Hub     │
                   │  - Tailwind CSS Modern Glass  │
                   │  - Vanilla JS Asynchronous UI │
                   │  - Google Maps Navigation URL │
                   │  - Live Countdown Tickers     │
                   └───────────────────────────────┘
```

---

## 🛠️ REST API Specification

### Ambulance Dispatch & Telemetry
* `GET /api/ambulances` — Retrieves the fleet status and active emergency missions.
* `POST /api/ambulance/request` — Dispatches nearest ambulance, assigns severity level, and generates Google Maps route.
* `POST /api/ambulance/update-status` — Driver console transitions (`En-Route`, `Arrived at Scene`, `Complete Trip`).

### Regional Blood Bank Reserves
* `GET /api/blood` — Fetches verified regional trauma center stock.
* `GET, POST /api/blood/filter?group=<group>` — Filters inventory by specific blood group.
* `POST /api/blood/update` — Coordinates stock updates and manages critical shortage triggers.

### Clinic Queue & Outpatient Appointments
* `GET /api/appointments` — Lists active outpatient queue.
* `POST /api/appointments/book` — Registers appointment, applies department triage matching, issues sequential token.
* `POST /api/appointments/update-status` — Cycles status (`Waiting` $\rightarrow$ `In-Clinic` $\rightarrow$ `Completed`).

### Authentication & Role-Based Access Control (RBAC)
* `POST /api/auth/login` — 1-Click demo role logins and custom credential verification.
* `POST /api/auth/register` — Creates user account with designated role (`patient`, `reception`, `doctor`, `ambulance`).
* `POST /api/auth/logout` — Terminates active session.
* `GET /api/auth/me` — Fetches profile of currently authenticated user.

### Prescription Locker & Medicine Reminder Vault
* `GET /api/prescriptions` — Lists active patient prescriptions.
* `POST /api/prescriptions/add` — Doctor issues prescription, synchronizing immediately with the patient vault.
* `POST /api/prescriptions/toggle-taken` — Logs patient dose adherence status (`Taken` / `Pending`).

---

## 💻 Local Setup Instructions

### 1. Prerequisites
* Python 3.10 or 3.11+
* Git

### 2. Clone and Setup
```bash
# Clone the repository
git clone https://github.com/adityadudande294-cmd/ResQlife-emergency-sync.git
cd ResQlife-emergency-sync

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch Development Server
```bash
python app.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser.

---

## ☁️ Google Cloud Run Deployment

ResQLife is optimized for containerized deployment on **Google Cloud Run**:

### 1. Build and Test Container Locally
```bash
# Build Docker image
docker build -t resqlife:latest .

# Run container on port 8080
docker run -p 8080:8080 -e PORT=8080 resqlife:latest
```

### 2. Deploy via Google Cloud CLI (`gcloud`)
```bash
# Set your Google Cloud project ID
gcloud config set project [YOUR_PROJECT_ID]

# Build and push image to Google Artifact Registry / Container Registry
gcloud builds submit --tag gcr.io/[YOUR_PROJECT_ID]/resqlife:latest

# Deploy to Google Cloud Run
gcloud run deploy resqlife \
  --image gcr.io/[YOUR_PROJECT_ID]/resqlife:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080
```

---

## 🧪 Automated Testing & Verification

Run the end-to-end regression test suite verifying all routes:
```bash
python -c "
import app
client = app.app.test_client()

# Check Index View
assert client.get('/').status_code == 200

# Test Ambulance SOS Dispatch
res_sos = client.post('/api/ambulance/request', json={
    'phone': '+91 98765 43210',
    'pickup_location': 'Indiranagar 100ft Road, Bengaluru',
    'severity_level': 'Level 1'
})
assert res_sos.status_code == 200

# Test Blood Filter
assert client.get('/api/blood/filter?group=O-').status_code == 200

# Test Prescription Adherence
assert client.get('/api/prescriptions').status_code == 200

print('All ResQLife core workflows verified!')
"
```

---

## 📄 License & Team
Developed for **FIT-FEST 2026 Hackathon**.  
*ResQLife — When Every Second Matters.*
