'use strict';
const editorForm = document.getElementById('editor-form');
const initial = JSON.parse(document.getElementById('editor-data').textContent);
const questionList = document.getElementById('editor-questions');
const editorError = document.getElementById('editor-error');
let questionSequence = 0;
let editorDirty = false;
editorForm.addEventListener('input', () => { editorDirty = true; });
window.addEventListener('beforeunload', e => { if (editorDirty) { e.preventDefault(); e.returnValue = ''; } });
function addQuestion(value = {text: '', options: [{text:'',is_correct:true},{text:'',is_correct:false},{text:'',is_correct:false},{text:'',is_correct:false}]}) {
    const seq = ++questionSequence;
    const card = el('section', undefined, 'card editor-question');
    const heading = el('div', undefined, 'section-heading');
    heading.append(el('h3', 'Вопрос'));
    const remove = el('button', 'Удалить вопрос', 'text-button danger'); remove.type = 'button';
    remove.addEventListener('click', async () => { if (await ask('Удалить этот вопрос?')) { card.remove(); editorDirty = true; } });
    heading.append(remove);
    const label = el('label', 'Текст вопроса');
    const text = el('textarea'); text.required = true; text.maxLength = 5000; text.rows = 3; text.value = value.text; text.className = 'question-input';
    label.append(text);
    const pointsLabel = el('label', 'Баллы за правильный ответ');
    const points = el('input'); points.type = 'number'; points.min = 1; points.max = 1000; points.step = 1; points.required = true; points.value = value.points ?? 1; points.className = 'question-points'; pointsLabel.append(points);
    const options = el('div', undefined, 'stack option-editor');
    function addOption(option = {text:'',is_correct:false}) {
        if (options.children.length >= 8) return;
        const row = el('label', undefined, 'option-editor-row');
        const radio = el('input'); radio.type = 'radio'; radio.name = 'correct_' + seq; radio.checked = option.is_correct; radio.required = true; radio.setAttribute('aria-label','Правильный ответ');
        const input = el('input'); input.type = 'text'; input.value = option.text; input.required = true; input.maxLength = 255; input.placeholder = 'Вариант ответа'; input.setAttribute('aria-label','Текст варианта ответа');
        const del = el('button', '×', 'text-button'); del.type = 'button'; del.setAttribute('aria-label', 'Удалить вариант');
        del.addEventListener('click', () => { if (options.children.length > 2) { row.remove(); editorDirty = true; } });
        row.append(radio, input, del); options.append(row);
    }
    value.options.forEach(addOption);
    const add = el('button','+ Вариант ответа','text-button'); add.type = 'button';
    add.addEventListener('click', () => { addOption(); editorDirty = true; });
    card.append(heading, label, pointsLabel, el('p','Отметьте кружком единственный правильный ответ. От 2 до 8 вариантов.','hint'), options, add);
    questionList.append(card);
}
function localDate(date) {
    const d = new Date(date); return new Date(d.getTime() - d.getTimezoneOffset()*60000).toISOString().slice(0,16);
}
editorForm.elements.start_date.value = localDate(initial?.start_date || new Date());
if (initial) {
    ['title','classroom','duration'].forEach(key => { editorForm.elements[key].value = initial[key]; });
    initial.questions.forEach(addQuestion);
} else addQuestion();
document.getElementById('add-question').addEventListener('click', () => {
    if (questionList.children.length < 100) { addQuestion(); editorDirty = true; }
});
function collectTest() {
    return {
        title: editorForm.elements.title.value, classroom: editorForm.elements.classroom.value,
        duration: Number(editorForm.elements.duration.value),
        start_date: new Date(editorForm.elements.start_date.value).toISOString(),
        questions: Array.from(questionList.children).map(card => ({
            text: card.querySelector('textarea').value,
            points: Number(card.querySelector('.question-points').value),
            options: Array.from(card.querySelector('.option-editor').children).map(row => ({
                text: row.querySelector('[type=text]').value, is_correct: row.querySelector('[type=radio]').checked,
            })),
        })),
    };
}
let editorBusy = false;
async function saveEditor(publish = false) {
    if (editorBusy || !editorForm.reportValidity()) return;
    editorBusy = true; editorError.textContent = '';
    try {
        const result = await api('/api/teacher/tests/' + (initial ? initial.id + '/' : ''), collectTest());
        editorDirty = false;
        if (publish) await api('/api/teacher/tests/' + result.id + '/publish/', {});
        window.location.assign(publish ? '/' : '/teacher/tests/' + result.id + '/');
    } catch(e) { editorError.textContent = e.message; }
    finally { editorBusy = false; }
}
editorForm.addEventListener('submit', e => { e.preventDefault(); saveEditor(); });
document.getElementById('publish-test')?.addEventListener('click', async () => {
    if (await ask('Опубликовать тест? После публикации вопросы нельзя изменить.')) saveEditor(true);
});
for (const operation of ['duplicate','archive']) {
    document.getElementById(operation + '-test')?.addEventListener('click', async () => {
        if (editorBusy || !(await ask(operation === 'archive' ? 'Закрыть вход для новых участников и перенести тест в архив?' : 'Создать копию сохранённого теста с новым кодом?'))) return;
        editorBusy = true;
        try {
            const result = await api('/api/teacher/tests/' + initial.id + '/' + operation + '/', {});
            editorDirty = false;
            window.location.assign(operation === 'duplicate' ? '/teacher/tests/' + result.id + '/' : '/');
        } catch(e) { editorError.textContent = e.message; }
        finally { editorBusy = false; }
    });
}

document.getElementById('preview-test').addEventListener('click', () => {
    const data = collectTest();
    const dialog = el('dialog', undefined, 'preview-dialog');
    const heading = el('h2', data.title || 'Предпросмотр теста');
    heading.id = 'preview-heading'; dialog.setAttribute('aria-labelledby', heading.id);
    const close = el('button','Закрыть предпросмотр','button');
    close.addEventListener('click', () => dialog.close());
    dialog.append(heading, el('p','Так ученик увидит вопросы. Ответы в предпросмотре не сохраняются.','muted'));
    data.questions.forEach((q,i) => {
        const section = el('section', undefined, 'preview-question');
        section.append(el('h3', (i+1) + '. ' + q.text), el('p', 'За правильный ответ: ' + q.points + ' балл(ов)'));
        q.options.forEach(o => {
            const label = el('label', undefined, 'answer-option');
            const radio = el('input'); radio.type = 'radio'; radio.name = 'preview_' + i;
            label.append(radio,el('span',o.text)); section.append(label);
        });
        dialog.append(section);
    });
    dialog.append(close); document.body.append(dialog);
    dialog.addEventListener('close', () => dialog.remove(),{once:true});
    dialog.showModal(); close.focus();
});
