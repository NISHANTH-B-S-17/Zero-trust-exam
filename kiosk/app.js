// Constants
const API_BASE = 'http://127.0.0.1:8080/api/v1/student';
const STORAGE_KEY = 'NIVASHA_EXAM_SESSION_V2';

// State
let state = {
    uuid: null,
    token: null,
    paper: null,
    responses: {}, // { questionId: answer }
    flags: {}, // { questionId: boolean }
    visited: {}, // { questionId: boolean }
    currentIndex: 0,
    remainingSeconds: 0,
    lastSync: null
};

let heartbeatInterval = null;
let timerInterval = null;
let securityEventsQueue = [];

// DOM Elements
const views = {
    login: document.getElementById('login-view'),
    exam: document.getElementById('exam-view')
};

// Listeners
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    // Notify electron main process
    if (window.electronAPI) {
        window.electronAPI.reportRendererReady();
        window.electronAPI.onSecurityEvent(handleSecurityEvent);
    }

    // Try to restore session
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            if (parsed.uuid && parsed.paper) {
                state = parsed;
                resumeExam();
                return;
            }
        } catch (e) {
            console.error("Failed to parse saved state");
        }
    }

    // Setup Login
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    
    // Setup Exam UI controls
    document.getElementById('btn-next').addEventListener('click', () => navigate(1));
    document.getElementById('btn-prev').addEventListener('click', () => navigate(-1));
    document.getElementById('btn-flag').addEventListener('click', toggleFlag);
    document.getElementById('header-submit-btn').addEventListener('click', finalSubmit);
    document.getElementById('exit-btn').addEventListener('click', () => window.close());
    
    // Clipboard prevention
    document.addEventListener('copy', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_copy'); });
    document.addEventListener('cut', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_cut'); });
    document.addEventListener('paste', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_paste'); });
    
    // Context menu prevention
    document.addEventListener('contextmenu', e => e.preventDefault());
}

// --- API & Auth ---

async function handleLogin(e) {
    e.preventDefault();
    const roll = document.getElementById('roll-number').value;
    const name = document.getElementById('candidate-name').value;
    const seat = document.getElementById('seat-number').value;
    
    try {
        const res = await fetch(`${API_BASE}/authenticate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roll_number: roll, name, seat_number: seat })
        });
        
        if (!res.ok) throw new Error('Auth failed');
        
        const data = await res.json();
        state.uuid = data.uuid || roll; // fallback to roll if backend doesn't send uuid
        state.token = data.token || 'dummy-token';
        
        await fetchPaper();
    } catch (err) {
        console.error(err);
        document.getElementById('login-error').classList.remove('hidden');
        
        // Mock fallback for testing if backend is down
        if (err.message === 'Failed to fetch') {
            console.warn("Backend down. Generating mock paper for development.");
            state.uuid = roll;
            generateMockPaper();
            startExam();
        }
    }
}

async function fetchPaper() {
    try {
        const res = await fetch(`${API_BASE}/fetch-paper`, {
            method: 'POST', // or GET depending on backend
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify({ student_uuid: state.uuid })
        });
        
        if (!res.ok) throw new Error('Failed to fetch paper');
        
        const data = await res.json();
        state.paper = data.paper || data;
        state.remainingSeconds = data.duration_seconds || 3600;
        startExam();
    } catch (err) {
        console.error(err);
        // Fallback
        if (err.message === 'Failed to fetch') {
            generateMockPaper();
            startExam();
        }
    }
}

function generateMockPaper() {
    state.paper = {
        title: "Sample Assessment",
        questions: [
            { id: "q1", type: "mcq", text: "What is the capital of France?", options: ["London", "Berlin", "Paris", "Madrid"], metadata: "Geography - Easy" },
            { id: "q2", type: "mcq", text: "Which protocol is used for secure communication over the internet?", options: ["HTTP", "FTP", "HTTPS", "SMTP"], metadata: "Security - Medium" },
            { id: "q3", type: "numerical", text: "Calculate 25 * 4", metadata: "Math - Easy" }
        ]
    };
    state.remainingSeconds = 3600;
}

// --- Exam Engine ---

function startExam() {
    views.login.classList.remove('active');
    views.login.classList.add('hidden');
    views.exam.classList.remove('hidden');
    views.exam.classList.add('active');
    
    // Header Setup
    document.getElementById('header-name').textContent = document.getElementById('candidate-name').value || 'Candidate';
    document.getElementById('header-roll').textContent = state.uuid;
    document.getElementById('header-seat').textContent = document.getElementById('seat-number').value || 'N/A';
    
    const wmText = `${state.uuid} - ${new Date().toISOString().split('T')[0]}`;
    document.getElementById('watermark-overlay').textContent = wmText;

    buildPalette();
    renderQuestion();
    startTimer();
    startHeartbeat();
    saveState();
}

function resumeExam() {
    views.login.classList.remove('active');
    views.login.classList.add('hidden');
    views.exam.classList.remove('hidden');
    views.exam.classList.add('active');
    
    document.getElementById('header-roll').textContent = state.uuid;
    document.getElementById('watermark-overlay').textContent = state.uuid;
    
    buildPalette();
    renderQuestion();
    startTimer();
    startHeartbeat();
}

function renderQuestion() {
    const q = state.paper.questions[state.currentIndex];
    
    state.visited[q.id] = true;
    
    document.getElementById('q-number').textContent = `Question ${state.currentIndex + 1}`;
    document.getElementById('q-meta').textContent = q.metadata || 'General';
    document.getElementById('q-text').textContent = q.text;
    
    const ansArea = document.getElementById('answer-area');
    ansArea.innerHTML = '';
    
    if (q.type === 'mcq') {
        q.options.forEach((opt, idx) => {
            const div = document.createElement('div');
            div.className = 'option';
            if (state.responses[q.id] === idx.toString()) {
                div.classList.add('selected');
            }
            
            const input = document.createElement('input');
            input.type = 'radio';
            input.name = `q-${q.id}`;
            input.value = idx;
            if (state.responses[q.id] === idx.toString()) input.checked = true;
            
            const label = document.createElement('label');
            label.textContent = opt;
            
            div.appendChild(input);
            div.appendChild(label);
            
            div.addEventListener('click', () => {
                state.responses[q.id] = idx.toString();
                renderQuestion(); // re-render to update selection style
                updatePalette();
                saveState();
            });
            
            ansArea.appendChild(div);
        });
    } else if (q.type === 'numerical') {
        const input = document.createElement('input');
        input.type = 'number';
        input.className = 'numerical-input';
        input.placeholder = 'Enter numerical answer';
        if (state.responses[q.id]) input.value = state.responses[q.id];
        
        input.addEventListener('input', (e) => {
            state.responses[q.id] = e.target.value;
            updatePalette();
            saveState();
        });
        
        ansArea.appendChild(input);
    }
    
    // Update Flag Button
    const flagBtn = document.getElementById('btn-flag');
    if (state.flags[q.id]) {
        flagBtn.classList.add('active');
        flagBtn.textContent = 'Unflag';
    } else {
        flagBtn.classList.remove('active');
        flagBtn.textContent = 'Flag for Review';
    }
    
    // Update Nav Buttons
    document.getElementById('btn-prev').disabled = state.currentIndex === 0;
    document.getElementById('btn-next').disabled = state.currentIndex === state.paper.questions.length - 1;
    
    updatePalette();
}

function navigate(dir) {
    const newIdx = state.currentIndex + dir;
    if (newIdx >= 0 && newIdx < state.paper.questions.length) {
        state.currentIndex = newIdx;
        renderQuestion();
        saveState();
    }
}

function toggleFlag() {
    const qId = state.paper.questions[state.currentIndex].id;
    state.flags[qId] = !state.flags[qId];
    renderQuestion();
    saveState();
}

// --- Palette ---

function buildPalette() {
    const grid = document.getElementById('palette-grid');
    grid.innerHTML = '';
    
    state.paper.questions.forEach((q, idx) => {
        const btn = document.createElement('button');
        btn.className = 'q-btn';
        btn.textContent = idx + 1;
        btn.id = `pal-${q.id}`;
        
        btn.addEventListener('click', () => {
            state.currentIndex = idx;
            renderQuestion();
            saveState();
        });
        
        grid.appendChild(btn);
    });
    updatePalette();
}

function updatePalette() {
    state.paper.questions.forEach((q, idx) => {
        const btn = document.getElementById(`pal-${q.id}`);
        if (!btn) return;
        
        btn.className = 'q-btn'; // reset
        
        if (idx === state.currentIndex) btn.classList.add('active');
        
        if (state.flags[q.id]) {
            btn.classList.add('flagged');
        } else if (state.responses[q.id] !== undefined && state.responses[q.id] !== '') {
            btn.classList.add('answered');
        } else if (state.visited[q.id]) {
            btn.classList.add('visited');
        } else {
            btn.classList.add('unvisited');
        }
    });
}

// --- Timers & State ---

function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    updateTimerDisplay();
    
    timerInterval = setInterval(() => {
        state.remainingSeconds--;
        updateTimerDisplay();
        
        if (state.remainingSeconds % 60 === 0) saveState();
        
        if (state.remainingSeconds <= 0) {
            clearInterval(timerInterval);
            finalSubmit(true); // Auto submit
        }
    }, 1000);
}

function updateTimerDisplay() {
    if (state.remainingSeconds < 0) state.remainingSeconds = 0;
    const h = Math.floor(state.remainingSeconds / 3600);
    const m = Math.floor((state.remainingSeconds % 3600) / 60);
    const s = state.remainingSeconds % 60;
    
    document.getElementById('live-timer').textContent = 
        `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function saveState() {
    state.lastSync = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

// --- Background Sync & Security ---

function startHeartbeat() {
    if (heartbeatInterval) clearInterval(heartbeatInterval);
    heartbeatInterval = setInterval(syncWithBackend, 5000);
}

async function syncWithBackend() {
    try {
        const payload = {
            student_uuid: state.uuid,
            active_question_id: state.paper.questions[state.currentIndex].id,
            responses: state.responses,
            remaining_seconds: state.remainingSeconds,
            flags: state.flags,
            security_events: securityEventsQueue
        };
        
        const res = await fetch(`${API_BASE}/heartbeat`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error('Sync failed');
        
        // Clear reported events
        securityEventsQueue = [];
        updateConnectionStatus(true);
        
    } catch (err) {
        // Backend down, keep events in queue
        updateConnectionStatus(false);
    }
}

function updateConnectionStatus(isConnected) {
    const dot = document.getElementById('conn-status');
    const text = document.getElementById('conn-text');
    const banner = document.getElementById('connection-banner');
    
    if (isConnected) {
        dot.className = 'dot green';
        text.textContent = 'Connected';
        banner.classList.add('hidden');
    } else {
        dot.className = 'dot red';
        text.textContent = 'Offline';
        banner.classList.remove('hidden');
    }
}

function handleSecurityEvent(eventType) {
    console.warn(`Security event detected: ${eventType}`);
    const event = {
        type: eventType,
        timestamp: new Date().toISOString(),
        question_idx: state.currentIndex
    };
    securityEventsQueue.push(event);
    
    // Clear clipboard just in case
    navigator.clipboard.writeText('').catch(() => {});
    
    // Attempt immediate log to dedicated endpoint
    fetch(`${API_BASE}/log-security-event`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${state.token}`
        },
        body: JSON.stringify({ student_uuid: state.uuid, ...event })
    }).catch(e => { /* Will be handled by heartbeat queue if fails */ });
}

// --- Submit ---

async function finalSubmit(isAuto = false) {
    if (!isAuto) {
        const unans = state.paper.questions.length - Object.keys(state.responses).length;
        if (unans > 0) {
            const conf = confirm(`You have ${unans} unanswered questions. Are you sure you want to submit?`);
            if (!conf) return;
        }
    }
    
    clearInterval(timerInterval);
    clearInterval(heartbeatInterval);
    
    handleSecurityEvent('exam_submit');
    
    try {
        const payload = {
            student_uuid: state.uuid,
            responses: state.responses,
            remaining_seconds: state.remainingSeconds,
            auto_submit: isAuto
        };
        
        const res = await fetch(`${API_BASE}/submit`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify(payload)
        });
        
        let data = {};
        if (res.ok) {
            data = await res.json();
        } else {
            // Mock response if backend down
            data = { receipt_hash: 'LOCAL-' + Math.random().toString(36).substring(2, 15) };
        }
        
        showReceipt(data);
        
    } catch (err) {
        console.error(err);
        // Fallback receipt
        showReceipt({ receipt_hash: 'OFFLINE-' + Math.random().toString(36).substring(2, 15) });
    }
}

function showReceipt(data) {
    localStorage.removeItem(STORAGE_KEY); // Clear session
    
    document.getElementById('receipt-hash').textContent = data.receipt_hash || 'N/A';
    document.getElementById('receipt-time').textContent = new Date().toLocaleString();
    
    if (data.score !== undefined) {
        document.getElementById('score-container').classList.remove('hidden');
        document.getElementById('receipt-score').textContent = data.score;
    }
    
    document.getElementById('receipt-modal').classList.remove('hidden');
}
