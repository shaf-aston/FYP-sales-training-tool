# Voice Features Documentation

## Overview

The AI Sales Training Chatbot now includes advanced voice capabilities powered by:
- **Coqui TTS** for high-quality Text-to-Speech with persona-specific voices
- **OpenAI Whisper** for accurate Speech-to-Text transcription
- **SpeechRecognition** as a fallback STT option

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Voice Features Layer                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐              ┌──────────────────┐        │
│  │   STT Service    │              │   TTS Service    │        │
│  │  (Whisper)       │              │  (Coqui AI)      │        │
│  ├──────────────────┤              ├──────────────────┤        │
│  │ • Audio → Text   │              │ • Text → Audio   │        │
│  │ • Multi-language │              │ • Persona voices │        │
│  │ • Caching        │              │ • Speed/Pitch    │        │
│  │ • GPU support    │              │ • Caching        │        │
│  └──────────────────┘              └──────────────────┘        │
│           │                                  │                  │
│           └──────────┬───────────────────────┘                  │
│                      │                                          │
│              ┌───────▼────────┐                                │
│              │  Voice Routes  │                                │
│              │  /api/stt      │                                │
│              │  /api/tts      │                                │
│              │  /api/voice-chat│                               │
│              └────────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### 1. Speech-to-Text (STT)

**Endpoint:** `POST /api/stt`

Converts uploaded audio to text using Whisper.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/stt" \
  -F "audio=@recording.wav" \
  -F "language=en"
```

**Response:**
```json
{
  "text": "Hello, I'm interested in your fitness program",
  "confidence": 0.95,
  "language": "en",
  "duration": 3.5,
  "processing_time": 1.2,
  "status": "success"
}
```

**Supported Audio Formats:**
- WAV (recommended)
- MP3
- M4A
- FLAC
- OGG

**Supported Languages:**
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Russian (ru)
- Japanese (ja)
- Korean (ko)
- Chinese (zh)
- And many more...

### 2. Text-to-Speech (TTS)

**Endpoint:** `POST /api/tts`

Converts text to speech with persona-specific voices.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! I am interested in learning more about your services.",
    "persona_name": "Mary",
    "format": "wav"
  }' \
  --output speech.wav
```

**Request Body:**
```json
{
  "text": "Text to convert to speech",
  "persona_name": "Mary",  // Optional: Mary, Jake, Sarah, David, System
  "format": "wav"          // Optional: wav (default)
}
```

**Response:**
- Audio stream (WAV format)
- `Content-Type: audio/wav`
- Downloadable file

**Available Personas:**
- **Mary** - 65-year-old retired teacher (warm, cautious tone)
- **Jake** - 35-year-old busy executive (fast, direct tone)
- **Sarah** - 28-year-old budget-conscious professional (friendly, practical tone)
- **David** - 45-year-old family man (thoughtful, steady tone)
- **System** - Neutral system voice

### 3. Complete Voice Chat

**Endpoint:** `POST /api/voice-chat`

End-to-end voice conversation: Audio → STT → AI Chat → TTS → Audio

**Request:**
```bash
curl -X POST "http://localhost:8000/api/voice-chat" \
  -F "audio=@user_question.wav" \
  -F "user_id=user123" \
  -F "persona_name=Mary" \
  -F "session_id=session-abc-123"
```

**Response:**
```json
{
  "user_text": "What fitness programs do you offer?",
  "ai_response": "Great question! We offer several programs tailored to different needs...",
  "ai_audio_base64": "UklGRiQAAABXQVZFZm10...",
  "confidence": 0.95,
  "session_id": "session-abc-123",
  "persona_name": "Mary",
  "message_count": 3,
  "status": "success"
}
```

**Frontend Integration Example:**
```javascript
// Play the AI's audio response
const audio = new Audio();
audio.src = `data:audio/wav;base64,${response.ai_audio_base64}`;
audio.play();
```

### 4. Voice Service Status

**Endpoint:** `GET /api/voice-status`

Check TTS and STT service availability and statistics.

