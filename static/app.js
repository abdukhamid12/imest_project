'use strict';
function errorText(value) {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map(errorText).join(' ');
    if (value && typeof value === 'object') return Object.entries(value).map(([k,v]) => k === 'detail' ? errorText(v) : k + ': ' + errorText(v)).join(' ');
    return 'Не удалось выполнить запрос.';
}
async function api(url, data) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
        const response = await fetch(url, {
            method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''},
            body: data === undefined ? undefined : JSON.stringify(data), signal: controller.signal,
        });
        const body = await response.json().catch(() => ({detail: 'Сервер недоступен. Повторите запрос.'}));
        if (!response.ok) {
            const error = new Error(errorText(body)); error.status = response.status; throw error;
        }
        return body;
    } catch (error) {
        if (error.name === 'AbortError' || error instanceof TypeError) throw new Error('Нет ответа от сервера. Проверьте соединение и повторите запрос.');
        throw error;
    } finally { clearTimeout(timeout); }
}
function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
}
document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    try {
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = 'Код скопирован ✓';
        setTimeout(() => { button.textContent = button.dataset.copy + ' ⧉'; }, 1800);
    } catch { button.textContent = button.dataset.copy + ' — выделите и скопируйте'; }
}));
const lookupForm = document.getElementById('lookup-form');
if (lookupForm) lookupForm.addEventListener('submit', async event => {
    event.preventDefault();
    const error = document.getElementById('lookup-error');
    const preview = document.getElementById('test-preview');
    const button = lookupForm.querySelector('button');
    button.disabled = true; error.textContent = ''; preview.hidden = true;
    try {
        const code = document.getElementById('test-code').value.trim();
        const test = await api('/api/tests/lookup/?code=' + encodeURIComponent(code));
        preview.replaceChildren(el('h3', test.title), el('p', 'Вопросов: ' + test.question_count + ' · Время: ' + test.duration + ' мин'),
            el('p', 'Доступен с ' + new Date(test.start_date).toLocaleString('ru-RU')));
        const start = el('button', test.attempt_id ? 'Открыть мою попытку →' : 'Начать попытку →', 'button');
        start.type = 'button'; start.disabled = !test.can_start && !test.attempt_id;
        preview.append(el('p', 'Одна попытка. После старта время продолжает идти при закрытии страницы.', 'hint'), start);
        preview.hidden = false;
        start.addEventListener('click', async () => {
            start.disabled = true;
            try {
                const id = test.attempt_id || (await api('/api/tests/' + test.code + '/start/', {})).attempt_id;
                window.location.assign('/attempts/' + id + '/');
            } catch (e) { error.textContent = e.message; start.disabled = false; }
        });
    } catch (e) { error.textContent = e.status === 404 ? 'Тест не найден. Проверьте код и уточните у учителя, опубликован ли тест.' : e.message; }
    finally { button.disabled = false; }
});

function ask(message) {
    return new Promise(resolve => {
        const dialog = el('dialog', undefined, 'confirm-dialog');
        const title = el('h2', 'Подтвердите действие'); title.id = 'confirm-title';
        dialog.setAttribute('aria-labelledby', title.id);
        const actions = el('div', undefined, 'card-actions');
        const cancel = el('button', 'Отмена', 'button secondary');
        const accept = el('button', 'Подтвердить', 'button');
        let accepted = false;
        cancel.addEventListener('click', () => dialog.close());
        accept.addEventListener('click', () => { accepted = true; dialog.close(); });
        dialog.addEventListener('close', () => { dialog.remove(); resolve(accepted); }, {once:true});
        actions.append(cancel, accept); dialog.append(title, el('p', message), actions);
        document.body.append(dialog); dialog.showModal(); cancel.focus();
    });
}
