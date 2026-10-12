(function (root) {
  'use strict';
  const choices = ['人直接写下规则', '从样本中学习参数', '信息不足，暂不能判断'];
  const questions = [
    {text:'一个报警器规定：温度超过 80°C 就报警。这属于哪一种？',answer:0,feedback:'判断条件由人明确指定，这是规则系统。即便它非常准确，也不因此变成机器学习。',hint:'看判断条件怎样产生，不要看它有没有用电脑。'},
    {text:'研究者给系统看大量标注为“猫”或“狗”的图片，通过训练调整参数。系统随后分类新图片。',answer:1,feedback:'参数通过训练样本调整，这是学习型模型。现在你把邮件场景中的区别迁移到了图片场景。',hint:'留意“通过训练调整参数”，这与手写条件不同。'},
    {text:'有人只告诉你：“这款软件识别缺陷的准确率是 99%。”你能判断它是否使用机器学习吗？',answer:2,feedback:'不能。准确率描述表现，不说明判断方式怎样产生。需要了解规则、训练数据和参数的来源。',hint:'一个结果数字能告诉你系统内部如何建立判断方式吗？'}
  ];
  function check(index, choice) {
    if (!Number.isInteger(index) || index < 0 || index >= questions.length || !Number.isInteger(choice) || choice < 0 || choice >= choices.length) throw new RangeError('Unknown question or choice');
    const item = questions[index];
    return {correct:choice === item.answer, message:choice === item.answer ? item.feedback : item.hint};
  }
  const englishChoices = ['Rules specified by people', 'Parameters learned from examples', 'Not enough information'];
  const englishQuestions = [
    {text:'An alarm is programmed to sound when the temperature exceeds 80°C. How was its decision made?',answer:0,feedback:'A person explicitly specified the condition. This is a rule-based system, even if the alarm is very accurate.',hint:'Look at how the condition was created, not whether a computer is involved.'},
    {text:'Researchers train a model on images labeled “cat” or “dog”, adjusting its parameters. It then classifies new images.',answer:1,feedback:'The parameters were fitted using training examples. You have transferred the distinction from email to images.',hint:'Notice “adjusting its parameters” using labeled examples. Is that the same as directly specifying a condition?'},
    {text:'Someone says only: “This software detects defects with 99% accuracy.” Can you tell whether it uses machine learning?',answer:2,feedback:'No. Accuracy describes performance, not how the decision process was created. Ask about the rules, training data, and parameter fitting.',hint:'Does a performance number explain how the system obtained its decision process?'}
  ];
  // Both pages share behavior; translations must preserve the same answer contract.
  function forLanguage(language) {
    const english = language === 'en';
    const selectedQuestions = english ? englishQuestions : questions;
    return {
      choices: english ? englishChoices : choices,
      questions: selectedQuestions,
      check(index, choice) {
        const result = check(index, choice);
        const item = selectedQuestions[index];
        return {correct: result.correct, message: result.correct ? item.feedback : item.hint};
      },
      progress: (current) => english ? `Question ${current} / ${questions.length}` : `练习 ${current} / ${questions.length}`,
      correct: english ? 'Correct. ' : '判断正确。',
      retry: english ? 'Try again. ' : '再想一想。',
      complete: english ? ' You completed the sample; this is not a mastery certification.' : ' 你完成了样例练习；这不是掌握程度认证。'
    };
  }
  const api = {choices, questions, check, forLanguage};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MasteryDemo = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
