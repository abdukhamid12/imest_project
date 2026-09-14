'use strict';
const examRoot = document.getElementById('exam');
const attemptId = examRoot.dataset.attempt;
const pendingKey = 'imest:attempt:' + attemptId;
let attempt, answers = {}, current = 0, dirty = false, saving = null, finishing = false, conflicted = false;
let clockOffset = 0, timerHandle;
const errorBox = document.getElementById('exam-error');
const saveStatus = document.getElementById('save-status');
const retry = document.getElementById('retry-save');
function remember() {
    try { localStorage.setItem(pendingKey, JSON.stringify({revision: attempt.revision, answers})); }
    catch { errorBox.textContent = 'Браузер не разрешает локальное сохранение. Не закрывайте страницу до подтверждения сервера.'; }
}
function showResult() {
    clearInterval(timerHandle); dirty = false;
    document.getElementById('exam-guard').hidden = true;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    try { localStorage.removeItem(pendingKey); } catch {}
    document.getElementById('exam-active').hidden = true;
    document.getElementById('exam-result').hidden = false;
    document.querySelector('.timer-box').hidden = true;
    document.getElementById('result-score').textContent = attempt.score + ' / ' + attempt.max_score;
    document.getElementById('result-detail').textContent = Math.round(attempt.score / attempt.max_score * 100) + '% от максимума баллов · Результат сохранён';
    retry.hidden = true; errorBox.textContent = '';
}
function renderQuestion() {
    const q = attempt.questions[current];
    document.getElementById('question-counter').textContent = 'ВОПРОС ' + (current + 1) + ' ИЗ ' + attempt.total;
    document.getElementById('question-text').textContent = q.text;
    const options = document.getElementById('answer-options');
    options.replaceChildren();
    for (const option of q.options) {
        const label = el('label', undefined, 'answer-option');
        const radio = el('input'); radio.type = 'radio'; radio.name = 'answer';
        radio.value = option.id; radio.checked = answers[q.id] === option.id;
        radio.disabled = finishing || conflicted;
        radio.addEventListener('change', () => {
            answers[q.id] = option.id; dirty = true; remember(); renderNav(); save();
        });
        label.append(radio, el('span', option.text)); options.append(label);
    }
    document.getElementById('previous-question').disabled = current === 0;
    document.getElementById('next-question').disabled = current === attempt.total - 1;
    renderNav();
}
function renderNav() {
    const nav = document.getElementById('question-nav'); nav.replaceChildren();
    attempt.questions.forEach((q,index) => {
        const button = el('button', String(index + 1), 'page-button' + (answers[q.id] ? ' answered' : '') + (index === current ? ' current' : ''));
        button.setAttribute('aria-label', 'Вопрос ' + (index + 1) + (answers[q.id] ? ', есть ответ' : ', без ответа'));
        if (index === current) button.setAttribute('aria-current','step');
        button.addEventListener('click', () => { current = index; renderQuestion(); });
        nav.append(button);
    });
    document.getElementById('progress-text').textContent = 'Отвечено ' + Object.keys(answers).length + ' из ' + attempt.total;
}
function payload() {
    return {revision: attempt.revision, answers: Object.entries(answers).map(([q,a]) => ({question_id:Number(q),answer_id:a}))};
}
function handleSaveError(e) {
    dirty = true; remember(); errorBox.textContent = e.message;
    retry.hidden = false;
    if (e.status === 409) {
        conflicted = true; retry.textContent = 'Загрузить ответы с сервера';
        errorBox.textContent += ' Локальная копия сохранена в этом браузере.';
        renderQuestion();
    }
    saveStatus.textContent = 'Не сохранено';
}
async function save() {
    if (saving) return saving;
    if (conflicted || attempt.finished_at) return;
    saving = (async () => {
        while (dirty && !attempt.finished_at && !conflicted) {
            const data = payload(); dirty = false; saveStatus.textContent = 'Сохраняем…';
            try {
                const response = await api('/api/attempts/' + attemptId + '/save/', data);
                attempt = response;
                if (attempt.finished_at) { showResult(); return; }
                if (dirty) remember();
                else { try { localStorage.removeItem(pendingKey); } catch {} }
                saveStatus.textContent = dirty ? 'Сохраняем…' : 'Сохранено';
                errorBox.textContent = ''; retry.hidden = true;
            } catch(e) { handleSaveError(e); return; }
        }
    })();
    try { await saving; } finally { saving = null; }
}
async function complete(expired = false) {
    if (finishing || conflicted || attempt.finished_at) return;
    const missing = attempt.total - Object.keys(answers).length;
    if (!expired && !(await ask('Завершить тест?' + (missing ? ' Без ответа: ' + missing + '. За пропуски — 0 баллов.' : '') + ' Изменить ответы после этого нельзя.'))) return;
    if (finishing || attempt.finished_at) return;
    finishing = true; renderQuestion();
    document.getElementById('finish-test').disabled = true;
    try {
        await save();
        if (attempt.finished_at) return;
        if (conflicted || (dirty && !expired)) return;
        attempt = await api('/api/attempts/' + attemptId + '/submit/', payload());
        showResult();
    } catch(e) { handleSaveError(e); }
    finally {
        finishing = false; document.getElementById('finish-test').disabled = false;
        if (!attempt.finished_at) renderQuestion();
    }
}
function tick() {
    const seconds = Math.max(0, Math.ceil((new Date(attempt.deadline).getTime() - (Date.now() + clockOffset)) / 1000));
    document.getElementById('timer').textContent = Math.floor(seconds / 60).toString().padStart(2,'0') + ':' + (seconds % 60).toString().padStart(2,'0');
    document.getElementById('timer').classList.toggle('danger',seconds < 60);
    if (!seconds && !finishing && !conflicted && !attempt.finished_at) {
        clearInterval(timerHandle);
        complete(true);
    }
}
document.getElementById('previous-question').addEventListener('click', () => { if (current > 0) { current--; renderQuestion(); } });
document.getElementById('next-question').addEventListener('click', () => { if (current < attempt.total - 1) { current++; renderQuestion(); } });
document.getElementById('finish-test').addEventListener('click', () => complete());
retry.addEventListener('click', async () => {
    if (!attempt) { window.location.reload(); return; }
    if (conflicted) {
        if (!(await ask('Заменить локальную копию ответами с сервера?'))) return;
        try { localStorage.removeItem(pendingKey); } catch {}
        window.location.reload(); return;
    }
    await save();
    if (!attempt.finished_at && Date.now() + clockOffset >= new Date(attempt.deadline).getTime()) complete(true);
});
window.addEventListener('online', () => { if (attempt && dirty && !conflicted) save(); });
window.addEventListener('beforeunload', e => { if (attempt && !attempt.finished_at) { e.preventDefault(); e.returnValue = ''; } });
(async () => {
    try {
        attempt = await api('/api/attempts/' + attemptId + '/');
        clockOffset = new Date(attempt.server_time).getTime() - Date.now();
        document.getElementById('exam-title').textContent = attempt.title;
        if (attempt.finished_at) { showResult(); return; }
        answers = {...attempt.answers};
        let pending;
        try { pending = JSON.parse(localStorage.getItem(pendingKey)); } catch {}
        if (pending) {
            if (pending.revision === attempt.revision) { answers = pending.answers; dirty = true; }
            else if (JSON.stringify(pending.answers) !== JSON.stringify(answers)) {
                conflicted = true; errorBox.textContent = 'В браузере есть несохранённая копия, но попытка уже изменена. Загрузите актуальные ответы с сервера.';
                retry.hidden = false; retry.textContent = 'Загрузить ответы с сервера';
            } else { try { localStorage.removeItem(pendingKey); } catch {} }
        }
        document.getElementById('exam-guard').hidden = false; renderQuestion();
        timerHandle = setInterval(tick,1000); tick();
        if (dirty) save();
    } catch(e) { errorBox.textContent = e.message; retry.hidden = false; retry.textContent = 'Повторить загрузку'; }
})();


