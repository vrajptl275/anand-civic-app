"""
Civic Issue Reporting System - Flask Backend
Anand City, Gujarat, India
"""

from flask import Flask, jsonify, request, send_from_directory, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import bcrypt
import uuid
import re
from functools import wraps
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv('config/.env')

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'civic-issue-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///data/instance/app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'data/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='citizen')  # citizen, municipal, department, officer
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    citizen_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
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
    
    # Status workflow: pending -> assigned -> in_progress -> completed -> resolved -> closed
    # If reopened: closed -> reopened -> in_progress -> ...
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    
    # Additional fields
    remarks = db.Column(db.Text)
    citizen_feedback = db.Column(db.Text)
    is_fake = db.Column(db.Boolean, default=False)  # Fake issue flag
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    assigned_at = db.Column(db.DateTime)
    in_progress_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    reopened_at = db.Column(db.DateTime)
    
    # Relationships
    citizen = db.relationship('User', foreign_keys=[citizen_id], back_populates='complaints_reported')
    department = db.relationship('Department', back_populates='complaints')
    officer = db.relationship('User', foreign_keys=[officer_id], back_populates='assigned_complaints')
    notifications = db.relationship('Notification', back_populates='complaint')
    
    def to_dict(self, include_images=False):
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
            'reopened_at': self.reopened_at.isoformat() if self.reopened_at else None
        }
        if include_images:
            data['before_image'] = self.before_image
            data['after_image'] = self.after_image
        return data


