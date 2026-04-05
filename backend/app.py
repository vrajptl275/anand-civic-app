"""
Civic Issue Reporting System - Flask Backend
Anand City, Gujarat, India
"""

from flask import Flask, jsonify, request, send_from_directory, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_limiter import Limiter
from datetime import datetime, timedelta, timezone
import os
import bcrypt
import uuid
import re
import logging
import jwt
import base64
import requests
import mimetypes
from functools import wraps
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

def utcnow():
    """Timezone-aware UTC now, avoids deprecation."""
    return datetime.now(timezone.utc)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, 'config', '.env'))
load_dotenv()


def get_database_url():
    """Resolve and normalize the database URL, preferring PostgreSQL when configured."""
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///data/instance/app.db').strip()
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    return database_url

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend', static_url_path='')

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'civic-issue-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'data/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['TOKEN_EXPIRY_HOURS'] = int(os.environ.get('TOKEN_EXPIRY_HOURS', '24'))

if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql://'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'app.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        'CORS_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:8001,http://localhost:8001'
    ).split(',')
    if origin.strip()
]
CORS(app, origins=allowed_origins)

# Initialize rate limiter
limiter = Limiter(app)

if os.environ.get('FLASK_ENV') == 'production' and app.config['SECRET_KEY'] == 'civic-issue-secret-key-2024':
    raise RuntimeError('SECRET_KEY must be set in production')

# Create database directory for SQLite fallback
db_path = app.config['SQLALCHEMY_DATABASE_URI']
if db_path.startswith('sqlite:///'):
    db_file_path = db_path.replace('sqlite:///', '')
    db_dir = os.path.dirname(db_file_path)
    os.makedirs(db_dir, exist_ok=True)

# Create upload directories
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'before'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'after'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)

db = SQLAlchemy(app)

# ============== ANAND CITY BOUNDARY (Approximate) ==============
# Anand city coordinates - we'll use a rectangular boundary
ANAND_BOUNDS = {
    'min_lat': 22.40,
    'max_lat': 22.60,
    'min_lng': 72.80,
    'max_lng': 73.00
}

def is_within_anand(lat, lng):
    """Check if coordinates are within Anand city boundary"""
    return (ANAND_BOUNDS['min_lat'] <= lat <= ANAND_BOUNDS['max_lat'] and 
            ANAND_BOUNDS['min_lng'] <= lng <= ANAND_BOUNDS['max_lng'])

# ============== DATABASE MODELS ==============

class User(db.Model):
    """User model with role-based access"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='citizen', index=True)  # citizen, municipal, department, officer
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    
    # Relationships
    department = db.relationship('Department', back_populates='users', foreign_keys=[department_id])
    complaints_reported = db.relationship('Complaint', foreign_keys='Complaint.citizen_id', back_populates='citizen')
    assigned_complaints = db.relationship('Complaint', foreign_keys='Complaint.officer_id', back_populates='officer')
    notifications = db.relationship('Notification', back_populates='user')
    
    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_sensitive:
            data['password_hash'] = self.password_hash
        return data


class Department(db.Model):
    """Department model with keywords for fake issue detection"""
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    keywords = db.Column(db.Text)  # Comma-separated keywords for validation
    icon = db.Column(db.String(50), default='folder')
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    
    # Relationships
    users = db.relationship('User', back_populates='department', foreign_keys='User.department_id')
    complaints = db.relationship('Complaint', back_populates='department')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'keywords': self.keywords.split(',') if self.keywords else [],
            'icon': self.icon,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Complaint(db.Model):
    """Complaint model with full workflow"""
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False, index=True)
    officer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    # Issue details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # For backward compatibility
    
    # Location
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(500))
    
    # Images
    before_image = db.Column(db.String(255))
    after_image = db.Column(db.String(255))
    
    # Status workflow: pending -> assigned -> in_progress -> completed -> resolved/reassigned -> closed
    # Roles: Department=assign/reject/resolve/reassign, Officer=start/complete, Citizen=close/reopen, Municipal=view
    status = db.Column(db.String(20), default='pending', index=True)
    priority = db.Column(db.String(20), default='medium', index=True)  # low, medium, high
    
    # Deadline tracking
    deadline_days = db.Column(db.Integer, default=7)  # Days allowed to resolve
    deadline = db.Column(db.DateTime)  # Computed: assigned_at + deadline_days
    
    # Additional fields
    remarks = db.Column(db.Text)
    citizen_feedback = db.Column(db.Text)
    is_fake = db.Column(db.Boolean, default=False)  # Fake issue flag
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    assigned_at = db.Column(db.DateTime)
    in_progress_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    reopened_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)
    
    # Relationships
    citizen = db.relationship('User', foreign_keys=[citizen_id], back_populates='complaints_reported')
    department = db.relationship('Department', back_populates='complaints')
    officer = db.relationship('User', foreign_keys=[officer_id], back_populates='assigned_complaints')
    notifications = db.relationship('Notification', back_populates='complaint')
    
    def to_dict(self, include_images=False):
        # Compute overdue status
        is_overdue = False
        if self.deadline and self.status not in ('resolved', 'closed', 'rejected'):
            is_overdue = utcnow() > self.deadline
        
        data = {
            'id': self.id,
            'citizen_id': self.citizen_id,
            'citizen_name': self.citizen.name if self.citizen else None,
            'citizen_phone': self.citizen.phone if self.citizen else None,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'officer_id': self.officer_id,
            'officer_name': self.officer.name if self.officer else None,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address,
            'status': self.status,
            'priority': self.priority,
            'deadline_days': self.deadline_days,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'is_overdue': is_overdue,
            'remarks': self.remarks,
            'citizen_feedback': self.citizen_feedback,
            'is_fake': self.is_fake,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'in_progress_at': self.in_progress_at.isoformat() if self.in_progress_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'reopened_at': self.reopened_at.isoformat() if self.reopened_at else None,
            'rejected_at': self.rejected_at.isoformat() if self.rejected_at else None
        }
        if include_images:
            data['before_image'] = self.before_image
            data['after_image'] = self.after_image
        return data


class Notification(db.Model):
    """Notification model for real-time updates"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='general', index=True)  # submitted, assigned, in_progress, completed, resolved, closed, reopened
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='notifications')
    complaint = db.relationship('Complaint', back_populates='notifications')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'complaint_id': self.complaint_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============== HELPER FUNCTIONS ==============

