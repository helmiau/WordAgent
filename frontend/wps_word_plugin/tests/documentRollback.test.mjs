import assert from 'node:assert/strict';
import test from 'node:test';
import { captureDeleteSnapshot, rollbackDeletedParagraphs } from '../src/components/js/documentRollback.js';

function fixture() {
  const original = [{ ParaID: 101, Range: { Text: '正文\r' } }];
  const doc = {
    DocID: 9, items: original,
    get Content() { return { Text: this.items.map(p => p.Range.Text).join('') }; },
    get Paragraphs() { return { Count: this.items.length, Item: i => this.items[i - 1] }; }
  };
  const snapshot = captureDeleteSnapshot(doc, original);
  doc.items = [];
  return { doc, original, snapshot };
}

test('Undo 无异常但未恢复内容时不能声称撤销成功', () => {
  const { doc, snapshot } = fixture();
  doc.Undo = () => {};
  const result = rollbackDeletedParagraphs(doc, snapshot, 1);
  assert.equal(result.rollbackVerified, false);
  assert.deepEqual(result.unrestoredParaIDs, [101]);
  assert.equal(result.requiresRead, true);
});

test('Undo 抛异常时仍然核实实际状态并返回错误', () => {
  const { doc, snapshot } = fixture();
  doc.Undo = () => { throw new Error('undo failed'); };
  const result = rollbackDeletedParagraphs(doc, snapshot, 1);
  assert.equal(result.rollbackVerified, false);
  assert.equal(result.rollbackError, 'undo failed');
});

test('只有原 ID、段落文本和全文都恢复才确认回滚', () => {
  const { doc, original, snapshot } = fixture();
  doc.Undo = count => { assert.equal(count, 1); doc.items = original; };
  assert.equal(rollbackDeletedParagraphs(doc, snapshot, 1).rollbackVerified, true);
  doc.Undo = () => { doc.items = [{ ParaID: 202, Range: { Text: '正文\r' } }]; };
  assert.equal(rollbackDeletedParagraphs(doc, snapshot, 1).rollbackVerified, false);
  doc.Undo = () => { doc.items = [{ ParaID: 101, Range: { Text: '错误正文\r' } }]; };
  assert.equal(rollbackDeletedParagraphs(doc, snapshot, 1).rollbackVerified, false);
});

test('不对另一个活动文档执行全局撤销', () => {
  const { doc, snapshot } = fixture();
  let called = false;
  const result = rollbackDeletedParagraphs(doc, snapshot, 1, {
    ActiveDocument: { DocID: 10 }, Undo() { called = true; }
  });
  assert.equal(called, false);
  assert.equal(result.rollbackVerified, false);
});
