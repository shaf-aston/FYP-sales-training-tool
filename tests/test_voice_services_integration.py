import os
import unittest
import asyncio
from src.services.voice_services import get_voice_service
from src.services.voice_services.voice_config import VoiceEmotion

class VoiceServicesIntegrationTest(unittest.TestCase):
    """Comprehensive test of STT and TTS functionality"""
    
    @classmethod
    def setUpClass(cls):
        cls.voice_service = get_voice_service()
        cls.test_audio_path = "test_audio.wav"
        cls.test_text = "This is a test of the voice services module"
        
    def test_stt_tts_roundtrip(self):
        async def run_test():
            # Text to Speech
            tts_result = await self.voice_service.text_to_speech(
                self.test_text,
                emotion=VoiceEmotion.NEUTRAL,
                speaker_voice="System"
            )
            
            self.assertIsNotNone(tts_result, "TTS failed to generate audio")
            if tts_result:
                self.assertGreater(len(tts_result), 100, "TTS audio too short")
                
                # Save audio to file
                with open(self.test_audio_path, "wb") as f:
                    f.write(tts_result)
                
                # Speech to Text
                stt_result = await self.voice_service.speech_to_text(
                    tts_result, 
                    language="en"
                )
                
                self.assertIsNotNone(stt_result, "STT failed to transcribe audio")
                if stt_result:
                    self.assertIn("text", stt_result, "STT result missing text")
                    self.assertIn(self.test_text.lower(), stt_result["text"].lower(), 
                                 "STT transcription doesn't match original text")
        
        # Run the async test
        asyncio.run(run_test())
        
    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_audio_path):
            os.remove(cls.test_audio_path)

if __name__ == "__main__":
    unittest.main()