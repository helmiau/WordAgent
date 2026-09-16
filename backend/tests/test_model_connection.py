import json
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.api.routes import models


class ModelConnectionTests(unittest.IsolatedAsyncioTestCase):
    def request(self, **overrides):
        return models.ProviderConnectionRequest(
            **{"base_url": "https://provider.example", "api_key": "test-secret", "model": "selected-model", **overrides}
        )

    async def run_request(self, handler, **overrides):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            patch.object(models.httpx, "AsyncClient", return_value=client) as factory,
            patch("app.services.llm_client.get_proxy_url", return_value="http://localhost:8080"),
            patch.object(models, "perf_counter", side_effect=[10.0, 10.123]),
        ):
            result = await models.test_provider_connection(self.request(**overrides))
        factory.assert_called_once_with(timeout=20, proxy="http://localhost:8080")
        self.assertTrue(client.is_closed)
        return result

    async def test_openai_tests_selected_model_with_current_credentials_and_measures_ms(self):
        def respond(request):
            self.assertEqual(str(request.url), "https://provider.example/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer test-secret")
            body = json.loads(request.content)
            self.assertEqual(body["model"], "selected-model")
            self.assertEqual(body["messages"], [{"role": "user", "content": "Reply with only OK."}])
            self.assertFalse(body["stream"])
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "OK"}}]})

        self.assertEqual(await self.run_request(respond), {"success": True, "latency_ms": 123})

    async def test_anthropic_uses_messages_endpoint_without_duplicate_version(self):
        def respond(request):
            self.assertEqual(str(request.url), "https://provider.example/v1/messages")
            self.assertEqual(request.headers["x-api-key"], "test-secret")
            self.assertEqual(request.headers["anthropic-version"], "2023-06-01")
            self.assertEqual(json.loads(request.content)["max_tokens"], 16)
            return httpx.Response(200, json={"type": "message", "content": [{"type": "text", "text": "OK"}]})

        result = await self.run_request(respond, api_type="anthropic", base_url="https://provider.example/v1/")
        self.assertEqual(result, {"success": True, "latency_ms": 123})

    async def test_provider_error_includes_status_and_redacts_key(self):
        result = await self.run_request(
            lambda _: httpx.Response(401, json={"error": {"message": "Invalid API key test-secret"}})
        )
        self.assertFalse(result["success"])
        self.assertIn("401", result["error"])
        self.assertNotIn("test-secret", result["error"])
        self.assertNotIn("latency_ms", result)

    async def test_timeout_and_network_failure_are_not_successes(self):
        for error in (httpx.ReadTimeout("slow"), TimeoutError(), httpx.ConnectError("unreachable")):
            with self.subTest(error=type(error).__name__):

                def fail(_):
                    raise error

                result = await self.run_request(fail)
                self.assertFalse(result["success"])
                self.assertTrue(result["error"])

    async def test_http_200_without_model_response_is_rejected(self):
        for data in ([], {}, {"choices": []}, {"error": {"message": "Model unavailable"}}):
            with self.subTest(data=data):
                result = await self.run_request(lambda _: httpx.Response(200, json=data))
                self.assertFalse(result["success"])
                self.assertNotIn("latency_ms", result)

    async def test_non_json_response_is_rejected(self):
        result = await self.run_request(lambda _: httpx.Response(200, text="<html>Proxy login</html>"))
        self.assertFalse(result["success"])

    def test_rejects_empty_credentials_model_and_invalid_url(self):
        for overrides in ({"api_key": " "}, {"model": " "}, {"base_url": " "}, {"base_url": "file:///tmp/test"}):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                self.request(**overrides)


if __name__ == "__main__":
    unittest.main()
