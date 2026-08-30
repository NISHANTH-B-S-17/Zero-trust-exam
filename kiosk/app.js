// Constants & Environment Configuration
const isLocalHost = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
const KIOSK_ENV_API = (typeof process !== 'undefined' && process.env && process.env.KIOSK_API_BASE) ? process.env.KIOSK_API_BASE : null;
const API_BASE = KIOSK_ENV_API || (isLocalHost ? 'http://127.0.0.1:8080/api/v1/student' : '/api/v1/student');
const STORAGE_KEY = 'ZERO_TRUST_EXAM_SESSION_V8';

// Unified State Architecture
let state = {
    uuid: null,
    token: null,
    paper: null,
    responses: {}, // { questionId: answer }
    flags: {},     // { questionId: boolean }
    visited: {},   // { questionId: boolean }
    currentIndex: 0,
    remainingSeconds: 0,
    lastSync: null
};

let heartbeatInterval = null;
let timerInterval = null;
let securityEventsQueue = [];
let isSubmitting = false;

// DOM View References
const views = {
    login: document.getElementById('login-view'),
    exam: document.getElementById('exam-view')
};

// Application Initialization
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    if (window.electronAPI) {
        window.electronAPI.reportRendererReady();
        window.electronAPI.onSecurityEvent(handleSecurityEvent);
    }

    // Auto-focus Student UUID field
    const uuidInput = document.getElementById('uuid');
    if (uuidInput) setTimeout(() => uuidInput.focus(), 200);

    // Restore existing session if present
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
            console.error("Failed to parse saved session state", e);
        }
    }

    // Login Form Listener
    const loginForm = document.getElementById('login-form');
    if (loginForm) loginForm.addEventListener('submit', handleLogin);
    
    // Exam Controls Initialization
    const btnNext = document.getElementById('btn-next');
    if (btnNext) {
        btnNext.addEventListener('click', () => {
            saveState();
            if (state.currentIndex === state.paper.questions.length - 1) {
                showToast('Final Answer Saved. Opening Submission Confirmation...', 'success');
                confirmSubmit();
            } else {
                navigate(1);
            }
        });
    }

    const btnPrev = document.getElementById('btn-prev');
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            saveState();
            navigate(-1);
        });
    }

    const btnFlag = document.getElementById('btn-flag');
    if (btnFlag) btnFlag.addEventListener('click', toggleFlag);

    const btnClear = document.getElementById('btn-clear');
    if (btnClear) btnClear.addEventListener('click', clearAnswer);

    const btnHeaderSubmit = document.getElementById('header-submit-btn');
    if (btnHeaderSubmit) btnHeaderSubmit.addEventListener('click', confirmSubmit);
    
    const btnCancelSubmit = document.getElementById('btn-cancel-submit');
    if (btnCancelSubmit) {
        btnCancelSubmit.addEventListener('click', () => {
            const modal = document.getElementById('submit-confirm-modal');
            if (modal) modal.classList.add('hidden');
        });
    }

    const btnConfirmSubmit = document.getElementById('btn-confirm-submit');
    if (btnConfirmSubmit) {
        btnConfirmSubmit.addEventListener('click', () => {
            const modal = document.getElementById('submit-confirm-modal');
            if (modal) modal.classList.add('hidden');
            finalSubmit(false);
        });
    }

    const btnExit = document.getElementById('exit-btn');
    if (btnExit) {
        btnExit.addEventListener('click', () => {
            if (window.electronAPI) window.close();
            else location.reload();
        });
    }
    
    // Clipboard & Right-click protection
    document.addEventListener('copy', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_copy'); });
    document.addEventListener('cut', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_cut'); });
    document.addEventListener('paste', (e) => { e.preventDefault(); handleSecurityEvent('clipboard_attempt_paste'); });
    document.addEventListener('contextmenu', e => e.preventDefault());

    // Keyboard Shortcuts
    document.addEventListener('keydown', handleAutomatedKeybinds);
}

// Automated Keyboard Shortcuts
function handleAutomatedKeybinds(e) {
    if (!views.exam || !views.exam.classList.contains('active')) return;
    
    const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (activeTag === 'input' || activeTag === 'textarea') return;

    const key = e.key.toUpperCase();

    if (key === 'ARROWRIGHT' || key === 'N' || key === 'PAGEDOWN') {
        e.preventDefault();
        saveState();
        if (state.currentIndex === state.paper.questions.length - 1) {
            confirmSubmit();
        } else {
            navigate(1);
            showToast('Navigated Next', 'info');
        }
    } else if (key === 'ARROWLEFT' || key === 'P' || key === 'PAGEUP') {
        e.preventDefault();
        saveState();
        navigate(-1);
        showToast('Navigated Previous', 'info');
    } else if (key === 'M') {
        e.preventDefault();
        toggleFlag();
    } else if (['1', '2', '3', '4', '5', '6', 'A', 'B', 'C', 'D', 'E', 'F'].includes(key)) {
        const q = state.paper.questions[state.currentIndex];
        if (!q) return;
        const qType = (q.type || 'mcq').toLowerCase();
        if (['mcq', 'single_choice', 'true_false'].includes(qType)) {
            let optIndex = -1;
            if (['1','2','3','4','5','6'].includes(key)) optIndex = parseInt(key, 10) - 1;
            else optIndex = key.charCodeAt(0) - 65;

            const opts = q.options || (q.type === 'true_false' ? ['True', 'False'] : []);
            if (optIndex >= 0 && optIndex < opts.length) {
                e.preventDefault();
                const val = (q.type === 'true_false' ? String(opts[optIndex]) : String(optIndex));
                state.responses[q.id] = val;
                updateQuestionUI();
                updatePalette();
                saveState();
                showToast(`Option ${opts[optIndex]} Selected`, 'success');
            }
        }
    }
}

// Automated UI Toast Feedback
function showToast(message, type = 'info') {
    const existing = document.querySelector('.auto-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `auto-toast ${type}`;
    toast.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span>${message}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
        if (toast && toast.parentNode) toast.remove();
    }, 2400);
}

