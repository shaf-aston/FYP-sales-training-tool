"""Small test runner for TTS that falls back to pyttsx3 when Coqui TTS or torchaudio
native libraries fail to load (prevents process crash during import-time failures).
"""
try:
	from TTS.api import TTS
	tts_available = True
except Exception as _e:
	# Import failed (likely torchaudio native lib mismatch). We'll fall back.
	tts_available = False

if tts_available:
	tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
	tts.tts_to_file(text="Hello, this is a test.", file_path="output.wav")
else:
	# Fallback: try pyttsx3 (pure-Python TTS) — won't require torchaudio/native libs.
	try:
		import pyttsx3

		engine = pyttsx3.init()
		engine.save_to_file("Hello, this is a test.", "output_fallback.wav")
		engine.runAndWait()
	except Exception as e:
		# Last-resort fallback: write text to a file so the app can continue.
		with open("output_text_fallback.txt", "w", encoding="utf-8") as fh:
			fh.write("Hello, this is a test. (TTS unavailable: %s)" % e)