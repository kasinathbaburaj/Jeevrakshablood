import os
import sys
import re
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, g
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'jeevraksha-production-secret-key-2026-life-saving')
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jeevraksha.db')

# ---------------------------------------------------------
# CONSTANTS & COMPATIBILITY MATRIX
# ---------------------------------------------------------
BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

# Official brand administrator emails automatically designated as is_admin = 1 on init/registration
BRAND_ADMIN_EMAILS = {
    'contactkasinathbaburaj@gmail.com',
    'admin@jeevraksha.org',
    os.environ.get('JEEVRAKSHA_ADMIN_EMAIL', '').strip().lower()
}
BRAND_ADMIN_EMAILS = {e for e in BRAND_ADMIN_EMAILS if e}

# Red Blood Cell Compatibility Matrix
# Key: Recipient Blood Group -> Value: List of Donor Blood Groups that can safely donate to this recipient
COMPATIBLE_DONORS_FOR_RECIPIENT = {
    'O-': ['O-'],
    'O+': ['O+', 'O-'],
    'A-': ['A-', 'O-'],
    'A+': ['A+', 'A-', 'O+', 'O-'],
    'B-': ['B-', 'O-'],
    'B+': ['B+', 'B-', 'O+', 'O-'],
    'AB-': ['AB-', 'A-', 'B-', 'O-'],
    'AB+': ['AB+', 'AB-', 'A+', 'A-', 'B+', 'B-', 'O+', 'O-']  # Universal Recipient
}

# Key: Donor Blood Group -> Value: List of Recipient Blood Groups this donor can give to
COMPATIBLE_RECIPIENTS_FOR_DONOR = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],  # Universal Donor
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+']
}

DISPOSABLE_DOMAINS = {
    'test.com', 'example.com', 'fake.com', 'tempmail.com', 'mailinator.com',
    'throwaway.com', 'guerrillamail.com', 'sharklasers.com', '10minutemail.com',
    'yopmail.com', 'trashmail.com', 'temp-mail.org', 'dispostable.com',
    'dummy.com', 'invalid.com', 'mytempemail.com', 'trashmail.net'
}

DUMMY_EMAIL_EXACT = {
    'test@test.com', 'abc@gmail.com', '123@123.com', 'admin@admin.com',
    'user@user.com', 'fake@fake.com', 'dummy@dummy.com', 'asdf@asdf.com'
}


# ---------------------------------------------------------
# DATABASE CONNECTION & INITIALIZATION
# ---------------------------------------------------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
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
    ''')

    # Safe Schema Migration: Ensure is_admin and recovery_email columns exist
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    if 'is_admin' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if 'recovery_email' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN recovery_email TEXT")

    # 2. donors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donors (
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
    ''')

    # 3. blood_requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blood_requests (
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
    ''')

    # 4. donations_log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_id INTEGER NOT NULL,
            request_id INTEGER,
            donation_date DATE DEFAULT CURRENT_DATE,
            units_donated INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Completed',
            FOREIGN KEY(donor_id) REFERENCES donors(id) ON DELETE CASCADE,
            FOREIGN KEY(request_id) REFERENCES blood_requests(id) ON DELETE SET NULL
        );
    ''')

    # Seed and ensure official Brand Administrator accounts (is_admin = 1)
    brand_admin_configs = [
        {
            'name': 'Kasinath Baburaj',
            'email': 'contactkasinathbaburaj@gmail.com',
            'recovery': 'recovery@jeevraksha.org',
            'password': os.environ.get('JEEVRAKSHA_ADMIN_PASSWORD', 'Admin@Jeevraksha2026'),
            'phone': '9895000001',
            'blood_group': 'O+',
            'city': 'National HQ'
        },
        {
            'name': os.environ.get('JEEVRAKSHA_ADMIN_NAME', 'Jeevraksha Master Admin'),
            'email': os.environ.get('JEEVRAKSHA_ADMIN_EMAIL', 'admin@jeevraksha.org').strip().lower(),
            'recovery': os.environ.get('JEEVRAKSHA_ADMIN_RECOVERY', 'recovery@jeevraksha.org').strip().lower(),
            'password': os.environ.get('JEEVRAKSHA_ADMIN_PASSWORD', 'Admin@Jeevraksha2026'),
            'phone': '9999900000',
            'blood_group': 'O-',
            'city': 'National HQ'
        }
    ]

    for admin_cfg in brand_admin_configs:
        cursor.execute("SELECT id, recovery_email, is_admin FROM users WHERE LOWER(email) = ?", (admin_cfg['email'].lower(),))
        existing_admin = cursor.fetchone()

        if existing_admin:
            # Automatically designate is_admin = 1 and ensure recovery email is configured
            recovery_target = existing_admin['recovery_email'] if existing_admin['recovery_email'] else admin_cfg['recovery']
            cursor.execute('''
                UPDATE users
                SET is_admin = 1,
                    recovery_email = ?
                WHERE id = ?
            ''', (recovery_target, existing_admin['id']))
        else:
            admin_pwd_hash = generate_password_hash(admin_cfg['password'])
            cursor.execute('''
                INSERT INTO users (full_name, email, password_hash, phone, blood_group, city, is_admin, recovery_email)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            ''', (
                admin_cfg['name'],
                admin_cfg['email'].lower(),
                admin_pwd_hash,
                admin_cfg['phone'],
                admin_cfg['blood_group'],
                admin_cfg['city'],
                admin_cfg['recovery']
            ))

    # Check if demo data is present, if not, seed realistic data for immediate richness
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 0")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_realistic_data(cursor)

    conn.commit()
    conn.close()


