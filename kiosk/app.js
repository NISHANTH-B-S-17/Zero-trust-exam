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
    exam: document.getElementById('exam-view'),
    offline: document.getElementById('offline-view')
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
    document.getElementById('btn-next').addEventListener('click', () => {
        saveState();
        navigate(1);
    });
    document.getElementById('btn-prev').addEventListener('click', () => {
        saveState();
        navigate(-1);
    });
    document.getElementById('btn-flag').addEventListener('click', toggleFlag);
    document.getElementById('btn-clear').addEventListener('click', clearAnswer);
    document.getElementById('header-submit-btn').addEventListener('click', confirmSubmit);
    document.getElementById('btn-cancel-submit').addEventListener('click', () => {
        document.getElementById('submit-confirm-modal').classList.add('hidden');
    });
    document.getElementById('btn-confirm-submit').addEventListener('click', () => {
        document.getElementById('submit-confirm-modal').classList.add('hidden');
        finalSubmit(false);
    });
    document.getElementById('exit-btn').addEventListener('click', () => {
        if(window.electronAPI) window.close();
        else location.reload();
    });
    
    // Clipboard prevention
    document.addEventListener('copy', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_copy'); });
    document.addEventListener('cut', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_cut'); });
    document.addEventListener('paste', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_paste'); });
    
    // Context menu prevention
    document.addEventListener('contextmenu', e => e.preventDefault());

    // Initialize mock times for login screen if backend logic doesn't provide it yet
    const now = new Date();
    document.getElementById('login-open-time').textContent = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    const examStart = new Date(now.getTime() + 15 * 60000);
    document.getElementById('exam-start-time').textContent = examStart.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

// --- API & Auth ---

async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('start-verification-btn');
    const errBox = document.getElementById('login-error');
    btn.disabled = true;
    btn.textContent = 'Verifying...';
    errBox.classList.add('hidden');
    
    const uuid = document.getElementById('uuid').value.trim();
    
    try {
        const res = await fetch(`${API_BASE}/authenticate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roll_number: uuid })
        });
        
        if (!res.ok) throw new Error('Auth failed');
        
        const data = await res.json();
        state.uuid = data.uuid || uuid;
        state.token = data.token || 'dummy-token';
        
        await fetchPaper();
    } catch (err) {
        console.error(err);
        document.getElementById('login-error-text').textContent = "Authentication failed. Please check UUID or connection.";
        errBox.classList.remove('hidden');
        btn.disabled = false;
        btn.textContent = 'Start Verification';
        
        // Removed offline mock fallback. Must actually fail if no backend.
        if (err.message === 'Failed to fetch') {
             document.getElementById('login-error-text').textContent = "Backend offline. Connect to local security node.";
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
        const errBox = document.getElementById('login-error');
        document.getElementById('login-error-text').textContent = "Failed to load exam paper.";
        errBox.classList.remove('hidden');
        const btn = document.getElementById('start-verification-btn');
        btn.disabled = false;
        btn.textContent = 'Start Verification';
    }
}

// --- Exam Engine ---

function startExam() {
    views.login.classList.remove('active');
    views.login.classList.add('hidden');
    views.exam.classList.remove('hidden');
    views.exam.classList.add('active');
    
    // Header Setup
    document.getElementById('header-uuid').textContent = state.uuid;
    
    // Wait slightly to let CSS render then apply watermark
    setTimeout(() => {
        // The exact forensic pattern expected by existing logic
        const wmText = `${state.uuid} - ${new Date().toISOString().split('T')[0]}`;
        document.getElementById('watermark-overlay').textContent = wmText;
    }, 100);

    // Initial render
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
    
    document.getElementById('header-uuid').textContent = state.uuid;
    
    setTimeout(() => {
        const wmText = `${state.uuid} - ${new Date().toISOString().split('T')[0]}`;
        document.getElementById('watermark-overlay').textContent = wmText;
    }, 100);
    
    buildPalette();
    renderQuestion();
    startTimer();
    startHeartbeat();
}

function renderQuestion() {
    const q = state.paper.questions[state.currentIndex];
    const total = state.paper.questions.length;
    state.visited[q.id] = true;
    
    // Progress Left Panel
    const answeredCount = Object.keys(state.responses).length;
    document.getElementById('answered-count').textContent = answeredCount;
    document.getElementById('total-count').textContent = total;
    
    const progress = (answeredCount / total) * 100;
    document.getElementById('progress-circle').setAttribute('stroke-dasharray', `${progress}, 100`);
    document.getElementById('progress-text').textContent = `${Math.round(progress)}%`;

    // Center Panel Header
    document.getElementById('q-counter').textContent = `QUESTION ${state.currentIndex + 1} OF ${total}`;
    
    // Metadata parsing if available
    const parts = (q.metadata || '').split('|');
    document.getElementById('q-subject').textContent = parts[0] || 'General';
    document.getElementById('q-topic').textContent = parts[1] || 'Topic';
    document.getElementById('q-difficulty').textContent = parts[2] || 'Normal';
    
    // Question Content
    document.getElementById('q-text').textContent = q.text;
    
    // Dynamic Answer Area
    const ansArea = document.getElementById('answer-area');
    ansArea.innerHTML = '';
    
    if (q.type === 'mcq' || q.type === 'single_choice' || q.type === 'true_false') {
        // Safe fallback for options
        const opts = q.options || (q.type === 'true_false' ? ['True', 'False'] : []);
        
        opts.forEach((opt, idx) => {
            const div = document.createElement('div');
            div.className = 'option-card';
            if (state.responses[q.id] === idx.toString() || state.responses[q.id] === opt) {
                div.classList.add('selected');
            }
            
            const input = document.createElement('input');
            input.type = 'radio';
            input.name = `q-${q.id}`;
            input.value = opt; // Using value as text or index depending on existing logic
            if (state.responses[q.id] === idx.toString() || state.responses[q.id] === opt) input.checked = true;
            
            const label = document.createElement('span');
            label.className = 'option-text';
            label.textContent = opt;
            
            div.appendChild(input);
            div.appendChild(label);
            
            div.addEventListener('click', () => {
                // If backend expects index vs string, adapt here. Assuming string option or idx for now
                // Sticking to index as original app.js did for mcq
                state.responses[q.id] = (q.type === 'true_false' ? opt : idx.toString());
                renderQuestion(); 
                updatePalette();
                saveState();
            });
            
            ansArea.appendChild(div);
        });
    } else if (q.type === 'multiple_choice') {
        const opts = q.options || [];
        const currentAns = state.responses[q.id] || []; // Expected array
        
        opts.forEach((opt, idx) => {
            const div = document.createElement('div');
            div.className = 'option-card';
            
            const isSelected = Array.isArray(currentAns) && currentAns.includes(idx.toString());
            if (isSelected) div.classList.add('selected');
            
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.name = `q-${q.id}`;
            if (isSelected) input.checked = true;
            
            const label = document.createElement('span');
            label.className = 'option-text';
            label.textContent = opt;
            
            div.appendChild(input);
            div.appendChild(label);
            
            div.addEventListener('click', () => {
                let newAns = Array.isArray(state.responses[q.id]) ? [...state.responses[q.id]] : [];
                if (newAns.includes(idx.toString())) {
                    newAns = newAns.filter(i => i !== idx.toString());
                } else {
                    newAns.push(idx.toString());
                }
                
                if (newAns.length > 0) {
                    state.responses[q.id] = newAns;
                } else {
                    delete state.responses[q.id];
                }
                
                renderQuestion();
                updatePalette();
                saveState();
            });
            
            ansArea.appendChild(div);
        });
    } else if (q.type === 'numerical' || q.type === 'short_answer') {
        const input = document.createElement('input');
        input.type = q.type === 'numerical' ? 'number' : 'text';
        input.className = 'answer-input';
        input.placeholder = 'Type your answer here...';
        input.style.minHeight = '60px'; // Shorter for short answer
        if (state.responses[q.id]) input.value = state.responses[q.id];
        
        let timeout = null;
        input.addEventListener('input', (e) => {
            state.responses[q.id] = e.target.value;
            // Debounce save to avoid thrashing
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                updatePalette();
                saveState();
            }, 500);
        });
        ansArea.appendChild(input);
        
    } else if (q.type === 'text' || q.type === 'long_answer') {
        const input = document.createElement('textarea');
        input.className = 'answer-input';
        input.placeholder = 'Type your comprehensive answer here...';
        if (state.responses[q.id]) input.value = state.responses[q.id];
        
        let timeout = null;
        input.addEventListener('input', (e) => {
            state.responses[q.id] = e.target.value;
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                updatePalette();
                saveState();
            }, 500);
        });
        ansArea.appendChild(input);
    } else {
        // Fallback for unknown types
        const input = document.createElement('textarea');
        input.className = 'answer-input';
        input.placeholder = 'Answer area (unsupported type fallback)';
        if (state.responses[q.id]) input.value = state.responses[q.id];
        
        input.addEventListener('input', (e) => {
            state.responses[q.id] = e.target.value;
            saveState();
        });
        ansArea.appendChild(input);
    }
    
    // Update Flag Button
    const flagBtn = document.getElementById('btn-flag');
    if (state.flags[q.id]) {
        flagBtn.classList.add('active');
        flagBtn.textContent = 'Unmark Review';
    } else {
        flagBtn.classList.remove('active');
        flagBtn.textContent = 'Mark for Review';
    }

    // Update Clear Button
    const clearBtn = document.getElementById('btn-clear');
    if(state.responses[q.id] !== undefined && state.responses[q.id] !== '' && (!Array.isArray(state.responses[q.id]) || state.responses[q.id].length > 0)) {
        clearBtn.classList.remove('hidden');
    } else {
        clearBtn.classList.add('hidden');
    }
    
    // Update Nav Buttons
    document.getElementById('btn-prev').disabled = state.currentIndex === 0;
    
    const nextBtn = document.getElementById('btn-next');
    if (state.currentIndex === state.paper.questions.length - 1) {
        nextBtn.textContent = 'Save (Last)';
    } else {
        nextBtn.textContent = 'Save & Next';
    }
    
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

function clearAnswer() {
    const qId = state.paper.questions[state.currentIndex].id;
    delete state.responses[qId];
    renderQuestion();
    saveState();
}

// --- Palette ---

function buildPalette() {
    const grid = document.getElementById('question-palette');
    grid.innerHTML = '';
    
    state.paper.questions.forEach((q, idx) => {
        const btn = document.createElement('div');
        btn.className = 'palette-btn';
        btn.id = `pal-${q.id}`;
        btn.textContent = idx + 1;
        
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
        
        btn.className = 'palette-btn'; // reset
        
        if (idx === state.currentIndex) btn.classList.add('active');
        
        const hasAnswer = state.responses[q.id] !== undefined && state.responses[q.id] !== '' && (!Array.isArray(state.responses[q.id]) || state.responses[q.id].length > 0);
        
        if (state.flags[q.id]) {
            btn.classList.add('review');
            if (hasAnswer) btn.classList.add('answered'); // Visual merging for answered+review handled by CSS
        } else if (hasAnswer) {
            btn.classList.add('answered');
        } else if (state.visited[q.id]) {
            btn.classList.add('visited');
        } // else default styling (unvisited)
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
    updateAutosaveStatus();
}

function updateAutosaveStatus() {
    if (!state.lastSync) return;
    const d = new Date(state.lastSync);
    document.getElementById('status-autosave').textContent = `Last saved: ${d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}`;
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
    const banner = document.getElementById('connection-banner');
    const nodeStatus = document.getElementById('status-node');
    
    if (isConnected) {
        banner.classList.add('hidden');
        if(nodeStatus) {
            nodeStatus.textContent = 'Connected';
            nodeStatus.className = 'value success';
        }
    } else {
        banner.classList.remove('hidden');
        if(nodeStatus) {
            nodeStatus.textContent = 'Connection Lost';
            nodeStatus.className = 'value warning';
        }
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
    
    document.getElementById('status-integrity').textContent = 'Warning';
    document.getElementById('status-integrity').className = 'value warning';
    
    // Clear clipboard just in case
    navigator.clipboard.writeText('').catch(() => {});
    
    if (state.uuid) {
        fetch(`${API_BASE}/log-security-event`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify({ student_uuid: state.uuid, ...event })
        }).catch(e => { /* Will be handled by heartbeat queue if fails */ });
    }
}

// --- Submit ---

function confirmSubmit() {
    const answered = Object.keys(state.responses).length;
    const total = state.paper.questions.length;
    const review = Object.keys(state.flags).filter(k => state.flags[k]).length;
    
    document.getElementById('confirm-answered').textContent = answered;
    document.getElementById('confirm-unanswered').textContent = total - answered;
    document.getElementById('confirm-review').textContent = review;
    
    document.getElementById('submit-confirm-modal').classList.remove('hidden');
}

async function finalSubmit(isAuto = false) {
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
        document.getElementById('score-row').classList.remove('hidden');
        document.getElementById('receipt-score').textContent = data.score;
    }
    
    document.getElementById('receipt-modal').classList.remove('hidden');
}