**Response:**
```json
{
  "stt": {
    "available": true,
    "backend": "whisper",
    "gpu_enabled": true,
    "transcriptions": 145,
    "cache_hit_rate": 34.5,
    "avg_processing_time": 1.234
  },
  "tts": {
    "available": true,
    "gpu_enabled": true,
    "loaded_models": ["tts_models/en/ljspeech/tacotron2-DDC"],
    "generations": 89,
    "cache_hit_rate": 45.2,
    "avg_generation_time": 2.156
  },
  "available_voices": [
    {"name": "Mary", "model_name": "...", "speed": 0.9, "pitch_shift": 2.0},
    ...
  ],
  "supported_languages": ["en", "es", "fr", "de", "it", ...],
  "status": "ready"
}
```

## Performance Features

### Caching
Both TTS and STT services implement intelligent caching:
- **STT Cache:** Stores transcriptions to avoid re-processing identical audio
- **TTS Cache:** Stores generated audio to speed up repeated phrases
- **Cache Management:** Automatic cleanup when size limits are reached
- **Cache Hit Rates:** Typically 30-50% in production

### GPU Acceleration
- Automatically detects and uses CUDA GPUs when available
- Significantly faster processing (2-5x speedup)
- Falls back to CPU if GPU is unavailable

### Multi-Backend Fallback
- Primary: Whisper (high accuracy, offline)
- Fallback: Google Speech Recognition (online, requires internet)
- Graceful degradation ensures service continuity

## Frontend Integration

### HTML5 Audio Recording

```html
<!-- Record button -->
<button id="recordBtn">🎤 Record</button>
<button id="stopBtn" disabled>⏹️ Stop</button>

<script>
let mediaRecorder;
let audioChunks = [];

document.getElementById('recordBtn').addEventListener('click', async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  
  mediaRecorder.ondataavailable = (event) => {
    audioChunks.push(event.data);
  };
  
  mediaRecorder.onstop = async () => {
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    await sendVoiceChat(audioBlob);
    audioChunks = [];
  };
  
  mediaRecorder.start();
  document.getElementById('recordBtn').disabled = true;
  document.getElementById('stopBtn').disabled = false;
});

document.getElementById('stopBtn').addEventListener('click', () => {
  mediaRecorder.stop();
  document.getElementById('recordBtn').disabled = false;
  document.getElementById('stopBtn').disabled = true;
});

async function sendVoiceChat(audioBlob) {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.wav');
  formData.append('user_id', 'user123');
  formData.append('persona_name', 'Mary');
  
  const response = await fetch('/api/voice-chat', {
    method: 'POST',
    body: formData
  });
  
  const data = await response.json();
  
  // Display transcription
  document.getElementById('userText').textContent = data.user_text;
  
  // Display AI response
  document.getElementById('aiResponse').textContent = data.ai_response;
  
  // Play AI audio
  if (data.ai_audio_base64) {
    const audio = new Audio(`data:audio/wav;base64,${data.ai_audio_base64}`);
    audio.play();
  }
}
</script>
```

### React Integration

```jsx
import React, { useState, useRef } from 'react';

function VoiceChat() {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorderRef.current = new MediaRecorder(stream);
    
    mediaRecorderRef.current.ondataavailable = (event) => {
      audioChunksRef.current.push(event.data);
    };
    
    mediaRecorderRef.current.onstop = async () => {
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
      await handleVoiceChat(audioBlob);
      audioChunksRef.current = [];
    };
    
    mediaRecorderRef.current.start();
    setIsRecording(true);
  };

  const stopRecording = () => {
    mediaRecorderRef.current.stop();
    setIsRecording(false);
  };

  const handleVoiceChat = async (audioBlob) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');
    formData.append('persona_name', 'Mary');
    
    const response = await fetch('/api/voice-chat', {
      method: 'POST',
      body: formData
    });
    
    const data = await response.json();
    setTranscript(data.user_text);
    setAiResponse(data.ai_response);
    
    // Play audio response
    if (data.ai_audio_base64) {
      const audio = new Audio(`data:audio/wav;base64,${data.ai_audio_base64}`);
      audio.play();
    }
  };

  return (
    <div>
      <button onClick={isRecording ? stopRecording : startRecording}>
        {isRecording ? '⏹️ Stop' : '🎤 Record'}
      </button>
      <div>You said: {transcript}</div>
      <div>AI: {aiResponse}</div>
    </div>
  );
}
```