def validate_keywords(description, department_id):
    """Validate if description matches department keywords (fake issue detection)"""
    department = db.session.get(Department, department_id)
    if not department or not department.keywords:
        return True  # No keywords = allow all
    
    keywords = [k.strip().lower() for k in department.keywords.split(',')]
    description_lower = description.lower()
    
    # Check if any keyword matches
    for keyword in keywords:
        if keyword in description_lower:
            return True
    return False


def create_notification(user_id, complaint_id, title, message, notification_type):
    """Create a notification for a user"""
    notification = Notification(
        user_id=user_id,
        complaint_id=complaint_id,
        title=title,
        message=message,
        type=notification_type
    )
    db.session.add(notification)
    return notification


def send_notifications_to_role(role, complaint_id, title, message, notification_type):
    """Send notifications to all users of a specific role"""
    users = User.query.filter_by(role=role, is_active=True).all()
    for user in users:
        create_notification(user.id, complaint_id, title, message, notification_type)


def _notify_department_users(department_id, complaint_id, title, message, notification_type):
    """Send notifications to all department-role users of a specific department"""
    users = User.query.filter_by(role='department', department_id=department_id, is_active=True).all()
    for user in users:
        create_notification(user.id, complaint_id, title, message, notification_type)


def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password, password_hash):
    """Check password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def is_valid_email(email):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email or ''))


def validate_password_strength(password):
    return isinstance(password, str) and len(password) >= 6


def validate_name(name):
    return isinstance(name, str) and 2 <= len(name.strip()) <= 100


def validate_phone(phone):
    return isinstance(phone, str) and 7 <= len(phone.strip()) <= 20


def validate_complaint_payload(title, description):
    if not isinstance(title, str) or not 3 <= len(title.strip()) <= 200:
        return 'Title must be between 3 and 200 characters'
    if not isinstance(description, str) or not 10 <= len(description.strip()) <= 2000:
        return 'Description must be between 10 and 2000 characters'
    return None


def create_access_token(user):
    expires_at = utcnow() + timedelta(hours=app.config['TOKEN_EXPIRY_HOURS'])
    payload = {
        'sub': str(user.id),
        'role': user.role,
        'email': user.email,
        'exp': expires_at,
        'iat': utcnow()
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    return token, expires_at


def decode_access_token(token):
    return jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])


def save_image(file, folder='before'):
    """Save uploaded image and return filename"""
    if file and file.filename:
        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        file.save(filepath)
        return filename
    return None


def analyze_image_with_gemini(image_path, department_name, department_keywords):
    """Analyze image using Gemini API to verify it matches department"""
    api_key = (
        os.environ.get('GEMINI_API_KEY')
        or os.environ.get('GOOGLE_API_KEY')
    )
    if not api_key or api_key == 'your_gemini_api_key_here':
        return {
            'error': 'missing_api_key',
            'message': 'Image analysis unavailable - set GEMINI_API_KEY or GOOGLE_API_KEY'
        }

    configured_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash').strip() or 'gemini-2.5-flash'
    candidate_models = []
    for model_name in [configured_model, 'gemini-2.5-flash', 'gemini-2.0-flash']:
        if model_name not in candidate_models:
            candidate_models.append(model_name)
    
    try:
        with open(image_path, 'rb') as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')

        mime_type = mimetypes.guess_type(image_path)[0] or 'image/jpeg'
        if not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'
        
        prompt = f"""You are an image classifier for a civic issue reporting system.
Department: {department_name}
Keywords for this department: {department_keywords}

Analyze the uploaded image and determine:
1. Does this image match the department category? (e.g., if department is "Garbage & Sanitation", look for trash, waste, dirty areas, etc.)
2. What category/issue do you see in the image?

Respond ONLY in JSON format like this:
{{
  "is_match": true or false,
  "detected_category": "what you see in the image",
  "confidence": "high" or "medium" or "low",
  "reason": "brief explanation"
}}

