"""
Test script for Google Cloud Speech-to-Text integration
Run this to verify your Google Cloud STT setup
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

async def test_google_cloud_stt():
    """Test Google Cloud Speech-to-Text functionality"""
    print("🧪 Testing Google Cloud Speech-to-Text Integration")
    print("=" * 60)
    
    # Import voice service
    try:
        from services.voice_service import get_voice_service
        print("✅ Voice service imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import voice service: {e}")
        return False
    
    # Get voice service instance
    service = get_voice_service()
    print(f"✅ Voice service instance created")
    
    # Check service availability
    print("\n📊 Service Availability:")
    available_services = service.is_available()
    for service_name, is_available in available_services.items():
        status = "✅" if is_available else "❌"
        print(f"   {status} {service_name}: {is_available}")
    
    # Check Google Cloud STT specifically
    print("\n🔍 Google Cloud STT Status:")
    if not service.available_services.get('google_cloud_stt'):
        print("❌ Google Cloud STT not available")
        print("\nPossible reasons:")
        print("1. google-cloud-speech package not installed")
        print("   Solution: pip install google-cloud-speech")
        print("2. GOOGLE_APPLICATION_CREDENTIALS not set")
        print("   Solution: Set environment variable to your credentials JSON file")
        print("3. Credentials file doesn't exist at specified path")
        print("   Solution: Verify the file path in GOOGLE_APPLICATION_CREDENTIALS")
        
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if creds_path:
            print(f"\n   Current GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
            if os.path.exists(creds_path):
                print("   ✅ File exists")
            else:
                print("   ❌ File not found at this location")
        else:
            print("\n   ℹ️  GOOGLE_APPLICATION_CREDENTIALS not set")
        
        return False
    
    print("✅ Google Cloud STT is available")
    
    # Get capabilities
    print("\n📋 Voice Capabilities:")
    capabilities = service.get_voice_capabilities()
    
    print("\n   Speech-to-Text:")
    stt_info = capabilities.get('speech_to_text', {})
    print(f"      Available: {stt_info.get('available')}")
    print(f"      Backends:")
    for backend, available in stt_info.get('backends', {}).items():
        status = "✅" if available else "❌"
        print(f"         {status} {backend}")
    print(f"      Supported Languages: {', '.join(stt_info.get('supported_languages', []))}")
    print(f"      Features: {', '.join(stt_info.get('features', []))}")
    
    # Installation recommendations
    recommendations = service._get_installation_recommendations()
    if recommendations:
        print("\n💡 Recommendations:")
        for rec in recommendations:
            print(f"   • {rec}")
    
    print("\n" + "=" * 60)
    print("✨ Google Cloud STT test complete!")
    print("\nTo test actual transcription:")
    print("1. Record or obtain an audio file (WAV, FLAC, MP3, etc.)")
    print("2. Run: python tests/test_voice_transcription.py --audio your_audio.wav")
    
    return True

async def test_transcription_with_audio(audio_file: str):
    """Test transcription with an actual audio file"""
    print(f"\n🎤 Testing transcription with audio file: {audio_file}")
    print("=" * 60)
    
    if not os.path.exists(audio_file):
        print(f"❌ Audio file not found: {audio_file}")
        return False
    
    from services.voice_service import get_voice_service
    service = get_voice_service()
    
    # Perform transcription
    print("🔄 Transcribing audio...")
    result = await service.speech_to_text(audio_file, language="en")
    
    if not result:
        print("❌ Transcription failed")
        return False
    
    print("\n✅ Transcription successful!")
    print(f"\n📝 Transcribed Text:")
    print(f"   {result.get('text', 'N/A')}")
    print(f"\n📊 Details:")
    print(f"   Method: {result.get('method', 'N/A')}")
    print(f"   Language: {result.get('language', 'N/A')}")
    print(f"   Confidence: {result.get('confidence', 'N/A'):.2%}")
    print(f"   Speaking Rate: {result.get('speaking_rate', 'N/A'):.1f} words/min")
    
    # Pause analysis
    pause_analysis = result.get('pause_analysis', {})
    if pause_analysis.get('total_pauses', 0) > 0:
        print(f"\n⏸️  Pause Analysis:")
        print(f"   Total Pauses: {pause_analysis.get('total_pauses')}")
        print(f"   Average Pause: {pause_analysis.get('average_pause', 0):.2f}s")
        print(f"   Max Pause: {pause_analysis.get('max_pause', 0):.2f}s")
    
    # Emotion indicators
    emotions = result.get('emotion_indicators', {})
    if emotions:
        print(f"\n😊 Detected Emotions:")
        for emotion, score in emotions.items():
            print(f"   {emotion.capitalize()}: {score:.1%}")
    
    # Speaker tags (if available)
    speaker_tags = result.get('speaker_tags', {})
    if speaker_tags:
        print(f"\n👥 Speaker Analysis:")
        for speaker_id, info in speaker_tags.items():
            print(f"   Speaker {speaker_id}:")
            print(f"      Word Count: {info.get('word_count')}")
            print(f"      Speaking Time: {info.get('speaking_time', 0):.2f}s")
    
    return True

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Google Cloud Speech-to-Text")
    parser.add_argument("--audio", type=str, help="Path to audio file for transcription test")
    
    args = parser.parse_args()
    
    # Run basic availability test
    success = asyncio.run(test_google_cloud_stt())
    
    # If audio file provided, test transcription
    if args.audio and success:
        asyncio.run(test_transcription_with_audio(args.audio))
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
