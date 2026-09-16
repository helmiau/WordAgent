import assert from "node:assert/strict";
import test from "node:test";

import { editDocxParagraph } from "../src/components/js/docxJsonConverter.js";

function createWordMock(originalText = "旧文字") {
  const operations = [];
  const fonts = [];

  function createInsertedRange() {
    const font = {};
    fonts.push(font);
    return {
      font,
      insertText(text, location) {
        operations.push({ text, location });
        return createInsertedRange();
      },
    };
  }

  const contentRange = {
    text: originalText,
    load() {},
    select() {},
    insertText(text, location) {
      operations.push({ text, location });
      return createInsertedRange();
    },
  };
  const contentControl = {
    isNullObject: true,
    load() {},
  };
  const paragraph = {
    set style(_) { throw new Error('pStyle must not be modified'); },
    set paragraphFormat(_) { throw new Error('pStyle must not be modified'); },
    getRange(name) {
      if (name === "Content") {
        return contentRange;
      }
      if (name === "Start") {
        return {
          getBookmarks() {
            return { value: ["_123456789_p"] };
          },
        };
      }
      if (name === "Whole") {
        return {
          parentContentControlOrNullObject: contentControl,
          getBookmarks() {
            return { value: ["_123456789_p"] };
          },
        };
      }
      throw new Error(`unexpected range: ${name}`);
    },
  };
  const context = {
    document: {
      body: {
        paragraphs: {
          items: [paragraph],
          load() {},
        },
      },
    },
    async sync() {},
  };

  globalThis.Word = {
    InsertLocation: { replace: "Replace", end: "End" },
    async run(callback) {
      return callback(context);
    },
  };

  return { operations, fonts };
}

test("edit_document 只替换段落正文并保留段落标记", async () => {
  const { operations } = createWordMock();

  const result = await editDocxParagraph(123456789, [
    { text: "新" },
    { text: "文字" },
  ]);

  assert.equal(result.success, true);
  assert.equal(result.originalText, "旧文字");
  assert.deepEqual(operations, [
    { text: "新", location: "Replace" },
    { text: "文字", location: "End" },
  ]);
});

test("edit_document 支持将段落正文清空", async () => {
  const { operations } = createWordMock();

  const result = await editDocxParagraph(123456789, []);

  assert.equal(result.success, true);
  assert.deepEqual(operations, [{ text: "", location: "Replace" }]);
});


test("edit_document 应用字符样式且不修改段落样式", async () => {
  const { operations, fonts } = createWordMock();
  const style = font => [font, 12, false, false, 0, "#000000", "#000000", 0, false, false, false];
  const result = await editDocxParagraph(123456789, [
    { text: "中文", rStyle: style("宋体") },
    { text: "2026", rStyle: style("Times New Roman") }
  ]);
  assert.equal(result.success, true);
  assert.deepEqual(fonts.map(f => f.name), ["宋体", "Times New Roman"]);
  assert.deepEqual(operations.map(o => o.location), ["Replace", "End"]);
});

test("未解析样式不触发 Word 文档写入", async () => {
  const { operations } = createWordMock();
  const result = await editDocxParagraph(123456789, [{ text: "新内容", rStyle: "rS_1" }]);
  assert.equal(result.success, false);
  assert.deepEqual(operations, []);
});