class Notification(db.Model):
    """Notification model for real-time updates"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='general')  # submitted, assigned, in_progress, completed, resolved, closed, reopened
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    department = Department.query.get(department_id)
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


def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password, password_hash):
    """Check password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def save_image(file, folder='before'):
    """Save uploaded image and return filename"""
    if file and file.filename:
        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        file.save(filepath)
        return filename
    return None


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
        
        # For simplicity, we'll use email as token (in production, use JWT)
        user = User.query.filter_by(email=token, is_active=True).first()
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
def register():
    """Citizen self-registration"""
    data = request.get_json()
    
    required_fields = ['name', 'email', 'phone', 'password']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
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
def login():
    """Login for all user types"""
    data = request.get_json()
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not check_password(data['password'], user.password_hash):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 401
    
    # Return user data (in production, return JWT token)
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'token': user.email  # Using email as simple token
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
    data = request.get_json()
    
    required_fields = ['name', 'email', 'phone', 'password', 'role']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
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
    return jsonify({'message': 'User updated', 'user': user.to_dict()})


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
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Department name required'}), 400
        
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Department email and password required for login'}), 400
        
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
    db.session.commit()
    return jsonify({'message': 'Department deactivated'})


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
    
    complaints = query.order_by(Complaint.created_at.desc()).all()
    return jsonify([c.to_dict(include_images=True) for c in complaints])


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
    
    # 1. GPS Boundary Validation - Anand check
    if not is_within_anand(latitude, longitude):
        return jsonify({'error': 'Out of boundary. Complaints can only be submitted within Anand city.'}), 400
    
    # 2. Fake Issue Detection - Keyword validation
    if not validate_keywords(description, department_id):
        return jsonify({'error': 'Fake issue detected - description does not match selected department. Please select the correct department or provide a description matching the department keywords.'}), 400
    
    # Save image
    image_filename = None
    if before_image:
        image_filename = save_image(before_image, 'before')
    
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
    
    # Create notification
    create_notification(
        request.current_user.id,
        complaint.id,
        'Complaint Submitted',
        f'Your complaint "{title}" has been submitted successfully.',
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
    
    return jsonify({
        'message': 'Complaint submitted successfully',
        'complaint': complaint.to_dict(include_images=True)
    }), 201


@app.route('/api/complaints/<int:id>/assign', methods=['POST'])
@token_required
@role_required('municipal', 'department')
def assign_complaint(id):
    """Assign complaint to officer"""
    complaint = Complaint.query.get_or_404(id)
    data = request.get_json()
    
    officer_id = data.get('officer_id')
    if not officer_id:
        return jsonify({'error': 'Officer ID required'}), 400
    
    # Verify officer exists and belongs to same department
    officer = User.query.filter_by(id=officer_id, role='officer', is_active=True).first()
    if not officer:
        return jsonify({'error': 'Invalid officer'}), 400
    
    if officer.department_id != complaint.department_id:
        return jsonify({'error': 'Officer must be from the same department'}), 400
    
    complaint.officer_id = officer_id
    complaint.status = 'assigned'
    complaint.assigned_at = datetime.utcnow()
    
    db.session.commit()
    
    # Notify officer
    create_notification(
        officer.id,
        complaint.id,
        'Complaint Assigned',
        f'You have been assigned to complaint: {complaint.title}',
        'assigned'
    )
    
    # Notify citizen
    create_notification(
        complaint.citizen_id,
        complaint.id,
        'Complaint Assigned',
        f'Your complaint has been assigned to an officer.',
        'assigned'
    )
    
    return jsonify({
        'message': 'Complaint assigned',
        'complaint': complaint.to_dict(include_images=True)
    })


@app.route('/api/complaints/<int:id>/status', methods=['PUT'])
@token_required
@role_required('municipal', 'department', 'officer')
def update_complaint_status(id):
    """Update complaint status"""
    complaint = Complaint.query.get_or_404(id)
    data = request.get_json()
    
    new_status = data.get('status')
    valid_statuses = ['pending', 'assigned', 'in_progress', 'completed', 'resolved', 'closed', 'reopened', 'rejected', 'reassigned']
    
    if complaint.status == 'closed':
        return jsonify({'error': 'Cannot update a permanently closed complaint'}), 400
        
    if new_status not in valid_statuses:
        return jsonify({'error': 'Invalid status'}), 400
    
    # Role-based validation
    user = request.current_user
    if user.role == 'officer' and complaint.officer_id != user.id:
        return jsonify({'error': 'Not assigned to this complaint'}), 403
    
    if user.role == 'department' and complaint.department_id != user.department_id:
        return jsonify({'error': 'Not in your department'}), 403
    
    # Update status with timestamp
    complaint.status = new_status
    
    if new_status == 'in_progress':
        complaint.in_progress_at = datetime.utcnow()
    elif new_status == 'completed':
        complaint.completed_at = datetime.utcnow()
        # Handle after image upload
        if 'after_image' in data:
            complaint.after_image = data['after_image']
    elif new_status == 'resolved':
        complaint.resolved_at = datetime.utcnow()
    elif new_status == 'closed':
        complaint.closed_at = datetime.utcnow()
    elif new_status == 'reopened':
        complaint.reopened_at = datetime.utcnow()
    
    # Update remarks if provided
    if 'remarks' in data:
        complaint.remarks = data['remarks']
    
    db.session.commit()
    
    # Create notifications
    if new_status == 'in_progress':
        create_notification(complaint.citizen_id, complaint.id, 'In Progress', 'Your complaint is now being worked on.', 'in_progress')
    elif new_status == 'completed':
        create_notification(complaint.citizen_id, complaint.id, 'Completed', 'Your complaint has been completed. Please verify.', 'completed')
    elif new_status == 'resolved':
        create_notification(complaint.citizen_id, complaint.id, 'Resolved', 'Your complaint has been resolved.', 'resolved')
    elif new_status == 'closed':
        create_notification(complaint.citizen_id, complaint.id, 'Closed', 'Your complaint has been closed.', 'closed')
    elif new_status == 'reopened':
        send_notifications_to_role('municipal', complaint.id, 'Complaint Reopened', f'Complaint "{complaint.title}" has been reopened.', 'reopened')
    
    return jsonify({
        'message': 'Status updated',
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
    """Submit citizen feedback and optionally reopen"""
    complaint = Complaint.query.get_or_404(id)
    data = request.get_json()
    
    if complaint.citizen_id != request.current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    complaint.citizen_feedback = data.get('feedback')
    
    # If citizen not satisfied, reopen
    if data.get('reopen'):
        complaint.status = 'reopened'
        complaint.reopened_at = datetime.utcnow()
        
        # Notify municipal
        send_notifications_to_role(
            'municipal',
            complaint.id,
            'Complaint Reopened',
            f'Citizen has reopened complaint: {complaint.title}',
            'reopened'
        )
    else:
        # If citizen is satisfied, permanently close the issue
        complaint.status = 'closed'
    
    db.session.commit()
    
    return jsonify({
        'message': 'Feedback submitted',
        'complaint': complaint.to_dict()
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
    
    image_filename = save_image(after_image, 'after')
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
    notifications = Notification.query.filter_by(user_id=user.id).order_by(
        Notification.created_at.desc()
    ).limit(50).all()
    return jsonify([n.to_dict() for n in notifications])


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
    
    query = Complaint.query.filter(Complaint.status.in_(['pending', 'in_progress', 'closed']))
    
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
    data = request.get_json()
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
    data = request.get_json()
    description = data.get('description')
    department_id = data.get('department_id')
    
    if not description or not department_id:
        return jsonify({'error': 'Description and department_id required'}), 400
    
    is_valid = validate_keywords(description, department_id)
    
    return jsonify({
        'valid': is_valid,
        'message': 'Description matches department keywords' if is_valid else 'Fake issue detected - description does not match department'
    })


# ============== SEED DATA ROUTES ==============

@app.route('/api/seed', methods=['POST'])
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


@app.route('/api/proxy/overpass', methods=['POST'])
def proxy_overpass():
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
            return response.read(), response.getcode(), response.headers.items()
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
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


# ============== APP INITIALIZATION ==============

with app.app_context():
    # Execute unconditionally on cloud boot to ensure PostgreSQL tables exist
    db.create_all()
    
    # Bootstrap Security: Ensure a Municipal Admin always exists in a fresh database
    from sqlalchemy.exc import ProgrammingError
    try:
        if not User.query.filter_by(role='municipal').first():
            hashed_pw = hash_password('admin123')
            admin = User(name='Anand Administrator', email='admin@anand.gov.in', phone='9999999999', password_hash=hashed_pw, role='municipal', is_active=True)
            db.session.add(admin)
            db.session.commit()
            print("System Bootstrap: Default Municipal Admin created (admin@anand.gov.in / admin123)")
    except Exception as e:
        db.session.rollback()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8001))
    app.run(host='0.0.0.0', port=port, debug=True)
