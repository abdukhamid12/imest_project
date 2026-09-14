const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

function element() {
    return {hidden:true, dataset:{attempt:'1'}, value:'csrf-test-token', listeners:{},
        addEventListener(type, fn) { this.listeners[type] = fn; },
        append() {}, replaceChildren() {}, setAttribute() {},
        querySelector() { return {value:'csrf-test-token'}; },
        classList:{toggle() {}}};
}
async function setup() {
    const elements = new Map();
    const doc = element();
    doc.getElementById = id => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
    doc.querySelector = () => element();
    doc.fullscreenEnabled = true;
    doc.documentElement = {async requestFullscreen() { doc.fullscreenElement = this; }};
    doc.exitFullscreen = async () => { doc.fullscreenElement = null; };
    const window = element();
    const requests = [];
    const context = vm.createContext({document:doc, window, console, Date, Map, JSON, Number, Object, Math,
        crypto:require('node:crypto'), setInterval() {return 1;}, clearInterval() {},
        localStorage:{getItem() {return null;},setItem() {},removeItem() {}},
        el:element, ask:async () => true,
        fetch:async (url, options) => { requests.push({url,options}); return {}; },
        api:async () => ({id:1,title:'Test',revision:0,server_time:new Date().toISOString(),deadline:new Date(Date.now()+600000).toISOString(),
            finished_at:null,answers:{},questions:[{id:1,text:'Question',points:6,options:[{id:2,text:'Answer'}]}],total:1,max_score:6})});
    vm.runInContext(fs.readFileSync('static/room.js','utf8'), context);
    await new Promise(resolve => setImmediate(resolve));
    return {context,doc,window,requests,get:id=>doc.getElementById(id)};
}

test('questions require fullscreen; leaving hides them and reports an authenticated event', async () => {
    const {doc,get,requests} = await setup();
    assert.equal(get('question-counter').textContent, 'ВОПРОС 1 ИЗ 1');
    assert.equal(get('exam-active').hidden,true);
    assert.equal(get('exam-guard').hidden,false);
    await get('enter-exam').listeners.click();
    assert.equal(get('exam-active').hidden,false);
    doc.fullscreenElement = null;
    doc.listeners.fullscreenchange();
    assert.equal(get('exam-active').hidden,true);
    assert.equal(get('exam-guard').hidden,false);
    assert.equal(JSON.parse(requests[0].options.body).kind,'fullscreen_exit');
    assert.equal(requests[0].options.headers['X-CSRFToken'],'csrf-test-token');
    assert.equal(requests[0].options.keepalive,true);
    await get('enter-exam').listeners.click();
    assert.equal(get('exam-active').hidden,false);
});

test('blur pauses questions, unload warns, reserved shortcuts are discouraged', async () => {
    const {doc,window,get,requests} = await setup();
    await get('enter-exam').listeners.click();
    window.listeners.blur();
    assert.equal(get('exam-active').hidden,true);
    assert.equal(JSON.parse(requests[0].options.body).kind,'blur');
    let warned = false;
    window.listeners.beforeunload({preventDefault() {warned = true;}});
    assert.equal(warned,true);
    let blocked = false;
    doc.listeners.keydown({key:'u',ctrlKey:true,preventDefault() {blocked = true;}});
    assert.equal(blocked,true);
});

test('completed result releases fullscreen and no longer traps navigation', async () => {
    const {context,doc,window,get,requests} = await setup();
    await get('enter-exam').listeners.click();
    vm.runInContext("attempt.finished_at = new Date().toISOString(); attempt.score=6; showResult();",context);
    assert.equal(get('exam-guard').hidden,true);
    assert.equal(get('exam-result').hidden,false);
    assert.equal(doc.fullscreenElement,null);
    window.listeners.beforeunload({preventDefault() {throw Error('Result must allow navigation');}});
    doc.listeners.fullscreenchange();
    assert.equal(requests.length,0);
});
