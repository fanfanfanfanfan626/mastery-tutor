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
  const api = {choices, questions, check};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MasteryDemo = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
