/**
 * JEEVRAKSHA - Blood Donation & Emergency Receiving Platform
 * Frontend Controller & Real-Time Engine
 */

// --------------------------------------------------------------------------
// GLOBAL STATE & CONSTANTS
// --------------------------------------------------------------------------
let currentUser = null;
let currentDonor = null;
let currentEligibility = null;
let activeRequestBloodFilter = '';
let activeRequestCityFilter = '';
let filterDebounceTimer = null;
let pendingRespondRequestId = null;

const DISPOSABLE_DOMAINS_JS = [
  'test.com', 'example.com', 'fake.com', 'tempmail.com', 'mailinator.com',
  'throwaway.com', 'guerrillamail.com', 'sharklasers.com', '10minutemail.com',
  'yopmail.com', 'trashmail.com', 'temp-mail.org', 'dispostable.com',
  'dummy.com', 'invalid.com', 'mytempemail.com', 'trashmail.net'
];

const DUMMY_EMAILS_JS = [
  'test@test.com', 'abc@gmail.com', '123@123.com', 'admin@admin.com',
  'user@user.com', 'fake@fake.com', 'dummy@dummy.com', 'asdf@asdf.com'
];

// --------------------------------------------------------------------------
// INITIALIZATION ON DOM READY
// --------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // Check if we are on Dashboard or Auth page
  const body = document.body;
  const initialTab = body.dataset.initialTab;

  if (document.getElementById('requestsFeedContainer')) {
    // Authenticated Dashboard Page
    initDashboard(initialTab || 'dashboard');
  } else {
    // Auth Page (Login / Register)
    initAuthPage();
  }

  // Handle browser back/forward buttons
  window.addEventListener('popstate', (e) => {
    if (e.state && e.state.tab) {
      navigateToTab(e.state.tab, null, false);
    }
  });
});