## Installation & Setup

### Prerequisites

1. **FFmpeg** (Required for audio processing)
   ```bash
   # Windows (using Chocolatey)
   choco install ffmpeg
   
   # Or download from: https://ffmpeg.org/download.html
   # Add to PATH
   ```

2. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### GPU Setup (Optional but Recommended)

For CUDA-enabled GPU acceleration:
```bash
# Install CUDA-enabled PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Model Downloads

Models are downloaded automatically on first use:
- **Whisper**: ~150MB (base model)
- **Coqui TTS**: ~150MB per voice model

Cache location: `model_cache/`

## Configuration

### Environment Variables

```bash
# Enable/disable GPU
USE_GPU=true

# Log level for voice services
LOG_LEVEL=INFO

# Cache settings
TTS_CACHE_SIZE_MB=500
STT_CACHE_SIZE_MB=100
```

### Custom Voice Profiles

Add custom voice profiles in `tts_service.py`:

```python
from services.tts_service import TTSVoiceProfile, get_tts_service

# Create custom profile
custom_voice = TTSVoiceProfile(
    name="CustomVoice",
    model_name="tts_models/en/ljspeech/tacotron2-DDC",
    speed=1.0,
    pitch_shift=0.0
)

# Register it
tts_service = get_tts_service()
tts_service.add_voice_profile(custom_voice)
```

## Troubleshooting

### Common Issues

**1. "FFmpeg not found"**
- Install FFmpeg and add to PATH
- Restart terminal/IDE after installation

**2. "CUDA out of memory"**
- Reduce batch size or switch to CPU mode
- Close other GPU-intensive applications

**3. "Audio transcription failed"**
- Check audio format (WAV recommended)
- Ensure audio is clear and not corrupted
- Check file size (<25MB)

**4. "TTS generation too slow"**
- Enable GPU acceleration
- Use caching (enabled by default)
- Consider using smaller/faster models

### Performance Optimization

1. **Preload Models** (startup time optimization)
   ```python
   from services.tts_service import get_tts_service
   
   tts_service = get_tts_service()
   tts_service.preload_models()
   ```

2. **Adjust Cache Sizes**
   - Increase cache size for repeated phrases
   - Monitor cache hit rates via `/api/voice-status`

3. **Use GPU**
   - 2-5x faster processing
   - Lower latency for real-time conversations

## Best Practices

1. **Audio Quality**
   - Use 16kHz+ sample rate
   - WAV format for best compatibility
   - Minimize background noise

2. **Text Preparation**
   - Clean text before TTS (remove markdown, special chars)
   - Limit text length to 500 characters
   - Use proper punctuation for natural speech

3. **Error Handling**
   - Always check `status` in responses
   - Provide fallback for failed TTS (show text)
   - Handle network errors gracefully

4. **User Experience**
   - Show recording indicator
   - Display transcription in real-time
   - Allow replay of AI audio responses
   - Provide text alternative

## Monitoring & Analytics

Track voice feature usage via `/api/voice-status`:
- Transcription count and accuracy
- TTS generation statistics
- Cache performance
- Processing times
- Error rates

## Future Enhancements

- [ ] Streaming TTS for lower latency
- [ ] Real-time STT (live transcription)
- [ ] Emotion detection in voice
- [ ] Multi-speaker conversations
- [ ] Voice cloning for custom personas
- [ ] Language auto-detection

---

For more information, see:
- [Main README](README.md)
- [API Documentation](API.md)
- [Coqui TTS Documentation](https://github.com/coqui-ai/TTS)
- [Whisper Documentation](https://github.com/openai/whisper)