Important: Only return true for is_match if the image clearly shows issues related to the department keywords."""

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_data}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 500,
                "responseMimeType": "application/json"
            }
        }

        last_error = None

        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 404:
                app.logger.warning('Gemini model %s returned 404, trying next fallback if available', model_name)
                last_error = {
                    'error': 'model_not_found',
                    'message': f'Image analysis failed - Gemini model {model_name} was not found'
                }
                continue

            if response.status_code != 200:
                app.logger.error('Gemini API returned %s for model %s: %s', response.status_code, model_name, response.text[:500])
                return {
                    'error': 'api_error',
                    'message': f'Image analysis failed - Gemini API returned {response.status_code} for {model_name}'
                }

            result = response.json()
            candidates = result.get('candidates') or []
            parts = (((candidates[0] or {}).get('content') or {}).get('parts') or []) if candidates else []
            text = '\n'.join(part.get('text', '') for part in parts if isinstance(part, dict) and part.get('text')).strip()

            if not text:
                app.logger.error('Gemini API returned no text for model %s: %s', model_name, result)
                return {
                    'error': 'empty_response',
                    'message': f'Image analysis failed - Gemini returned an empty response for {model_name}'
                }

            import json

            if text.startswith('```'):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text).strip()

            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                app.logger.error('Gemini response did not contain JSON for model %s: %s', model_name, text[:500])
                return {
                    'error': 'invalid_response',
                    'message': f'Image analysis failed - Gemini returned an unreadable response for {model_name}'
                }

            parsed = json.loads(json_match.group())
            parsed['message'] = parsed.get('message') or 'Image analysis completed'
            parsed['model'] = model_name
            return parsed

        return last_error or {
            'error': 'model_not_found',
            'message': 'Image analysis failed - no compatible Gemini model was found'
        }
        
    except Exception as e:
        app.logger.error(f"Gemini API error: {str(e)}")
        return {
            'error': 'request_failed',
            'message': f'Image analysis failed - {str(e)}'
        }


# ============== AUTH DECORATOR ==============

def token_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]

        try:
            payload = decode_access_token(token)
            user_id = int(payload.get('sub'))
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except (jwt.InvalidTokenError, TypeError, ValueError):
            return jsonify({'error': 'Invalid token'}), 401

        user = User.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            return jsonify({'error': 'Invalid token'}), 401
        
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Decorator to require specific role(s)"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(request, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            if request.current_user.role not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ============== AUTH ROUTES ==============

@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("3 per minute")
def register():
    """Citizen self-registration"""
    data = request.get_json() or {}
    
    required_fields = ['name', 'email', 'phone', 'password']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    if not validate_name(data['name']):
        return jsonify({'error': 'Name must be between 2 and 100 characters'}), 400
    if not is_valid_email(data['email']):
        return jsonify({'error': 'Please provide a valid email address'}), 400
    if not validate_phone(data['phone']):
        return jsonify({'error': 'Phone number must be between 7 and 20 characters'}), 400
    if not validate_password_strength(data['password']):
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
    
    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    # Create citizen user
    user = User(
        name=data['name'],
        email=data['email'],
        phone=data['phone'],
        password_hash=hash_password(data['password']),
        role='citizen'
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'Registration successful',
        'user': user.to_dict()
    }), 201


@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Login for all user types"""
    data = request.get_json() or {}
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
        
    email_clean = str(data['email']).strip()
    if not is_valid_email(email_clean):
        return jsonify({'error': 'Please provide a valid email address'}), 400
    
    user = User.query.filter_by(email=email_clean).first()
    
    if not user or not check_password(data['password'], user.password_hash):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 401

    token, expires_at = create_access_token(user)

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'token': token,
        'expires_at': expires_at.isoformat() + 'Z'
    })


@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user():
    """Get current user profile"""
    return jsonify(request.current_user.to_dict())


# ============== USER MANAGEMENT ROUTES ==============

@app.route('/api/users', methods=['GET'])
@token_required
@role_required('municipal', 'department')
def get_users():
    """Get all users (municipal and department)"""
    role = request.args.get('role')
    department_id = request.args.get('department_id', type=int)
    
    query = User.query
    if role:
        query = query.filter_by(role=role)
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    users = query.all()
    return jsonify([user.to_dict() for user in users])


@app.route('/api/users', methods=['POST'])
@token_required
@role_required('municipal')
def create_user():
    """Create department user or officer (municipal only)"""
    data = request.get_json() or {}
    
    required_fields = ['name', 'email', 'phone', 'password', 'role']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    if not validate_name(data['name']):
        return jsonify({'error': 'Name must be between 2 and 100 characters'}), 400
    if not is_valid_email(data['email']):
        return jsonify({'error': 'Please provide a valid email address'}), 400
    if not validate_phone(data['phone']):
        return jsonify({'error': 'Phone number must be between 7 and 20 characters'}), 400
    if not validate_password_strength(data['password']):
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
    
    if data['role'] not in ['department', 'officer']:
        return jsonify({'error': 'Invalid role. Must be department or officer'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    user = User(
        name=data['name'],
        email=data['email'],
        phone=data['phone'],
        password_hash=hash_password(data['password']),
        role=data['role'],
        department_id=data.get('department_id')
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User created successfully',
        'user': user.to_dict()
    }), 201


@app.route('/api/users/<int:id>', methods=['PUT'])
@token_required
@role_required('municipal')
def update_user(id):
    """Update user (municipal only)"""
    user = User.query.get_or_404(id)
    data = request.get_json()
    
    if 'name' in data:
        user.name = data['name']
    if 'phone' in data:
        user.phone = data['phone']
    if 'department_id' in data:
        user.department_id = data['department_id']
    if 'is_active' in data:
        user.is_active = data['is_active']
    if 'password' in data:
        user.password_hash = hash_password(data['password'])
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'User updated', 'user': user.to_dict()})


@app.route('/api/users/<int:id>', methods=['DELETE'])
@token_required
@role_required('municipal')
def delete_user(id):
    """Deactivate user (municipal only)"""
    user = User.query.get_or_404(id)
    user.is_active = False
    db.session.commit()
    return jsonify({'message': 'User deactivated'})


# ============== DEPARTMENT ROUTES ==============

@app.route('/api/departments', methods=['GET'])
def get_departments():
    """Get all active departments (public)"""
    departments = Department.query.filter_by(is_active=True).all()
    return jsonify([dept.to_dict() for dept in departments])


@app.route('/api/departments', methods=['POST'])
@token_required
@role_required('municipal')
def create_department():
    """Create department (municipal only)"""
    data = request.get_json() or {}
    
    if not data.get('name'):
        return jsonify({'error': 'Department name required'}), 400
        
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Department email and password required for login'}), 400
    if not validate_name(data['name']):
        return jsonify({'error': 'Department name must be between 2 and 100 characters'}), 400
    if not is_valid_email(data['email']):
        return jsonify({'error': 'Please provide a valid email address'}), 400
    if not validate_password_strength(data['password']):
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
        
    # Check if email is already registered
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    department = Department(
        name=data['name'],
        description=data.get('description'),
        keywords=data.get('keywords', ''),  # Comma-separated keywords
        icon=data.get('icon', 'folder')
    )
    db.session.add(department)
    db.session.flush() # get id
    
    # Create the department auth user
    hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    dept_user = User(
        name=data['name'] + ' Admin',
        email=data['email'],
        phone=data.get('phone', ''),
        password_hash=hashed_pw,
        role='department',
        department_id=department.id
    )
    db.session.add(dept_user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Department created',
        'department': department.to_dict()
    }), 201


