// Civic Issue Reporting System - Main JavaScript
const API_BASE = 'https://YOUR_NEW_CLOUD_URL.onrender.com'; // CHANGE THIS when you deploy!

// Global state
let currentUser = null;
let map = null;
let complaintMarkers = [];

// ==================== AUTH FUNCTIONS ====================

async function login(email, password) {
    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            localStorage.setItem('user', JSON.stringify(data.user));
            localStorage.setItem('token', data.token);
            return { success: true, user: data.user };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function register(name, email, phone, password, role = 'citizen') {
    try {
        const response = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, phone, password, role })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            return { success: true, user: data.user };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

function logout() {
    currentUser = null;
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    window.location.href = 'index.html';
}

function checkAuth() {
    const user = localStorage.getItem('user');
    const token = localStorage.getItem('token');
    
    if (user && token) {
        currentUser = JSON.parse(user);
        return true;
    }
    return false;
}

function getAuthHeaders() {
    const token = localStorage.getItem('token');
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };
}

// ==================== API FUNCTIONS ====================

// Departments
async function getDepartments() {
    try {
        const response = await fetch(`${API_BASE}/api/departments`);
        return await response.json();
    } catch (error) {
        console.error('Error fetching departments:', error);
        return [];
    }
}

// Complaints
async function getComplaints(filters = {}) {
    try {
        const params = new URLSearchParams(filters);
        const response = await fetch(`${API_BASE}/api/complaints?${params}`, {
            headers: getAuthHeaders()
        });
        return await response.json();
    } catch (error) {
        console.error('Error fetching complaints:', error);
        return [];
    }
}

async function getComplaint(id) {
    try {
        const response = await fetch(`${API_BASE}/api/complaints/${id}`, {
            headers: getAuthHeaders()
        });
        return await response.json();
    } catch (error) {
        console.error('Error fetching complaint:', error);
        return null;
    }
}