// These controls discourage leaving; browsers and operating systems retain control.
const guard = document.getElementById('exam-guard');
const guardMessage = document.getElementById('guard-message');
let monitoring = false;
const recentEvents = new Map();
function recordEvent(kind) {
    if (!attempt || attempt.finished_at || !monitoring) return;
    const now = Date.now();
    if (now - (recentEvents.get(kind) || 0) < 2000) return;
    recentEvents.set(kind, now);
    const body = JSON.stringify({kind, event_id: crypto.randomUUID()});
    fetch('/api/attempts/' + attemptId + '/events/', {
        method: 'POST', credentials: 'same-origin', keepalive: true,
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': examRoot.querySelector('[name=csrfmiddlewaretoken]').value}, body,
    }).catch(() => {});
}
function pauseExam(kind) {
    if (!attempt || attempt.finished_at || !monitoring) return;
    recordEvent(kind);
    document.getElementById('exam-active').hidden = true;
    guard.hidden = false;
    guardMessage.textContent = 'Вы покинули режим теста. Уходы фиксируются для учителя при наличии связи. Таймер продолжает идти. Вернитесь в полноэкранный режим, чтобы продолжить.';
}
document.getElementById('enter-exam').addEventListener('click', async () => {
    try {
        if (!document.fullscreenEnabled) {
            guardMessage.textContent = 'Этот браузер не поддерживает полноэкранный режим. Откройте эту попытку на компьютере в браузере с поддержкой полного экрана. Таймер продолжает идти.';
            return;
        }
        if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
        if (attempt.finished_at) return;
        monitoring = true;
        guard.hidden = true;
        document.getElementById('exam-active').hidden = false;
    } catch {
        guardMessage.textContent = 'Браузер не разрешил полноэкранный режим. Разрешите его и нажмите кнопку ещё раз. Таймер продолжает идти.';
    }
});
document.addEventListener('visibilitychange', () => { if (document.hidden) pauseExam('hidden'); });
window.addEventListener('blur', () => pauseExam('blur'));
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) pauseExam('fullscreen_exit'); });
window.addEventListener('pagehide', () => recordEvent('page_exit'));
document.addEventListener('contextmenu', e => { if (attempt && !attempt.finished_at) { e.preventDefault(); recordEvent('shortcut'); } });
document.addEventListener('keydown', e => {
    if (!attempt || attempt.finished_at) return;
    const key = e.key.toLowerCase();
    if (key === 'f12' || ((e.ctrlKey || e.metaKey) && (['u','s','p','n','t'].includes(key) || (e.shiftKey && ['i','j','c'].includes(key))))) {
        e.preventDefault(); recordEvent('shortcut');
    }
});
