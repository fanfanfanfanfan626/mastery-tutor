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
console.log('Demo: 3 questions, feedback/retry paths and invalid inputs passed.');
