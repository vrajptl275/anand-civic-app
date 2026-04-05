// ============================================================
// main.js — Anand Civic Issue Reporting System
// Shared utilities: auth, API, helpers
// ============================================================

'use strict';

// ── THEME SYSTEM (runs immediately to prevent flash) ─────────
function getPreferredTheme() {
    try {
        const saved = localStorage.getItem('theme');
        if (saved === 'dark' || saved === 'light') return saved;
    } catch {}
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
}

function applyTheme(theme) {
    const nextTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', nextTheme);

    try {
        localStorage.setItem('theme', nextTheme);
    } catch {}

    document.querySelectorAll('.theme-toggle').forEach(btn => {
        btn.innerHTML = nextTheme === 'dark'
            ? '<i class="bi bi-sun-fill"></i>'
            : '<i class="bi bi-moon-stars-fill"></i>';
        btn.setAttribute('aria-label', nextTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
        btn.setAttribute('title', nextTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    });
}

(function initTheme() {
    applyTheme(getPreferredTheme());
})();

let themeAnimationTimer = null;
let themeOverlayTimer = null;

function runThemeOverlay(nextTheme) {
    const existing = document.querySelector('.theme-transition-overlay');
    if (existing) existing.remove();

    const trigger = document.activeElement && document.activeElement.classList?.contains('theme-toggle')
        ? document.activeElement
        : document.querySelector('.theme-toggle');

    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;

    if (trigger) {
        const rect = trigger.getBoundingClientRect();
        x = rect.left + rect.width / 2;
        y = rect.top + rect.height / 2;
    }

    const overlay = document.createElement('div');
    overlay.className = `theme-transition-overlay theme-transition-overlay-${nextTheme}`;
    overlay.style.setProperty('--theme-origin-x', `${x}px`);
    overlay.style.setProperty('--theme-origin-y', `${y}px`);
    document.body.appendChild(overlay);

    requestAnimationFrame(() => {
        overlay.classList.add('is-active');
    });

    if (themeOverlayTimer) {
        clearTimeout(themeOverlayTimer);
    }

    themeOverlayTimer = window.setTimeout(() => {
        overlay.remove();
    }, 720);
}

function animateThemeSwitch(nextTheme) {
    const html = document.documentElement;

    if (themeAnimationTimer) {
        clearTimeout(themeAnimationTimer);
    }

    html.classList.add('theme-animating');
    runThemeOverlay(nextTheme);

    requestAnimationFrame(() => {
        applyTheme(nextTheme);
        themeAnimationTimer = window.setTimeout(() => {
            html.classList.remove('theme-animating');
        }, 520);
    });
}

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    animateThemeSwitch(next);
}

// Update icons after DOM loads
document.addEventListener('DOMContentLoaded', () => {
    applyTheme(document.documentElement.getAttribute('data-theme') || getPreferredTheme());
});

// ── API CONFIGURATION ────────────────────────────────────────
let API_BASE = '';

(function initApiBase() {
    const { protocol, hostname, port } = window.location;
    API_BASE = (port && port !== '80' && port !== '443')
        ? `${protocol}//${hostname}:${port}`
        : `${protocol}//${hostname}`;
    window.API_BASE = API_BASE;
})();

// ── AUTHENTICATION ───────────────────────────────────────────

function getToken() {
    return localStorage.getItem('token');
}

function setToken(token) {
    localStorage.setItem('token', token);
}

function getStoredUser() {
    try {
        const raw = localStorage.getItem('user');
        return raw ? JSON.parse(raw) : null;
    } catch {
        localStorage.removeItem('user');
        return null;
    }
}

function setStoredUser(user) {
    localStorage.setItem('user', JSON.stringify(user));
}

function removeToken() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
}

function isAuthenticated() {
    const token = getToken();
    if (!token) return false;
    try {
        const { exp } = JSON.parse(atob(token.split('.')[1]));
        return exp > Date.now() / 1000;
    } catch {
        return false;
    }
}

function getAuthHeaders() {
    const token = getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── CORE API REQUEST ─────────────────────────────────────────

async function apiRequest(endpoint, options = {}) {
    const token = getToken();
    const url   = `${API_BASE}${endpoint}`;

    const config = {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(token && { Authorization: `Bearer ${token}` }),
            ...options.headers,
        },
    };

    // Remove Content-Type for FormData — let browser set boundary
    if (options.body instanceof FormData) {
        delete config.headers['Content-Type'];
    }

    const response = await fetch(url, config);

    if (response.status === 401) {
        removeToken();
        window.location.href = '../auth/login.html';
        throw new Error('Authentication required');
    }

    return response;
}

// ── AUTH FUNCTIONS ───────────────────────────────────────────

