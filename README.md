# Anand Civic Issue Reporting System

A role-based civic complaint management system built for Anand City. The project allows citizens to report local issues with location and image evidence, while municipal administrators, department admins, and field officers manage the complaint lifecycle through dedicated dashboards.

This project is well-suited for a college major project because it demonstrates full-stack development, authentication, role-based access control, complaint workflow automation, notifications, file uploads, location validation, and dashboard analytics in one system.

## Project Overview

The application is built as a single Flask backend that also serves a multi-page frontend dashboard. It supports four roles:

- `Citizen`: registers, logs in, reports complaints, tracks progress, and closes or reopens resolved issues.
- `Municipal Admin`: views city-wide analytics, creates departments, creates officers, manages users, and monitors all complaints.
- `Department Admin`: sees complaints for their department, assigns officers, updates priority, resolves or reassigns complaints.
- `Officer`: works on assigned complaints, updates status, and uploads completion images.

## Core Features

- Role-based login and JWT authentication
- Citizen complaint submission with:
  - title and description
  - department selection
  - GPS coordinates
  - address
  - before-image upload
- Anand city boundary validation for complaint location
- Department keyword validation to reduce mismatched or fake complaints
- Optional Gemini AI image validation for uploaded complaint images
- Department-wise complaint assignment to officers
- Strict complaint lifecycle and status transition rules
- Citizen feedback flow to close or reopen resolved complaints
- Notification system for status updates and assignments
- Dashboard statistics by status, priority, and department
- Public stats and map endpoints for dashboard/landing-page display
- Before/after image handling for complaint evidence
- SQLite fallback for local development and PostgreSQL support for deployment

## Complaint Workflow

The complaint flow in the project is:

`pending -> assigned -> in_progress -> completed -> resolved -> closed`

Additional branches supported by the system:

- `pending -> rejected`
- `completed -> reassigned`
- `resolved -> reopened`

Role permissions in the workflow:

- `Citizen`
  - submit complaint
  - view own complaints
  - close resolved complaint
  - reopen resolved complaint
- `Department Admin`
  - assign complaint to officer
  - reject pending complaint
  - resolve completed complaint
  - reassign completed complaint
  - update priority
- `Officer`
  - move assigned complaint to `in_progress`
  - move `in_progress` complaint to `completed`
  - upload after-work image
- `Municipal Admin`
  - monitor all complaints and analytics
  - manage departments and officers

## Tech Stack

### Backend

- Python
- Flask
- Flask-SQLAlchemy
- Flask-CORS
- Flask-Limiter
- JWT authentication with `PyJWT`
- `bcrypt` for password hashing
- `requests` for Gemini API calls

### Frontend

- HTML
- CSS
- Vanilla JavaScript
- Bootstrap Icons
- Leaflet map integration
- Chart-based analytics in dashboards

### Database

- SQLite for local fallback
- PostgreSQL for production/deployment

## Folder Structure

```text
v1/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── render.yaml
│   ├── config/
│   │   └── .env
│   ├── data/
│   │   ├── instance/
│   │   └── uploads/
│   └── scripts/
│       └── migrate_db.py
├── frontend/
│   ├── pages/
│   │   ├── auth/
│   │   ├── dashboards/
│   │   └── home/
│   └── public/
│       ├── css/
│       └── js/
└── README.md
```

## Main Pages

- Landing page: `frontend/pages/home/index.html`
- Login page: `frontend/pages/auth/login.html`
- Register page: `frontend/pages/auth/register.html`
- Citizen dashboard: `frontend/pages/dashboards/dashboard-citizen.html`
- Department dashboard: `frontend/pages/dashboards/dashboard-department.html`
- Officer dashboard: `frontend/pages/dashboards/dashboard-officer.html`
- Municipal dashboard: `frontend/pages/dashboards/dashboard-municipal.html`

## Backend Data Model

The main database entities are:

- `User`
  - stores name, email, phone, password hash, role, department, active state
- `Department`
  - stores department name, description, keywords, icon, active state
- `Complaint`
  - stores citizen, department, officer, issue details, location, images, status, priority, deadlines, remarks, timestamps
- `Notification`
  - stores user-specific updates related to complaint events

## Important Backend Capabilities

### Authentication

- citizen self-registration
- multi-role login
- JWT token generation and verification
- route protection using decorators

### Validation

- basic input validation for names, email, phone, and passwords
- complaint payload validation
- location restriction within Anand city boundary
- department keyword matching
- optional AI image analysis through Gemini

### Notifications

Notifications are generated automatically when:

- a complaint is submitted
- a complaint is assigned
- work starts
- work is completed
- a complaint is resolved
- a complaint is rejected
- a complaint is reassigned
- a complaint is reopened
- a complaint is closed