async function createComplaint(formData) {
    try {
        const response = await fetch(`${API_BASE}/api/complaints`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            return { success: true, complaint: data.complaint };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function updateComplaintStatus(id, status, remarks = '') {
    try {
        const response = await fetch(`${API_BASE}/api/complaints/${id}/status`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({ status, remarks })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            return { success: true, complaint: data.complaint };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function assignComplaint(id, officerId) {
    try {
        const response = await fetch(`${API_BASE}/api/complaints/${id}/assign`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ officer_id: officerId })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            return { success: true, complaint: data.complaint };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function updatePriority(id, priority) {
    try {
        const response = await fetch(`${API_BASE}/api/complaints/${id}/priority`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({ priority })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            return { success: true, complaint: data.complaint };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function submitFeedback(id, feedback, reopen = false) {
    try {
        const response = await fetch(`${API_BASE}/api/complaints/${id}/feedback`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ feedback, reopen })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            return { success: true, complaint: data.complaint };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function uploadAfterImage(id, imageFile) {
    try {
        const formData = new FormData();
        formData.append('after_image', imageFile);
        
        const response = await fetch(`${API_BASE}/api/complaints/${id}/image`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            return { success: true, complaint: data.complaint };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

// Users
async function getUsers(role = null, departmentId = null) {
    try {
        const params = new URLSearchParams();
        if (role) params.append('role', role);
        if (departmentId) params.append('department_id', departmentId);
        
        const response = await fetch(`${API_BASE}/api/users?${params}`, {
            headers: getAuthHeaders()
        });
        return await response.json();
    } catch (error) {
        console.error('Error fetching users:', error);
        return [];
    }
}

async function createUser(userData) {
    try {
        const response = await fetch(`${API_BASE}/api/users`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(userData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            return { success: true, user: data.user };
        } else {
            return { success: false, error: data.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

// Departments (Admin)
async function createDepartment(data) {
    try {
        const response = await fetch(`${API_BASE}/api/departments`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            return { success: true, department: result.department };
        } else {
            return { success: false, error: result.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function updateDepartment(id, data) {
    try {
        const response = await fetch(`${API_BASE}/api/departments/${id}`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            return { success: true, department: result.department };
        } else {
            return { success: false, error: result.error };
        }
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function deleteDepartment(id) {
    try {
        const response = await fetch(`${API_BASE}/api/departments/${id}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        const result = await response.json();
        return { success: response.ok, message: result.message || result.error };
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function deleteUser(id) {
    try {
        const response = await fetch(`${API_BASE}/api/users/${id}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        const result = await response.json();
        return { success: response.ok, message: result.message || result.error };
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

async function updateUser(id, data) {
    try {
        const response = await fetch(`${API_BASE}/api/users/${id}`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify(data)
        });
        const result = await response.json();
        return { success: response.ok, message: result.message || result.error };
    } catch (error) {
        return { success: false, error: 'Network error. Please try again.' };
    }
}

// Statistics
async function getStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`, {
            headers: getAuthHeaders()
        });
        return await response.json();
    } catch (error) {
        console.error('Error fetching stats:', error);
        return { total: 0, by_status: {}, by_priority: {} };
    }
}

// Map Data
async function getMapData() {
    try {
        const response = await fetch(`${API_BASE}/api/stats/map`);
        return await response.json();
    } catch (error) {
        console.error('Error fetching map data:', error);
        return [];
    }
}

// Notifications
async function getNotifications() {
    try {
        const response = await fetch(`${API_BASE}/api/notifications`, {
            headers: getAuthHeaders()
        });
        return await response.json();
    } catch (error) {
        console.error('Error fetching notifications:', error);
        return [];
    }
}

async function markNotificationRead(id) {
    try {
        await fetch(`${API_BASE}/api/notifications/${id}/read`, {
            method: 'PUT',
            headers: getAuthHeaders()
        });
    } catch (error) {
        console.error('Error marking notification read:', error);
    }
}

async function markAllNotificationsRead() {
    try {
        await fetch(`${API_BASE}/api/notifications/read-all`, {
            method: 'PUT',
            headers: getAuthHeaders()
        });
    } catch (error) {
        console.error('Error marking all notifications read:', error);
    }
}

// Validation
async function validateLocation(lat, lng) {
    try {
        const response = await fetch(`${API_BASE}/api/validate/location`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latitude: lat, longitude: lng })
        });
        return await response.json();
    } catch (error) {
        return { valid: false, error: 'Network error' };
    }
}

async function validateKeywords(description, departmentId) {
    try {
        const response = await fetch(`${API_BASE}/api/validate/keywords`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description, department_id: departmentId })
        });
        return await response.json();
    } catch (error) {
        return { valid: false, error: 'Network error' };
    }
}

// ==================== MAP FUNCTIONS ====================

function initMap(containerId, center = [22.5, 72.9], zoom = 13) {
    if (map) {
        map.remove();
    }
    
    map = L.map(containerId).setView(center, zoom);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    return map;
}

function addComplaintMarkers(complaints) {
    // Clear existing markers
    complaintMarkers.forEach(marker => map.removeLayer(marker));
    complaintMarkers = [];
    
    const statusColors = {
        'pending': '#f56565',
        'assigned': '#4299e1',
        'in_progress': '#ecc94b',
        'completed': '#48bb78',
        'resolved': '#2c7a7b',
        'closed': '#718096',
        'reopened': '#f56565'
    };
    
    complaints.forEach(complaint => {
        const color = statusColors[complaint.status] || '#718096';
        
        const marker = L.circleMarker([complaint.latitude, complaint.longitude], {
            radius: 10,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(map);
        
        marker.bindPopup(`
            <strong>${complaint.title}</strong><br>
            <span class="badge bg-${getStatusBadgeClass(complaint.status)}">${complaint.status}</span><br>
            ${complaint.department || ''}
        `);
        
        marker.on('click', () => {
            showComplaintDetail(complaint.id);
        });
        
        complaintMarkers.push(marker);
    });
}

async function fetchAndDisplayPlaces(targetMap) {
    if (!targetMap) targetMap = map; // fallback to global map
    const overpassUrl = 'https://overpass-api.de/api/interpreter';
    
    // Detailed query for Anand city places
    const query = `
        [out:json][timeout:25];
        (
          node["amenity"~"hospital|clinic|police|school|college|university|post_office|townhall|courthouse"](22.40,72.80,22.60,73.00);
          node["leisure"~"park|garden"](22.40,72.80,22.60,73.00);
          node["natural"="water"](22.40,72.80,22.60,73.00);
        );
        out body;
    `;
    
    try {
        const response = await fetch(overpassUrl, {
            method: 'POST',
            body: query
        });
        
        const data = await response.json();
        
        data.elements.forEach(element => {
            const tags = element.tags || {};
            const type = tags.amenity || tags.leisure || tags.natural;
            const name = tags.name || type;
            
            const typeColors = {
                'hospital': '#e53e3e', 'clinic': '#e53e3e',
                'police': '#3182ce', 'courthouse': '#3182ce',
                'school': '#38a169', 'college': '#805ad5', 'university': '#805ad5',
                'post_office': '#ed8936', 'townhall': '#718096',
                'park': '#48bb78', 'garden': '#48bb78',
                'water': '#63b3ed'
            };
            
            const color = typeColors[type] || '#718096';
            
            let iconLabel = '📍';
            if (['hospital', 'clinic'].includes(type)) iconLabel = '🏥';
            else if (['school', 'college', 'university'].includes(type)) iconLabel = '🎓';
            else if (type === 'police') iconLabel = '👮';
            else if (['park', 'garden'].includes(type)) iconLabel = '🌳';
            else if (type === 'water') iconLabel = '💧';
            else if (type === 'post_office') iconLabel = '📮';
            else if (['townhall', 'courthouse'].includes(type)) iconLabel = '🏛️';

            L.circleMarker([element.lat, element.lon], {
                radius: 6,
                fillColor: color,
                color: '#fff',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.9
            }).addTo(targetMap).bindPopup(`<strong>${iconLabel} ${name}</strong><br><small class="text-muted" style="text-transform: capitalize;">${type}</small>`);
        });
    } catch (error) {
        console.error('Error fetching places:', error);
    }
}

// ==================== UI HELPERS ====================

function showAlert(message, type = 'info') {
    const alertClass = {
        'success': 'alert-success-custom',
        'danger': 'alert-danger-custom',
        'warning': 'alert-warning-custom',
        'info': 'alert-info-custom'
    };
    
    const alertHtml = `
        <div class="alert alert-custom alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const container = document.getElementById('alert-container');
    if (container) {
        container.innerHTML = alertHtml;
        setTimeout(() => {
            const alert = container.querySelector('.alert');
            if (alert) alert.remove();
        }, 5000);
    }
}

function getStatusBadgeClass(status) {
    const classes = {
        'pending': 'warning',
        'assigned': 'info',
        'in_progress': 'warning',
        'completed': 'success',
        'resolved': 'success',
        'closed': 'secondary',
        'reopened': 'danger'
    };
    return classes[status] || 'secondary';
}

function getPriorityBadgeClass(priority) {
    const classes = {
        'low': 'success',
        'medium': 'warning',
        'high': 'danger'
    };
    return classes[priority] || 'secondary';
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function renderComplaintCard(complaint) {
    return `
        <div class="complaint-card priority-${complaint.priority}">
            <div class="row">
                <div class="col-md-3">
                    ${complaint.before_image ? 
                        `<img src="${API_BASE}/uploads/before/${complaint.before_image}" class="complaint-image" alt="Before">` :
                        `<div class="complaint-image bg-light d-flex align-items-center justify-content-center">
                            <i class="bi bi-camera text-muted" style="font-size: 2rem;"></i>
                        </div>`
                    }
                </div>
                <div class="col-md-9">
                    <h5>${complaint.title}</h5>
                    <p class="text-muted mb-1">${complaint.description.substring(0, 100)}...</p>
                    <div class="d-flex gap-2">
                        <span class="department-badge">${complaint.department_name || complaint.category}</span>
                        <span class="status-${complaint.status}">${complaint.status}</span>
                        <span class="priority-${complaint.priority}">${complaint.priority}</span>
                    </div>
                    <small class="text-muted">${formatDate(complaint.created_at)}</small>
                </div>
            </div>
        </div>
    `;
}

function renderComplaintTable(complaints) {
    return `
        <table class="table table-hover">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Department</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Date</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${complaints.map(c => `
                    <tr>
                        <td>#${c.id}</td>
                        <td>${c.title}</td>
                        <td>${c.department_name || c.category}</td>
                        <td><span class="status-${c.status}">${c.status}</span></td>
                        <td><span class="text-${c.priority === 'high' ? 'danger' : c.priority === 'medium' ? 'warning' : 'success'}">${c.priority}</span></td>
                        <td>${formatDate(c.created_at)}</td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="showComplaintDetail(${c.id})">
                                <i class="bi bi-eye"></i> View
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function renderNotification(notification) {
    return `
        <div class="list-group-item list-group-item-action ${notification.is_read ? '' : 'bg-light'}" 
             onclick="markNotificationRead(${notification.id})" style="cursor: pointer;">
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1">${notification.title}</h6>
                <small>${formatDate(notification.created_at)}</small>
            </div>
            <p class="mb-1">${notification.message}</p>
        </div>
    `;
}

// ==================== DASHBOARD FUNCTIONS ====================

async function loadDashboardStats() {
    const stats = await getStats();
    
    document.getElementById('stat-total').textContent = stats.total || 0;
    document.getElementById('stat-pending').textContent = stats.by_status?.pending || 0;
    document.getElementById('stat-progress').textContent = stats.by_status?.in_progress || 0;
    document.getElementById('stat-resolved').textContent = stats.by_status?.resolved || 0;
    
    return stats;
}

function renderDashboard() {
    if (!currentUser) {
        window.location.href = 'index.html';
        return;
    }
    
    // Update UI
    document.getElementById('user-name').textContent = currentUser.name;
    document.getElementById('user-role').textContent = 'App Citizen';
    
    // Show citizen dashboard
    document.querySelectorAll('.dashboard-section').forEach(section => {
        section.style.display = 'none';
    });
    
    const dashboard = document.getElementById('dashboard-citizen');
    if (dashboard) {
        dashboard.style.display = 'block';
    }
}

// ==================== GEOLOCATION ====================

function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation is not supported'));
            return;
        }
        
        navigator.geolocation.getCurrentPosition(
            position => {
                resolve({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                });
            },
            error => {
                reject(error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    });
}

async function validateAndSetLocation(inputLat, inputLng) {
    const result = await validateLocation(inputLat, inputLng);
    
    if (!result.valid) {
        showAlert(result.message || 'Location is outside Anand city boundary', 'warning');
        return false;
    }
    
    return true;
}

// ==================== IMAGE HANDLING ====================

function previewImage(file, previewId) {
    const preview = document.getElementById(previewId);
    if (!preview) return;
    
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
}

function handleImageUpload(inputId, previewId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    input.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            // Validate file type
            if (!file.type.startsWith('image/')) {
                showAlert('Please select an image file', 'warning');
                return;
            }
            
            // Validate file size (max 5MB)
            if (file.size > 5 * 1024 * 1024) {
                showAlert('Image size must be less than 5MB', 'warning');
                return;
            }
            
            previewImage(file, previewId);
        }
    });
}

// ==================== CHART FUNCTIONS ====================

function renderStatusChart(stats) {
    const ctx = document.getElementById('statusChart');
    if (!ctx) return;
    
    const byStatus = stats.by_status || {};
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(byStatus),
            datasets: [{
                data: Object.values(byStatus),
                backgroundColor: ['#f56565', '#4299e1', '#ecc94b', '#48bb78', '#2c7a7b', '#718096'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function renderPriorityChart(stats) {
    const ctx = document.getElementById('priorityChart');
    if (!ctx) return;
    
    const byPriority = stats.by_priority || {};
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(byPriority).map(p => p.charAt(0).toUpperCase() + p.slice(1)),
            datasets: [{
                label: 'Complaints by Priority',
                data: Object.values(byPriority),
                backgroundColor: ['#48bb78', '#ecc94b', '#f56565'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// ==================== MODAL FUNCTIONS ====================

function showComplaintDetail(id) {
    getComplaint(id).then(complaint => {
        if (!complaint) {
            showAlert('Complaint not found', 'danger');
            return;
        }
        
        const modalContent = document.getElementById('complaint-detail-content');
        if (!modalContent) return;
        
        modalContent.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    ${complaint.before_image ? 
                        `<img src="${API_BASE}/uploads/before/${complaint.before_image}" class="img-fluid rounded" alt="Before">` :
                        `<div class="bg-light p-5 text-center rounded"><i class="bi bi-camera" style="font-size: 3rem;"></i></div>`
                    }
                    ${complaint.after_image ? 
                        `<div class="mt-3"><h6>After Image</h6><img src="${API_BASE}/uploads/after/${complaint.after_image}" class="img-fluid rounded" alt="After"></div>` : ''
                    }
                </div>
                <div class="col-md-6">
                    <h4>${complaint.title}</h4>
                    <p class="text-muted">${complaint.description}</p>
                    
                    <table class="table table-sm">
                        <tr><td><strong>Department:</strong></td><td>${complaint.department_name}</td></tr>
                        <tr><td><strong>Status:</strong></td><td><span class="status-${complaint.status}">${complaint.status}</span></td></tr>
                        <tr><td><strong>Priority:</strong></td><td><span class="priority-${complaint.priority}">${complaint.priority}</span></td></tr>
                        <tr><td><strong>Address:</strong></td><td>${complaint.address || 'N/A'}</td></tr>
                        <tr><td><strong>Submitted:</strong></td><td>${formatDate(complaint.created_at)}</td></tr>
                        ${complaint.officer_name ? `<tr><td><strong>Officer:</strong></td><td>${complaint.officer_name}</td></tr>` : ''}
                        ${complaint.remarks ? `<tr><td><strong>Remarks:</strong></td><td>${complaint.remarks}</td></tr>` : ''}
                    </table>
                    
                    <div id="detail-map-${complaint.id}" style="height: 250px; border-radius: 8px; border: 1px solid #dee2e6;" class="mt-3 mb-3"></div>
                    
                    ${renderActionButtons(complaint)}
                </div>
            </div>
        `;
        
        const modalElement = document.getElementById('complaintDetailModal');
        const modal = new bootstrap.Modal(modalElement);
        
        modalElement.addEventListener('shown.bs.modal', function onModalShown() {
            const mapContainer = document.getElementById(`detail-map-${complaint.id}`);
            if (mapContainer && complaint.latitude && complaint.longitude && !mapContainer._leaflet_id) {
                const map = L.map(mapContainer).setView([complaint.latitude, complaint.longitude], 15);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
                L.marker([complaint.latitude, complaint.longitude]).addTo(map).bindPopup(complaint.title).openPopup();
            }
            modalElement.removeEventListener('shown.bs.modal', onModalShown);
        });
        
        modal.show();
    });
}

function renderActionButtons(complaint) {
    if (complaint.status === 'closed') {
        return `
            <div class="mt-3 text-success p-2 rounded" style="background-color: #f0fdf4; border: 1px solid #bbf7d0;">
                <i class="bi bi-check-circle-fill"></i> <strong>This issue has been successfully closed and permanently resolved.</strong>
            </div>
        `;
    }
    
    if (complaint.status === 'resolved') {
        return `
            <div class="mt-3 p-3 rounded" style="background-color: #f8f9fa; border: 1px solid #dee2e6;">
                <h6>Issue Resolution Feedback</h6>
                <p class="small text-muted mb-2">The department has marked this resolved. Do you accept the work?</p>
                <textarea id="citizen-feedback" class="form-control mb-2" placeholder="Add feedback before closing..." rows="2"></textarea>
                <div class="d-flex gap-2">
                    <button class="btn btn-success flex-grow-1" onclick="submitCitizenFeedback(${complaint.id}, true)">Accept & Close Issue</button>
                    <button class="btn btn-outline-danger" onclick="submitCitizenFeedback(${complaint.id}, false)">Reopen Issue</button>
                </div>
            </div>
        `;
    } else {
        return '<div class="mt-3 p-2 text-muted bg-light rounded text-center small border"><i class="bi bi-hourglass-split"></i> Issue is currently being processed by the system.</div>';
    }
}

// Admin action handlers removed from citizen app bundle for security

async function submitCitizenFeedback(id, accept) {
    const feedback = document.getElementById('citizen-feedback')?.value || (accept ? 'Accepted' : 'Not satisfied');
    
    const result = await submitFeedback(id, feedback, !accept);
    
    if (result.success) {
        showAlert(accept ? 'Thank you for your feedback!' : 'Complaint has been reopened', accept ? 'success' : 'warning');
        location.reload();
    } else {
        showAlert(result.error, 'danger');
    }
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', () => {
    // Check if user is logged in for dashboard pages
    if (window.location.pathname.includes('dashboard')) {
        if (!checkAuth()) {
            window.location.href = 'login.html';
            return;
        }
        renderDashboard();
    }
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
});
