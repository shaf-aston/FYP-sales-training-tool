import unittest
import time
from services.model_service import ModelService

class TestPerformanceMetrics(unittest.TestCase):

    def setUp(self):
        self.model_service = ModelService()
        self.model_service.model_name = "test-model"

    def test_model_loading_time(self):
        start_time = time.time()
        self.model_service._load_pipeline("test-model")
        duration = time.time() - start_time
        self.assertLess(duration, 10, "Model loading took too long")

if __name__ == "__main__":
    unittest.main()