// --------------------------------------------------------------------------
// TOAST NOTIFICATION SYSTEM
// --------------------------------------------------------------------------
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  if (type === 'error') icon = '❌';

  toast.innerHTML = `
    <span style="font-size: 1.1rem;">${icon}</span>
    <div class="toast-message">${escapeHtml(message)}</div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4200);
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// --------------------------------------------------------------------------
// AUTHENTICATION CONTROLLER (LOGIN & REGISTER)
// --------------------------------------------------------------------------
function initAuthPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode');
  if (mode === 'register') {
    switchAuthTab('register');
  }
}

function switchAuthTab(tab) {
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const tabBtnLogin = document.getElementById('tabBtnLogin');
  const tabBtnRegister = document.getElementById('tabBtnRegister');
  const alertBox = document.getElementById('authAlert');

  if (alertBox) {
    alertBox.className = 'alert-banner';
    alertBox.style.display = 'none';
  }

  if (tab === 'register') {
    if (loginForm) loginForm.style.display = 'none';
    if (registerForm) registerForm.style.display = 'block';
    if (tabBtnLogin) tabBtnLogin.classList.remove('active');
    if (tabBtnRegister) tabBtnRegister.classList.add('active');
    history.replaceState(null, '', '/register');
  } else {
    if (registerForm) registerForm.style.display = 'none';
    if (loginForm) loginForm.style.display = 'block';
    if (tabBtnRegister) tabBtnRegister.classList.remove('active');
    if (tabBtnLogin) tabBtnLogin.classList.add('active');
    history.replaceState(null, '', '/login');
  }
}

function showAuthAlert(message, type = 'danger') {
  const alertBox = document.getElementById('authAlert');
  const alertMsg = document.getElementById('alertMessage');
  const alertIcon = document.getElementById('alertIcon');

  if (!alertBox || !alertMsg) return;

  alertBox.className = `alert-banner alert-${type} visible`;
  alertBox.style.display = 'flex';
  alertMsg.textContent = message;
  alertIcon.textContent = type === 'danger' ? '⚠️' : '✅';
  alertBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Strict Real-Time Email Validation
function validateEmailField(input) {
  const val = (input.value || '').trim().toLowerCase();
  const errorEl = document.getElementById(input.id + 'Error');
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (!val) {
    clearFieldValidation(input, errorEl);
    return false;
  }

  if (!regex.test(val)) {
    setFieldInvalid(input, errorEl, 'Please enter a valid email format (e.g. name@domain.com)');
    return false;
  }

  if (DUMMY_EMAILS_JS.includes(val)) {
    setFieldInvalid(input, errorEl, 'Placeholder or dummy email addresses are strictly prohibited.');
    return false;
  }

  const parts = val.split('@');
  if (parts.length === 2 && DISPOSABLE_DOMAINS_JS.includes(parts[1])) {
    setFieldInvalid(input, errorEl, `Disposable domain (@${parts[1]}) is blocked. Use a real email.`);
    return false;
  }

  setFieldValid(input, errorEl);
  return true;
}

// Strict Phone Validation
function validatePhoneField(input) {
  const val = (input.value || '').trim();
  const errorEl = document.getElementById(input.id + 'Error');
  const phoneRegex = /^[6-9]\d{9}$/;

  if (!val) {
    clearFieldValidation(input, errorEl);
    return false;
  }

  if (!phoneRegex.test(val)) {
    setFieldInvalid(input, errorEl, 'Must be a 10-digit number starting with 6, 7, 8, or 9.');
    return false;
  }

  setFieldValid(input, errorEl);
  return true;
}

// Strict Password Validation Checklist
function checkPasswordRules(password) {
  const reqLength = document.getElementById('reqLength');
  const reqUpper = document.getElementById('reqUpper');
  const reqLower = document.getElementById('reqLower');
  const reqNumber = document.getElementById('reqNumber');
  const reqSpecial = document.getElementById('reqSpecial');

  const hasLength = password.length >= 8;
  const hasUpper = /[A-Z]/.test(password);
  const hasLower = /[a-z]/.test(password);
  const hasNumber = /\d/.test(password);
  const hasSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password);

  updateReqItem(reqLength, hasLength);
  updateReqItem(reqUpper, hasUpper);
  updateReqItem(reqLower, hasLower);
  updateReqItem(reqNumber, hasNumber);
  updateReqItem(reqSpecial, hasSpecial);

  checkPasswordMatch();

  return hasLength && hasUpper && hasLower && hasNumber && hasSpecial;
}

function updateReqItem(element, isMet) {
  if (!element) return;
  if (isMet) {
    element.classList.add('met');
  } else {
    element.classList.remove('met');
  }
}

function checkPasswordMatch() {
  const pwd = document.getElementById('regPassword');
  const confirmPwd = document.getElementById('regConfirmPassword');
  const errorEl = document.getElementById('regConfirmPasswordError');

  if (!pwd || !confirmPwd || !confirmPwd.value) return;

  if (pwd.value !== confirmPwd.value) {
    setFieldInvalid(confirmPwd, errorEl, 'Passwords do not match.');
    return false;
  } else {
    setFieldValid(confirmPwd, errorEl);
    return true;
  }
}

function setFieldInvalid(input, errorEl, message) {
  input.classList.add('is-invalid');
  input.classList.remove('is-valid');
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.classList.add('visible');
  }
}

function setFieldValid(input, errorEl) {
  input.classList.remove('is-invalid');
  input.classList.add('is-valid');
  if (errorEl) {
    errorEl.textContent = '';
    errorEl.classList.remove('visible');
  }
}

function clearFieldValidation(input, errorEl) {
  input.classList.remove('is-invalid', 'is-valid');
  if (errorEl) {
    errorEl.textContent = '';
    errorEl.classList.remove('visible');
  }
}

// Handle Login Submission
async function handleLoginSubmit(event) {
  event.preventDefault();
  const emailInput = document.getElementById('loginEmail');
  const passwordInput = document.getElementById('loginPassword');
  const submitBtn = document.getElementById('loginSubmitBtn');

  const email = (emailInput.value || '').trim();
  const password = passwordInput.value;

  if (!email || !password) {
    showAuthAlert('Please fill in both email and password.');
    return;
  }

  // Set loading state
  submitBtn.disabled = true;
  const originalBtnText = submitBtn.innerHTML;
  submitBtn.innerHTML = '<span>Verifying credentials...</span>';

  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (response.ok && data.success) {
      showToast('Authentication successful. Redirecting...', 'success');
      window.location.href = data.redirect || '/dashboard';
    } else {
      // Explicit error handling from backend
      showAuthAlert(data.error || 'Authentication failed. Please verify credentials.', 'danger');
      showToast(data.error || 'Login failed', 'error');
    }
  } catch (err) {
    showAuthAlert('Unable to connect to the server. Please check your internet connection.', 'danger');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalBtnText;
  }
}

// Handle Register Submission
async function handleRegisterSubmit(event) {
  event.preventDefault();
  const submitBtn = document.getElementById('regSubmitBtn');

  const fullName = document.getElementById('regFullName').value.trim();
  const emailInput = document.getElementById('regEmail');
  const email = emailInput.value.trim();
  const bloodGroup = document.getElementById('regBloodGroup').value;
  const phone = document.getElementById('regPhone').value.trim();
  const city = document.getElementById('regCity').value.trim();
  const password = document.getElementById('regPassword').value;
  const confirmPassword = document.getElementById('regConfirmPassword').value;
  const registerAsDonor = document.getElementById('regEnrollDonor').checked;

  // Frontend check before firing
  if (!validateEmailField(emailInput)) {
    showAuthAlert('Please provide a valid and non-disposable email address.');
    return;
  }

  if (!checkPasswordRules(password)) {
    showAuthAlert('Please satisfy all password complexity rules shown in the checklist.');
    return;
  }

  if (password !== confirmPassword) {
    showAuthAlert('Passwords do not match.');
    return;
  }

  submitBtn.disabled = true;
  const originalBtnText = submitBtn.innerHTML;
  submitBtn.innerHTML = '<span>Registering verified account...</span>';

  try {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_name: fullName,
        email,
        password,
        confirm_password: confirmPassword,
        blood_group: bloodGroup,
        phone,
        city,
        register_as_donor: registerAsDonor
      })
    });

    const data = await response.json();

    if (response.ok && data.success) {
      showToast('Welcome to Jeevraksha! Account created.', 'success');
      window.location.href = data.redirect || '/dashboard';
    } else {
      showAuthAlert(data.error || 'Registration could not be completed.', 'danger');
      showToast(data.error || 'Registration failed', 'error');
    }
  } catch (err) {
    showAuthAlert('Network error occurred during registration. Please retry.', 'danger');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalBtnText;
  }
}

// --------------------------------------------------------------------------
// DASHBOARD CONTROLLER
// --------------------------------------------------------------------------
async function initDashboard(initialTab = 'dashboard') {
  setupFilterListeners();
  await loadCurrentUser();
  await loadStats();
  await loadRequestsFeed();

  // Switch to initial tab requested by URL
  navigateToTab(initialTab, null, false);
}

function setupFilterListeners() {
  const pillsContainer = document.getElementById('feedBloodFilters');
  if (pillsContainer) {
    pillsContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('.bg-pill');
      if (!btn) return;

      pillsContainer.querySelectorAll('.bg-pill').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');

      activeRequestBloodFilter = btn.dataset.bg || '';
      loadRequestsFeed();
    });
  }
}

function debounceFilterRequests() {
  clearTimeout(filterDebounceTimer);
  filterDebounceTimer = setTimeout(() => {
    const input = document.getElementById('feedCityFilter');
    activeRequestCityFilter = input ? input.value.trim() : '';
    loadRequestsFeed();
  }, 350);
}

// Tab Navigation
function navigateToTab(tabName, event, updateHistory = true) {
  if (event) event.preventDefault();

  // Hide all tabs
  document.querySelectorAll('.page-tab-content').forEach(el => el.classList.remove('active'));
  // Deactivate all nav links
  document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));

  const targetTab = document.getElementById(`tab-${tabName}`);
  const targetNav = document.getElementById(`nav-${tabName}`);

  if (targetTab) targetTab.classList.add('active');
  if (targetNav) targetNav.classList.add('active');

  if (updateHistory) {
    const path = tabName === 'dashboard' ? '/dashboard' : `/${tabName === 'activity' ? 'my-activity' : tabName}`;
    history.pushState({ tab: tabName }, '', path);
  }

  // Load contextual data if opening a specific tab
  if (tabName === 'inventory') {
    loadInventory();
  } else if (tabName === 'activity') {
    loadMyActivity();
  }
}

// --------------------------------------------------------------------------
// API CALLS: USER PROFILE, STATS & FEED
// --------------------------------------------------------------------------
async function loadCurrentUser() {
  try {
    const res = await fetch('/api/me');
    if (!res.ok) {
      if (res.status === 401) window.location.href = '/login';
      return;
    }
    const data = await res.json();
    if (!data.success) return;

    currentUser = data.user;
    currentDonor = data.donor;
    currentEligibility = data.eligibility;

    // Update Nav Badge
    const navName = document.getElementById('navUserName');
    const navBG = document.getElementById('navUserBloodGroup');
    const navAvatar = document.getElementById('navUserAvatar');

    if (navName) navName.textContent = currentUser.full_name;
    if (navBG) navBG.textContent = currentUser.blood_group;
    if (navAvatar) {
      const initials = currentUser.full_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
      navAvatar.textContent = initials;
    }

    // Pre-populate forms
    prepopulateForms();
    updateEligibilitySummaryCard();
    updateDigitalDonorCard();

  } catch (err) {
    console.error('Failed to load user info:', err);
  }
}

function prepopulateForms() {
  // Prepopulate Donor form if registered
  if (currentDonor) {
    const bgSelect = document.getElementById('donateBloodGroup');
    const ageInput = document.getElementById('donateAge');
    const weightInput = document.getElementById('donateWeight');
    const lastDateInput = document.getElementById('donateLastDate');
    const locInput = document.getElementById('donateLocation');
    const phoneInput = document.getElementById('donatePhone');
    const cardStatus = document.getElementById('donorActiveStatusCard');

    if (bgSelect) bgSelect.value = currentDonor.blood_group;
    if (ageInput) ageInput.value = currentDonor.age;
    if (weightInput) weightInput.value = currentDonor.weight;
    if (lastDateInput && currentDonor.last_donation_date) {
      lastDateInput.value = currentDonor.last_donation_date;
    }
    if (locInput) locInput.value = currentDonor.location;
    if (phoneInput && currentUser) phoneInput.value = currentUser.phone;

    if (cardStatus) {
      cardStatus.style.display = 'block';
      document.getElementById('donorProfileBG').textContent = currentDonor.blood_group;
      document.getElementById('donorProfileAge').textContent = currentDonor.age;
      document.getElementById('donorProfileWeight').textContent = currentDonor.weight;
      
      const cdEl = document.getElementById('donorProfileCooldown');
      if (cdEl && currentDonor.eligibility) {
        cdEl.textContent = currentDonor.eligibility.reason;
      }

      const toggleBtn = document.getElementById('btnToggleAvailability');
      if (toggleBtn) {
        toggleBtn.textContent = currentDonor.is_available ? 'Set Temporarily Inactive' : 'Set as Active & Available';
        toggleBtn.className = currentDonor.is_available ? 'btn btn-secondary btn-sm' : 'btn btn-primary btn-sm';
      }
    }
  }

  // Prepopulate emergency request contact phone with user phone
  const reqPhone = document.getElementById('reqContactPhone');
  if (reqPhone && currentUser && !reqPhone.value) {
    reqPhone.value = currentUser.phone;
  }
}

function updateEligibilitySummaryCard() {
  const elStatus = document.getElementById('statEligibilityStatus');
  const elSubtext = document.getElementById('statEligibilitySubtext');
  const elIcon = document.getElementById('eligibilityIcon');

  if (!elStatus || !currentEligibility) return;

  if (currentEligibility.eligible) {
    elStatus.textContent = 'Eligible Now';
    elStatus.style.color = 'var(--success)';
    elSubtext.textContent = 'Cooldown cleared. Ready to save a life.';
    if (elIcon) elIcon.className = 'stat-icon green';
  } else {
    elStatus.textContent = `${currentEligibility.days_remaining} Days Left`;
    elStatus.style.color = 'var(--warning)';
    elSubtext.textContent = currentEligibility.reason || '90-day cooldown active';
    if (elIcon) elIcon.className = 'stat-icon amber';
  }
}

function updateDigitalDonorCard() {
  const cardName = document.getElementById('cardDonorName');
  const cardBG = document.getElementById('cardDonorBG');
  const cardCity = document.getElementById('cardDonorCity');
  const cardId = document.getElementById('cardDonorId');

  if (!currentUser) return;

  if (cardName) cardName.textContent = currentUser.full_name;
  if (cardBG) cardBG.textContent = currentUser.blood_group;
  if (cardCity) cardCity.textContent = currentUser.city || 'India';
  if (cardId) cardId.textContent = `JR-ID: 2026-${String(currentUser.id).padStart(4, '0')}-V`;
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const data = await res.json();
    if (!data.success) return;

    const stats = data.stats;
    const totalDonorsEl = document.getElementById('statTotalDonors');
    const activeReqEl = document.getElementById('statActiveRequests');
    const criticalSubEl = document.getElementById('statCriticalSubtext');
    const compatibleUnitsEl = document.getElementById('statCompatibleUnits');
    const compatibleBreakdownEl = document.getElementById('statCompatibleBreakdown');

    if (totalDonorsEl) totalDonorsEl.textContent = stats.total_available_donors;
    if (activeReqEl) activeReqEl.textContent = stats.active_emergency_requests;
    if (criticalSubEl) {
      criticalSubEl.textContent = `${stats.critical_emergency_requests} marked Critical`;
    }
    if (compatibleUnitsEl) compatibleUnitsEl.textContent = `${stats.compatible_units_available} Units`;
    if (compatibleBreakdownEl) {
      compatibleBreakdownEl.textContent = `Compatible types: ${stats.compatible_donor_types.join(', ')}`;
    }

    // Cache inventory for inventory tab
    window.cachedInventory = stats.inventory;

  } catch (err) {
    console.error('Failed to load stats:', err);
  }
}

// --------------------------------------------------------------------------
// REQUESTS FEED (FILTERABLE BY BLOOD GROUP & CITY)
// --------------------------------------------------------------------------
async function loadRequestsFeed() {
  const container = document.getElementById('requestsFeedContainer');
  if (!container) return;

  let url = `/api/requests?blood_group=${encodeURIComponent(activeRequestBloodFilter)}&city=${encodeURIComponent(activeRequestCityFilter)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();

    if (!data.success || !data.requests || data.requests.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 50px 20px; background: #FFFFFF; border-radius: var(--radius-md); border: 1px dashed var(--border-color);">
          <div style="font-size: 2.2rem; margin-bottom: 8px;">🩸</div>
          <h4 style="font-size: 1.15rem; font-weight: 600; color: var(--text-main);">No matching emergency requests found</h4>
          <p style="font-size: 0.88rem; color: var(--text-muted); margin-top: 4px;">
            ${activeRequestBloodFilter || activeRequestCityFilter ? 'Try clearing your filters or search criteria.' : 'All pending emergency requirements have been fulfilled.'}
          </p>
        </div>
      `;
      return;
    }

    container.innerHTML = data.requests.map(req => renderRequestCard(req)).join('');

  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--danger); padding: 30px;">Error loading live feed. Please retry.</div>`;
  }
}

