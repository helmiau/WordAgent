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
