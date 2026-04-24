"""API connectivity and modular design verification tests."""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from core.providers.factory import create_provider, get_available_providers

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")


class APITester:
    """Test suite for API connectivity and module coherence."""

    def __init__(self):
        self.results = {"passed": [], "failed": [], "warnings": []}

    def test_providers_available(self):
        """KNOW: Verify all configured LLM providers are instantiable."""
        try:
            providers = get_available_providers()
            print(f"\n[OK] Provider factory response:\n{json.dumps(providers, indent=2)}")

            for provider_info in providers:
                name = provider_info.get("name")
                available = provider_info.get("available")
                model = provider_info.get("model")

                status = "[OK] available" if available else "[FAIL] unavailable"
                print(f"  {name:15} {status:20} model: {model}")

                if available:
                    self.results["passed"].append(f"Provider {name} available")
                else:
                    self.results["warnings"].append(f"Provider {name} unavailable (may require API key)")

            return True
        except Exception as e:
            self.results["failed"].append(f"Provider factory failed: {str(e)}")
            return False

    def test_groq_connectivity(self):
        """KNOW: Test Groq provider with actual API call."""
        try:
            provider = create_provider("groq")
            if not provider.is_available():
                self.results["warnings"].append("Groq provider not available (API key missing?)")
                return False

            # Minimal test: use chat method with messages list format
            messages = [{"role": "user", "content": "Say 'Connected' in one word."}]
            response = provider.chat(messages)

            if response and response.content and len(response.content.strip()) > 0:
                print("\n[OK] Groq connectivity test passed")
                print(f"  Response: {response.content[:100]}...")
                self.results["passed"].append("Groq API connectivity verified")
                return True
            else:
                self.results["failed"].append("Groq returned empty response")
                return False
        except Exception as e:
            self.results["failed"].append(f"Groq test failed: {str(e)}")
            return False

    def test_sambanova_connectivity(self):
        """KNOW: Test SambaNova provider with actual API call."""
        try:
            provider = create_provider("sambanova")
            if not provider.is_available():
                self.results["warnings"].append("SambaNova provider not available (API key missing?)")
                return False

            messages = [{"role": "user", "content": "Say 'Connected' in one word."}]
            response = provider.chat(messages)

            if response and response.content and len(response.content.strip()) > 0:
                print("\n[OK] SambaNova connectivity test passed")
                print(f"  Response: {response.content[:100]}...")
                self.results["passed"].append("SambaNova API connectivity verified")
                return True
            else:
                self.results["failed"].append("SambaNova returned empty response")
                return False
        except Exception as e:
            self.results["failed"].append(f"SambaNova test failed: {str(e)}")
            return False

    def test_dummy_provider(self):
        """KNOW: Verify dummy provider (always available for testing)."""
        try:
            provider = create_provider("dummy")
            if provider.is_available():
                messages = [{"role": "user", "content": "test"}]
                response = provider.chat(messages)
                print("\n[OK] Dummy provider test passed")
                print(f"  Response: {response.content[:100]}...")
                self.results["passed"].append("Dummy provider works (fallback mode)")
                return True
            else:
                self.results["failed"].append("Dummy provider unavailable")
                return False
        except Exception as e:
            self.results["failed"].append(f"Dummy provider test failed: {str(e)}")
            return False

    def test_modular_imports(self):
        """KNOW: Verify core modules are independent and well-separated."""
        try:
            # Test core module imports (should not have circular dependencies)
            from core.content import generate_init_greeting
            from core.flow import SalesFlowEngine
            from core.analysis import classify_intent_level
            from core.prompts import SHARED_RULES
            from core.chatbot import SalesChatbot

            assert generate_init_greeting
            assert SalesFlowEngine
            assert classify_intent_level
            assert SHARED_RULES
            assert SalesChatbot

            print("\n[OK] All core modules imported successfully")
            print("  - content (prompt generation)")
            print("  - flow (FSM engine)")
            print("  - analysis (NLU)")
            print("  - prompts (templates)")
            print("  - chatbot (main orchestrator)")

            self.results["passed"].append("Core module separation verified (no circular imports)")
            return True
        except ImportError as e:
            self.results["failed"].append(f"Module import failed: {str(e)}")
            return False

    def test_backend_routes(self):
        """KNOW: Verify Flask route blueprints initialize without errors."""
        try:
            # Flask app context check
            from flask import Flask
            from backend.routes import chat, session

            app = Flask(__name__, instance_path="/tmp")

            # Mock dependency functions
            def mock_get(key):
                return None
            def mock_set(key, val):
                pass
            def mock_delete(key):
                pass
            def mock_validate_message(msg):
                return msg, None
            def mock_require_session():
                return None, ("error", 400)
            def mock_bot_state(bot):
                return {}

            # Initialize routes (should not raise)
            # session.init_routes requires: app, session_manager, get, set, delete, bot_state
            session.init_routes(app, None, mock_get, mock_set, mock_delete, mock_bot_state)
            # chat.init_routes requires: app, get_session, require_session, validate_message, bot_state
            chat.init_routes(app, mock_get, mock_require_session, mock_validate_message, mock_bot_state)

            print("\n[OK] Flask route blueprints initialized")
            print("  - session routes")
            print("  - chat routes")

            self.results["passed"].append("Flask route separation verified")
            return True
        except Exception as e:
            self.results["failed"].append(f"Flask routes initialization failed: {str(e)}")
            return False

    def test_data_flow_integrity(self):
        """KNOW: Verify modular data contracts (request/response shapes)."""
        try:
            # Check provider response contract
            from core.providers.base import LLMResponse
            provider = create_provider("dummy")
            messages = [{"role": "user", "content": "test"}]
            response = provider.chat(messages)

            # Should return LLMResponse with content attribute
            if isinstance(response, LLMResponse) and hasattr(response, 'content'):
                print("\n[OK] Provider response contract verified (LLMResponse type)")
                self.results["passed"].append("Provider response contract correct")
                return True
            else:
                self.results["failed"].append(f"Provider response wrong type: {type(response)}")
                return False
        except Exception as e:
            self.results["failed"].append(f"Data contract test failed: {str(e)}")
            return False

    def run_all(self):
        """Execute all tests and summarize."""
        print("=" * 70)
        print("CS3IP API CONNECTIVITY & MODULAR DESIGN AUDIT")
        print("=" * 70)

        self.test_providers_available()
        self.test_groq_connectivity()
        self.test_sambanova_connectivity()
        self.test_dummy_provider()
        self.test_modular_imports()
        self.test_backend_routes()
        self.test_data_flow_integrity()

        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"[OK] Passed:  {len(self.results['passed'])}")
        print(f"[FAIL] Failed:  {len(self.results['failed'])}")
        print(f"[WARN] Warnings: {len(self.results['warnings'])}")

        if self.results["passed"]:
            print("\nPassed tests:")
            for item in self.results["passed"]:
                print(f"  [OK] {item}")

        if self.results["failed"]:
            print("\nFailed tests:")
            for item in self.results["failed"]:
                print(f"  [FAIL] {item}")

        if self.results["warnings"]:
            print("\nWarnings:")
            for item in self.results["warnings"]:
                print(f"  [WARN] {item}")

        print("\n" + "=" * 70)
        return len(self.results["failed"]) == 0


if __name__ == "__main__":
    tester = APITester()
    success = tester.run_all()
    sys.exit(0 if success else 1)
