#!/usr/bin/env python3
"""
Jeevraksha Admin Management Utility
Allows updating administrator username, email, password, and recovery email.
Usage:
  python change_admin.py
  python change_admin.py --email admin@jeevraksha.org --password NewPass#2026 --name "Dr. Arjun Mehta" --recovery-email backup@jeevraksha.org
  python change_admin.py --promote user@domain.com
  python change_admin.py --list
"""

import sys
import os
import argparse
import sqlite3
import getpass
from werkzeug.security import generate_password_hash

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def prompt_password_masked(prompt="Enter password: "):
    """
    Displays asterisks '*' in terminal as the user types on Windows (using msvcrt),
    with graceful fallback to getpass if running without a tty or on other platforms.
    """
    print(prompt, end='', flush=True)
    if os.name == 'nt' and sys.stdin.isatty():
        try:
            import msvcrt
            pwd = []
            while True:
                ch = msvcrt.getch()
                if ch in (b'\r', b'\n'):
                    print()
                    break
                elif ch == b'\x03':  # Ctrl+C
                    print()
                    raise KeyboardInterrupt
                elif ch in (b'\x00', b'\xe0'):  # Arrow keys / special key prefix
                    msvcrt.getch()
                    continue
                elif ch == b'\x08':  # Backspace
                    if pwd:
                        pwd.pop()
                        sys.stdout.write('\b \b')
                        sys.stdout.flush()
                else:
                    try:
                        char = ch.decode('utf-8', errors='ignore')
                        if char and char.isprintable():
                            pwd.append(char)
                            sys.stdout.write('*')
                            sys.stdout.flush()
                    except Exception:
                        pass
            return "".join(pwd).strip()
        except Exception:
            pass

    return getpass.getpass("").strip()

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jeevraksha.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # Ensure recovery_email column exists
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'recovery_email' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN recovery_email TEXT")
        conn.commit()
    return conn

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least 1 uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least 1 lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least 1 number."
    special = "!@#$%^&*()_+-=[]{};':\"|,.<>/?"
    if not any(c in special for c in password):
        return False, "Password must contain at least 1 special character."
    return True, ""

def change_or_create_admin(email, password, full_name="Jeevraksha Master Admin", recovery_email="recovery@jeevraksha.org"):
    email = email.strip().lower()
    recovery_email = recovery_email.strip().lower() if recovery_email else None
    val, err = validate_password(password)
    if not val:
        print(f"❌ Error: {err}")
        return False

    conn = get_db()
    cursor = conn.cursor()

    # Check if user with this email already exists
    cursor.execute("SELECT id, full_name, email, is_admin FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()

    password_hash = generate_password_hash(password)

    if user:
        cursor.execute('''
            UPDATE users
            SET is_admin = 1, password_hash = ?, full_name = ?, recovery_email = ?
            WHERE id = ?
        ''', (password_hash, full_name or user['full_name'], recovery_email, user['id']))
        print(f"✅ Existing user '{email}' successfully updated with username '{full_name}', new password, and recovery email '{recovery_email}'!")
    else:
        cursor.execute('''
            INSERT INTO users (full_name, email, password_hash, phone, blood_group, city, is_admin, recovery_email)
            VALUES (?, ?, ?, '9999900000', 'O-', 'National HQ', 1, ?)
        ''', (full_name, email, password_hash, recovery_email))
        print(f"✅ New Master Administrator '{email}' ('{full_name}') successfully created with recovery email '{recovery_email}'!")

    conn.commit()
    conn.close()
    return True

def promote_user(email, recovery_email=None):
    email = email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, is_admin FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()

    if not user:
        print(f"❌ No user found with email '{email}'.")
        conn.close()
        return False

    if recovery_email:
        cursor.execute("UPDATE users SET is_admin = 1, recovery_email = ? WHERE id = ?", (recovery_email.strip().lower(), user['id']))
    else:
        cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user['id'],))

    conn.commit()
    conn.close()
    print(f"✅ User '{user['full_name']}' ({email}) has been promoted to Administrator.")
    return True

def list_admins():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, recovery_email, phone, created_at FROM users WHERE is_admin = 1")
    admins = cursor.fetchall()
    conn.close()

    print("\n🛡️ Current Jeevraksha Administrators:")
    print("-" * 80)
    for a in admins:
        rec = a['recovery_email'] or "Not Configured"
        print(f"• ID #{a['id']}: {a['full_name']} | Login: {a['email']} | Recovery: {rec}")
    print("-" * 80 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Jeevraksha Administrator Management")
    parser.add_argument("--email", help="New or existing administrator email")
    parser.add_argument("--password", help="New administrator password")
    parser.add_argument("--name", help="Administrator username / full name", default="Jeevraksha Master Admin")
    parser.add_argument("--recovery-email", help="Administrator recovery email", default="recovery@jeevraksha.org")
    parser.add_argument("--promote", help="Email of an existing user to promote to administrator")
    parser.add_argument("--list", action="store_true", help="List all current administrators")

    args = parser.parse_args()

    if args.list:
        list_admins()
        return

    if args.promote:
        promote_user(args.promote, args.recovery_email)
        return

    if args.email and args.password:
        change_or_create_admin(args.email, args.password, args.name, args.recovery_email)
        return

    # Interactive mode
    print("=" * 65)
    print("🩸 JEEVRAKSHA - ADMINISTRATOR CREDENTIALS & RECOVERY MANAGER")
    print("=" * 65)
    list_admins()

    email = input("Enter administrator primary login email: ").strip()
    if not email or "@" not in email:
        print("❌ Invalid email format.")
        sys.exit(1)

    name = input("Enter administrator username / full name [Jeevraksha Master Admin]: ").strip()
    if not name:
        name = "Jeevraksha Master Admin"

    recovery_email = input("Enter recovery email address [recovery@jeevraksha.org]: ").strip()
    if not recovery_email:
        recovery_email = "recovery@jeevraksha.org"

    print("\nℹ️  Password Input: Visual asterisks (*) will display as you type. Press Enter when finished.")
    password = prompt_password_masked("Enter new strong password: ")
    confirm = prompt_password_masked("Confirm new password: ")

    if password != confirm:
        print("❌ Passwords do not match.")
        sys.exit(1)

    change_or_create_admin(email, password, name, recovery_email)

if __name__ == "__main__":
    main()