async function login(email, password) {
    try {
        const res  = await fetch(`${API_BASE}/api/auth/login`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (res.ok) {
            setToken(data.token);
            setStoredUser(data.user);
            return { success: true, user: data.user };
        }
        return { success: false, error: data.error };
    } catch {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function register(name, email, phone, password, role) {
    try {
        const res  = await fetch(`${API_BASE}/api/auth/register`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ name, email, phone, password, role }),
        });
        const data = await res.json();
        if (res.ok) {
            if (data.token)  setToken(data.token);
            if (data.user)   setStoredUser(data.user);
            return { success: true, user: data.user };
        }
        return { success: false, error: data.error };
    } catch {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

function logout() {
    removeToken();
    window.location.href = '../auth/login.html';
}

// ── DATA FETCH HELPERS ───────────────────────────────────────

async function getStats() {
    const res = await apiRequest('/api/stats');
    return res.json();
}

/** Public stats — no auth required */
async function getPublicStats() {
    try {
        const res = await fetch(`${API_BASE}/api/stats/public`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    } catch {
        return null;
    }
}

async function getComplaints(filters = {}) {
    const params = new URLSearchParams(filters);
    const query  = params.toString();
    const res    = await apiRequest(`/api/complaints${query ? `?${query}` : ''}`);
    const data   = await res.json();

    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.complaints)) return data.complaints;
    return [];
}

/** Public map data — no auth required */
async function getMapData() {
    try {
        const res = await fetch(`${API_BASE}/api/stats/map`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    } catch {
        return [];
    }
}

async function getDepartments() {
    const res = await apiRequest('/api/departments');
    return res.json();
}

async function getUsers(role = null, departmentId = null) {
    const params = new URLSearchParams();
    if (role) params.set('role', role);
    if (departmentId) params.set('department_id', departmentId);
    const qs = params.toString();
    const res = await apiRequest(`/api/users${qs ? '?' + qs : ''}`);
    return res.json();
}

async function getNotifications() {
    const res = await apiRequest('/api/notifications');
    const data = await res.json();
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.notifications)) return data.notifications;
    return [];
}

// ── COMPLAINT ACTIONS ────────────────────────────────────────

