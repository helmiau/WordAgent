import assert from 'node:assert/strict';
import test from 'node:test';
import { testModelConnection } from '../src/components/js/api.js';

const params = { baseUrl: 'https://provider.example', apiKey: 'test-key', apiType: 'anthropic', model: 'selected-model' };

test('connection test sends the current form and selected model and preserves millisecond latency', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'http://localhost:3880/api/chat/providers/test-connection');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), {
      base_url: params.baseUrl, api_key: params.apiKey, api_type: 'anthropic', model: 'selected-model'
    });
    return Response.json({ success: true, latency_ms: 123 });
  });
  assert.deepEqual(await testModelConnection(params), { success: true, latency_ms: 123 });
});

test('connection test surfaces provider and request validation errors', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch');
  fetch.mock.mockImplementation(async () => Response.json({ success: false, error: 'HTTP 401: Invalid API key' }));
  await assert.rejects(testModelConnection(params), /HTTP 401: Invalid API key/);
  fetch.mock.mockImplementation(async () => Response.json({ detail: [{ loc: ['body', 'base_url'], msg: 'Invalid URL' }] }, { status: 422 }));
  await assert.rejects(testModelConnection(params), /base_url: Invalid URL/);
});

test('connection test rejects missing latency but accepts a valid zero', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => Response.json({ success: true }));
  await assert.rejects(testModelConnection(params), /延迟/);
  fetch.mock.mockImplementation(async () => Response.json({ success: true, latency_ms: 0 }));
  assert.equal((await testModelConnection(params)).latency_ms, 0);
});

// Exercise the actual form behavior, including Office-friendly inline feedback.
import { readFileSync } from 'node:fs';
import { ref, watch, computed, effectScope } from 'vue';

const modelSource = readFileSync(new URL('../src/components/setting/ModelSetting.vue', import.meta.url), 'utf8');
const modelScript = modelSource.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?;\s*/gm, '');
function modelForm(t, connectionTest, providers = [{
  name: 'Local', baseUrl: ' http://localhost:8000/v1 ', apiKey: ' local-key ',
  apiType: 'openai', models: [{ id: 'qwen3-4b', name: 'Qwen', enabled: true }]
}]) {
  const component = new Function('ref', 'watch', 'computed', 'api', 't', 'iconConnect', 'iconSetting', 'iconDelete',
    modelScript.replace('export default', 'return'))(ref, watch, computed, { testModelConnection: connectionTest },
      (key, params = {}) => `${key} ${JSON.stringify(params)}`, '', '', '');
  const scope = effectScope();
  t.after(() => scope.stop());
  return scope.run(() => component.setup({ providers }, { emit() {} }));
}

test('model form tests unsaved settings, prevents duplicate requests and shows model and latency', async t => {
  let finish;
  const requests = [];
  const vm = modelForm(t, params => {
    requests.push(params);
    return new Promise(resolve => { finish = resolve; });
  });
  vm.localProviders.value[0].baseUrl = ' http://localhost:9000/v1 ';
  const model = vm.localProviders.value[0].models[0];
  const testing = vm.testConnection(0, model);
  assert.equal(vm.isTestingModel(0, model.id), true);
  await vm.testConnection(0, model);
  assert.equal(requests.length, 1);
  assert.deepEqual(requests[0], {
    baseUrl: 'http://localhost:9000/v1', apiKey: 'local-key', apiType: 'openai', model: 'qwen3-4b'
  });
  finish({ success: true, latency_ms: 123 });
  await testing;
  assert.equal(vm.testingConnection.value, null);
  assert.equal(vm.connectionFeedback.value.error, false);
  assert.match(vm.connectionFeedback.value.message, /Qwen/);
  assert.match(vm.connectionFeedback.value.message, /123/);
});

test('model form renders failures and releases the loading state for a later retry', async t => {
  let count = 0;
  const vm = modelForm(t, async () => {
    if (++count === 1) throw new Error('HTTP 401');
    return { success: true, latency_ms: 0 };
  });
  const model = vm.localProviders.value[0].models[0];
  await vm.testConnection(0, model);
  assert.equal(vm.connectionFeedback.value.error, true);
  assert.match(vm.connectionFeedback.value.message, /HTTP 401/);
  assert.equal(vm.testingConnection.value, null);
  await vm.testConnection(0, model);
  assert.equal(vm.connectionFeedback.value.error, false);
});

test('missing model credentials are shown without sending a request', async t => {
  const vm = modelForm(t, () => assert.fail('must not send request'));
  vm.localProviders.value[0].apiKey = ' ';
  await vm.testConnection(0, vm.localProviders.value[0].models[0]);
  assert.equal(vm.connectionFeedback.value.error, true);
  assert.match(vm.connectionFeedback.value.message, /credentialsRequired/);
  assert.equal(vm.testingConnection.value, null);
});