function renderRequestCard(req) {
  const urgencyLower = req.urgency_level.toLowerCase();
  const borderClass = `${urgencyLower}-border`;
  const isFulfilled = req.status === 'Fulfilled';
  const isOwner = currentUser && req.requester_id === currentUser.id;

  return `
    <div class="request-card ${borderClass}">
      <div>
        <div class="request-header">
          <div class="request-patient-info">
            <span class="urgency-badge ${urgencyLower}">
              ● ${escapeHtml(req.urgency_level)} Priority
            </span>
            <h4>${escapeHtml(req.patient_name)}</h4>
            <div class="request-hospital-meta">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
              ${escapeHtml(req.hospital_name)}
            </div>
          </div>
          <div class="request-blood-badge">
            <div class="bg-label">${escapeHtml(req.blood_group_needed)}</div>
            <div class="units-label">${req.units_required} Unit${req.units_required > 1 ? 's' : ''}</div>
          </div>
        </div>

        <ul class="request-details-list">
          <li>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
            Location: <strong>${escapeHtml(req.location)}</strong>
          </li>
          <li>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            Status: <strong>${escapeHtml(req.status)}</strong>
          </li>
          <li>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            Requester: <strong>${escapeHtml(req.requester_name || 'Emergency Desk')}</strong>
          </li>
        </ul>
      </div>

      <div class="request-card-actions">
        ${!isFulfilled && !isOwner ? `
          <button class="btn btn-primary btn-sm btn-block" onclick="openRespondModal(${req.id}, '${escapeHtml(req.patient_name)}', '${escapeHtml(req.hospital_name)}', '${escapeHtml(req.blood_group_needed)}')">
            Respond to Help
          </button>
        ` : ''}

        ${isOwner && !isFulfilled ? `
          <button class="btn btn-secondary btn-sm btn-block" onclick="updateRequestStatus(${req.id}, 'Fulfilled')">
            Mark Fulfilled
          </button>
        ` : ''}

        <button class="btn btn-secondary btn-sm" onclick="openContactModal('${escapeHtml(req.hospital_name)}', '${escapeHtml(req.location)}', '${escapeHtml(req.contact_phone)}')">
          Contact
        </button>
      </div>
    </div>
  `;
}

