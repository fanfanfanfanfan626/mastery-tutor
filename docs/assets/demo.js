/* Prepared teaching sample. No storage, telemetry, or network requests. */
'use strict';
(() => {
  // Keep the readable static lesson when a script is unavailable.
  if (!window.MasteryDemo) return;
  const engine = window.MasteryDemo.forLanguage(document.documentElement.lang);
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
    document.getElementById('step').textContent = engine.progress(index + 1);
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
    feedback.textContent = (result.correct ? engine.correct : engine.retry) + result.message;
    if (result.correct) {
      form.querySelector('button').disabled = true;
      form.querySelectorAll('input').forEach(input => { input.disabled = true; });
      next.hidden = index === engine.questions.length - 1;
      restart.hidden = !next.hidden;
      if (next.hidden) feedback.textContent += engine.complete;
      // Disabling the submitted button must not strand keyboard focus on the body.
      (next.hidden ? restart : next).focus();
    }
  });
  next.addEventListener('click', () => { index += 1; render(true); });
  restart.addEventListener('click', () => { index = 0; render(true); });
  render(false);
})();
