# Nivasha Student Kiosk Terminal

A secure, air-gapped Electron shell for the Nivasha Zero-Trust Exam Engine.

## Requirements
- Node.js (v18+)
- Local FastAPI Security Node running on `127.0.0.1:8080` (or runs in mock offline mode)

## Installation
```bash
cd kiosk
npm install
```

## Running the Kiosk
```bash
npm start
```
*(or `npm run dev`)*

## Features
- **Loopback Isolation:** Rejects all non-loopback network traffic to prevent outbound leaks.
- **Anti-VM Protection:** Inspects hardware via WMIC to detect common hypervisors (VMware, VirtualBox, etc.).
- **Shortcut Interception:** Traps dangerous combinations like Alt+Tab, Alt+F4, and F12.
- **Clipboard Hygiene:** Clears the clipboard upon window blur/focus events.

## Demo Steps
1. Launch the backend node (if available).
2. Run `npm start` in the `kiosk` directory.
3. The dark-themed portal will appear.
4. Enter any Candidate UUID (e.g., `550e8400-e29b-41d4-a716-446655440000`).
5. The exam will load. Try answering questions, marking for review, and checking the minimal palette navigation.
6. Try copying text (it is blocked/detected).
7. Submit the exam to receive a generated offline receipt hash.

## Limitations & Security Model
This application provides a **defense-in-depth kiosk** designed to raise the cost of cheating and support incident response. It is **not** a perfect lockdown mechanism and cannot guarantee 100% screenshot prevention or full leak-proof isolation. It effectively detects suspicious events (like focus loss and banned keystrokes) and reports them to the local security node's Insider Risk Engine, but a determined user with physical access to an unmanaged machine could potentially bypass standard Electron constraints (e.g. via Ctrl+Alt+Del). True bare-metal security requires OS-level policies like Windows Assigned Access (see `lockdown.ps1`).
