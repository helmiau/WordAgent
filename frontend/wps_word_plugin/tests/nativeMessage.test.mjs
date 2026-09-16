import assert from 'node:assert/strict';
import test from 'node:test';
import { showNativeMessage } from '../src/components/js/util.js';

const message = '连接成功\n模型：Deepseek V4 Flash\n延迟：937 ms';
const title = '测试连接';

test('unsupported DoAlert falls back to the WPS alert instead of silently losing the result', (t) => {
  const originalWindow = globalThis.window;
  t.after(() => { globalThis.window = originalWindow; });
  for (const result of [0, undefined, null]) {
    const alerts = [];
    globalThis.window = {
      Application: { Assistant: { DoAlert: () => result } },
      alert: text => alerts.push(text)
    };
    showNativeMessage(message, title);
    assert.deepEqual(alerts, [message]);
  }
});

test('working native dialog uses no icon and does not show a second alert', (t) => {
  const originalWindow = globalThis.window;
  t.after(() => { globalThis.window = originalWindow; });
  for (const result of [1, 2]) {
    const assistant = { DoAlert(...args) {
      assert.equal(this, assistant);
      assert.deepEqual(args, [title, message, 0, 0, 0, -1, true]);
      return result;
    } };
    globalThis.window = { Application: { Assistant: assistant }, alert: () => assert.fail('Duplicate dialog') };
    showNativeMessage(message, title);
  }
});

test('missing or throwing native API still displays the success message', (t) => {
  const originalWindow = globalThis.window;
  t.after(() => { globalThis.window = originalWindow; });
  t.mock.method(console, 'warn', () => {});
  for (const Application of [undefined, {}, { Assistant: { DoAlert() { throw new Error('Not implemented'); } } }]) {
    const alerts = [];
    globalThis.window = { Application, alert: text => alerts.push(text) };
    showNativeMessage(message, title);
    assert.deepEqual(alerts, [message]);
  }
});
