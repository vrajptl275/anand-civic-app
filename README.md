# Anand Civic Issue Reporting System

A comprehensive, role-based smart city platform engineered to streamline infrastructure complaint management for Anand City. This system provides a dedicated mobile interface for citizens to upload geo-tagged photo evidence of issues, and seamlessly routes the data into a secure web portal for municipal officers and department administrators to resolve.

## 🏛 Architecture Overview
The repository is fundamentally split into three isolated stacks for maximum security and scalability:

* **`backend/`**: A powerful Flask Python API processing all data, managing authentication, handling file uploads, and tracking the strict lifecycle state-machine of each complaint inside a **PostgreSQL** database.
* **`frontend/`**: The main Administrative Web Portal. This interface serves role-based dashboards specifically designed for Municipal Admins, Department Heads, and Field Officers to manage and resolve issues dynamically.
* **`mobile-app/`**: An entirely separate, mobile-optimized interface strictly for Citizens. Stripped of all administrative logic, it allows users to securely capture photos, validate their GPS coordinates visually on a map, and push issue reports straight into the municipal pipeline. Designed to be compiled into a robust Android `.apk` via Capacitor/Cordova.

## 🚀 Key Features
* **Role-Based Access Control (RBAC):** Perfect segregation of duties between Citizens, Field Officers, Departments, and Municipal Administrators.
* **Strict State-Machine Security:** The system enforces an un-breakable lifecycle. Admins cannot change an issue while a Field Officer is actively working, Citizens cannot close an issue until it's verified by the Department, and once an issue is universally "Closed," it is cryptographically locked by the backend to prevent tampering.
* **Geo-Fencing Validation:** GPS integration mathematically verifies that submitted complaints fall within the Anand City boundaries.
* **NLP Keyword AI Detection:** Warns users dynamically if their textual description does not match the department they selected (e.g. submitting a "water leak" to the "Lighting Department") to filter out spam.
* **Real-time Map Visualizations:** Dynamic Leaflet.js dashboards charting complaints by status and severity, alongside civic infrastructure layouts pulled via Overpass APIs.

## ☁️ Cloud Deployment (Render.com)

This system is configured using **Infrastructure as Code** via a `render.yaml` Blueprint, allowing instant 1-click cloud deployment.

1. Upload this repository to **GitHub**.
2. Log into [Render.com](https://render.com) and click **"New Blueprint"**.
3. Select this repository. The `render.yaml` file will automatically intercept the deployment, provision an enterprise-grade **PostgreSQL** server in the background, spin up a massive secure Python **Gunicorn** layer for the API, and securely load the production environmental tokens. 

> **Important Mobile App Note:**
> Before packaging the `mobile-app/` directory into a native `.apk`, remember to replace the `API_BASE` variable inside `mobile-app/js/main.js` with your newly minted Render production URL so the smartphones know where to find the server!

## 💻 Local Development Setup

To run this instance locally on your machine for testing or development:

```bash
# 1. Start the PostgreSQL Server via Homebrew
brew services start postgresql

# 2. Navigate to the backend directory
cd backend

# 3. Create a python virtual environment and install requirements
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Boot the system
python app.py
```
The Flask server will handle syncing with the PostgreSQL database implicitly via `.env` files and broadcast the unified Web Portal directly to `http://localhost:8001/`!