// --- Student Authentication ---

async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('start-verification-btn');
    const errBox = document.getElementById('login-error');
    
    if (btn) { btn.disabled = true; btn.innerHTML = `<span>Verifying...</span>`; }
    if (errBox) errBox.classList.add('hidden');
    
    const uuidInput = document.getElementById('uuid').value.trim();
    
    if (!uuidInput) {
        showLoginError("Verification failed. Please enter Student UUID.");
        resetLoginBtn();
        return;
    }
    
    try {
        const res = await fetch(`${API_BASE}/authenticate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identifier: uuidInput })
        });
        
        if (res.status === 401) {
            throw new Error('Student UUID verification failed. Student record not found.');
        } else if (!res.ok) {
            throw new Error('Authentication node error. Please try again.');
        }
        
        const data = await res.json();
        const studentInfo = data.student || {};
        
        state.uuid = studentInfo.uuid || uuidInput;
        state.token = data.token || 'dummy-token';
        
        await fetchPaper();
    } catch (err) {
        console.error(err);
        showLoginError(err.message || "Verification failed. Check Student UUID.");
        resetLoginBtn();
    }
}

function resetLoginBtn() {
    const btn = document.getElementById('start-verification-btn');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<span>Start Verification</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`;
    }
}

function showLoginError(msg) {
    const errBox = document.getElementById('login-error');
    const errText = document.getElementById('login-error-text');
    if (errText) errText.textContent = msg;
    if (errBox) errBox.classList.remove('hidden');
}

async function fetchPaper() {
    try {
        const res = await fetch(`${API_BASE}/fetch-paper?student_uuid=${encodeURIComponent(state.uuid)}`, {
            method: 'GET',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            }
        });
        
        if (!res.ok) throw new Error('Examination paper unavailable for this student session.');
        
        const data = await res.json();
        state.paper = {
            questions: data.paper || []
        };
        state.remainingSeconds = data.duration_seconds || 3600;
        
        if (!state.paper.questions || state.paper.questions.length === 0) {
            throw new Error('No examination questions returned from paper generator.');
        }

        startExam();
    } catch (err) {
        console.error(err);
        showLoginError(err.message || "Failed to load examination paper.");
        resetLoginBtn();
    }
}

// --- Live Exam Terminal Transition ---

function startExam() {
    views.login.classList.remove('active');
    views.login.classList.add('hidden');
    views.exam.classList.remove('hidden');
    views.exam.classList.add('active');
    
    document.getElementById('header-uuid').textContent = state.uuid;
    
    setTimeout(() => {
        const wmText = `${state.uuid} - ${new Date().toISOString().split('T')[0]}`;
        const overlay = document.getElementById('watermark-overlay');
        if (overlay) overlay.textContent = wmText;
    }, 100);

    buildPalette();
    renderQuestion();
    startTimer();
    startHeartbeat();
    saveState();
    showToast('Secure Exam Terminal Loaded', 'success');
}