@app.route('/api/departments/<int:id>', methods=['PUT'])
@token_required
@role_required('municipal')
def update_department(id):
    """Update department (municipal only)"""
    department = Department.query.get_or_404(id)
    data = request.get_json()
    
    if 'name' in data:
        department.name = data['name']
    if 'description' in data:
        department.description = data['description']
    if 'keywords' in data:
        department.keywords = data['keywords']
    if 'icon' in data:
        department.icon = data['icon']
    if 'is_active' in data:
        department.is_active = data['is_active']
    
    db.session.commit()
    return jsonify({'message': 'Department updated', 'department': department.to_dict()})


@app.route('/api/departments/<int:id>', methods=['DELETE'])
@token_required
@role_required('municipal')
def delete_department(id):
    """Deactivate department (municipal only)"""
    department = Department.query.get_or_404(id)
    department.is_active = False
    
    # Also deactivate associated department admin/officer users to revoke their login access
    associated_users = User.query.filter_by(department_id=id).all()
    for user_entry in associated_users:
        if user_entry.is_active:
            user_entry.is_active = False
            user_entry.email = f"deleted_dept{id}_{user_entry.id}_{user_entry.email}"
        
    db.session.commit()
    return jsonify({'success': True, 'message': 'Department deactivated'})


# ============== COMPLAINT ROUTES ==============

@app.route('/api/complaints', methods=['GET'])
@token_required
def get_complaints():
    """Get complaints based on user role"""
    user = request.current_user
    
    # Query parameters
    status = request.args.get('status')
    department_id = request.args.get('department_id', type=int)
    priority = request.args.get('priority')
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 50, type=int), 100)
    
    query = Complaint.query
    
    # Filter based on role
    if user.role == 'citizen':
        query = query.filter_by(citizen_id=user.id)
    elif user.role == 'officer':
        query = query.filter_by(officer_id=user.id)
    elif user.role == 'department':
        query = query.filter_by(department_id=user.department_id)
    # Municipal can see all
    
    # Apply filters
    if status:
        query = query.filter_by(status=status)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if priority:
        query = query.filter_by(priority=priority)
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    complaints = query.order_by(Complaint.created_at.desc()).offset(offset).limit(limit).all()
    
    return jsonify({
        'complaints': [c.to_dict(include_images=True) for c in complaints],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit
        }
    })


@app.route('/api/complaints/<int:id>', methods=['GET'])
@token_required
def get_complaint(id):
    """Get single complaint details"""
    complaint = Complaint.query.get_or_404(id)
    user = request.current_user
    
    # Check access
    if user.role == 'citizen' and complaint.citizen_id != user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify(complaint.to_dict(include_images=True))


@app.route('/api/complaints', methods=['POST'])
@token_required
@role_required('citizen')
def create_complaint():
    """Submit new complaint (citizen only)"""
    # Handle multipart form data
    title = request.form.get('title')
    description = request.form.get('description')
    department_id = request.form.get('department_id', type=int)
    latitude = request.form.get('latitude', type=float)
    longitude = request.form.get('longitude', type=float)
    address = request.form.get('address')
    before_image = request.files.get('before_image')
    
    # Validate required fields
    if not all([title, description, department_id, latitude, longitude]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Enhanced input validation
    if not isinstance(department_id, int) or department_id <= 0:
        return jsonify({'error': 'Invalid department ID'}), 400
    
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return jsonify({'error': 'Invalid GPS coordinates'}), 400
    
    if address and (not isinstance(address, str) or len(address.strip()) > 500):
        return jsonify({'error': 'Address must be less than 500 characters'}), 400

    validation_error = validate_complaint_payload(title, description)
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    # 1. GPS Boundary Validation - Anand check
    if not is_within_anand(latitude, longitude):
        return jsonify({'error': 'Out of boundary. Complaints can only be submitted within Anand city.'}), 400
    
    # 2. Fake Issue Detection - Keyword validation
    if not validate_keywords(description, department_id):
        return jsonify({'error': 'Fake issue detected - description does not match selected department. Please select the correct department or provide a description matching the department keywords.'}), 400
    
    # Save image first (needed for analysis below)
    image_filename = None
    if before_image:
        image_filename = save_image(before_image, 'before')
    
    # 3. AI Image Analysis - Gemini check (optional warning)
    analyze_image_flag = request.form.get('analyze_image', 'false').lower() == 'true'
    image_analysis_result = None
    
    if before_image and analyze_image_flag and image_filename:
        department = db.session.get(Department, department_id)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'before', image_filename)
        
        image_analysis_result = analyze_image_with_gemini(
            temp_path,
            department.name if department else '',
            department.keywords if department else ''
        )
        
        if image_analysis_result and image_analysis_result.get('error'):
            app.logger.warning('Skipping fake-image rejection during complaint submission: %s', image_analysis_result.get('message'))
        elif image_analysis_result and not image_analysis_result.get('is_match', True):
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({
                'error': 'Fake image detected',
                'message': f'This image does not appear to be related to {department.name}. Please upload an image that shows the issue you are reporting.',
                'detected_category': image_analysis_result.get('detected_category'),
                'confidence': image_analysis_result.get('confidence')
            }), 400
    
    # Create complaint
    complaint = Complaint(
        citizen_id=request.current_user.id,
        department_id=department_id,
        title=title,
        description=description,
        latitude=latitude,
        longitude=longitude,
        address=address,
        before_image=image_filename,
        status='pending',
        priority='medium'
    )
    
    db.session.add(complaint)
    db.session.commit()
    
    # Notify citizen
    create_notification(
        request.current_user.id,
        complaint.id,
        'Complaint Submitted',
        f'Your complaint "{title}" has been submitted successfully.',
        'submitted'
    )
    
    # Notify the specific department
    _notify_department_users(
        department_id, complaint.id,
        'New Complaint',
        f'New complaint submitted: {title}. Please review and assign an officer.',
        'submitted'
    )
    
    # Notify municipal users
    send_notifications_to_role(
        'municipal',
        complaint.id,
        'New Complaint',
        f'New complaint submitted: {title}',
        'submitted'
    )
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Complaint submitted successfully',
        'complaint': complaint.to_dict(include_images=True)
    }), 201


