import { getParagraphParaID } from './docxJsonConverter.js';

// Capture before mutating: live WPS Paragraph/Range objects change after Delete.
export function captureDeleteSnapshot(doc, paragraphs) {
  const documentText = doc.Content.Text;
  if (typeof documentText !== 'string') {
    throw new Error('无法获取删除前的文档快照，未执行删除');
  }
  return {
    documentText,
    paragraphs: paragraphs.map(para => {
      const text = para.Range.Text;
      if (typeof text !== 'string') {
        throw new Error('无法获取删除前的段落快照，未执行删除');
      }
      return { paraID: Number(getParagraphParaID(para)), text };
    })
  };
}

export function rollbackDeletedParagraphs(doc, snapshot, undoCount, application) {
  let rollbackError = null;
  try {
    if (typeof doc.Undo === 'function') {
      doc.Undo(undoCount);
    } else {
      const active = application?.ActiveDocument;
      const sameDocument = active === doc || (doc.DocID != null && active?.DocID === doc.DocID);
      if (!sameDocument) {
        throw new Error('目标文档不是活动文档，未调用全局 Undo');
      }
      application.Undo(undoCount);
    }
  } catch (error) {
    rollbackError = error?.message || String(error);
  }

  let unrestoredParaIDs = snapshot.paragraphs.map(item => item.paraID);
  let rollbackVerified = false;
  try {
    const current = new Map();
    for (let index = 1; index <= doc.Paragraphs.Count; index++) {
      const para = doc.Paragraphs.Item(index);
      current.set(Number(getParagraphParaID(para)), String(para.Range.Text));
    }
    unrestoredParaIDs = snapshot.paragraphs
      .filter(item => current.get(item.paraID) !== item.text).map(item => item.paraID);
    rollbackVerified = unrestoredParaIDs.length === 0 && String(doc.Content.Text) === snapshot.documentText;
  } catch (error) {
    rollbackError ||= error?.message || String(error);
  }
  return { rollbackVerified, requiresRead: true, unrestoredParaIDs,
    ...(rollbackError ? { rollbackError } : {}) };
}
