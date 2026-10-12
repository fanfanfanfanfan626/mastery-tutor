const assert = require('node:assert/strict');
const demo = require('../docs/assets/demo-engine.js');
assert.equal(demo.questions.length, 3);
demo.questions.forEach((q, i) => {
  demo.choices.forEach((_, choice) => {
    const result = demo.check(i, choice);
    assert.equal(result.correct, choice === q.answer);
    assert.ok(result.message.length > 12);
    if (!result.correct) assert.notEqual(result.message, q.feedback);
  });
});
for (const [index, choice] of [[-1,0],[3,0],[0,-1],[0,3],[0,NaN],[0,'0']]) {
  assert.throws(() => demo.check(index, choice), RangeError);
}
for (const language of ['en', 'zh-CN']) {
  const lesson = demo.forLanguage(language);
  assert.equal(lesson.questions.length, 3);
  for (const [index, q] of lesson.questions.entries()) {
    assert.equal(q.answer, demo.questions[index].answer);
    lesson.choices.forEach((_, choice) => {
      const result = lesson.check(index, choice);
      assert.equal(result.correct, choice === q.answer);
      assert.equal(result.message, choice === q.answer ? q.feedback : q.hint);
    });
  }
  assert.throws(() => lesson.check(99, 0), RangeError);
}
assert.deepEqual(demo.forLanguage('unknown').choices, demo.choices);
assert.match(demo.forLanguage('en').progress(2), /Question 2 \/ 3/);
console.log('Demo: both languages, 3 questions, feedback/retry paths and invalid inputs passed.');
