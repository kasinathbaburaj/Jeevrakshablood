# 🩸 Jeevraksha - Blood Donation & Emergency Receiving Platform

> *"A single drop of your blood can be a lifetime for someone else. Be the lifeline."*

**Jeevraksha** is a full-stack, production-ready web application engineered to bridge the critical gap between blood donors and emergency patients/hospitals in real-time. Built with a minimalist medical design system, strict authentication security, dynamic blood group compatibility matching, and instant emergency dispatching.

---

## 🎨 Visual & UI/UX Design System

- **Brand Logo & Mark:** "Jeevraksha" rendered with Google Fonts **'Poppins'** (700 bold typographic mark with a custom minimalist blood drop icon).
- **Typography:** **Poppins** imported globally across all elements (300, 400, 500, 600, 700 weights).
- **Color Palette:**
  - **Primary Background:** Pure White (`#FFFFFF`) & Soft Off-White (`#F8F9FA`).
  - **Primary Accent:** Blood Red (`#D90429`), Deep Crimson (`#EF233C`), and Dark Red (`#8D0801`).
  - **Text Colors:** Charcoal Black (`#1A1A1A`) for high-contrast headings, Slate Grey (`#6C757D`) for readable body text.
  - **Status Colors:** Medical Emerald (`#2B9348`) for available/eligible, Amber (`#F59E0B`) for high urgency, Crimson (`#D90429`) with pulse animation for critical ICU requests.
- **Aesthetic:** Minimalist, generous whitespace, rounded corners (`12px` border radius), soft elevated shadows (`0 10px 30px rgba(0,0,0,0.05)`), and smooth micro-interactions.

---

## 🚀 Key Features

### 1. Split-Screen Authentication (`/login`, `/register`)
- **Left Panel:** High-contrast blood red gradient (`linear-gradient(135deg, #D90429 0%, #8D0801 100%)`) featuring the centered quote, vector pulse line, and trust metrics (100% verified donors, < 3 mins match speed, 24/7 lifeline).
- **Right Panel:** Minimalist form with instant tab switching between Log In and Create Account.
- **Strict Real-Time & Backend Validation:**
  - **Email:** Strict regex format, rejects dummy emails (`test@test.com`, `abc@gmail.com`, `123@123.com`) and disposable domain providers (`@mailinator.com`, `@tempmail.com`, etc.).
  - **Password:** Minimum 8 characters, at least 1 uppercase letter, 1 lowercase letter, 1 numeric digit, and 1 special character (`!@#$%^&*`). Features a live interactive checklist.
  - **Database Verification:** Login authenticates against stored `werkzeug.security` password hashes with explicit alerts for unregistered emails or invalid credentials.