// --------------------------------------------------------------------------
// DONATE BLOOD CONTROLLER (WITH 90-DAY COOLDOWN AUTO-CHECK)
// --------------------------------------------------------------------------
function checkDonorFormEligibility() {
  const age = parseInt(document.getElementById('donateAge').value, 10);
  const weight = parseFloat(document.getElementById('donateWeight').value);
  const lastDateStr = document.getElementById('donateLastDate').value;
  const noticeEl = document.getElementById('donorEligibilityNotice');
  const submitBtn = document.getElementById('btnSaveDonor');

  if (!noticeEl) return;

  if (age && (age < 18 || age > 65)) {
    noticeEl.className = 'alert-banner alert-danger visible';
    noticeEl.style.display = 'block';
    noticeEl.textContent = `Age restriction: Blood donors must be between 18 and 65 years old. Current: ${age}.`;
    return false;
  }

  if (weight && weight < 50) {
    noticeEl.className = 'alert-banner alert-danger visible';
    noticeEl.style.display = 'block';
    noticeEl.textContent = `Weight restriction: Whole blood donation requires a minimum body weight of 50 kg. Current: ${weight} kg.`;
    return false;
  }

  if (lastDateStr) {
    const lastDate = new Date(lastDateStr);
    const today = new Date();
    const diffTime = today - lastDate;
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays < 90) {
      const daysLeft = 90 - diffDays;
      noticeEl.className = 'alert-banner alert-danger visible';
      noticeEl.style.display = 'block';
      noticeEl.textContent = `90-Day Cooldown Notice: Your last donation was ${diffDays} days ago. You will become eligible again in ${daysLeft} days.`;
      return true;
    }
  }

  noticeEl.className = 'alert-banner alert-success visible';
  noticeEl.style.display = 'block';
  noticeEl.textContent = 'Medical parameters clear! You are fully eligible for immediate donation.';
  return true;
}