function resumeExam() {
    startExam();
}

// --- MODULAR QUESTION RENDERER ---

class QuestionRenderer {
    static render(question, container, currentAnswer, onAnswerChange) {
        container.innerHTML = '';
        const qType = (question.type || 'mcq').toLowerCase();

        switch (qType) {
            case 'mcq':
            case 'single_choice':
            case 'true_false':
                QuestionRenderer.renderSingleChoice(question, container, currentAnswer, onAnswerChange);
                break;
            case 'multiple_choice':
            case 'multi_select':
                QuestionRenderer.renderMultipleChoice(question, container, currentAnswer, onAnswerChange);
                break;
            case 'numerical':
                QuestionRenderer.renderNumericInput(question, container, currentAnswer, onAnswerChange);
                break;
            case 'short_answer':
            case 'fill_in_the_blank':
                QuestionRenderer.renderShortInput(question, container, currentAnswer, onAnswerChange);
                break;
            case 'text':
            case 'long_answer':
            case 'essay':
            case 'descriptive':
                QuestionRenderer.renderLongInput(question, container, currentAnswer, onAnswerChange);
                break;
            default:
                QuestionRenderer.renderFallbackInput(question, container, currentAnswer, onAnswerChange);
                break;
        }
    }

    static renderSingleChoice(q, container, currentAnswer, onAnswerChange) {
        const opts = q.options || (q.type === 'true_false' ? ['True', 'False'] : []);
        const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

        opts.forEach((opt, idx) => {
            const card = document.createElement('div');
            card.className = 'option-card-row';
            
            let isSelected = false;
            if (q.type === 'true_false') {
                isSelected = String(currentAnswer) === String(opt);
            } else {
                isSelected = String(currentAnswer) === String(idx);
            }

            if (isSelected) card.classList.add('selected');

            const badge = document.createElement('div');
            badge.className = 'option-badge';
            badge.textContent = letters[idx % letters.length];

            const text = document.createElement('div');
            text.className = 'option-text-content';
            text.textContent = opt;

            card.appendChild(badge);
            card.appendChild(text);

            if (isSelected) {
                const check = document.createElement('div');
                check.className = 'selected-check-icon';
                check.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`;
                card.appendChild(check);
            }

            card.addEventListener('click', () => {
                const val = (q.type === 'true_false' ? String(opt) : String(idx));
                onAnswerChange(val);
                renderQuestion();
                showToast(`Option ${letters[idx % letters.length]} Saved`, 'success');
            });

            container.appendChild(card);
        });
    }

    static renderMultipleChoice(q, container, currentAnswer, onAnswerChange) {
        const opts = q.options || [];
        const currentAnsArr = Array.isArray(currentAnswer) ? currentAnswer.map(String) : [];
        const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

        opts.forEach((opt, idx) => {
            const card = document.createElement('div');
            card.className = 'option-card-row';
            
            const val = String(idx);
            const isSelected = currentAnsArr.includes(val);
            if (isSelected) card.classList.add('selected');

            const badge = document.createElement('div');
            badge.className = 'option-badge';
            badge.textContent = letters[idx % letters.length];

            const text = document.createElement('div');
            text.className = 'option-text-content';
            text.textContent = opt;

            card.appendChild(badge);
            card.appendChild(text);

            if (isSelected) {
                const check = document.createElement('div');
                check.className = 'selected-check-icon';
                check.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`;
                card.appendChild(check);
            }

            card.addEventListener('click', () => {
                let newArr = [...currentAnsArr];
                if (newArr.includes(val)) {
                    newArr = newArr.filter(i => i !== val);
                } else {
                    newArr.push(val);
                }
                onAnswerChange(newArr.length > 0 ? newArr : null);
                renderQuestion();
            });

            container.appendChild(card);
        });
    }

    static renderNumericInput(q, container, currentAnswer, onAnswerChange) {
        const input = document.createElement('input');
        input.type = 'number';
        input.step = 'any';
        input.className = 'text-answer-input';
        input.placeholder = 'Enter numerical answer...';
        if (currentAnswer !== undefined && currentAnswer !== null) input.value = currentAnswer;

        let debounce = null;
        input.addEventListener('input', (e) => {
            clearTimeout(debounce);
            debounce = setTimeout(() => {
                const val = e.target.value.trim();
                onAnswerChange(val !== '' ? val : null);
            }, 300);
        });

        container.appendChild(input);
    }

