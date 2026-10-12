/* Prepared teaching sample. No storage, telemetry, or network requests. */
'use strict';
(() => {
  const engine = window.MasteryDemo;
  const form = document.getElementById('demo-form');
  const question = document.getElementById('question');
  const choices = document.getElementById('choices');
  const feedback = document.getElementById('feedback');
  const next = document.getElementById('next');
  const restart = document.getElementById('restart');
  let index = 0;
  function render(focus) {
    form.hidden = false; next.hidden = true; restart.hidden = true;
    form.querySelector('button').disabled = false;
    question.textContent = engine.questions[index].text;
    document.getElementById('step').textContent = `练习 ${index + 1} / ${engine.questions.length}`;
    choices.replaceChildren(); feedback.textContent = '';
    engine.choices.forEach((text, value) => {
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'radio'; input.name = 'choice'; input.value = String(value); input.required = true;
      label.append(input, document.createTextNode(text)); choices.append(label);
    });
    if (focus) choices.querySelector('input').focus();
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const selected = form.querySelector('input:checked');
    if (!selected) return;
    const result = engine.check(index, Number(selected.value));
    feedback.textContent = (result.correct ? '判断正确。' : '再想一想。') + result.message;
    if (result.correct) {
      form.querySelector('button').disabled = true;
      form.querySelectorAll('input').forEach(input => { input.disabled = true; });
      next.hidden = index === engine.questions.length - 1;
      restart.hidden = !next.hidden;
      if (next.hidden) feedback.textContent += ' 你完成了样例练习；这不是掌握程度认证。';
    }
  });
  next.addEventListener('click', () => { index += 1; render(true); });
  restart.addEventListener('click', () => { index = 0; render(true); });
  render(false);
})();