async function handleDonorSubmit(event) {
  event.preventDefault();
  const bloodGroup = document.getElementById('donateBloodGroup').value;
  const age = document.getElementById('donateAge').value;
  const weight = document.getElementById('donateWeight').value;
  const lastDonationDate = document.getElementById('donateLastDate').value || null;
  const location = document.getElementById('donateLocation').value.trim();
  const medicalCleared = document.getElementById('donateMedicalCheck').checked;
  const phone = document.getElementById('donatePhone').value.trim();

  const submitBtn = document.getElementById('btnSaveDonor');
  submitBtn.disabled = true;

  try {
    const res = await fetch('/api/donors/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        blood_group: bloodGroup,
        age,
        weight,
        last_donation_date: lastDonationDate,
        location,
        medical_cleared: medicalCleared,
        phone
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message, 'success');
      await loadCurrentUser();
      await loadStats();
      navigateToTab('dashboard');
    } else {
      showToast(data.error || 'Failed to update donor registration.', 'error');
    }
  } catch (err) {
    showToast('Network error during registration.', 'error');
  } finally {
    submitBtn.disabled = false;
  }
}

async function toggleDonorAvailability() {
  try {
    const res = await fetch('/api/donors/toggle-availability', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      await loadCurrentUser();
      await loadStats();
    } else {
      showToast(data.error, 'error');
    }
  } catch (err) {
    showToast('Could not update status.', 'error');
  }
}