    static renderShortInput(q, container, currentAnswer, onAnswerChange) {
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'text-answer-input';
        input.placeholder = 'Type short answer here...';
        if (currentAnswer !== undefined && currentAnswer !== null) input.value = currentAnswer;

        let debounce = null;
        input.addEventListener('input', (e) => {
            clearTimeout(debounce);
            debounce = setTimeout(() => {
                const val = e.target.value.trim();
                onAnswerChange(val !== '' ? val : null);
            }, 300);
        });

        container.appendChild(input);
    }

    static renderLongInput(q, container, currentAnswer, onAnswerChange) {
        const textarea = document.createElement('textarea');
        textarea.className = 'text-answer-input';
        textarea.rows = 6;
        textarea.placeholder = 'Type your comprehensive response here...';
        if (currentAnswer !== undefined && currentAnswer !== null) textarea.value = currentAnswer;

        let debounce = null;
        textarea.addEventListener('input', (e) => {
            clearTimeout(debounce);
            debounce = setTimeout(() => {
                const val = e.target.value.trim();
                onAnswerChange(val !== '' ? val : null);
            }, 300);
        });

        container.appendChild(textarea);
    }

    static renderFallbackInput(q, container, currentAnswer, onAnswerChange) {
        const textarea = document.createElement('textarea');
        textarea.className = 'text-answer-input';
        textarea.rows = 5;
        textarea.placeholder = 'Type your answer here...';
        if (currentAnswer !== undefined && currentAnswer !== null) textarea.value = currentAnswer;

        textarea.addEventListener('input', (e) => {
            const val = e.target.value;
            onAnswerChange(val !== '' ? val : null);
        });

        container.appendChild(textarea);
    }
}

// --- Question Page Controller ---

function renderQuestion() {
    if (!state.paper || !state.paper.questions || state.paper.questions.length === 0) return;

    const q = state.paper.questions[state.currentIndex];
    const total = state.paper.questions.length;
    state.visited[q.id] = true;
    
    updateProgressUI(total);

    // Question Counter & Badges
    document.getElementById('q-counter').textContent = `QUESTION ${state.currentIndex + 1} OF ${total}`;
    
    const metadataStr = q.metadata || '';
    const parts = metadataStr.split('|');
    document.getElementById('q-subject').textContent = q.subject || parts[0] || 'Physics';
    document.getElementById('q-topic').textContent = q.topic || parts[1] || 'Dynamics';
    document.getElementById('q-difficulty').textContent = q.difficulty ? `Diff: ${q.difficulty}` : (parts[2] || 'Medium');
    
    document.getElementById('q-text').textContent = q.text || 'Question content missing.';
    
    // Render Answer Options
    const ansArea = document.getElementById('answer-area');
    const currentAns = state.responses[q.id];

    QuestionRenderer.render(q, ansArea, currentAns, (newAnswer) => {
        if (newAnswer !== null && newAnswer !== undefined) {
            state.responses[q.id] = newAnswer;
        } else {
            delete state.responses[q.id];
        }
        updateQuestionUI();
        updatePalette();
        saveState();
    });
    
    updateQuestionUI();
    updatePalette();
}

function updateProgressUI(total) {
    const answeredCount = calculateAnsweredCount();
    document.getElementById('answered-count').textContent = answeredCount;
    document.getElementById('total-count').textContent = total;
    
    const progressPercent = total > 0 ? Math.round((answeredCount / total) * 100) : 0;
    document.getElementById('progress-circle').setAttribute('stroke-dasharray', `${progressPercent}, 100`);
    document.getElementById('progress-text').textContent = `${progressPercent}%`;
}