### Analytics

The system provides:

- role-based dashboard stats
- public stats endpoint
- department-wise counts
- complaint map data

## API Summary

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

### Users

- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/<id>`
- `DELETE /api/users/<id>`

### Departments

- `GET /api/departments`
- `POST /api/departments`
- `PUT /api/departments/<id>`
- `DELETE /api/departments/<id>`

### Complaints

- `GET /api/complaints`
- `GET /api/complaints/<id>`
- `POST /api/complaints`
- `POST /api/complaints/<id>/assign`
- `PUT /api/complaints/<id>/status`
- `PUT /api/complaints/<id>/priority`
- `POST /api/complaints/<id>/feedback`
- `POST /api/complaints/<id>/image`

### Notifications

- `GET /api/notifications`
- `PUT /api/notifications/<id>/read`
- `PUT /api/notifications/read-all`

### Stats and Validation

- `GET /api/stats`
- `GET /api/stats/public`
- `GET /api/stats/map`
- `POST /api/validate/location`
- `POST /api/validate/keywords`
- `POST /api/analyze-image`

### Utility

- `GET /health`
- `GET /api`
- `POST /api/seed`

## Local Setup

### 1. Clone the project

```bash
git clone <your-repo-url>
cd v1
```

### 2. Create and activate a virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create or update `backend/config/.env` with values like:

```env
SECRET_KEY=your_secret_key
DATABASE_URL=sqlite:///data/instance/app.db
TOKEN_EXPIRY_HOURS=24
FLASK_ENV=development
CORS_ORIGINS=http://localhost:8001,http://127.0.0.1:8001
GEMINI_API_KEY=your_gemini_api_key
# Optional alias if your host already uses this name
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
BOOTSTRAP_ADMIN_EMAIL=municipal@example.com
BOOTSTRAP_ADMIN_PASSWORD=your_password
BOOTSTRAP_ADMIN_PHONE=9999999999
```

Notes:

- `GEMINI_API_KEY` is optional. `GOOGLE_API_KEY` is also accepted as an alias in deployment.
- If neither key is provided, AI image analysis is skipped gracefully.
- `DATABASE_URL` can point to SQLite for local use or PostgreSQL in deployment.
- `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` are useful for automatically creating the first municipal admin in a fresh database.

### 5. Run the application

```bash
python app.py
```

By default, the app runs on:

```text
http://127.0.0.1:8001
```

The root route redirects to:

```text
/pages/home/index.html
```

## Commands Reference

### Project setup commands

```bash
git clone <your-repo-url>
cd v1
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run commands

Run the development server:

```bash
cd backend
source venv/bin/activate
python app.py
```

Run with a custom port:

```bash
cd backend
source venv/bin/activate
PORT=8001 python app.py
```

Run in production style with Gunicorn:

```bash
cd backend
source venv/bin/activate
gunicorn app:app --log-file -
```

### Database commands

Use local SQLite by default:

```bash
cd backend
source venv/bin/activate
python app.py
```

Migrate SQLite data to PostgreSQL:

```bash
cd backend/scripts
python migrate_db.py
```

Important:

- the migration script expects `DATABASE_URL` to point to PostgreSQL
- it reads data from `backend/data/instance/app.db`
- it clears PostgreSQL tables before importing data

### Seed command

After logging in as a municipal admin, seed default departments:

```bash
curl -X POST http://127.0.0.1:8001/api/seed \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Health check commands

Check if the backend is alive:

```bash
curl http://127.0.0.1:8001/health
```

Check API info:

```bash
curl http://127.0.0.1:8001/api
```

Check public stats:

```bash
curl http://127.0.0.1:8001/api/stats/public
```

### Authentication API commands

Register a citizen:

```bash
curl -X POST http://127.0.0.1:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Citizen",
    "email": "citizen@example.com",
    "phone": "9876543210",
    "password": "password123"
  }'
```

Login:

```bash
curl -X POST http://127.0.0.1:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "citizen@example.com",
    "password": "password123"
  }'
```

Get current user:

```bash
curl http://127.0.0.1:8001/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Complaint API commands

Get complaints for the logged-in user:

```bash
curl http://127.0.0.1:8001/api/complaints \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Get complaints with filters:

```bash
curl "http://127.0.0.1:8001/api/complaints?status=pending&priority=high" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Get one complaint:

```bash
curl http://127.0.0.1:8001/api/complaints/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Create a complaint with image upload:

```bash
curl -X POST http://127.0.0.1:8001/api/complaints \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "title=Water Leakage" \
  -F "description=Water pipeline is leaking near the main road" \
  -F "department_id=3" \
  -F "latitude=22.5645" \
  -F "longitude=72.9289" \
  -F "address=Anand, Gujarat" \
  -F "before_image=@/absolute/path/to/image.jpg"