@app.route('/api/complaints/<int:id>/assign', methods=['POST'])
@token_required
@role_required('department')
def assign_complaint(id):
    """Assign/reassign complaint to officer (department only)"""
    complaint = Complaint.query.get_or_404(id)
    data = request.get_json()
    user = request.current_user
    
    # Department can only assign their own complaints
    if user.department_id != complaint.department_id:
        return jsonify({'error': 'Not in your department'}), 403
    
    # Only allow assignment from valid statuses
    if complaint.status not in ('pending', 'reopened', 'reassigned'):
        return jsonify({'error': f'Cannot assign from status: {complaint.status}'}), 400
    
    officer_id = data.get('officer_id')
    if not officer_id:
        return jsonify({'error': 'Officer ID required'}), 400
    
    # Verify officer exists and belongs to same department
    officer = User.query.filter_by(id=officer_id, role='officer', is_active=True).first()
    if not officer:
        return jsonify({'error': 'Invalid officer'}), 400
    
    if officer.department_id != complaint.department_id:
        return jsonify({'error': 'Officer must be from the same department'}), 400
    
    # Set deadline
    deadline_days = data.get('deadline_days', 7)
    if not isinstance(deadline_days, int) or deadline_days < 1:
        deadline_days = 7
    
    now = utcnow()
    complaint.officer_id = officer_id
    complaint.status = 'assigned'
    complaint.assigned_at = now
    complaint.deadline_days = deadline_days
    complaint.deadline = now + timedelta(days=deadline_days)
    
    db.session.commit()
    
    # Notify officer
    create_notification(
        officer.id, complaint.id,
        'Complaint Assigned',
        f'You have been assigned to complaint: {complaint.title}. Deadline: {deadline_days} days.',
        'assigned'
    )
    # Notify citizen
    create_notification(
        complaint.citizen_id, complaint.id,
        'Officer Assigned',
        f'Your complaint "{complaint.title}" has been assigned to officer {officer.name}.',
        'assigned'
    )
    # Notify all municipal users
    send_notifications_to_role(
        'municipal', complaint.id,
        'Complaint Assigned',
        f'Complaint "{complaint.title}" assigned to officer {officer.name} ({deadline_days}-day deadline).',
        'assigned'
    )
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Complaint assigned',
        'complaint': complaint.to_dict(include_images=True)
    })


@app.route('/api/complaints/<int:id>/status', methods=['PUT'])
@token_required
@role_required('department', 'officer')
def update_complaint_status(id):
    """Update complaint status with strict role-based transition rules"""
    complaint = Complaint.query.get_or_404(id)
    data = request.get_json()
    user = request.current_user
    
    new_status = data.get('status')
    
    # Closed complaints are permanently sealed
    if complaint.status == 'closed':
        return jsonify({'error': 'This complaint is permanently closed. No changes allowed.'}), 400
    
    # ─── STRICT ROLE→TRANSITION MATRIX ───────────────────────
    # Officer: assigned→in_progress, in_progress→completed
    # Department: pending→rejected, completed→resolved, completed→reassigned
    
    ALLOWED_TRANSITIONS = {
        'officer': {
            'assigned':    ['in_progress'],
            'in_progress': ['completed'],
        },
        'department': {
            'pending':    ['rejected'],
            'completed':  ['resolved', 'reassigned'],
        }
    }
    
    role = user.role
    current = complaint.status
    allowed = ALLOWED_TRANSITIONS.get(role, {}).get(current, [])
    
    if new_status not in allowed:
        return jsonify({'error': f'{role.title()} cannot change status from "{current}" to "{new_status}".'}), 400
    
    # ─── OWNERSHIP CHECKS ────────────────────────────────────
    if role == 'officer' and complaint.officer_id != user.id:
        return jsonify({'error': 'You are not assigned to this complaint'}), 403
    if role == 'department' and user.department_id != complaint.department_id:
        return jsonify({'error': 'Not in your department'}), 403
    
    # ─── APPLY STATUS + TIMESTAMPS ───────────────────────────
    now = utcnow()
    complaint.status = new_status
    
    if new_status == 'in_progress':
        complaint.in_progress_at = now
    elif new_status == 'completed':
        complaint.completed_at = now
    elif new_status == 'resolved':
        complaint.resolved_at = now
    elif new_status == 'rejected':
        complaint.rejected_at = now
    elif new_status == 'reassigned':
        complaint.officer_id = None  # Unassign officer, department will re-assign
    
    # Update remarks if provided
    if data.get('remarks'):
        complaint.remarks = data['remarks']
    
    db.session.commit()
    
    # ─── COMPREHENSIVE NOTIFICATIONS ─────────────────────────
    title_str = complaint.title
    
    if new_status == 'in_progress':
        # Officer started → notify citizen, department, municipal
        create_notification(complaint.citizen_id, complaint.id,
            'Work Started', f'Work has started on your complaint: {title_str}', 'in_progress')
        _notify_department_users(complaint.department_id, complaint.id,
            'Work Started', f'Officer {user.name} has started working on: {title_str}', 'in_progress')
        send_notifications_to_role('municipal', complaint.id,
            'Work Started', f'Officer {user.name} started work on: {title_str}', 'in_progress')
    
    elif new_status == 'completed':
        # Officer completed → notify citizen, department, municipal
        create_notification(complaint.citizen_id, complaint.id,
            'Issue Completed', f'Work has been completed on: {title_str}. Awaiting department review.', 'completed')
        _notify_department_users(complaint.department_id, complaint.id,
            'Issue Completed', f'Officer {user.name} has completed: {title_str}. Please review.', 'completed')
        send_notifications_to_role('municipal', complaint.id,
            'Issue Completed', f'Officer {user.name} completed: {title_str}', 'completed')
    
    elif new_status == 'resolved':
        # Department resolved → notify citizen, officer, municipal
        create_notification(complaint.citizen_id, complaint.id,
            'Issue Resolved', f'Your complaint "{title_str}" has been resolved. Please close or reopen it.', 'resolved')
        if complaint.officer_id:
            create_notification(complaint.officer_id, complaint.id,
                'Issue Resolved', f'Complaint "{title_str}" has been resolved by department.', 'resolved')
        send_notifications_to_role('municipal', complaint.id,
            'Issue Resolved', f'Complaint "{title_str}" has been resolved by department.', 'resolved')
    
    elif new_status == 'rejected':
        # Department rejected → notify citizen, municipal
        reason = data.get('remarks', 'No reason provided')
        create_notification(complaint.citizen_id, complaint.id,
            'Issue Rejected', f'Your complaint "{title_str}" has been rejected. Reason: {reason}', 'rejected')
        send_notifications_to_role('municipal', complaint.id,
            'Issue Rejected', f'Complaint "{title_str}" rejected by department. Reason: {reason}', 'rejected')
    
    elif new_status == 'reassigned':
        # Department reassigned → notify citizen, old officer, municipal
        old_officer_name = complaint.officer.name if complaint.officer else 'Unknown'
        create_notification(complaint.citizen_id, complaint.id,
            'Issue Reassigned', f'Your complaint "{title_str}" is being reassigned for better resolution.', 'reassigned')
        send_notifications_to_role('municipal', complaint.id,
            'Issue Reassigned', f'Complaint "{title_str}" reassigned by department (was: {old_officer_name}).', 'reassigned')
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Status updated to {new_status}',
        'complaint': complaint.to_dict(include_images=True)
    })