function updateQuestionUI() {
    if (!state.paper || !state.paper.questions) return;
    const q = state.paper.questions[state.currentIndex];
    const total = state.paper.questions.length;

    updateProgressUI(total);

    // Status Banner
    const statusText = document.getElementById('answer-status-text');
    if (statusText) {
        if (hasAnswer(q.id)) {
            statusText.textContent = "Answer recorded. Click 'Save & Next' or navigate to proceed.";
        } else {
            statusText.textContent = "You have not answered this question yet.";
        }
    }

    // Flag Button
    const flagBtn = document.getElementById('btn-flag');
    if (flagBtn) {
        if (state.flags[q.id]) {
            flagBtn.style.background = '#fffbeb';
            flagBtn.style.borderColor = '#f59e0b';
            flagBtn.style.color = '#d97706';
            flagBtn.querySelector('span').textContent = 'Unmark Review';
        } else {
            flagBtn.style.background = '';
            flagBtn.style.borderColor = '';
            flagBtn.style.color = '';
            flagBtn.querySelector('span').textContent = 'Mark for Review';
        }
    }

    // Clear Button
    const clearBtn = document.getElementById('btn-clear');
    if (clearBtn) {
        if (hasAnswer(q.id)) clearBtn.classList.remove('hidden');
        else clearBtn.classList.add('hidden');
    }

    // Navigation Buttons
    const prevBtn = document.getElementById('btn-prev');
    if (prevBtn) prevBtn.disabled = state.currentIndex === 0;
    
    const nextBtn = document.getElementById('btn-next');
    if (nextBtn) {
        if (state.currentIndex === total - 1) {
            nextBtn.querySelector('span').textContent = 'Save (Last)';
        } else {
            nextBtn.querySelector('span').textContent = 'Save & Next';
        }
    }
}

function hasAnswer(qId) {
    const ans = state.responses[qId];
    if (ans === undefined || ans === null) return false;
    if (typeof ans === 'string') return ans.trim() !== '';
    if (Array.isArray(ans)) return ans.length > 0;
    return true;
}

function calculateAnsweredCount() {
    if (!state.paper || !state.paper.questions) return 0;
    return state.paper.questions.filter(q => hasAnswer(q.id)).length;
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
    updateQuestionUI();
    updatePalette();
    saveState();
    showToast(state.flags[qId] ? 'Marked for Review' : 'Review Unmarked', 'info');
}

function clearAnswer() {
    const qId = state.paper.questions[state.currentIndex].id;
    delete state.responses[qId];
    renderQuestion();
    saveState();
    showToast('Response Cleared', 'info');
}

// --- Question Palette Rendering ---

function buildPalette() {
    const grid = document.getElementById('question-palette');
    if (!grid) return;
    grid.innerHTML = '';
    
    state.paper.questions.forEach((q, idx) => {
        const node = document.createElement('div');
        node.className = 'pal-node';
        node.id = `pal-${q.id}`;
        node.textContent = idx + 1;
        
        node.addEventListener('click', () => {
            saveState();
            state.currentIndex = idx;
            renderQuestion();
            saveState();
        });
        
        grid.appendChild(node);
    });
    updatePalette();
}

function updatePalette() {
    if (!state.paper || !state.paper.questions) return;

    state.paper.questions.forEach((q, idx) => {
        const node = document.getElementById(`pal-${q.id}`);
        if (!node) return;
        
        node.className = 'pal-node';
        node.innerHTML = `${idx + 1}`;
        
        if (idx === state.currentIndex) node.classList.add('current');
        
        const ans = hasAnswer(q.id);
        
        if (state.flags[q.id]) {
            node.classList.add('review');
            const flagBadge = document.createElement('div');
            flagBadge.className = 'flag-badge';
            flagBadge.innerHTML = `<svg viewBox="0 0 24 24" fill="#f59e0b"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/></svg>`;
            node.appendChild(flagBadge);
        }
        
        if (ans) {
            node.classList.add('answered');
        } else if (state.visited[q.id]) {
            node.classList.add('visited');
        }
    });
}

// --- Timer, Autosave & Heartbeat ---

function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    updateTimerDisplay();
    
    timerInterval = setInterval(() => {
        state.remainingSeconds--;
        updateTimerDisplay();
        
        if (state.remainingSeconds % 30 === 0) saveState();
        
        if (state.remainingSeconds <= 0) {
            clearInterval(timerInterval);
            finalSubmit(true);
        }
    }, 1000);
}

function updateTimerDisplay() {
    if (state.remainingSeconds < 0) state.remainingSeconds = 0;
    const h = Math.floor(state.remainingSeconds / 3600);
    const m = Math.floor((state.remainingSeconds % 3600) / 60);
    const s = state.remainingSeconds % 60;
    
    const timerElem = document.getElementById('live-timer');
    if (timerElem) {
        timerElem.textContent = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        if (state.remainingSeconds <= 300) timerElem.classList.add('urgent');
        else timerElem.classList.remove('urgent');
    }
}