// --------------------------------------------------------------------------
// REQUEST BLOOD MODULE & SMART MATCHING ENGINE
// --------------------------------------------------------------------------
async function previewCompatibleDonors(bloodGroup) {
  const helper = document.getElementById('compatibilityHelperText');
  const matchPanel = document.getElementById('smartMatchPanel');
  const matchList = document.getElementById('smartMatchList');
  const countEl = document.getElementById('smartMatchCount');
  const pillsEl = document.getElementById('smartMatchCompatibilityPills');

  if (!bloodGroup) {
    if (matchPanel) matchPanel.style.display = 'none';
    return;
  }

  try {
    const res = await fetch(`/api/donors/compatible?blood_group=${encodeURIComponent(bloodGroup)}`);
    const data = await res.json();

    if (data.success) {
      if (helper) {
        helper.textContent = `Compatible donor groups: ${data.compatible_groups.join(', ')}`;
      }

      if (matchPanel && matchList) {
        matchPanel.style.display = 'block';
        countEl.textContent = data.donors.length;
        pillsEl.textContent = `Universal & Exact Donors: ${data.compatible_groups.join(', ')}`;

        if (data.donors.length === 0) {
          matchList.innerHTML = `
            <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.88rem;">
              No available donors currently registered for groups (${data.compatible_groups.join(', ')}). Broadcasting will alert standby donors.
            </div>
          `;
        } else {
          matchList.innerHTML = data.donors.map(d => `
            <div class="matched-donor-item">
              <div class="donor-item-left">
                <div class="donor-bg-pill">${escapeHtml(d.blood_group)}</div>
                <div class="donor-details">
                  <h5>${escapeHtml(d.donor_name)}</h5>
                  <p>${escapeHtml(d.location || d.donor_city)} • Contact: ${escapeHtml(d.donor_phone)}</p>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <span class="match-badge ${d.blood_group === bloodGroup ? 'exact' : 'universal'}">
                  ${d.blood_group === bloodGroup ? 'Exact Match' : 'Universal Match'}
                </span>
                <button class="btn btn-secondary btn-sm" onclick="openContactModal('${escapeHtml(d.donor_name)}', '${escapeHtml(d.location)}', '${escapeHtml(d.donor_phone)}')">
                  Call Donor
                </button>
              </div>
            </div>
          `).join('');
        }
      }
    }
  } catch (err) {
    console.error('Failed to preview compatible donors:', err);
  }
}