@app.route('/api/complaints/<int:id>/priority', methods=['PUT'])
@token_required
@role_required('municipal', 'department')
def update_priority(id):
    """Update complaint priority"""
    complaint = Complaint.query.get_or_404(id)
    data = request.get_json()
    
    priority = data.get('priority')
    if priority not in ['low', 'medium', 'high']:
        return jsonify({'error': 'Invalid priority'}), 400
    
    complaint.priority = priority
    db.session.commit()
    
    return jsonify({
        'message': 'Priority updated',
        'complaint': complaint.to_dict()
    })


@app.route('/api/complaints/<int:id>/feedback', methods=['POST'])
@token_required
@role_required('citizen')
def submit_feedback(id):
    """Citizen closes or reopens a resolved complaint"""
    complaint = Complaint.query.get_or_404(id)
    data = request.get_json()
    
    if complaint.citizen_id != request.current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Citizen can only act on RESOLVED complaints
    if complaint.status != 'resolved':
        return jsonify({'error': 'You can only close or reopen a resolved complaint.'}), 400
    
    complaint.citizen_feedback = data.get('feedback')
    title_str = complaint.title
    
    if data.get('reopen'):
        # ── REOPEN ──
        complaint.status = 'reopened'
        complaint.reopened_at = utcnow()
        
        # Notify department
        _notify_department_users(complaint.department_id, complaint.id,
            'Complaint Reopened',
            f'Citizen is not satisfied with "{title_str}". Please reassign.',
            'reopened')
        # Notify municipal
        send_notifications_to_role('municipal', complaint.id,
            'Complaint Reopened',
            f'Citizen reopened complaint: {title_str}',
            'reopened')
    else:
        # ── CLOSE (permanently) ──
        complaint.status = 'closed'
        complaint.closed_at = utcnow()
        
        # Notify department
        _notify_department_users(complaint.department_id, complaint.id,
            'Complaint Closed',
            f'Citizen has confirmed and closed: {title_str}. Issue fully resolved!',
            'closed')
        # Notify the officer who completed it
        if complaint.officer_id:
            create_notification(complaint.officer_id, complaint.id,
                'Complaint Closed',
                f'Great work! Complaint "{title_str}" has been closed by the citizen.',
                'closed')
        # Notify municipal
        send_notifications_to_role('municipal', complaint.id,
            'Complaint Closed',
            f'Complaint "{title_str}" permanently closed by citizen.',
            'closed')
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Feedback submitted',
        'complaint': complaint.to_dict(include_images=True)
    })


@app.route('/api/complaints/<int:id>/image', methods=['POST'])
@token_required
@role_required('officer')
def upload_after_image(id):
    """Upload after image (officer only)"""
    complaint = Complaint.query.get_or_404(id)
    
    if complaint.officer_id != request.current_user.id:
        return jsonify({'error': 'Not assigned to this complaint'}), 403
    
    after_image = request.files.get('after_image')
    if not after_image:
        return jsonify({'error': 'No image provided'}), 400
    
    analyze_image_flag = request.form.get('analyze_image', 'true').lower() == 'true'
    
    image_filename = save_image(after_image, 'after')
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'after', image_filename)
    
    if analyze_image_flag:
        department = complaint.department
        analysis_result = analyze_image_with_gemini(
            temp_path,
            department.name if department else '',
            department.keywords if department else ''
        )
        
        if analysis_result and analysis_result.get('error'):
            app.logger.warning('Skipping fake-image rejection during completion upload: %s', analysis_result.get('message'))
        elif analysis_result and not analysis_result.get('is_match', True):
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({
                'error': 'Fake image detected',
                'message': f'This image does not appear to show work completed for {department.name}. Please upload a proper completion photo.',
                'detected_category': analysis_result.get('detected_category'),
                'confidence': analysis_result.get('confidence')
            }), 400
    
    complaint.after_image = image_filename
    
    db.session.commit()
    
    return jsonify({
        'message': 'Image uploaded',
        'complaint': complaint.to_dict(include_images=True)
    })


# ============== NOTIFICATION ROUTES ==============

@app.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications():
    """Get user notifications"""
    user = request.current_user
    
    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 20, type=int), 50)
    offset = (page - 1) * limit
    
    query = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc())
    total = query.count()
    notifications = query.offset(offset).limit(limit).all()
    
    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit
        }
    })


@app.route('/api/notifications/<int:id>/read', methods=['PUT'])
@token_required
def mark_notification_read(id):
    """Mark notification as read"""
    notification = Notification.query.get_or_404(id)
    
    if notification.user_id != request.current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Notification marked as read'})