function saveState() {
    state.lastSync = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    updateAutosaveStatus();
}

function updateAutosaveStatus() {
    if (!state.lastSync) return;
    const d = new Date(state.lastSync);
    const statusElem = document.getElementById('status-autosave');
    if (statusElem) {
        statusElem.textContent = `Last saved: ${d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}`;
    }
}

function startHeartbeat() {
    if (heartbeatInterval) clearInterval(heartbeatInterval);
    heartbeatInterval = setInterval(syncWithBackend, 5000);
}

async function syncWithBackend() {
    if (!state.uuid || !state.paper) return;

    try {
        const payload = {
            student_uuid: state.uuid,
            session_id: state.uuid,
            active_question_id: state.paper.questions[state.currentIndex]?.id,
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
        
        if (res.ok) {
            securityEventsQueue = [];
            updateConnectionStatus(true);
        } else {
            updateConnectionStatus(false);
        }
    } catch (err) {
        updateConnectionStatus(false);
    }
}

function updateConnectionStatus(isConnected) {
    const banner = document.getElementById('connection-banner');
    const nodeStatus = document.getElementById('status-node');
    
    if (isConnected) {
        if (banner) banner.classList.add('hidden');
        if (nodeStatus) {
            nodeStatus.textContent = 'Connected';
            nodeStatus.className = 'value connected';
        }
    } else {
        if (banner) banner.classList.remove('hidden');
        if (nodeStatus) {
            nodeStatus.textContent = 'Reconnecting...';
            nodeStatus.className = 'value';
            nodeStatus.style.color = '#d97706';
        }
    }
}

function handleSecurityEvent(eventType) {
    console.warn(`Security event detected: ${eventType}`);
    const event = {
        session_id: state.uuid || 'pre-login',
        event_type: eventType,
        detail: `Question index: ${state.currentIndex}`,
        timestamp: new Date().toISOString()
    };
    securityEventsQueue.push(event);
    
    navigator.clipboard.writeText('').catch(() => {});
    
    if (state.uuid) {
        fetch(`${API_BASE}/log-security-event`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify({ student_uuid: state.uuid, ...event })
        }).catch(() => {});
    }
}

// --- Submit & Confirmation Modal ---

function confirmSubmit() {
    const answered = calculateAnsweredCount();
    const total = state.paper ? state.paper.questions.length : 0;
    const review = Object.keys(state.flags).filter(k => state.flags[k]).length;
    
    const ansElem = document.getElementById('confirm-answered');
    const unansElem = document.getElementById('confirm-unanswered');
    const revElem = document.getElementById('confirm-review');

    if (ansElem) ansElem.textContent = answered;
    if (unansElem) unansElem.textContent = total - answered;
    if (revElem) revElem.textContent = review;
    
    const modal = document.getElementById('submit-confirm-modal');
    if (modal) modal.classList.remove('hidden');
}

async function finalSubmit(isAuto = false) {
    if (isSubmitting) return;
    isSubmitting = true;

    clearInterval(timerInterval);
    clearInterval(heartbeatInterval);
    
    saveState();
    handleSecurityEvent(isAuto ? 'exam_auto_submit' : 'exam_submit');
    
    try {
        const payload = {
            student_uuid: state.uuid,
            answers: state.responses,
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
            data = { receipt_hash: 'LOCAL-' + Math.random().toString(36).substring(2, 15) };
        }
        
        showReceipt(data);
    } catch (err) {
        console.error(err);
        showReceipt({ receipt_hash: 'OFFLINE-' + Math.random().toString(36).substring(2, 15) });
    }
}

function showReceipt(data) {
    localStorage.removeItem(STORAGE_KEY);
    
    const hashElem = document.getElementById('receipt-hash');
    const timeElem = document.getElementById('receipt-time');

    if (hashElem) hashElem.textContent = data.receipt_hash || 'N/A';
    if (timeElem) timeElem.textContent = new Date().toLocaleString();
    
    if (data.score !== undefined) {
        const scoreRow = document.getElementById('score-row');
        const scoreVal = document.getElementById('receipt-score');
        if (scoreRow) scoreRow.classList.remove('hidden');
        if (scoreVal) scoreVal.textContent = `${data.score}%`;
    }
    
    const modal = document.getElementById('receipt-modal');
    if (modal) modal.classList.remove('hidden');
}