async function handleRequestSubmit(event) {
  event.preventDefault();
  const patientName = document.getElementById('reqPatientName').value.trim();
  const bloodGroupNeeded = document.getElementById('reqBloodGroup').value;
  const unitsRequired = document.getElementById('reqUnits').value;
  const urgencyLevel = document.getElementById('reqUrgency').value;
  const hospitalName = document.getElementById('reqHospitalName').value.trim();
  const location = document.getElementById('reqLocation').value.trim();
  const contactPhone = document.getElementById('reqContactPhone').value.trim();

  const submitBtn = document.getElementById('btnSubmitRequest');
  submitBtn.disabled = true;

  try {
    const res = await fetch('/api/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        patient_name: patientName,
        blood_group_needed: bloodGroupNeeded,
        units_required: unitsRequired,
        urgency_level: urgencyLevel,
        hospital_name: hospitalName,
        location,
        contact_phone: contactPhone
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message, 'success');
      previewCompatibleDonors(bloodGroupNeeded);
      await loadStats();
      await loadRequestsFeed();

      // Reset form fields
      document.getElementById('emergencyRequestForm').reset();
      showToast(`Smart matching algorithm found ${data.matched_donors_count} compatible donor(s)!`, 'info');
    } else {
      showToast(data.error || 'Failed to submit emergency request.', 'error');
    }
  } catch (err) {
    showToast('Network error while submitting emergency request.', 'error');
  } finally {
    submitBtn.disabled = false;
  }
}