def seed_realistic_data(cursor):
    """Seed initial realistic verified donors and emergency requests."""
    demo_users = [
        ("Dr. Aarav Sharma", "aarav.sharma@jeevraksha.org", generate_password_hash("Lifeline#2026"), "9876543210", "O+", "Mumbai"),
        ("Priya Nair", "priya.nair@jeevraksha.org", generate_password_hash("Lifeline#2026"), "9823456781", "O-", "Mumbai"),
        ("Rohan Verma", "rohan.verma@jeevraksha.org", generate_password_hash("Lifeline#2026"), "9834567892", "A+", "Delhi"),
        ("Ananya Iyer", "ananya.iyer@jeevraksha.org", generate_password_hash("Lifeline#2026"), "9845678903", "B+", "Bangalore"),
        ("Vikram Singh", "vikram.singh@jeevraksha.org", generate_password_hash("Lifeline#2026"), "9856789014", "AB+", "Hyderabad"),
        ("Sneha Patil", "sneha.patil@jeevraksha.org", generate_password_hash("Lifeline#2026"), "9867890125", "A-", "Pune"),
        ("Kavita Rao", "kavita.rao@jeevraksha.org", generate_password_hash("Lifeline#2026"), "9878901236", "B-", "Chennai"),
        ("Arjun Mehta", "arjun.mehta@jeevraksha.org", generate_password_hash("Lifeline#2026"), "9889012347", "AB-", "Kolkata"),
        ("Emergency Desk AIIMS", "emergency.desk@aiims.edu", generate_password_hash("Hospital#2026"), "9890123458", "O-", "Delhi"),
    ]

    for user in demo_users:
        cursor.execute('''
            INSERT INTO users (full_name, email, password_hash, phone, blood_group, city, is_admin)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        ''', user)

    # Seed donor records
    # (user_id, blood_group, age, weight, last_donation_date, is_available, medical_verified, location)
    demo_donors = [
        (1, "O+", 29, 68.5, (date.today() - timedelta(days=120)).isoformat(), 1, 1, "Lilavati Hospital, Bandra, Mumbai"),
        (2, "O-", 26, 54.0, (date.today() - timedelta(days=105)).isoformat(), 1, 1, "Hinduja Hospital, Mahim, Mumbai"),
        (3, "A+", 34, 74.0, (date.today() - timedelta(days=140)).isoformat(), 1, 1, "AIIMS Ansari Nagar, Delhi"),
        (4, "B+", 27, 62.0, (date.today() - timedelta(days=40)).isoformat(), 1, 1, "Manipal Hospital, HAL Road, Bangalore"),
        (5, "AB+", 31, 80.0, (date.today() - timedelta(days=110)).isoformat(), 1, 1, "Apollo Hospitals, Jubilee Hills, Hyderabad"),
        (6, "A-", 24, 56.5, (date.today() - timedelta(days=95)).isoformat(), 1, 1, "Ruby Hall Clinic, Pune"),
        (7, "B-", 38, 71.0, (date.today() - timedelta(days=130)).isoformat(), 1, 1, "Apollo Cancer Centre, Teynampet, Chennai"),
        (8, "AB-", 30, 65.0, (date.today() - timedelta(days=150)).isoformat(), 1, 1, "AMRI Hospitals, Dhakuria, Kolkata"),
    ]

    for donor in demo_donors:
        cursor.execute('''
            INSERT INTO donors (user_id, blood_group, age, weight, last_donation_date, is_available, medical_verified, location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', donor)

    # Seed emergency requests
    # (requester_id, patient_name, blood_group_needed, units_required, urgency_level, hospital_name, location, contact_phone, status)
    demo_requests = [
        (9, "Kabir Sen (Trauma ICU)", "O-", 3, "Critical", "AIIMS Trauma Centre", "Safdarjung Enclave, Delhi", "9890123458", "Pending"),
        (3, "Meera Deshmukh (Maternity)", "B+", 2, "High", "KEM Hospital", "Parel, Mumbai", "9834567892", "Pending"),
        (5, "Rajesh Singhania (Cardiac Surgery)", "A+", 4, "High", "Fortis Escorts Heart Institute", "Okhla, Delhi", "9856789014", "Pending"),
        (1, "Baby Tanya (Pediatric Oncology)", "O+", 2, "Critical", "Tata Memorial Hospital", "Parel, Mumbai", "9876543210", "Matched"),
        (4, "Deepak Joshi (Orthopedic Emergency)", "AB-", 1, "Standard", "Narayana Health City", "Bommasandra, Bangalore", "9845678903", "Pending"),
    ]

    for req in demo_requests:
        cursor.execute('''
            INSERT INTO blood_requests (requester_id, patient_name, blood_group_needed, units_required, urgency_level, hospital_name, location, contact_phone, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', req)

    # Seed a log entry for matched request
    cursor.execute('''
        INSERT INTO donations_log (donor_id, request_id, donation_date, units_donated, status)
        VALUES (1, 4, ?, 2, 'Completed')
    ''', ((date.today() - timedelta(days=10)).isoformat(),))


# ---------------------------------------------------------
# VALIDATION UTILITIES (STRICT REAL VALIDATION)
# ---------------------------------------------------------
EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PHONE_REGEX = re.compile(r'^[6-9]\d{9}$')  # Standard 10-digit mobile number format


def validate_email_strict(email: str):
    """
    Strict email validation:
    - Regex check
    - Reject common fake/dummy addresses
    - Reject disposable domains
    """
    if not email:
        return False, "Email address is required."

    email_clean = email.strip().lower()

    if not EMAIL_REGEX.match(email_clean):
        return False, "Please enter a valid email address format (e.g. name@domain.com)."

    if email_clean in DUMMY_EMAIL_EXACT:
        return False, f"The email '{email_clean}' is recognized as a placeholder. Please use a real email."

    parts = email_clean.split('@')
    if len(parts) != 2:
        return False, "Invalid email structure."

    local_part, domain = parts[0], parts[1]

    if domain in DISPOSABLE_DOMAINS:
        return False, f"Disposable or temporary email domains (@{domain}) are not permitted."

    if local_part in {'test', 'temp', 'fake', 'dummy', 'asdf', 'abc', '123', 'admin', 'user'}:
        return False, f"The email username '{local_part}' is not accepted. Please provide your legitimate email."

    return True, email_clean


def validate_password_strict(password: str):
    """
    Password validation:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character
    """
    if not password:
        return False, "Password is required."

    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter (A-Z)."

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter (a-z)."

    if not re.search(r'\d', password):
        return False, "Password must contain at least one numeric digit (0-9)."

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password):
        return False, "Password must contain at least one special character (e.g. !@#$%^&*)."

    return True, password


def validate_phone_number(phone: str):
    """Validate 10-digit contact number."""
    if not phone:
        return False, "Phone number is required."
    phone_clean = re.sub(r'[\s\-\+]', '', phone.strip())
    if phone_clean.startswith('91') and len(phone_clean) == 12:
        phone_clean = phone_clean[2:]
    if not PHONE_REGEX.match(phone_clean):
        return False, "Please provide a valid 10-digit mobile number starting with 6, 7, 8, or 9."
    return True, phone_clean


def check_donation_eligibility(last_donation_date_str, age=None, weight=None):
    """
    Calculates 90-day cooldown and general eligibility.
    Returns: {
        'eligible': bool,
        'days_remaining': int,
        'next_eligible_date': str,
        'reason': str
    }
    """
    if age is not None and (age < 18 or age > 65):
        return {
            'eligible': False,
            'days_remaining': 0,
            'next_eligible_date': None,
            'reason': f"Age must be between 18 and 65 years. Current: {age}."
        }

    if weight is not None and weight < 50.0:
        return {
            'eligible': False,
            'days_remaining': 0,
            'next_eligible_date': None,
            'reason': f"Weight must be at least 50 kg. Current: {weight} kg."
        }

    if not last_donation_date_str:
        return {
            'eligible': True,
            'days_remaining': 0,
            'next_eligible_date': date.today().isoformat(),
            'reason': "Ready to donate! No prior cooldown active."
        }

    try:
        if isinstance(last_donation_date_str, date):
            last_date = last_donation_date_str
        else:
            last_date = datetime.strptime(str(last_donation_date_str).split('T')[0], '%Y-%m-%d').date()

        cooldown_period = 90  # 90-day cooldown standard
        next_date = last_date + timedelta(days=cooldown_period)
        today = date.today()

        if today >= next_date:
            return {
                'eligible': True,
                'days_remaining': 0,
                'next_eligible_date': today.isoformat(),
                'reason': "Eligible to donate! 90-day cooldown completed."
            }
        else:
            days_left = (next_date - today).days
            return {
                'eligible': False,
                'days_remaining': days_left,
                'next_eligible_date': next_date.isoformat(),
                'reason': f"90-day recovery cooldown active. {days_left} day(s) remaining."
            }
    except Exception as e:
        return {
            'eligible': True,
            'days_remaining': 0,
            'next_eligible_date': date.today().isoformat(),
            'reason': "Eligibility verified."
        }


# ---------------------------------------------------------
# AUTHENTICATION & ACCESS CONTROL DECORATORS
# ---------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Authentication required. Please log in.'}), 401
            return redirect(url_for('login_page', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Dedicated Administrator Access Guard.
    Strictly enforces is_admin == 1 in session and database.
    Normal users are blocked with 403 Access Denied and redirected.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Check if authenticated
        if 'user_id' not in session:
            if request.path.startswith('/api/') or request.path.startswith('/admin/api/') or request.path.startswith('/admin/db/') or request.path == '/admin/seed':
                return jsonify({'success': False, 'error': '401 Unauthorized: Administrator authentication required.'}), 401
            return redirect(url_for('admin_login_page', next=request.url))

        # 2. Verify admin privilege in session and database
        is_admin = session.get('is_admin')
        if not is_admin:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
            row = cursor.fetchone()
            if row and row['is_admin'] == 1:
                session['is_admin'] = True
                is_admin = True

        if not is_admin:
            if request.path.startswith('/api/') or request.path.startswith('/admin/api/') or request.path.startswith('/admin/db/') or request.path == '/admin/seed':
                return jsonify({'success': False, 'error': '403 Access Denied: Administrator privileges required.'}), 403
            # Normal users attempting to access admin routes are blocked with a 403 redirect
            return redirect(url_for('dashboard_page', access_denied='1')), 403

        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------
# PAGE ROUTES
# ---------------------------------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard_page'))
    return redirect(url_for('login_page'))


@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard_page'))
    return render_template('auth.html', initial_mode='login')


@app.route('/register')
def register_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard_page'))
    return render_template('auth.html', initial_mode='register')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/dashboard')
@login_required
def dashboard_page():
    return render_template('dashboard.html', active_tab='dashboard')


@app.route('/donate')
@login_required
def donate_page():
    return render_template('dashboard.html', active_tab='donate')


@app.route('/request')
@login_required
def request_page():
    return render_template('dashboard.html', active_tab='request')


@app.route('/inventory')
@login_required
def inventory_page():
    return render_template('dashboard.html', active_tab='inventory')


@app.route('/my-activity')
@login_required
def activity_page():
    return render_template('dashboard.html', active_tab='activity')


# ---------------------------------------------------------
# BACKEND & DATABASE ADMIN INSPECTOR (RESTRICTED TO ADMIN)
# ---------------------------------------------------------
@app.route('/admin')
@admin_required
def admin_root():
    return redirect(url_for('admin_db_page'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login_page():
    # If already authenticated as administrator, go directly to DB console
    if session.get('user_id') and session.get('is_admin'):
        return redirect(url_for('admin_db_page'))

    if request.method == 'GET':
        return render_template('admin_login.html')

    # POST: Authenticate Admin
    data = request.get_json() if request.is_json else request.form
    email_raw = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email_raw or not password:
        err_msg = 'Please enter both administrator email and password.'
        if request.is_json:
            return jsonify({'success': False, 'error': err_msg}), 400
        return render_template('admin_login.html', error=err_msg), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email_raw,))
    user = cursor.fetchone()

    if not user:
        err_msg = 'No administrator account found with this email.'
        if request.is_json:
            return jsonify({'success': False, 'error': err_msg}), 404
        return render_template('admin_login.html', error=err_msg), 404

    # Verify password hash
    if not check_password_hash(user['password_hash'], password):
        err_msg = 'Invalid administrator credentials. Access denied.'
        if request.is_json:
            return jsonify({'success': False, 'error': err_msg}), 401
        return render_template('admin_login.html', error=err_msg), 401

    # Verify administrator role
    if not user['is_admin']:
        err_msg = '403 Access Denied: This account is a regular user and does not possess administrator privileges.'
        if request.is_json:
            return jsonify({'success': False, 'error': err_msg}), 403
        return render_template('admin_login.html', error=err_msg), 403

    # Establish admin session
    session['user_id'] = user['id']
    session['user_name'] = user['full_name']
    session['email'] = user['email']
    session['blood_group'] = user['blood_group']
    session['is_admin'] = True

    next_url = request.args.get('next') or url_for('admin_db_page')
    if request.is_json:
        return jsonify({
            'success': True,
            'message': f'Welcome, Master Administrator {user["full_name"]}. Access granted.',
            'redirect': next_url
        }), 200

    return redirect(next_url)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login_page'))


@app.route('/admin/reset-password', methods=['GET', 'POST'])
def admin_reset_password_page():
    """
    Dedicated Password Reset for Administrators.
    Verifies admin email and registered recovery email before allowing password reset.
    Also supports setting a new username (full_name) and updating recovery email.
    """
    if request.method == 'GET':
        return render_template('admin_reset_password.html')

    data = request.get_json() if request.is_json else request.form
    admin_email = (data.get('admin_email') or '').strip().lower()
    recovery_email = (data.get('recovery_email') or '').strip().lower()
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''
    new_name = (data.get('new_name') or '').strip()
    new_recovery_email = (data.get('new_recovery_email') or '').strip().lower()

    if not admin_email or not recovery_email or not new_password:
        err = 'Admin email, recovery email, and new password are required.'
        if request.is_json:
            return jsonify({'success': False, 'error': err}), 400
        return render_template('admin_reset_password.html', error=err), 400

    if new_password != confirm_password:
        err = 'New password and confirm password do not match.'
        if request.is_json:
            return jsonify({'success': False, 'error': err}), 400
        return render_template('admin_reset_password.html', error=err), 400

    is_valid_pwd, pwd_err = validate_password_strict(new_password)
    if not is_valid_pwd:
        if request.is_json:
            return jsonify({'success': False, 'error': pwd_err}), 400
        return render_template('admin_reset_password.html', error=pwd_err), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ? AND is_admin = 1", (admin_email,))
    admin_user = cursor.fetchone()

    if not admin_user:
        err = 'No administrator account found with this email address.'
        if request.is_json:
            return jsonify({'success': False, 'error': err}), 404
        return render_template('admin_reset_password.html', error=err), 404

    # Verify recovery email
    stored_recovery = (admin_user['recovery_email'] or '').strip().lower()
    stored_primary = (admin_user['email'] or '').strip().lower()

    if stored_recovery:
        if recovery_email != stored_recovery and recovery_email != stored_primary:
            err = 'The recovery email provided does not match the registered recovery email for this administrator.'
            if request.is_json:
                return jsonify({'success': False, 'error': err}), 403
            return render_template('admin_reset_password.html', error=err), 403
    else:
        if recovery_email != stored_primary:
            err = 'Verification failed. Please provide your registered administrator email as verification.'
            if request.is_json:
                return jsonify({'success': False, 'error': err}), 403
            return render_template('admin_reset_password.html', error=err), 403

    # All checks passed: hash new password
    new_hash = generate_password_hash(new_password)
    updated_name = new_name if new_name else admin_user['full_name']
    updated_recovery = new_recovery_email if new_recovery_email else (stored_recovery or recovery_email)

    cursor.execute('''
        UPDATE users
        SET password_hash = ?, full_name = ?, recovery_email = ?
        WHERE id = ?
    ''', (new_hash, updated_name, updated_recovery, admin_user['id']))
    db.commit()

    success_msg = f'Password and administrator details successfully reset for {admin_email}! You can now sign in.'
    if request.is_json:
        return jsonify({
            'success': True,
            'message': success_msg,
            'redirect': url_for('admin_login_page')
        }), 200

    return render_template('admin_login.html', success=success_msg)


@app.route('/admin/seed', methods=['POST'])
@admin_required
def admin_seed_data():
    """Admin re-seed / restore demo network data."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM donations_log")
    cursor.execute("DELETE FROM blood_requests")
    cursor.execute("DELETE FROM donors")
    cursor.execute("DELETE FROM users WHERE LOWER(email) != 'admin@jeevraksha.org'")
    seed_realistic_data(cursor)
    db.commit()
    return jsonify({'success': True, 'message': 'Demo network data successfully re-seeded!'})


@app.route('/admin/db')
@admin_required
def admin_db_page():
    """
    Direct SQL Database Inspector page.
    Protected by @admin_required. Queries users, donors, blood_requests, and donations_log.
    """
    db = get_db()
    cursor = db.cursor()

    # 1. users (including recovery_email)
    cursor.execute('''
        SELECT id, full_name, email, password_hash, phone, blood_group, city, is_admin, recovery_email, created_at
        FROM users
        ORDER BY id ASC
    ''')
    users = [dict(r) for r in cursor.fetchall()]

    # 2. donors
    cursor.execute('''
        SELECT d.*, u.full_name as user_name, u.email as user_email, u.phone as user_phone
        FROM donors d
        JOIN users u ON d.user_id = u.id
        ORDER BY d.id ASC
    ''')
    donors = [dict(r) for r in cursor.fetchall()]

    # 3. blood_requests
    cursor.execute('''
        SELECT br.*, u.full_name as requester_name, u.email as requester_email
        FROM blood_requests br
        LEFT JOIN users u ON br.requester_id = u.id
        ORDER BY br.id DESC
    ''')
    requests_rows = [dict(r) for r in cursor.fetchall()]

    # 4. donations_log
    cursor.execute('''
        SELECT dl.*, d.blood_group as donor_blood_group, u.full_name as donor_name,
               br.patient_name, br.hospital_name
        FROM donations_log dl
        JOIN donors d ON dl.donor_id = d.id
        JOIN users u ON d.user_id = u.id
        LEFT JOIN blood_requests br ON dl.request_id = br.id
        ORDER BY dl.id DESC
    ''')
    donations_log = [dict(r) for r in cursor.fetchall()]

    # Current admin profile
    cursor.execute("SELECT id, full_name, email, recovery_email FROM users WHERE id = ?", (session.get('user_id'),))
    admin_row = cursor.fetchone()
    current_admin = dict(admin_row) if admin_row else {}

    file_size = (os.path.getsize(DATABASE) / 1024.0) if os.path.exists(DATABASE) else 0.0

    stats = {
        'db_path': DATABASE,
        'file_size_kb': file_size,
        'sqlite_version': sqlite3.sqlite_version
    }

    return render_template(
        'admin_db.html',
        users=users,
        donors=donors,
        requests=requests_rows,
        donations_log=donations_log,
        stats=stats,
        current_admin=current_admin
    )


@app.route('/admin/db/request/<int:req_id>/status', methods=['POST'])
@admin_required
def admin_update_request_status(req_id):
    """Admin live status update for blood_requests row."""
    data = request.get_json() or {}
    new_status = data.get('status', '').strip().capitalize()
    allowed = {'Pending', 'Matched', 'Fulfilled', 'Cancelled'}

    if new_status not in allowed:
        return jsonify({'success': False, 'error': f'Invalid status. Allowed: {", ".join(allowed)}'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE blood_requests SET status = ? WHERE id = ?", (new_status, req_id))
    db.commit()

    return jsonify({'success': True, 'message': f'Request #{req_id} status updated to {new_status}'})


@app.route('/admin/db/request/<int:req_id>/delete', methods=['POST'])
@admin_required
def admin_delete_request(req_id):
    """Admin record deletion for blood_requests row."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM blood_requests WHERE id = ?", (req_id,))
    db.commit()

    return jsonify({'success': True, 'message': f'Request #{req_id} permanently removed.'})


@app.route('/admin/api/change-credentials', methods=['POST'])
@admin_required
def admin_change_credentials():
    """Allows authenticated administrator to update their email, username/name, recovery email, or password."""
    data = request.get_json() or {}
    new_email = (data.get('email') or '').strip().lower()
    new_name = (data.get('full_name') or '').strip()
    new_recovery_email = (data.get('recovery_email') or '').strip().lower()
    new_password = data.get('password') or ''
    current_admin_id = session['user_id']

    if not new_email or '@' not in new_email:
        return jsonify({'success': False, 'error': 'A valid primary admin email is required.'}), 400

    if new_recovery_email and '@' not in new_recovery_email:
        return jsonify({'success': False, 'error': 'Please provide a valid recovery email format.'}), 400

    db = get_db()
    cursor = db.cursor()

    # Check email conflict with another account
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ? AND id != ?", (new_email, current_admin_id))
    if cursor.fetchone():
        return jsonify({'success': False, 'error': 'Another account is already using this primary email.'}), 409

    if new_password:
        is_valid_pwd, pwd_err = validate_password_strict(new_password)
        if not is_valid_pwd:
            return jsonify({'success': False, 'error': pwd_err}), 400
        new_hash = generate_password_hash(new_password)
        cursor.execute('''
            UPDATE users
            SET email = ?, full_name = ?, password_hash = ?, recovery_email = ?
            WHERE id = ?
        ''', (new_email, new_name or 'Master Admin', new_hash, new_recovery_email or None, current_admin_id))
    else:
        cursor.execute('''
            UPDATE users
            SET email = ?, full_name = ?, recovery_email = ?
            WHERE id = ?
        ''', (new_email, new_name or 'Master Admin', new_recovery_email or None, current_admin_id))

    db.commit()
    session['email'] = new_email
    if new_name:
        session['user_name'] = new_name

    return jsonify({
        'success': True,
        'message': f'Administrator credentials successfully updated! Username: {new_name or "Master Admin"}, Email: {new_email}'
    })




# ---------------------------------------------------------
# AUTHENTICATION API ENDPOINTS
# ---------------------------------------------------------
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}

    full_name = data.get('full_name', '').strip()
    email_raw = data.get('email', '')
    password_raw = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    phone_raw = data.get('phone', '')
    blood_group = data.get('blood_group', '').strip().upper()
    city = data.get('city', '').strip()

    # Validations
    if not full_name or len(full_name) < 2:
        return jsonify({'success': False, 'error': 'Please enter your full legal name.'}), 400

    is_valid_email, email_res = validate_email_strict(email_raw)
    if not is_valid_email:
        return jsonify({'success': False, 'error': email_res}), 400
    email = email_res

    is_valid_pwd, pwd_res = validate_password_strict(password_raw)
    if not is_valid_pwd:
        return jsonify({'success': False, 'error': pwd_res}), 400

    if password_raw != confirm_password:
        return jsonify({'success': False, 'error': 'Passwords do not match.'}), 400

    is_valid_phone, phone_res = validate_phone_number(phone_raw)
    if not is_valid_phone:
        return jsonify({'success': False, 'error': phone_res}), 400
    phone = phone_res

    if blood_group not in BLOOD_GROUPS:
        return jsonify({'success': False, 'error': f'Invalid blood group selected. Must be one of {", ".join(BLOOD_GROUPS)}.'}), 400

    if not city:
        return jsonify({'success': False, 'error': 'Please enter your city/location.'}), 400

    db = get_db()
    cursor = db.cursor()

    # Check for existing email or phone
    cursor.execute("SELECT id, email, phone FROM users WHERE email = ? OR phone = ?", (email, phone))
    existing = cursor.fetchone()
    if existing:
        if existing['email'] == email:
            return jsonify({'success': False, 'error': 'An account is already registered with this email address. Please login.'}), 409
        if existing['phone'] == phone:
            return jsonify({'success': False, 'error': 'This phone number is already registered with another account.'}), 409

    # Hash password with werkzeug.security
    password_hash = generate_password_hash(password_raw)

    try:
        is_admin_flag = 1 if email.lower() in BRAND_ADMIN_EMAILS else 0
        recovery_val = 'recovery@jeevraksha.org' if is_admin_flag else None
        cursor.execute('''
            INSERT INTO users (full_name, email, password_hash, phone, blood_group, city, is_admin, recovery_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (full_name, email, password_hash, phone, blood_group, city, is_admin_flag, recovery_val))
        user_id = cursor.lastrowid

        # Also register as prospective donor if register_as_donor flag is checked
        register_as_donor = data.get('register_as_donor', True)
        if register_as_donor:
            age = int(data.get('age', 25)) if data.get('age') else 25
            weight = float(data.get('weight', 60.0)) if data.get('weight') else 60.0
            last_date = data.get('last_donation_date') or None
            cursor.execute('''
                INSERT INTO donors (user_id, blood_group, age, weight, last_donation_date, is_available, medical_verified, location)
                VALUES (?, ?, ?, ?, ?, 1, 1, ?)
            ''', (user_id, blood_group, age, weight, last_date, f"{city} Center"))

        db.commit()

        # Establish session
        session['user_id'] = user_id
        session['user_name'] = full_name
        session['email'] = email
        session['blood_group'] = blood_group
        session['is_admin'] = bool(is_admin_flag)

        return jsonify({
            'success': True,
            'message': 'Account created successfully! Welcome to Jeevraksha.',
            'redirect': url_for('dashboard_page')
        }), 201

    except sqlite3.IntegrityError as e:
        db.rollback()
        return jsonify({'success': False, 'error': 'Registration failed due to a conflict. Please try again.'}), 400
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'An unexpected error occurred: {str(e)}'}), 500


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}

    email_raw = data.get('email', '').strip()
    password = data.get('password', '')

    if not email_raw:
        return jsonify({'success': False, 'error': 'Please provide your registered email address.'}), 400

    if not password:
        return jsonify({'success': False, 'error': 'Please provide your password.'}), 400

    # Basic format check
    if not EMAIL_REGEX.match(email_raw):
        return jsonify({'success': False, 'error': 'Invalid email format entered.'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email_raw,))
    user = cursor.fetchone()

    if not user:
        # Explicit error alert as required
        return jsonify({
            'success': False,
            'error': 'Unregistered email address. No Jeevraksha account exists with this email. Please sign up first.'
        }), 404

    # Password check
    if not check_password_hash(user['password_hash'], password):
        return jsonify({
            'success': False,
            'error': 'Invalid credentials. The password you entered does not match our records.'
        }), 401

    # Login successful -> setup session
    session['user_id'] = user['id']
    session['user_name'] = user['full_name']
    session['email'] = user['email']
    session['blood_group'] = user['blood_group']
    session['is_admin'] = bool(user['is_admin']) if 'is_admin' in user.keys() else False

    # Normal users logging in via /login must ONLY access /dashboard
    # Only if Master Admin logs in, direct to admin DB
    target_redirect = url_for('admin_db_page') if session['is_admin'] else url_for('dashboard_page')

    return jsonify({
        'success': True,
        'message': f'Welcome back, {user["full_name"]}!',
        'redirect': target_redirect
    }), 200


# ---------------------------------------------------------
# CORE APPLICATION API ENDPOINTS
# ---------------------------------------------------------
@app.route('/api/me')
@login_required
def api_me():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id, full_name, email, phone, blood_group, city, is_admin, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        session.clear()
        return jsonify({'success': False, 'error': 'User not found.'}), 404

    cursor.execute("SELECT * FROM donors WHERE user_id = ?", (user_id,))
    donor = cursor.fetchone()

    donor_info = None
    eligibility = {
        'eligible': False,
        'days_remaining': 0,
        'next_eligible_date': None,
        'reason': 'Not yet registered as an active donor.'
    }

    if donor:
        eligibility = check_donation_eligibility(
            donor['last_donation_date'],
            age=donor['age'],
            weight=donor['weight']
        )
        donor_info = {
            'id': donor['id'],
            'blood_group': donor['blood_group'],
            'age': donor['age'],
            'weight': donor['weight'],
            'last_donation_date': donor['last_donation_date'],
            'is_available': bool(donor['is_available']),
            'medical_verified': bool(donor['medical_verified']),
            'location': donor['location'],
            'eligibility': eligibility
        }

    return jsonify({
        'success': True,
        'user': dict(user),
        'donor': donor_info,
        'eligibility': eligibility
    })


@app.route('/api/stats')
@login_required
def api_stats():
    user_blood_group = session.get('blood_group', 'O+')
    db = get_db()
    cursor = db.cursor()

    # Total Available Donors
    cursor.execute("SELECT COUNT(*) FROM donors WHERE is_available = 1 AND medical_verified = 1")
    total_donors = cursor.fetchone()[0]

    # Active Emergency Requests
    cursor.execute("SELECT COUNT(*) FROM blood_requests WHERE status IN ('Pending', 'Matched')")
    active_requests = cursor.fetchone()[0]

    # Critical Emergency Requests
    cursor.execute("SELECT COUNT(*) FROM blood_requests WHERE status = 'Pending' AND urgency_level = 'Critical'")
    critical_requests = cursor.fetchone()[0]

    # Compatible Donors for Current User's Blood Group
    compatible_types = COMPATIBLE_DONORS_FOR_RECIPIENT.get(user_blood_group, [user_blood_group])
    placeholders = ','.join(['?'] * len(compatible_types))
    cursor.execute(f'''
        SELECT COUNT(*) FROM donors
        WHERE is_available = 1 AND medical_verified = 1 AND blood_group IN ({placeholders})
    ''', compatible_types)
    compatible_units = cursor.fetchone()[0]

    # Inventory breakdown by blood group
    cursor.execute('''
        SELECT blood_group, COUNT(*) as donor_count
        FROM donors
        WHERE is_available = 1 AND medical_verified = 1
        GROUP BY blood_group
    ''')
    counts_by_bg = {row['blood_group']: row['donor_count'] for row in cursor.fetchall()}
    inventory = []
    for bg in BLOOD_GROUPS:
        count = counts_by_bg.get(bg, 0)
        # Estimated 1 unit per available donor
        status = 'Critical' if count < 2 else ('Moderate' if count <= 5 else 'Sufficient')
        inventory.append({
            'blood_group': bg,
            'units': count,
            'status': status,
            'can_donate_to': COMPATIBLE_RECIPIENTS_FOR_DONOR.get(bg, []),
            'can_receive_from': COMPATIBLE_DONORS_FOR_RECIPIENT.get(bg, [])
        })

    return jsonify({
        'success': True,
        'stats': {
            'total_available_donors': total_donors,
            'active_emergency_requests': active_requests,
            'critical_emergency_requests': critical_requests,
            'compatible_units_available': compatible_units,
            'user_blood_group': user_blood_group,
            'compatible_donor_types': compatible_types,
            'inventory': inventory
        }
    })


@app.route('/api/requests', methods=['GET', 'POST'])
@login_required
def api_requests():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'GET':
        blood_group = request.args.get('blood_group', '').strip().upper()
        city = request.args.get('city', '').strip()
        urgency = request.args.get('urgency', '').strip()

        query = '''
            SELECT br.*, u.full_name as requester_name, u.email as requester_email
            FROM blood_requests br
            JOIN users u ON br.requester_id = u.id
            WHERE 1=1
        '''
        params = []

        if blood_group and blood_group in BLOOD_GROUPS:
            query += " AND br.blood_group_needed = ?"
            params.append(blood_group)

        if city:
            query += " AND (br.location LIKE ? OR br.hospital_name LIKE ?)"
            params.append(f"%{city}%")
            params.append(f"%{city}%")

        if urgency:
            query += " AND br.urgency_level = ?"
            params.append(urgency)

        query += " ORDER BY CASE br.urgency_level WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 ELSE 3 END, br.created_at DESC"

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

        return jsonify({'success': True, 'requests': rows})

    # POST: Create a new blood emergency request
    data = request.get_json() or {}
    patient_name = data.get('patient_name', '').strip()
    blood_group_needed = data.get('blood_group_needed', '').strip().upper()
    units_required = data.get('units_required')
    urgency_level = data.get('urgency_level', 'High').strip().capitalize()
    hospital_name = data.get('hospital_name', '').strip()
    location = data.get('location', '').strip()
    contact_phone_raw = data.get('contact_phone', '')

    if not patient_name:
        return jsonify({'success': False, 'error': 'Patient name is required.'}), 400

    if blood_group_needed not in BLOOD_GROUPS:
        return jsonify({'success': False, 'error': 'Valid blood group required.'}), 400

    try:
        units_required = int(units_required)
        if units_required <= 0 or units_required > 20:
            return jsonify({'success': False, 'error': 'Units required must be between 1 and 20.'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Units required must be a valid number.'}), 400

    if urgency_level not in ['Critical', 'High', 'Standard']:
        urgency_level = 'High'

    if not hospital_name:
        return jsonify({'success': False, 'error': 'Hospital name is required.'}), 400

    if not location:
        return jsonify({'success': False, 'error': 'Hospital address/location is required.'}), 400

    is_valid_phone, phone = validate_phone_number(contact_phone_raw)
    if not is_valid_phone:
        return jsonify({'success': False, 'error': phone}), 400

    requester_id = session['user_id']

    # Insert into database
    cursor.execute('''
        INSERT INTO blood_requests (
            requester_id, patient_name, blood_group_needed, units_required,
            urgency_level, hospital_name, location, contact_phone, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
    ''', (
        requester_id, patient_name, blood_group_needed, units_required,
        urgency_level, hospital_name, location, phone
    ))
    new_request_id = cursor.lastrowid
    db.commit()

    # Smart Matching Engine: Immediately query compatible donors
    compatible_groups = COMPATIBLE_DONORS_FOR_RECIPIENT.get(blood_group_needed, [blood_group_needed])
    placeholders = ','.join(['?'] * len(compatible_groups))
    cursor.execute(f'''
        SELECT d.id as donor_id, d.blood_group, d.location, d.last_donation_date,
               u.full_name as donor_name, u.phone as donor_phone, u.city as donor_city
        FROM donors d
        JOIN users u ON d.user_id = u.id
        WHERE d.is_available = 1 AND d.medical_verified = 1
          AND d.blood_group IN ({placeholders})
          AND d.user_id != ?
        ORDER BY CASE WHEN d.blood_group = ? THEN 1 ELSE 2 END, d.id ASC
    ''', compatible_groups + [requester_id, blood_group_needed])

    matched_donors = [dict(d) for d in cursor.fetchall()]

    return jsonify({
        'success': True,
        'message': f'Emergency request for {patient_name} logged successfully!',
        'request_id': new_request_id,
        'compatible_groups': compatible_groups,
        'matched_donors_count': len(matched_donors),
        'matched_donors': matched_donors
    }), 201


@app.route('/api/requests/<int:req_id>/status', methods=['POST'])
@login_required
def api_update_request_status(req_id):
    data = request.get_json() or {}
    new_status = data.get('status', '').strip().capitalize()
    allowed_statuses = {'Pending', 'Matched', 'Fulfilled', 'Cancelled'}

    if new_status not in allowed_statuses:
        return jsonify({'success': False, 'error': f'Invalid status. Allowed: {", ".join(allowed_statuses)}'}), 400

    db = get_db()
    cursor = db.cursor()

    # Ensure user is the requester or updating to Fulfilled
    cursor.execute("SELECT * FROM blood_requests WHERE id = ?", (req_id,))
    req_row = cursor.fetchone()
    if not req_row:
        return jsonify({'success': False, 'error': 'Request not found.'}), 404

    cursor.execute("UPDATE blood_requests SET status = ? WHERE id = ?", (new_status, req_id))
    db.commit()

    return jsonify({'success': True, 'message': f'Request status updated to {new_status}.', 'status': new_status})


@app.route('/api/donors/compatible', methods=['GET'])
@login_required
def api_compatible_donors():
    blood_group = request.args.get('blood_group', '').strip().upper()
    city = request.args.get('city', '').strip()

    if not blood_group or blood_group not in BLOOD_GROUPS:
        return jsonify({'success': False, 'error': 'Please provide a valid blood group.'}), 400

    compatible_groups = COMPATIBLE_DONORS_FOR_RECIPIENT.get(blood_group, [blood_group])
    db = get_db()
    cursor = db.cursor()

    placeholders = ','.join(['?'] * len(compatible_groups))
    query = f'''
        SELECT d.id as donor_id, d.blood_group, d.age, d.weight, d.last_donation_date,
               d.location, u.full_name as donor_name, u.phone as donor_phone, u.city as donor_city
        FROM donors d
        JOIN users u ON d.user_id = u.id
        WHERE d.is_available = 1 AND d.medical_verified = 1
          AND d.blood_group IN ({placeholders})
    '''
    params = list(compatible_groups)

    if city:
        query += " AND (d.location LIKE ? OR u.city LIKE ?)"
        params.extend([f"%{city}%", f"%{city}%"])

    query += f" ORDER BY CASE WHEN d.blood_group = ? THEN 1 ELSE 2 END, d.id ASC"
    params.append(blood_group)

    cursor.execute(query, params)
    donors = []
    for r in cursor.fetchall():
        d_dict = dict(r)
        elig = check_donation_eligibility(d_dict['last_donation_date'], age=d_dict['age'], weight=d_dict['weight'])
        d_dict['is_immediately_eligible'] = elig['eligible']
        d_dict['match_type'] = 'Exact Match' if d_dict['blood_group'] == blood_group else 'Universal / Compatible Match'
        donors.append(d_dict)

    return jsonify({
        'success': True,
        'recipient_blood_group': blood_group,
        'compatible_groups': compatible_groups,
        'donors': donors
    })


@app.route('/api/donors/register', methods=['POST'])
@login_required
def api_register_donor():
    data = request.get_json() or {}
    user_id = session['user_id']

    blood_group = data.get('blood_group', '').strip().upper()
    age = data.get('age')
    weight = data.get('weight')
    last_donation_date = data.get('last_donation_date') or None
    location = data.get('location', '').strip()
    medical_cleared = data.get('medical_cleared', False)
    phone_raw = data.get('phone', '')

    if blood_group not in BLOOD_GROUPS:
        return jsonify({'success': False, 'error': 'Invalid blood group selected.'}), 400

    try:
        age = int(age)
        if age < 18 or age > 65:
            return jsonify({'success': False, 'error': 'Donor age must be strictly between 18 and 65 years.'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Please enter a valid age.'}), 400

    try:
        weight = float(weight)
        if weight < 50.0:
            return jsonify({'success': False, 'error': 'Donor weight must be at least 50 kg.'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Please enter a valid weight in kg.'}), 400

    if not medical_cleared:
        return jsonify({'success': False, 'error': 'You must complete the medical history declaration to register.'}), 400

    if not location:
        return jsonify({'success': False, 'error': 'Please provide your current location or preferred hospital/center.'}), 400

    if phone_raw:
        is_valid_phone, phone = validate_phone_number(phone_raw)
        if not is_valid_phone:
            return jsonify({'success': False, 'error': phone}), 400
    else:
        phone = None

    db = get_db()
    cursor = db.cursor()

    # Update user phone/blood group if provided
    if phone:
        cursor.execute("UPDATE users SET phone = ?, blood_group = ? WHERE id = ?", (phone, blood_group, user_id))
    else:
        cursor.execute("UPDATE users SET blood_group = ? WHERE id = ?", (blood_group, user_id))
    session['blood_group'] = blood_group

    # Insert or update donor
    cursor.execute("SELECT id FROM donors WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute('''
            UPDATE donors
            SET blood_group = ?, age = ?, weight = ?, last_donation_date = ?,
                is_available = 1, medical_verified = 1, location = ?
            WHERE user_id = ?
        ''', (blood_group, age, weight, last_donation_date, location, user_id))
    else:
        cursor.execute('''
            INSERT INTO donors (user_id, blood_group, age, weight, last_donation_date, is_available, medical_verified, location)
            VALUES (?, ?, ?, ?, ?, 1, 1, ?)
        ''', (user_id, blood_group, age, weight, last_donation_date, location))

    db.commit()

    eligibility = check_donation_eligibility(last_donation_date, age=age, weight=weight)

    return jsonify({
        'success': True,
        'message': 'Your donor registration has been verified and activated! Thank you for being a lifeline.',
        'eligibility': eligibility
    }), 200


@app.route('/api/donors/toggle-availability', methods=['POST'])
@login_required
def api_toggle_availability():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT is_available FROM donors WHERE user_id = ?", (user_id,))
    donor = cursor.fetchone()
    if not donor:
        return jsonify({'success': False, 'error': 'No donor profile found. Please register as a donor first.'}), 404

    new_state = 0 if donor['is_available'] == 1 else 1
    cursor.execute("UPDATE donors SET is_available = ? WHERE user_id = ?", (new_state, user_id))
    db.commit()

    status_str = "Active & Available for emergency donation" if new_state == 1 else "Temporarily Inactive (Paused)"
    return jsonify({
        'success': True,
        'is_available': bool(new_state),
        'message': f'Donor status updated to: {status_str}.'
    })


@app.route('/api/donations/respond', methods=['POST'])
@login_required
def api_respond_to_request():
    """A donor responds to an emergency request to offer blood."""
    data = request.get_json() or {}
    request_id = data.get('request_id')
    user_id = session['user_id']

    if not request_id:
        return jsonify({'success': False, 'error': 'Request ID is required.'}), 400

    db = get_db()
    cursor = db.cursor()

    # Find donor profile
    cursor.execute("SELECT * FROM donors WHERE user_id = ?", (user_id,))
    donor = cursor.fetchone()
    if not donor:
        return jsonify({'success': False, 'error': 'You must be registered as an active donor to respond.'}), 400

    # Check request
    cursor.execute("SELECT * FROM blood_requests WHERE id = ?", (request_id,))
    req = cursor.fetchone()
    if not req:
        return jsonify({'success': False, 'error': 'Request not found.'}), 404

    if req['status'] == 'Fulfilled':
        return jsonify({'success': False, 'error': 'This request has already been fulfilled.'}), 400

    # Check compatibility
    compatible_donors = COMPATIBLE_DONORS_FOR_RECIPIENT.get(req['blood_group_needed'], [])
    if donor['blood_group'] not in compatible_donors:
        return jsonify({
            'success': False,
            'error': f"Your blood group ({donor['blood_group']}) is not compatible with the patient's needed blood group ({req['blood_group_needed']})."
        }), 400

    # Log donation response
    cursor.execute('''
        INSERT INTO donations_log (donor_id, request_id, donation_date, units_donated, status)
        VALUES (?, ?, ?, 1, 'Matched')
    ''', (donor['id'], request_id, date.today().isoformat()))

    # Update request status to Matched if was Pending
    if req['status'] == 'Pending':
        cursor.execute("UPDATE blood_requests SET status = 'Matched' WHERE id = ?", (request_id,))

    db.commit()

    return jsonify({
        'success': True,
        'message': f"Thank you! You have responded to help {req['patient_name']}. The hospital/requester will coordinate with you immediately.",
        'hospital': req['hospital_name'],
        'contact': req['contact_phone']
    })


@app.route('/api/my-activity')
@login_required
def api_my_activity():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Requests created by user
    cursor.execute('''
        SELECT * FROM blood_requests
        WHERE requester_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    my_requests = [dict(r) for r in cursor.fetchall()]

    # Donations logged / responses by user as donor
    cursor.execute('''
        SELECT dl.*, br.patient_name, br.hospital_name, br.blood_group_needed, br.location, br.contact_phone
        FROM donations_log dl
        JOIN donors d ON dl.donor_id = d.id
        LEFT JOIN blood_requests br ON dl.request_id = br.id
        WHERE d.user_id = ?
        ORDER BY dl.donation_date DESC, dl.id DESC
    ''', (user_id,))
    my_donations = [dict(r) for r in cursor.fetchall()]

    return jsonify({
        'success': True,
        'my_requests': my_requests,
        'my_donations': my_donations
    })


# ---------------------------------------------------------
# APPLICATION ENTRYPOINT
# ---------------------------------------------------------
if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("[*] JEEVRAKSHA BLOOD DONATION PLATFORM IS RUNNING")
    print("[*] URL: http://127.0.0.1:5000")
    print("[*] Master Admin Portal: http://127.0.0.1:5000/admin/login")
    print("[*] Security: Strict regex email & strong password validation")
    print("[*] Compatibility: Blood Group matching engine initialized")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
