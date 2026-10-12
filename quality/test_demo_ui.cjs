// Small DOM contract harness. Browser rendering and native focus still need a browser check.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const engine = require('../docs/assets/demo-engine.js');
const source = fs.readFileSync(require.resolve('../docs/assets/demo.js'), 'utf8');

function harness(language, available = true) {
  let active = null;
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.hidden = false; this.disabled = false; this.textContent = ''; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener(type, listener) { this.listeners[type] = listener; }
    focus() { assert.equal(this.hidden, false); assert.equal(this.disabled, false); active = this; }
    querySelectorAll(selector) {
      return this.children.flatMap(child => typeof child === 'object' ? [child, ...child.querySelectorAll('*')] : [])
        .filter(child => selector === '*' || child.tag === selector || (selector === 'input:checked' && child.tag === 'input' && child.checked));
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    fire(type) { this.listeners[type]({preventDefault() {}}); }
  }
  const ids = Object.fromEntries(['demo-form','question','choices','feedback','next','restart','step'].map(id => [id, new Element('div')]));
  ids['demo-form'].hidden = ids.next.hidden = ids.restart.hidden = true;
  const submit = new Element('button');
  ids['demo-form'].append(ids.choices, submit);
  const document = {documentElement:{lang:language}, getElementById:id => ids[id], createElement:tag => new Element(tag), createTextNode:text => text};
  vm.runInNewContext(source, {window:{MasteryDemo:available ? engine : undefined}, document});
  return {ids, submit, active:() => active, select(value) { ids.choices.querySelectorAll('input').forEach(input => { input.checked = Number(input.value) === value; }); }};
}

for (const lang of ['en', 'zh-CN']) {
  const ui = harness(lang);
  const lesson = engine.forLanguage(lang);
  assert.equal(ui.ids['demo-form'].hidden, false);
  assert.equal(ui.ids.question.textContent, lesson.questions[0].text);
  ui.ids['demo-form'].fire('submit'); // No selection is a no-op.
  assert.equal(ui.ids.feedback.textContent, '');
  ui.select(1); ui.ids['demo-form'].fire('submit');
  assert.equal(ui.ids.feedback.textContent, lesson.retry + lesson.questions[0].hint);
  assert.equal(ui.submit.disabled, false);
  for (let index = 0; index < 3; index++) {
    ui.select(lesson.questions[index].answer); ui.ids['demo-form'].fire('submit');
    assert.equal(ui.submit.disabled, true);
    assert.ok(ui.ids.choices.querySelectorAll('input').every(input => input.disabled));
    if (index < 2) {
      assert.equal(ui.active(), ui.ids.next);
      ui.ids.next.fire('click');
      assert.equal(ui.active(), ui.ids.choices.querySelector('input'));
      assert.equal(ui.ids.question.textContent, lesson.questions[index + 1].text);
    } else {
      assert.equal(ui.active(), ui.ids.restart);
      assert.ok(ui.ids.feedback.textContent.endsWith(lesson.complete));
    }
  }
  ui.ids.restart.fire('click');
  assert.equal(ui.ids.question.textContent, lesson.questions[0].text);
  assert.equal(ui.submit.disabled, false);
  assert.equal(ui.active(), ui.ids.choices.querySelector('input'));
}
assert.equal(harness('en', false).ids['demo-form'].hidden, true);
console.log('Demo UI contract: bilingual retry/completion/restart/focus and missing-engine fallback passed.');
