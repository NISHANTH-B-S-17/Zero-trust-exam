# Project Nivasha

## Overview
Project Nivasha is a secure, zero-trust system comprising a backend API, an admin dashboard, and a locked-down kiosk application. It incorporates forensic features like steganography for secure payload extraction.

## Deployment & Architecture Note
*   **Vercel Hosting:** Vercel hosts the Admin Frontend UI statically.
*   **Local Engine Required:** Full live telemetry, student monitoring, and T-5 crypto operations require running the backend engine locally at `http://127.0.0.1:8080`. Public web previews will display a clear "Local backend not connected" status until the local backend is started.

## Setup Steps
1. Clone the repository and navigate to the project directory.
2. Install backend dependencies: `pip install -r backend/requirements.txt`
3. Install kiosk dependencies: `cd kiosk && npm install && cd ..`
4. Set up necessary certificates and keys as documented by individual components.

## Commands to Run
*   **Backend:** `cd backend && uvicorn main:app --reload` (or appropriate launch command per backend setup)
*   **Admin Dashboard:** Serve the `admin/dashboard.html` file using a local web server (e.g., `python -m http.server 8080 --directory admin`).
*   **Kiosk:** `cd kiosk && npm start`

## Test Command
To run all automated tests across the project:
`pytest tests/`

## Demo Flow
1.  Start the backend service.
2.  Launch the admin dashboard and log in (or verify authorization tokens).
3.  Launch the kiosk application.
4.  Demonstrate the core workflow, including authentication, payload extraction (if applicable), and interaction between the kiosk and the backend via the admin system.

## Limitations
*   Requires pre-configured network access and appropriate permissions for local servers.
*   Kiosk lockdown mode may require administrative privileges on Windows (`lockdown.ps1`).
*   Certificates must be manually generated and placed in the correct directories for HTTPS/WSS (if configured).

## Final Demo Checklist
- [ ] Backend starts without errors and connects to the database.
- [ ] Admin dashboard loads and authenticates successfully.
- [ ] Kiosk application launches in lockdown mode.
- [ ] Kiosk can communicate securely with the backend.
- [ ] Forensic/steganography features work as expected.
- [ ] All unit tests pass.
- [ ] Uncommitted runtime files are correctly ignored by `.gitignore`.