@app.route('/api/notifications/read-all', methods=['PUT'])
@token_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    Notification.query.filter_by(
        user_id=request.current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    return jsonify({'message': 'All notifications marked as read'})


# ============== STATISTICS & ANALYTICS ROUTES ==============

def build_public_stats():
    """Get public stats using SQL aggregation (optimized)"""
    from sqlalchemy import func
    
    total = db.session.query(func.count(Complaint.id)).scalar() or 0
    
    status_counts = db.session.query(
        Complaint.status,
        func.count(Complaint.id)
    ).group_by(Complaint.status).all()
    
    by_status = {status: count for status, count in status_counts}
    
    resolved_total = (
        by_status.get('resolved', 0) +
        by_status.get('closed', 0) +
        by_status.get('completed', 0)
    )
    
    return {
        'total': total,
        'by_status': by_status,
        'resolved_total': resolved_total
    }


@app.route('/api/stats/public', methods=['GET'])
def get_public_stats():
    """Public aggregate stats for the landing page"""
    return jsonify(build_public_stats())

@app.route('/api/stats', methods=['GET'])
@token_required
def get_stats():
    """Get dashboard statistics based on role"""
    user = request.current_user
    
    query = Complaint.query
    
    # Filter based on role
    if user.role == 'citizen':
        query = query.filter_by(citizen_id=user.id)
    elif user.role == 'officer':
        query = query.filter_by(officer_id=user.id)
    elif user.role == 'department':
        query = query.filter_by(department_id=user.department_id)
    
    total = query.count()
    
    # By status
    by_status = db.session.query(
        Complaint.status, 
        db.func.count(Complaint.id)
    ).group_by(Complaint.status)
    
    # Apply role filter
    if user.role == 'citizen':
        by_status = by_status.filter(Complaint.citizen_id == user.id)
    elif user.role == 'officer':
        by_status = by_status.filter(Complaint.officer_id == user.id)
    elif user.role == 'department':
        by_status = by_status.filter(Complaint.department_id == user.department_id)
    
    by_status = by_status.all()
    
    # By priority
    by_priority = db.session.query(
        Complaint.priority,
        db.func.count(Complaint.id)
    )
    
    if user.role == 'citizen':
        by_priority = by_priority.filter(Complaint.citizen_id == user.id)
    elif user.role == 'officer':
        by_priority = by_priority.filter(Complaint.officer_id == user.id)
    elif user.role == 'department':
        by_priority = by_priority.filter(Complaint.department_id == user.department_id)
    
    by_priority = by_priority.group_by(Complaint.priority).all()
    
    # By department (for municipal)
    by_department = []
    if user.role == 'municipal':
        by_dept = db.session.query(
            Department.name,
            db.func.count(Complaint.id)
        ).join(Complaint).group_by(Department.name).all()
        by_department = [{'name': name, 'count': count} for name, count in by_dept]
    
    return jsonify({
        'total': total,
        'by_status': {status: count for status, count in by_status},
        'by_priority': {priority: count for priority, count in by_priority},
        'by_department': by_department
    })


@app.route('/api/stats/map', methods=['GET'])
def get_map_data():
    """Get complaints for map display"""
    status = request.args.get('status')
    
    # Show both in-progress/resolved statuses for map display
    query = Complaint.query.filter(Complaint.status.in_(['pending', 'in_progress', 'resolved', 'closed']))
    
    if status:
        query = query.filter_by(status=status)
    
    complaints = query.all()
    
    return jsonify([{
        'id': c.id,
        'title': c.title,
        'latitude': c.latitude,
        'longitude': c.longitude,
        'status': c.status,
        'department': c.department.name if c.department else None
    } for c in complaints])


# ============== FILE SERVE ROUTES ==============

@app.route('/uploads/<folder>/<filename>')
def serve_upload(folder, filename):
    """Serve uploaded files"""
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], folder), filename)


# ============== VALIDATION ROUTES ==============

@app.route('/api/validate/location', methods=['POST'])
def validate_location():
    """Validate if coordinates are within Anand"""
    data = request.get_json() or {}
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if latitude is None or longitude is None:
        return jsonify({'error': 'Latitude and longitude required'}), 400
    
    is_valid = is_within_anand(latitude, longitude)
    
    return jsonify({
        'valid': is_valid,
        'message': 'Within Anand city' if is_valid else 'Out of boundary'
    })


@app.route('/api/validate/keywords', methods=['POST'])
def validate_keywords_api():
    """Validate description against department keywords"""
    data = request.get_json() or {}
    description = data.get('description')
    department_id = data.get('department_id')
    
    if not description or not department_id:
        return jsonify({'error': 'Description and department_id required'}), 400
    
    is_valid = validate_keywords(description, department_id)
    
    return jsonify({
        'valid': is_valid,
        'message': 'Description matches department keywords' if is_valid else 'Fake issue detected - description does not match department'
    })


@app.route('/api/analyze-image', methods=['POST'])
@token_required
def analyze_image():
    """Analyze image using Gemini AI to verify it matches department"""
    department_id = request.form.get('department_id', type=int)
    image_file = request.files.get('image')
    
    if not department_id or not image_file:
        return jsonify({'error': 'Department ID and image required'}), 400
    
    department = db.session.get(Department, department_id)
    if not department:
        return jsonify({'error': 'Invalid department'}), 400
    
    temp_filename = f"{uuid.uuid4()}_{secure_filename(image_file.filename)}"
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
    image_file.save(temp_path)
    
    try:
        result = analyze_image_with_gemini(
            temp_path,
            department.name,
            department.keywords or ''
        )
        
        if not result:
            return jsonify({
                'message': 'Image analysis failed - unknown error',
                'is_match': None
            }), 200

        if result.get('error'):
            return jsonify({
                'message': result.get('message'),
                'error': result.get('error'),
                'is_match': None
            }), 200
        
        return jsonify({
            'is_match': result.get('is_match'),
            'detected_category': result.get('detected_category'),
            'confidence': result.get('confidence'),
            'reason': result.get('reason'),
            'model': result.get('model'),
            'is_fake': not result.get('is_match', True)
        })
        
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ============== SEED DATA ROUTES ==============