async function createComplaint(formData) {
    try {
        const res = await apiRequest('/api/complaints', {
            method: 'POST',
            body:   formData,
        });
        const data = await res.json();
        return res.ok ? { success: true, ...data } : { success: false, error: data.error || 'Submission failed' };
    } catch (e) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function updateComplaintStatus(id, status, remarks = '') {
    try {
        const res = await apiRequest(`/api/complaints/${id}/status`, {
            method: 'PUT',
            body:   JSON.stringify({ status, remarks }),
        });
        const data = await res.json();
        return res.ok ? { success: true, ...data } : { success: false, error: data.error || 'Update failed' };
    } catch (e) {
        return { success: false, error: 'Network error' };
    }
}

async function uploadAfterImage(id, imageFile) {
    const form = new FormData();
    form.append('after_image', imageFile);
    const res = await apiRequest(`/api/complaints/${id}/image`, {
        method:  'POST',
        headers: {},  // browser sets content-type with boundary
        body:    form,
    });
    return res.json();
}

// ── DEPARTMENT ACTIONS ───────────────────────────────────────

async function createDepartment(data) {
    const res = await apiRequest('/api/departments', { method: 'POST', body: JSON.stringify(data) });
    return res.json();
}

async function updateDepartment(id, data) {
    const res = await apiRequest(`/api/departments/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    return res.json();
}

async function deleteDepartment(id) {
    const res = await apiRequest(`/api/departments/${id}`, { method: 'DELETE' });
    return res.json();
}

// ── USER ACTIONS ─────────────────────────────────────────────

async function createUser(data) {
    const res = await apiRequest('/api/users', { method: 'POST', body: JSON.stringify(data) });
    return res.json();
}

async function updateUser(id, data) {
    const res = await apiRequest(`/api/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    return res.json();
}

async function deleteUser(id) {
    const res = await apiRequest(`/api/users/${id}`, { method: 'DELETE' });
    return res.json();
}

// ── UI HELPERS ───────────────────────────────────────────────

/**
 * Show a dismissible toast alert.
 * @param {string} message
 * @param {'info'|'success'|'danger'|'warning'} type
 * @param {number} duration  ms before auto-dismiss (0 = never)
 */
function showAlert(message, type = 'info', duration = 5000) {
    // Remove duplicates
    document.querySelectorAll('.alert').forEach(a => a.remove());

    const el = document.createElement('div');
    el.className = `alert alert-${type} alert-dismissible fade show`;
    el.style.cssText = `
        position: fixed; top: 1.5rem; right: 1.5rem;
        z-index: 9999; min-width: 300px; max-width: 380px;
        border: none; border-radius: 12px;
        font-weight: 500; font-size: 0.95rem;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    `;
    el.innerHTML = `${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;
    document.body.appendChild(el);

    if (duration > 0) {
        setTimeout(() => el.isConnected && el.remove(), duration);
    }
    return el;
}

/** Redirect to login if not authenticated. Returns false if redirected. */
function checkAuth() {
    if (!isAuthenticated()) {
        window.location.href = '../auth/login.html';
        return false;
    }
    return true;
}

// ── FORMATTERS ───────────────────────────────────────────────

/** Format an ISO date string to local date + short time */
function formatDate(dateString) {
    const d = new Date(dateString);
    return `${d.toLocaleDateString('en-IN')} ${d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}`;
}

/** Returns an accessible status badge HTML string */
function getStatusBadge(status) {
    const map = {
        pending:     ['bg-warning-subtle text-warning',  'Pending'],
        assigned:    ['bg-info-subtle text-info',        'Assigned'],
        in_progress: ['bg-primary-subtle text-primary',  'In Progress'],
        completed:   ['bg-success-subtle text-success',  'Completed'],
        resolved:    ['bg-success text-white',           'Resolved'],
        closed:      ['bg-dark text-white',              'Closed'],
        reopened:    ['bg-danger-subtle text-danger',    'Reopened'],
        rejected:    ['bg-danger text-white',            'Rejected'],
        reassigned:  ['bg-secondary-subtle text-secondary','Reassigned'],
    };
    const [cls, label] = map[status] ?? ['bg-light text-muted', status || 'Unknown'];
    return `<span class="badge ${cls}">${label}</span>`;
}

function getPriorityBadge(priority) {
    const map = {
        low:    ['bg-light text-muted', 'Low'],
        medium: ['bg-warning-subtle text-warning', 'Medium'],
        high:   ['bg-danger-subtle text-danger', 'High'],
    };
    const [cls, label] = map[priority] ?? ['bg-light text-muted', 'Unknown'];
    return `<span class="badge ${cls} fw-semibold">${label}</span>`;
}

function getRoleBadge(role) {
    const map = {
        citizen:    ['bg-light text-muted',     'Citizen'],
        officer:    ['bg-primary-subtle text-primary', 'Officer'],
        department: ['bg-info-subtle text-info', 'Department'],
        municipal:  ['bg-success-subtle text-success', 'Municipal'],
    };
    const [cls, label] = map[role] ?? ['bg-light text-muted', 'Unknown'];
    return `<span class="badge ${cls} fw-semibold">${label}</span>`;
}

// ── EXPORTS ──────────────────────────────────────────────────
// Assign complaint to officer (department/municipal)
async function assignOfficer(complaintId, officerId, deadlineDays = 7) {
    try {
        const res = await fetch(`${API_BASE}/api/complaints/${complaintId}/assign`, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ officer_id: officerId, deadline_days: deadlineDays })
        });
        const data = await res.json();
        return res.ok ? { success: true, ...data } : { success: false, error: data.error || 'Assignment failed' };
    } catch (e) {
        return { success: false, error: 'Network error' };
    }
}

// Update complaint priority (department only)
async function updatePriority(complaintId, priority) {
    try {
        const res = await apiRequest(`/api/complaints/${complaintId}/priority`, {
            method: 'PUT',
            body: JSON.stringify({ priority })
        });
        const data = await res.json();
        return res.ok ? { success: true, ...data } : { success: false, error: data.error || 'Priority update failed' };
    } catch (e) {
        return { success: false, error: 'Network error' };
    }
}

// Citizen feedback: close or reopen a resolved complaint
async function submitFeedback(complaintId, feedback, reopen = false) {
    try {
        const res = await apiRequest(`/api/complaints/${complaintId}/feedback`, {
            method: 'POST',
            body: JSON.stringify({ feedback, reopen })
        });
        const data = await res.json();
        return res.ok ? { success: true, ...data } : { success: false, error: data.error || 'Feedback failed' };
    } catch (e) {
        return { success: false, error: 'Network error' };
    }
}

Object.assign(window, {
    API_BASE,
    getToken, setToken, getStoredUser, setStoredUser, removeToken,
    isAuthenticated, getAuthHeaders,
    login, register, logout,
    getStats, getPublicStats, getMapData,
    getComplaints, getDepartments, getUsers, getNotifications,
    createComplaint, updateComplaintStatus, uploadAfterImage,
    createDepartment, updateDepartment, deleteDepartment,
    createUser, updateUser, deleteUser,
    assignOfficer, updatePriority, submitFeedback, toggleTheme,
    showAlert, checkAuth,
    formatDate, getStatusBadge, getPriorityBadge, getRoleBadge,
});

// ── OVERPASS API MAP POIS ──────────────────────────────────
window.loadMapPOIs = async function(mapObj) {
    if(!mapObj) return;
    const bbox = "22.52,72.90,22.58,72.98"; 
    const query = `[out:json][timeout:25];(node["amenity"~"hospital|college|university|police|school"](${bbox});node["leisure"~"park|garden"](${bbox});node["waterway"~"river|pond"](${bbox});node["office"~"government"](${bbox}););out body;`;
    
    try {
        const res = await fetch(`${API_BASE}/api/proxy/overpass`, {
            method: 'POST',
            headers: { 'Content-Type': 'text/plain' },
            body: query
        });
        const data = await res.json();
        
        const myIcons = { hospital: '🏥', college: '🎓', university: '🎓', school: '🎒', police: '🚓', park: '🌳', garden: '🌷', river: '🌊', pond: '🦆', government: '🏛️', default: '📍' };
        
        if (data && data.elements) {
            data.elements.forEach(el => {
                if(el.type === 'node') {
                    const type = el.tags.amenity || el.tags.leisure || el.tags.waterway || el.tags.office || 'default';
                    const iconEmoji = myIcons[type] || myIcons.default;
                    const name = el.tags.name || type.charAt(0).toUpperCase() + type.slice(1);
                    
                    const markerIcon = L.divIcon({
                        html: `<div style="font-size:24px; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.5));">${iconEmoji}</div>`,
                        className: 'poi-icon',
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    });
                    
                    L.marker([el.lat, el.lon], {icon: markerIcon})
                     .bindPopup(`<b>${name}</b><br><small class="text-muted text-uppercase">${type}</small>`)
                     .addTo(mapObj);
                }
            });
        }
    } catch(e) { console.error("POIs failed to load", e); }
};

// ── GLOBAL MODAL RENDERING: COMPLAINT DETAILS ───────────────
window.showComplaintDetail = async function(id) {
    // Show loading text
    const content = document.getElementById('complaint-detail-content');
    if (!content) return;
    content.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading Details...</p></div>';
    
    // Open the bootstrap modal
    const modalEl = document.getElementById('complaintDetailModal');
    let modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();

    // Fetch complaint data
    try {
        const complaints = await getComplaints(); // From main.js
        const c = complaints.find(x => x.id === id);
        if(!c) { content.innerHTML = '<div class="alert alert-danger">Complaint not found</div>'; return; }
        
        let pBadge = c.priority || 'medium';
        const latMap = parseFloat(c.latitude).toFixed(4);
        const lngMap = parseFloat(c.longitude).toFixed(4);

        let imgHTML = '';
        if (c.before_image || c.after_image) {
            imgHTML = `<div class="row mt-3 mb-3">
                ${c.before_image ? `<div class="col-md-6"><strong class="text-muted small">ISSUE (BEFORE)</strong><img src="${API_BASE}/uploads/before/${c.before_image}" class="img-fluid rounded border mt-1" style="max-height:250px;object-fit:cover;width:100%"></div>` : ''}
                ${c.after_image ? `<div class="col-md-6"><strong class="text-success small">RESOLVED (AFTER)</strong><img src="${API_BASE}/uploads/after/${c.after_image}" class="img-fluid rounded border border-success border-2 mt-1" style="max-height:250px;object-fit:cover;width:100%"></div>` : ''}
            </div>`;
        }
        
        content.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="fw-bold mb-0">${c.title}</h4>
                <div>
                    <span class="badge status-${c.status} me-2">${c.status.toUpperCase()}</span>
                    <span class="badge priority-${pBadge}">${pBadge.toUpperCase()}</span>
                </div>
            </div>
            <p class="text-secondary">${c.description}</p>
            
            ${imgHTML}
            
            <div class="bg-light p-3 rounded d-flex align-items-center gap-3">
                <i class="bi bi-geo-alt-fill text-danger fs-4"></i>
                <div>
                    <h6 class="mb-0 fw-bold">Live GPS Location</h6>
                    <small class="text-muted">Latitude: ${latMap}, Longitude: ${lngMap}</small>
                </div>
                <a href="https://www.google.com/maps/search/?api=1&query=${c.latitude},${c.longitude}" target="_blank" class="btn btn-sm btn-outline-primary ms-auto">Open in Google Maps</a>
            </div>
        `;
    } catch(e) {
        content.innerHTML = '<div class="alert alert-danger">Failed to load details</div>';
    }
};
