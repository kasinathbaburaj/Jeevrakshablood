import unittest
import json
import time
from datetime import date, timedelta
from app import app, init_db, COMPATIBLE_DONORS_FOR_RECIPIENT, validate_email_strict, validate_password_strict

class JeevrakshaTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-lifeline-2026'
        init_db()

    def setUp(self):
        self.client = app.test_client()

    def test_01_email_validation(self):
        # Invalid syntax
        valid, _ = validate_email_strict("plainaddress")
        self.assertFalse(valid)
        valid, _ = validate_email_strict("user@domain")
        self.assertFalse(valid)

        # Common dummy / disposable emails
        valid, _ = validate_email_strict("test@test.com")
        self.assertFalse(valid)
        valid, _ = validate_email_strict("abc@gmail.com")
        self.assertFalse(valid)
        valid, _ = validate_email_strict("doctor@mailinator.com")
        self.assertFalse(valid)
        valid, _ = validate_email_strict("donor@tempmail.com")
        self.assertFalse(valid)

        # Legitimate emails
        valid, res = validate_email_strict("vikram.mehta@apollohospitals.org")
        self.assertTrue(valid)
        self.assertEqual(res, "vikram.mehta@apollohospitals.org")

    def test_02_password_validation(self):
        # Short length
        valid, _ = validate_password_strict("P@ss1")
        self.assertFalse(valid)
        # No uppercase
        valid, _ = validate_password_strict("lifeline#2026")
        self.assertFalse(valid)
        # No lowercase
        valid, _ = validate_password_strict("LIFELINE#2026")
        self.assertFalse(valid)
        # No digit
        valid, _ = validate_password_strict("Lifeline#Secret")
        self.assertFalse(valid)
        # No special char
        valid, _ = validate_password_strict("Lifeline2026Pass")
        self.assertFalse(valid)
        # Valid strong password
        valid, _ = validate_password_strict("Lifeline#2026")
        self.assertTrue(valid)

    def test_03_login_unregistered_email(self):
        res = self.client.post('/api/auth/login', json={
            'email': 'nobody.exists@somewhere.org',
            'password': 'Lifeline#2026'
        })
        data = res.get_json()
        self.assertEqual(res.status_code, 404)
        self.assertFalse(data['success'])
        self.assertIn("Unregistered email", data['error'])

    def test_04_login_wrong_password(self):
        # Seeded user
        res = self.client.post('/api/auth/login', json={
            'email': 'aarav.sharma@jeevraksha.org',
            'password': 'WrongPassword#999'
        })
        data = res.get_json()
        self.assertEqual(res.status_code, 401)
        self.assertFalse(data['success'])
        self.assertIn("Invalid credentials", data['error'])

    def test_05_successful_login_and_session(self):
        res = self.client.post('/api/auth/login', json={
            'email': 'aarav.sharma@jeevraksha.org',
            'password': 'Lifeline#2026'
        })
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn("/dashboard", data['redirect'])

        # Check /api/me with session
        me_res = self.client.get('/api/me')
        me_data = me_res.get_json()
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_data['user']['email'], 'aarav.sharma@jeevraksha.org')

    def test_06_register_new_user(self):
        new_email = f"test.donor.{int(time.time()*1000)}@lifeline.org"
        phone_num = f"98{int(time.time())%100000000:08d}"
        res = self.client.post('/api/auth/register', json={
            'full_name': 'Kavya Sengupta',
            'email': new_email,
            'password': 'Lifeline#2026',
            'confirm_password': 'Lifeline#2026',
            'blood_group': 'B+',
            'phone': phone_num,
            'city': 'Kolkata',
            'register_as_donor': True,
            'age': 28,
            'weight': 62.0
        })
        data = res.get_json()
        self.assertEqual(res.status_code, 201)
        self.assertTrue(data['success'])

        # Duplicate register check
        dup_res = self.client.post('/api/auth/register', json={
            'full_name': 'Kavya Sengupta',
            'email': new_email,
            'password': 'Lifeline#2026',
            'confirm_password': 'Lifeline#2026',
            'blood_group': 'B+',
            'phone': phone_num,
            'city': 'Kolkata'
        })
        self.assertEqual(dup_res.status_code, 409)

    def test_07_compatibility_engine(self):
        # Recipient O- can only receive from O-
        self.assertEqual(COMPATIBLE_DONORS_FOR_RECIPIENT['O-'], ['O-'])
        # Recipient AB+ can receive from all 8 groups
        self.assertEqual(len(COMPATIBLE_DONORS_FOR_RECIPIENT['AB+']), 8)
        # Recipient A+ can receive from A+, A-, O+, O-
        self.assertEqual(set(COMPATIBLE_DONORS_FOR_RECIPIENT['A+']), {'A+', 'A-', 'O+', 'O-'})

        # Test API endpoint
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['blood_group'] = 'A+'

        res = self.client.get('/api/donors/compatible?blood_group=A%2B')
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('A+', data['compatible_groups'])
        self.assertIn('O-', data['compatible_groups'])

    def test_08_emergency_request_and_smart_match(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['blood_group'] = 'O+'

        res = self.client.post('/api/requests', json={
            'patient_name': 'Ramesh Tandon',
            'blood_group_needed': 'O-',
            'units_required': 2,
            'urgency_level': 'Critical',
            'hospital_name': 'Apollo Indraprastha',
            'location': 'Sarita Vihar, Delhi',
            'contact_phone': '9899123456'
        })
        data = res.get_json()
        self.assertEqual(res.status_code, 201)
        self.assertTrue(data['success'])
        self.assertIn('matched_donors_count', data)
        self.assertEqual(data['compatible_groups'], ['O-'])

    def test_09_donor_registration_cooldown_and_restrictions(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['blood_group'] = 'O+'

        # Underage restriction
        res_age = self.client.post('/api/donors/register', json={
            'blood_group': 'O+',
            'age': 16,
            'weight': 60,
            'medical_cleared': True,
            'location': 'Mumbai'
        })
        self.assertEqual(res_age.status_code, 400)
        self.assertIn("18 and 65", res_age.get_json()['error'])

        # Underweight restriction
        res_wt = self.client.post('/api/donors/register', json={
            'blood_group': 'O+',
            'age': 25,
            'weight': 44.0,
            'medical_cleared': True,
            'location': 'Mumbai'
        })
        self.assertEqual(res_wt.status_code, 400)
        self.assertIn("50 kg", res_wt.get_json()['error'])

        # Valid registration with cooldown
        ten_days_ago = (date.today() - timedelta(days=10)).isoformat()
        res_valid = self.client.post('/api/donors/register', json={
            'blood_group': 'O+',
            'age': 29,
            'weight': 68.0,
            'last_donation_date': ten_days_ago,
            'medical_cleared': True,
            'location': 'Lilavati Hospital, Mumbai',
            'phone': '9876543210'
        })
        data_valid = res_valid.get_json()
        self.assertEqual(res_valid.status_code, 200)
        self.assertFalse(data_valid['eligibility']['eligible'])
        self.assertIn("80 day(s) remaining", data_valid['eligibility']['reason'])

    def test_10_admin_security_and_role_separation(self):
        # 1. Unauthenticated visit to /admin/db redirects to /admin/login
        unauth_res = self.client.get('/admin/db')
        self.assertEqual(unauth_res.status_code, 302)
        self.assertIn('/admin/login', unauth_res.headers['Location'])

        # 2. Login as regular user (aarav.sharma@jeevraksha.org)
        user_login = self.client.post('/api/auth/login', json={
            'email': 'aarav.sharma@jeevraksha.org',
            'password': 'Lifeline#2026'
        })
        self.assertEqual(user_login.status_code, 200)
        self.assertIn('/dashboard', user_login.get_json()['redirect'])

        # Verify normal user dashboard does NOT have the admin button
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertNotIn(b'Backend DB View', dash_res.data)
        self.assertNotIn(b'Admin DB', dash_res.data)

        # 3. Normal user attempts to access /admin/db directly in URL
        blocked_res = self.client.get('/admin/db')
        self.assertEqual(blocked_res.status_code, 403)
        self.assertIn('access_denied=1', blocked_res.headers['Location'])

        # Normal user attempts to call admin API
        blocked_api = self.client.post('/admin/db/request/1/status', json={'status': 'Fulfilled'})
        self.assertEqual(blocked_api.status_code, 403)
        self.assertIn('Administrator privileges required', blocked_api.get_json()['error'])

        # 4. Normal user attempts to login through /admin/login
        admin_fail = self.client.post('/admin/login', json={
            'email': 'aarav.sharma@jeevraksha.org',
            'password': 'Lifeline#2026'
        })
        self.assertEqual(admin_fail.status_code, 403)
        self.assertIn('does not possess administrator privileges', admin_fail.get_json()['error'])

        # 5. Master Admin login at /admin/login
        admin_login = self.client.post('/admin/login', json={
            'email': 'admin@jeevraksha.org',
            'password': 'Admin@Jeevraksha2026'
        })
        self.assertEqual(admin_login.status_code, 200)
        self.assertTrue(admin_login.get_json()['success'])
        self.assertIn('/admin/db', admin_login.get_json()['redirect'])

        # 6. Master Admin accesses /admin/db successfully
        admin_page = self.client.get('/admin/db')
        self.assertEqual(admin_page.status_code, 200)
        self.assertIn(b'Master DB Console', admin_page.data)
        self.assertIn(b'admin@jeevraksha.org', admin_page.data)
        self.assertIn(b'Admin Logout', admin_page.data)
        self.assertIn(b'table-users', admin_page.data)

        # 7. Master Admin updates status & deletes request
        status_res = self.client.post('/admin/db/request/1/status', json={'status': 'Fulfilled'})
        self.assertEqual(status_res.status_code, 200)
        self.assertTrue(status_res.get_json()['success'])

        del_res = self.client.post('/admin/db/request/1/delete')
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.get_json()['success'])

        # 8. Admin logout
        logout_res = self.client.get('/admin/logout')
        self.assertEqual(logout_res.status_code, 302)
        self.assertIn('/admin/login', logout_res.headers['Location'])

    def test_11_admin_recovery_and_password_reset(self):
        # 1. GET /admin/reset-password loads page
        get_reset = self.client.get('/admin/reset-password')
        self.assertEqual(get_reset.status_code, 200)
        self.assertIn(b'Admin Password & Account Recovery', get_reset.data)
        self.assertIn(b'Recovery Email', get_reset.data)

        # 2. Test missing fields
        fail_missing = self.client.post('/admin/reset-password', json={
            'admin_email': 'admin@jeevraksha.org',
            'recovery_email': '',
            'new_password': 'NewPassword#2026',
            'confirm_password': 'NewPassword#2026'
        })
        self.assertEqual(fail_missing.status_code, 400)

        # 3. Test password mismatch
        fail_mismatch = self.client.post('/admin/reset-password', json={
            'admin_email': 'admin@jeevraksha.org',
            'recovery_email': 'recovery@jeevraksha.org',
            'new_password': 'NewPassword#2026',
            'confirm_password': 'Different#2026'
        })
        self.assertEqual(fail_mismatch.status_code, 400)
        self.assertIn('do not match', fail_mismatch.get_json()['error'])

        # 4. Test weak password
        fail_weak = self.client.post('/admin/reset-password', json={
            'admin_email': 'admin@jeevraksha.org',
            'recovery_email': 'recovery@jeevraksha.org',
            'new_password': 'weakpassword',
            'confirm_password': 'weakpassword'
        })
        self.assertEqual(fail_weak.status_code, 400)

        # 5. Test wrong recovery email
        fail_recovery = self.client.post('/admin/reset-password', json={
            'admin_email': 'admin@jeevraksha.org',
            'recovery_email': 'hacker@phishing.com',
            'new_password': 'NewPassword#2026',
            'confirm_password': 'NewPassword#2026'
        })
        self.assertEqual(fail_recovery.status_code, 403)
        self.assertIn('does not match the registered recovery email', fail_recovery.get_json()['error'])

        # 6. Valid password reset with recovery email + update username & recovery email
        success_reset = self.client.post('/admin/reset-password', json={
            'admin_email': 'admin@jeevraksha.org',
            'recovery_email': 'recovery@jeevraksha.org',
            'new_name': 'Chief Executive Admin',
            'new_password': 'ResetSuccess#2026',
            'confirm_password': 'ResetSuccess#2026',
            'new_recovery_email': 'chief.recovery@jeevraksha.org'
        })
        self.assertEqual(success_reset.status_code, 200)
        self.assertTrue(success_reset.get_json()['success'])

        # 7. Old password no longer works
        old_login = self.client.post('/admin/login', json={
            'email': 'admin@jeevraksha.org',
            'password': 'Admin@Jeevraksha2026'
        })
        self.assertEqual(old_login.status_code, 401)

        # 8. New password works
        new_login = self.client.post('/admin/login', json={
            'email': 'admin@jeevraksha.org',
            'password': 'ResetSuccess#2026'
        })
        self.assertEqual(new_login.status_code, 200)
        self.assertTrue(new_login.get_json()['success'])

        # 9. In session: Change credentials via Admin DB Modal API
        cred_res = self.client.post('/admin/api/change-credentials', json={
            'full_name': 'Jeevraksha Master Admin',
            'email': 'admin@jeevraksha.org',
            'recovery_email': 'recovery@jeevraksha.org',
            'password': 'Admin@Jeevraksha2026'
        })
        self.assertEqual(cred_res.status_code, 200)
        self.assertTrue(cred_res.get_json()['success'])

        # 10. Verify restored password works again
        self.client.get('/admin/logout')
        restored_login = self.client.post('/admin/login', json={
            'email': 'admin@jeevraksha.org',
            'password': 'Admin@Jeevraksha2026'
        })
        self.assertEqual(restored_login.status_code, 200)
        self.assertTrue(restored_login.get_json()['success'])


if __name__ == '__main__':
    unittest.main()