@app.route('/api/seed', methods=['POST'])
@token_required
@role_required('municipal')
def seed_data():
    """Seed initial data (for development)"""
    # Check if already seeded
    if Department.query.first():
        return jsonify({'message': 'Data already seeded'}), 400
    
    # Create departments with keywords
    departments = [
        Department(
            name='Garbage & Sanitation',
            description='Issues related to garbage collection, waste management, and sanitation',
            keywords='garbage,waste,trash,dustbin,dirty,cleanliness,sewage,drain,stench,smell, refuse, litter, garbage truck, sweeper',
            icon='trash'
        ),
        Department(
            name='Roads & Infrastructure',
            description='Issues related to roads, bridges, footpaths, and infrastructure',
            keywords='road,pothole,bridge,footpath,sidewalk,drainage,traffic light,signal,street light,lighting, pavement, crack, broken, damaged, construction',
            icon='road'
        ),
        Department(
            name='Water Supply',
            description='Issues related to water supply, pipelines, and drainage',
            keywords='water,leak,pipeline,pipe,tank,tap,supply,drinking,overflow,drain,sewage',
            icon='tint'
        ),
        Department(
            name='Electricity',
            description='Issues related to electricity, street lights, and power supply',
            keywords='electricity,power,light,street light,transformer,cable,wire,outage,voltage',
            icon='flash'
        ),
        Department(
            name='Parks & Gardens',
            description='Issues related to public parks, gardens, and green spaces',
            keywords='park,garden,tree,green,bench,playground,maintenance,landscape',
            icon='tree'
        ),
        Department(
            name='Health & Hospitals',
            description='Issues related to health services and medical facilities',
            keywords='hospital,clinic,doctor,medical,health,ambulance,pharmacy,medicine',
            icon='plus'
        ),
        Department(
            name='Education',
            description='Issues related to schools, colleges, and educational institutions',
            keywords='school,college,education,student,teacher,building,classroom',
            icon='book'
        ),
        Department(
            name='Police & Security',
            description='Issues related to police, security, and law enforcement',
            keywords='police,security,crime,accident,safety,emergency,danger',
            icon='shield'
        )
    ]
    
    for dept in departments:
        db.session.add(dept)
    
    # Create municipal user (admin)
    municipal = User(
        name='Municipal Administrator',
        email='municipal@anand.gov.in',
        phone='9876543210',
        password_hash=hash_password('municipal123'),
        role='municipal'
    )
    db.session.add(municipal)
    
    db.session.commit()
    
    return jsonify({'message': 'Seed data created successfully'})


# ============== ROOT ROUTE ==============

@app.route('/')
def home():
    return redirect('/pages/home/index.html')


# ============== HEALTH CHECK ==============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for load balancers and monitoring"""
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'

    status = 'ok' if db_status == 'healthy' else 'degraded'
    status_code = 200 if status == 'ok' else 503

    return jsonify({
        'status': 'ok' if db_status == 'healthy' else 'degraded',
        'database': db_status,
        'timestamp': utcnow().isoformat()
    }), status_code


@app.route('/api/proxy/overpass', methods=['POST', 'OPTIONS'])
def proxy_overpass():
    if request.method == 'OPTIONS':
        return '', 200
        
    import urllib.request
    try:
        req = urllib.request.Request(
            'https://overpass-api.de/api/interpreter',
            data=request.data,
            headers={
                'User-Agent': 'AnandCivicApp/1.0',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        with urllib.request.urlopen(req) as response:
            body = response.read()
            # ONLY return safe dictionary headers (Strip Transfer-Encoding to prevent App crash)
            safe_headers = {k: v for k, v in response.headers.items() if k.lower() in ['content-type']}
            return body, response.getcode(), safe_headers
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mobile-app/<path:filename>')
def serve_mobile_app(filename):
    return send_from_directory('../mobile-app', filename)

@app.route('/api')
def api_info():
    return jsonify({
        'message': 'Civic Issue Reporting System - Anand City API',
        'version': '1.0.0',
        'endpoints': {
            'auth': '/api/auth',
            'users': '/api/users',
            'departments': '/api/departments',
            'complaints': '/api/complaints',
            'notifications': '/api/notifications',
            'stats': '/api/stats',
            'map': '/api/stats/map',
            'validate': '/api/validate'
        }
    })


# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(error):
    app.logger.warning('404 for path %s', request.path)
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.exception('Unhandled server error on %s', request.path)
    return jsonify({'error': 'Internal server error'}), 500


# ============== APP INITIALIZATION ==============

with app.app_context():
    # Execute unconditionally on cloud boot to ensure PostgreSQL tables exist
    db.create_all()
    
    # Bootstrap Security: Ensure a Municipal Admin exists in a fresh database when explicitly configured
    from sqlalchemy.exc import ProgrammingError
    try:
        if not User.query.filter_by(role='municipal').first():
            admin_email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL')
            admin_password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
            admin_phone = os.environ.get('BOOTSTRAP_ADMIN_PHONE', '9999999999')
            if admin_email and admin_password:
                hashed_pw = hash_password(admin_password)
                admin = User(name='Municipal Administrator', email=admin_email, phone=admin_phone, password_hash=hashed_pw, role='municipal', is_active=True)
                db.session.add(admin)
                db.session.commit()
                print(f"System Bootstrap: Municipal Admin created ({admin_email})")
            else:
                print('WARNING: No municipal admin found. Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD to initialize the first admin. If using existing DB, ignore this.')
    except Exception as e:
        db.session.rollback()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8001))
    print("\n" + "="*50, flush=True)
    print("🚀 ANAND CIVIC SERVER IS LIVE AND RUNNING!", flush=True)
    print(f"🌐 LOCAL URL: http://127.0.0.1:{port}", flush=True)
    print(f"➡️  CTRL+C to quit", flush=True)
    print("="*50 + "\n", flush=True)
    app.run(host='0.0.0.0', port=port, debug=True)