### 2. Main Dashboard & Command Center (`/dashboard`)
- **Quick Summary Cards:**
  1. *Total Available Donors* (with live online pulse indicator).
  2. *Active Emergency Requests* (with breakdown of Critical ICU emergencies).
  3. *Compatible Blood Units Available* (calculated in real-time based on the logged-in user's blood group).
  4. *User's Donation Eligibility Status* (dynamic 90-day cooldown countdown).
- **Live Emergency Request Feed:**
  - Real-time urgent blood requests filterable by **Blood Group** (`A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`) and **City/Hospital search**.
  - Dynamic urgency tags: Critical (pulsing red), High (amber), Standard (blue).
  - Quick action buttons: **Respond to Help / Donate** and **Direct Emergency Call**.

### 3. Active Donor Module (`/donate`)
- Form to register as a verified donor or update eligibility.
- Validates age strictly between **18 and 65 years**.
- Validates weight strictly **>= 50 kg**.
- **90-Day Cooldown Auto-Check:** Computes the recovery period from the last donation date in real-time on both client and server.
- Medical clearance declaration checkbox.
- Availability toggle switch (Active vs. Temporarily Inactive).

### 4. Receive / Emergency Blood Module (`/request`)
- Rapid requisition form for patients and hospitals (patient name, required blood group, units, urgency, hospital name, location, contact number).
- **Smart Compatibility Matching Engine:** Immediately executes an SQL query to match verified active donors in the system based on red blood cell compatibility:
  - Recipient `O-` $\rightarrow$ Donors: `O-`
  - Recipient `O+` $\rightarrow$ Donors: `O+`, `O-`
  - Recipient `A-` $\rightarrow$ Donors: `A-`, `O-`
  - Recipient `A+` $\rightarrow$ Donors: `A+`, `A-`, `O+`, `O-`
  - Recipient `B-` $\rightarrow$ Donors: `B-`, `O-`
  - Recipient `B+` $\rightarrow$ Donors: `B+`, `B-`, `O+`, `O-`
  - Recipient `AB-` $\rightarrow$ Donors: `AB-`, `A-`, `B-`, `O-`
  - Recipient `AB+` $\rightarrow$ Universal Recipient (all 8 groups)

### 5. Live Inventory Matrix (`/inventory`)
- Real-time stock status across all 8 blood groups (Critical Low, Moderate, Sufficient).
- Transparent compatibility guides for every blood group.

### 6. My Activity & Digital Donor Card (`/my-activity`)
- User's submitted requests tracking with "Mark as Fulfilled" action.
- Logged donation history.
- Sleek **Digital Donor Card** with donor ID, verified badge, and quick print option.

### 7. Restricted Backend & Database Admin Inspector (`/admin/db`)
- **Strict Role-Based Access Control (`@admin_required`):** Completely hidden and protected from normal users.
  - Normal users logging in via `/login` ONLY have access to `/dashboard`, `/donate`, and `/request`.
  - Normal users visiting `/admin` or `/admin/db` directly are intercepted and rejected with a `403 Access Denied` redirect to `/dashboard`.
  - The "Backend DB View" navbar shortcut is completely hidden unless `session.get('is_admin') == True`.
- **Dedicated Admin Authentication (`/admin/login`):**
  - Dedicated admin entrance verifying `users.is_admin == 1` and password hash.
  - Features quick-access link to the **Admin Password & Account Recovery Portal**.
  - Default Master Admin credentials:
    - **Username:** `Jeevraksha Master Admin`
    - **Email:** `admin@jeevraksha.org`
    - **Password:** `Admin@Jeevraksha2026`
    - **Recovery Email:** `recovery@jeevraksha.org`
- **Dynamic Credential & Recovery Management:**
  - **In-Console Settings Modal:** Modify the administrator username, primary login email, password, and recovery email directly from the top bar in `/admin/db`.
  - **Password Reset via Recovery Email (`/admin/reset-password`):** If locked out, administrators can verify their identity using their registered **Recovery Email** and set a new password and username.
  - **CLI Management Utility (`change_admin.py`):** Change admin credentials or promote users via the terminal.
- **Tables Visualized & Managed:**
  - `users`: ID, Role (`is_admin`), Name, Email, Recovery Email, full Werkzeug Password Hashes (with one-click copy), Phone, Blood Group, City, Created At.
  - `donors`: ID, User FK, Blood Group, Age, Weight, Last Donation Date, Availability status, Medical Verification, Location.
  - `blood_requests`: ID, Patient, Blood Group, Units, Urgency, Hospital, Requester, **Live Status Switcher** (Pending $\rightarrow$ Matched $\rightarrow$ Fulfilled), and **Delete record** action.
  - `donations_log`: Complete audit trail linking donors with patient emergencies.
  - **SQL DDL Schema Viewer:** Live display of table schemas and foreign key cascades.
  - **Re-Seed Demo Data Button:** One-click re-population of demo network records.
  - **Admin Logout:** Dedicated sign-out cleanly clearing administrator privileges.

---

## 🗄️ Database Architecture (`jeevraksha.db`)

Built using SQLite with foreign key enforcement, schema migration, and indexed queries:

```sql
-- 1. Users Table (with Role-Based Access Control & Recovery Email)
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    blood_group TEXT NOT NULL,
    city TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0,
    recovery_email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Donors Table
CREATE TABLE donors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    blood_group TEXT NOT NULL,
    age INTEGER NOT NULL,
    weight REAL NOT NULL,
    last_donation_date DATE,
    is_available INTEGER DEFAULT 1,
    medical_verified INTEGER DEFAULT 1,
    location TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. Blood Requests Table
CREATE TABLE blood_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id INTEGER NOT NULL,
    patient_name TEXT NOT NULL,
    blood_group_needed TEXT NOT NULL,
    units_required INTEGER NOT NULL,
    urgency_level TEXT NOT NULL,
    hospital_name TEXT NOT NULL,
    location TEXT NOT NULL,
    contact_phone TEXT NOT NULL,
    status TEXT DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(requester_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 4. Donations Log Table
CREATE TABLE donations_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL,
    request_id INTEGER,
    donation_date DATE DEFAULT CURRENT_DATE,
    units_donated INTEGER DEFAULT 1,
    status TEXT DEFAULT 'Completed',
    FOREIGN KEY(donor_id) REFERENCES donors(id) ON DELETE CASCADE,
    FOREIGN KEY(request_id) REFERENCES blood_requests(id) ON DELETE SET NULL
);
```

---

## ⚡ Quick Start & Installation

### 1. Requirements
- Python 3.9+
- Flask & Werkzeug

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python app.py
```
Open your web browser and navigate to:
**`http://127.0.0.1:5000`**

*(Unauthenticated visits automatically load the Split-Screen Login & Registration page)*

---

## 🔑 Pre-Seeded Demo Credentials

The database automatically seeds realistic verified donors, hospital emergency requests, and the Master Administrator:

| Role | Username | Primary Email | Password | Recovery Email | Portal Access |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Brand Admin** | `Kasinath Baburaj` | `contactkasinathbaburaj@gmail.com` | *(Your Account Password)* | `recovery@jeevraksha.org` | `/dashboard` & `/admin/db` |
| **Master Admin** | `Jeevraksha Master Admin` | `admin@jeevraksha.org` | `Admin@Jeevraksha2026` | `recovery@jeevraksha.org` | `/admin/login` & `/admin/db` |
| **Verified Donor** | `Aarav Sharma` | `aarav.sharma@jeevraksha.org` | `Lifeline#2026` | — | `/dashboard` (Normal User) |
| **Universal Donor** | `Priya Nair` | `priya.nair@jeevraksha.org` | `Lifeline#2026` | — | `/dashboard` (Normal User) |
| **Hospital Trauma** | `AIIMS Emergency` | `emergency.desk@aiims.edu` | `Hospital#2026` | — | `/dashboard` (Normal User) |
| **Verified Donor** | `Rohan Verma` | `rohan.verma@jeevraksha.org` | `Lifeline#2026` | — | `/dashboard` (Normal User) |

*(Click "Need demo login?" on `/login` or "Autofill" on `/admin/login` to automatically populate credentials)*

---

## 🛠️ Changing Admin Username, Password & Recovery Email

You have three easy ways to update or recover administrator credentials:

### Method 1: In the Web Console (`/admin/db`)
1. Log in at `http://127.0.0.1:5000/admin/login`.
2. Click the **"⚙️ Admin Profile & Settings"** button in the top navbar.
3. Update the **Username / Full Name**, **Primary Admin Email**, **Recovery Email**, or enter a **New Strong Password**.
4. Click **"Save Changes"**.

### Method 2: Reset Password via Recovery Email (`/admin/reset-password`)
If you forgot your password or got locked out:
1. Go to `http://127.0.0.1:5000/admin/reset-password` (or click *"Forgot Password? Reset with Recovery Email"* on `/admin/login`).
2. Enter your primary admin email and your verified **Recovery Email** (default: `recovery@jeevraksha.org`).
3. Optionally enter an updated username and updated recovery email.
4. Enter and confirm your new password (must meet complexity requirements: 8+ chars, uppercase, lowercase, digit, special character).
5. Click **"Verify Recovery & Reset Password"**.

### Method 3: Via Terminal CLI (`change_admin.py`)
Run the standalone administration script:
```bash
# Interactive mode:
python change_admin.py

# Or via command line arguments:
python change_admin.py --email admin@jeevraksha.org --password NewPass#2026 --name "Dr. Arjun Mehta" --recovery-email backup@jeevraksha.org

# View all current administrators and their recovery emails:
python change_admin.py --list
```

---

## 🧪 Automated Test Suite

A complete test suite covering email regex, disposable domain blocking, password complexity, authentication sessions, compatibility engine calculations, 90-day cooldown logic, strict admin security isolation, brand administrator designation, and admin password reset/recovery is included:

```bash
python test_app.py
```
Expected output:
```
Ran 12 tests in 1.7s
OK
```

---

## 📂 Project Directory Structure

```
jeevraksha/
├── app.py                      # Flask backend, SQL connections, CRUD APIs, compatibility matrix
├── change_admin.py             # CLI Administrator & Recovery manager tool
├── requirements.txt            # Python dependency declarations
├── test_app.py                 # Automated unit & integration test suite (11 tests)
├── jeevraksha.db               # SQLite database with seeded demo network & Master Admin
├── templates/
│   ├── auth.html               # Split-screen Login / Signup page with real-time validation
│   ├── admin_login.html        # Dedicated Master Admin authentication portal
│   ├── admin_reset_password.html # Admin Password & Credentials Reset with recovery verification
│   ├── admin_db.html           # Visual Database & Relational Schema Inspector (Protected)
│   └── dashboard.html          # Main interface (Dashboard, Donate, Request, Inventory, Activity)
└── static/
    ├── css/
    │   └── style.css           # Clean White & Blood Red minimalist stylesheet
    └── js/
        └── main.js             # Frontend controller, live validation, async APIs & smart matching
```
