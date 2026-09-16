import assert from 'node:assert/strict';
import test from 'node:test';

import { editDocxParagraph } from '../src/components/js/docxJsonConverter.js';

function mockDocument() {
  const operations = [];
  const fonts = [];
  const paragraphStyle = { alignment: "justify", firstLineIndent: 24 };
  const para = {
    ParaID: 101,
    Range: { Start: 10, End: 16, ParagraphFormat: paragraphStyle }
  };
  return {
    Paragraphs: { Count: 1, Item: () => para },
    Content: { End: 100 },
    Range(start, end) {
      const range = { Start: start, End: end, Font: {}, Select() {},
        set ParagraphFormat(_) { throw new Error('pStyle must not be modified'); } };
      fonts.push(range.Font);
      Object.defineProperty(range, 'Text', {
        set(value) {
          operations.push({ type: 'text', start, end, value }); 
        }
      });
      range.Delete = () => operations.push({ type: 'delete', start, end });
      return range;
    },
    operations, fonts, paragraphStyle
  };
}

test('编辑段落时只删除内容范围，不删除段落标记', () => {
  const doc = mockDocument();
  const result = editDocxParagraph(101, [{ text: '新内容' }], doc);

  assert.equal(result.success, true);
  assert.deepEqual(doc.operations.slice(0, 2), [
    { type: 'delete', start: 10, end: 15 },
    { type: 'text', start: 10, end: 10, value: '新内容' }
  ]);
});

test('空 runs 清空段落正文但保留段落', () => {
  const doc = mockDocument();
  const result = editDocxParagraph(101, [], doc);

  assert.equal(result.success, true);
  assert.deepEqual(doc.operations, [{ type: 'delete', start: 10, end: 15 }]);
});


test('字符样式分别应用于中英文 run，保留 pStyle 和段落标记', () => {
  const doc = mockDocument();
  const originalPStyle = structuredClone(doc.paragraphStyle);
  const style = font => [font, 12, false, false, 0, '#000000', '#000000', 0, false, false, false];
  const result = editDocxParagraph(101, [
    { text: '中文', rStyle: style('宋体') },
    { text: '2026', rStyle: style('Times New Roman') }
  ], doc);
  assert.equal(result.success, true);
  assert.deepEqual(doc.fonts.filter(f => f.Name).map(f => f.Name), ['宋体', 'Times New Roman']);
  assert.deepEqual(doc.paragraphStyle, originalPStyle);
  assert.deepEqual(doc.operations[0], { type: 'delete', start: 10, end: 15 });
  assert.ok(doc.fonts.filter(f => f.Name).every(f => f.Color === 0));
});

test('未解析的字符样式在删除旧内容之前被拒绝', () => {
  const doc = mockDocument();
  const result = editDocxParagraph(101, [{ text: '新内容', rStyle: 'rS_1' }], doc);
  assert.equal(result.success, false);
  assert.equal(doc.operations.length, 0);
});