```

Assign a complaint to an officer:

```bash
curl -X POST http://127.0.0.1:8001/api/complaints/1/assign \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "officer_id": 5,
    "deadline_days": 7
  }'
```

Update complaint status:

```bash
curl -X PUT http://127.0.0.1:8001/api/complaints/1/status \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in_progress",
    "remarks": "Work has started"
  }'
```

Update complaint priority:

```bash
curl -X PUT http://127.0.0.1:8001/api/complaints/1/priority \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "priority": "high"
  }'
```

Submit citizen feedback to close a complaint:

```bash
curl -X POST http://127.0.0.1:8001/api/complaints/1/feedback \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "Issue solved properly",
    "reopen": false
  }'
```

Submit citizen feedback to reopen a complaint:

```bash
curl -X POST http://127.0.0.1:8001/api/complaints/1/feedback \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "Problem still exists",
    "reopen": true
  }'
```

Upload after-work image:

```bash
curl -X POST http://127.0.0.1:8001/api/complaints/1/image \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "after_image=@/absolute/path/to/after.jpg"
```

### Notification API commands

Get notifications:

```bash
curl http://127.0.0.1:8001/api/notifications \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Mark one notification as read:

```bash
curl -X PUT http://127.0.0.1:8001/api/notifications/1/read \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Mark all notifications as read:

```bash
curl -X PUT http://127.0.0.1:8001/api/notifications/read-all \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Validation commands

Validate location:

```bash
curl -X POST http://127.0.0.1:8001/api/validate/location \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 22.5645,
    "longitude": 72.9289
  }'
```

Validate complaint keywords:

```bash
curl -X POST http://127.0.0.1:8001/api/validate/keywords \
  -H "Content-Type: application/json" \
  -d '{
    "description": "There is garbage near the roadside",
    "department_id": 1
  }'
```

Analyze image with AI:

```bash
curl -X POST http://127.0.0.1:8001/api/analyze-image \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "department_id=1" \
  -F "image=@/absolute/path/to/image.jpg"
```

### Useful development commands

Check installed Python packages:

```bash
pip list
```

Freeze dependencies:

```bash
pip freeze
```

Deactivate the virtual environment:

```bash
deactivate
```

## First-Time Project Setup

When the database is empty, you can:

1. start the server
2. log in using a bootstrapped municipal admin, or configure one in `.env`
3. call `POST /api/seed` to create initial departments and a default municipal account for development

The seed route creates default departments such as:

- Garbage & Sanitation
- Roads & Infrastructure
- Water Supply
- Electricity
- Parks & Gardens
- Health & Hospitals
- Education
- Police & Security

## Default Development Notes

- Uploaded images are stored inside `backend/data/uploads/`
- Local SQLite data is stored inside `backend/data/instance/app.db`
- Logs are written to `backend/logs/app.log`
- Complaint list endpoints include pagination metadata
- Static frontend files are served by Flask

## Deployment

The project includes `backend/render.yaml` for deployment on Render.

Configured deployment behavior:

- installs Python dependencies from `backend/requirements.txt`
- starts the Flask app using Gunicorn
- provisions a PostgreSQL database
- injects environment variables such as:
  - `DATABASE_URL`
  - `SECRET_KEY`
  - `GEMINI_API_KEY`
  - `GOOGLE_API_KEY`
  - `FLASK_ENV`

Example start command used in deployment:

```bash
gunicorn app:app --log-file -
```

## Security and Validation Highlights

- JWT-based protected APIs
- password hashing with bcrypt
- rate limiting on login and registration routes
- role-based authorization decorators
- complaint ownership checks
- department ownership checks before assignment/resolution
- permanent seal behavior for closed complaints
- file upload size limit set to 16 MB

## Why This Project Is Good for a College Major Project

This project demonstrates multiple practical software engineering concepts in one system:

- frontend and backend integration
- REST API design
- authentication and authorization
- database modeling
- CRUD operations
- workflow/state management
- notifications
- file uploads
- geolocation validation
- cloud deployment readiness
- optional AI-assisted validation

It is not just a static website. It shows a complete real-world problem-solving system with multiple user roles and operational workflows.

## Future Improvements

Possible extensions if you want to continue improving the project:

- add email or SMS notifications
- add complaint search and advanced filters
- add dashboard export reports
- add audit trail/history timeline for each complaint
- add stronger image moderation and duplicate issue detection
- add unit tests and API integration tests
- add pagination controls in the frontend UI
- add admin controls for resolving overdue complaints faster

## Author Notes

This project is designed as a practical civic-tech complaint management platform focused on usability, role separation, and workflow clarity. It is appropriate for academic demonstration, portfolio use, and further expansion into a larger smart-city application.
