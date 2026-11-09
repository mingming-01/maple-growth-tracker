import unittest
from flask import Flask

from tracker.controller.ai_controller import _service_error_response


class AIAnalysisHTTPErrorTests(unittest.TestCase):
    def test_provider_quota_is_returned_as_http_429_with_retry_after(self):
        app = Flask(__name__)
        with app.test_request_context():
            response = _service_error_response({
                "error": "AI 분석 사용량 한도를 초과했습니다.",
                "statusCode": 429,
                "retryAfterSeconds": 30262,
                "errorType": "provider_quota",
            })

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers.get("Retry-After"), "30262")
        self.assertEqual(response.get_json()["retryAfterSeconds"], 30262)
        self.assertNotIn("statusCode", response.get_json())


if __name__ == "__main__":
    unittest.main()