async function updateRequestStatus(reqId, newStatus) {
  try {
    const res = await fetch(`/api/requests/${reqId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      await loadRequestsFeed();
      await loadStats();
      if (document.getElementById('tab-activity').classList.contains('active')) {
        loadMyActivity();
      }
    } else {
      showToast(data.error, 'error');
    }
  } catch (err) {
    showToast('Failed to update request status.', 'error');
  }
}

// --------------------------------------------------------------------------
// RESPOND TO REQUEST / LOG DONATION
// --------------------------------------------------------------------------
function openRespondModal(reqId, patientName, hospitalName, bloodGroup) {
  pendingRespondRequestId = reqId;
  document.getElementById('modalPatientName').textContent = patientName;
  document.getElementById('modalHospitalInfo').textContent = hospitalName;
  document.getElementById('modalBloodNeeded').textContent = `Blood Group Needed: ${bloodGroup}`;
  
  const modal = document.getElementById('respondModal');
  if (modal) modal.classList.add('active');
}

async function submitDonationResponse() {
  if (!pendingRespondRequestId) return;
  const confirmBtn = document.getElementById('modalConfirmBtn');
  confirmBtn.disabled = true;

  try {
    const res = await fetch('/api/donations/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: pendingRespondRequestId })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      closeModal('respondModal');
      showToast(data.message, 'success');
      await loadRequestsFeed();
      await loadStats();
    } else {
      showToast(data.error || 'Could not record response.', 'error');
    }
  } catch (err) {
    showToast('Network error occurred.', 'error');
  } finally {
    confirmBtn.disabled = false;
  }
}

function openContactModal(hospitalName, location, phone) {
  document.getElementById('contactHospitalName').textContent = hospitalName;
  document.getElementById('contactLocation').textContent = location;
  document.getElementById('contactPhoneNumber').textContent = phone;
  
  const callBtn = document.getElementById('contactCallBtn');
  if (callBtn) callBtn.href = `tel:${phone}`;

  const modal = document.getElementById('contactModal');
  if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

// --------------------------------------------------------------------------
// LIVE INVENTORY TAB
// --------------------------------------------------------------------------
function loadInventory() {
  const container = document.getElementById('inventoryGridContainer');
  if (!container) return;

  const inventory = window.cachedInventory || [
    { blood_group: 'A+', units: 0, status: 'Critical', can_donate_to: ['A+', 'AB+'], can_receive_from: ['A+', 'A-', 'O+', 'O-'] },
    { blood_group: 'A-', units: 0, status: 'Critical', can_donate_to: ['A+', 'A-', 'AB+', 'AB-'], can_receive_from: ['A-', 'O-'] },
    { blood_group: 'B+', units: 0, status: 'Critical', can_donate_to: ['B+', 'AB+'], can_receive_from: ['B+', 'B-', 'O+', 'O-'] },
    { blood_group: 'B-', units: 0, status: 'Critical', can_donate_to: ['B+', 'B-', 'AB+', 'AB-'], can_receive_from: ['B-', 'O-'] },
    { blood_group: 'AB+', units: 0, status: 'Critical', can_donate_to: ['AB+'], can_receive_from: ['All Groups (Universal Recipient)'] },
    { blood_group: 'AB-', units: 0, status: 'Critical', can_donate_to: ['AB+', 'AB-'], can_receive_from: ['AB-', 'A-', 'B-', 'O-'] },
    { blood_group: 'O+', units: 0, status: 'Critical', can_donate_to: ['O+', 'A+', 'B+', 'AB+'], can_receive_from: ['O+', 'O-'] },
    { blood_group: 'O-', units: 0, status: 'Critical', can_donate_to: ['All Groups (Universal Donor)'], can_receive_from: ['O-'] }
  ];

  container.innerHTML = inventory.map(item => {
    const statusClass = item.status.toLowerCase();
    return `
      <div class="inventory-card">
        <div class="inventory-group">${escapeHtml(item.blood_group)}</div>
        <div class="inventory-units">${item.units} Verified Units</div>
        <div class="stock-tag ${statusClass}">● ${escapeHtml(item.status)} Availability</div>
        <div class="compatibility-preview">
          <div>Can donate to: <strong>${item.can_donate_to.join(', ')}</strong></div>
          <div style="margin-top: 4px;">Can receive from: <strong>${item.can_receive_from.join(', ')}</strong></div>
        </div>
      </div>
    `;
  }).join('');
}

// --------------------------------------------------------------------------
// MY ACTIVITY TAB
// --------------------------------------------------------------------------
async function loadMyActivity() {
  const reqBody = document.getElementById('myRequestsTableBody');
  const donBody = document.getElementById('myDonationsTableBody');

  try {
    const res = await fetch('/api/my-activity');
    const data = await res.json();

    if (!data.success) return;

    // Populate user requests
    if (reqBody) {
      if (data.my_requests.length === 0) {
        reqBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">You have not logged any emergency requests.</td></tr>`;
      } else {
        reqBody.innerHTML = data.my_requests.map(r => `
          <tr>
            <td><strong>${escapeHtml(r.patient_name)}</strong></td>
            <td><span class="user-blood-badge">${escapeHtml(r.blood_group_needed)}</span></td>
            <td>${r.units_required}</td>
            <td>${escapeHtml(r.hospital_name)}</td>
            <td><strong>${escapeHtml(r.status)}</strong></td>
            <td>
              ${r.status === 'Pending' ? `
                <button class="btn btn-secondary btn-sm" onclick="updateRequestStatus(${r.id}, 'Fulfilled')">Mark Fulfilled</button>
              ` : `
                <span style="font-size: 0.8rem; color: var(--text-muted);">Completed</span>
              `}
            </td>
          </tr>
        `).join('');
      }
    }

    // Populate user donations
    if (donBody) {
      if (data.my_donations.length === 0) {
        donBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">No donation records logged yet. Register as donor to get started.</td></tr>`;
      } else {
        donBody.innerHTML = data.my_donations.map(d => `
          <tr>
            <td>${escapeHtml(d.donation_date)}</td>
            <td>${escapeHtml(d.patient_name || 'Emergency Reserve')}</td>
            <td>${escapeHtml(d.hospital_name || 'Direct Blood Bank')}</td>
            <td>${d.units_donated} Unit</td>
            <td><span style="color: var(--success); font-weight: 600;">${escapeHtml(d.status)}</span></td>
          </tr>
        `).join('');
      }
    }

  } catch (err) {
    console.error('Failed to load my activity:', err);
  }
}
