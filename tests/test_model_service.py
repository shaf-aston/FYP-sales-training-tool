import unittest
from unittest.mock import patch, MagicMock
from src.services.ai_services.model_service import ModelService

class TestModelService(unittest.TestCase):

    def setUp(self):
        self.model_service = ModelService()
        self.model_service.model_name = "test-model"

    @patch("src.services.ai_services.model_service.AutoTokenizer.from_pretrained")
    @patch("src.services.ai_services.model_service.AutoModelForCausalLM.from_pretrained")
    @patch("src.services.ai_services.model_service.pipeline")
    def test_load_pipeline_success(self, mock_pipeline, mock_model, mock_tokenizer):
        mock_pipeline.return_value = "mocked_pipeline"
        mock_model.return_value = MagicMock()
        mock_tokenizer.return_value = MagicMock()

        pipeline = self.model_service._load_pipeline("test-model")

        self.assertIsNotNone(pipeline)
        self.assertEqual(pipeline, "mocked_pipeline")
        mock_tokenizer.assert_called_once()
        mock_model.assert_called_once()
        mock_pipeline.assert_called_once()

    @patch("services.model_service.AutoTokenizer.from_pretrained", side_effect=Exception("Tokenizer error"))
    def test_load_pipeline_tokenizer_failure(self, mock_tokenizer):
        pipeline = self.model_service._load_pipeline("test-model")
        self.assertIsNone(pipeline)
        mock_tokenizer.assert_called_once()

    @patch("services.model_service._lazy_load_transformers", return_value=False)
    def test_load_pipeline_transformers_not_loaded(self, mock_lazy_load):
        pipeline = self.model_service._load_pipeline("test-model")
        self.assertIsNone(pipeline)
        mock_lazy_load.assert_called_once()

if __name__ == "__main__":
    unittest.main()