"""
Test transcript preprocessing pipeline
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.services.analysis_services.transcript_processor import get_transcript_processor


def test_stt_corrections():
    """Test STT correction functionality"""
    print("\n🧪 Testing STT Corrections")
    print("=" * 60)
    
    processor = get_transcript_processor()
    
    sample_result = {
        'text': 'I can understand the restaurant now. You want to start getting healthy, but I suppose for you, why is this something you want to do now as opposed to waiting another 3632 months from now?',
        'segments': [
            {'text': 'I can understand the restaurant now', 'start': 0, 'end': 2},
            {'text': 'You want to start getting healthy', 'start': 2, 'end': 4},
            {'text': 'but I suppose for you', 'start': 4, 'end': 5},
            {'text': 'why is this something you want to do now', 'start': 5, 'end': 7},
            {'text': 'as opposed to waiting another 3632 months from now', 'start': 7, 'end': 10},
        ]
    }
    
    corrected = processor.apply_stt_corrections(sample_result)
    
    print(f"Original text:")
    print(f"  {sample_result['text']}\n")
    print(f"Corrected text:")
    print(f"  {corrected['text']}\n")
    print(f"Corrections applied: {len(corrected.get('corrections_applied', []))}")
    
    for correction in corrected.get('corrections_applied', []):
        print(f"  • {correction['incorrect']} → {correction['correct']}")
        print(f"    Explanation: {correction['explanation']}")
    
    return True


def test_speaker_diarization():
    """Test speaker labeling"""
    print("\n🧪 Testing Speaker Diarization")
    print("=" * 60)
    
    processor = get_transcript_processor()
    
    sample_result = {
        'text': 'I can understand the rationale now. You want to start getting healthy. I guess I have to do it now or I\'ll just procrastinate.',
        'segments': [
            {'text': 'I can understand the rationale now', 'start': 0, 'end': 2, 'speaker_tag': 1},
            {'text': 'You want to start getting healthy', 'start': 2, 'end': 4, 'speaker_tag': 1},
            {'text': 'I guess I have to do it now', 'start': 4, 'end': 6, 'speaker_tag': 2},
            {'text': 'or I\'ll just procrastinate', 'start': 6, 'end': 8, 'speaker_tag': 2},
        ],
        'speaker_tags': {
            1: {'word_count': 10, 'speaking_time': 4.0},
            2: {'word_count': 8, 'speaking_time': 4.0}
        }
    }
    
    labeled = processor.add_speaker_labels(sample_result)
    
    print(f"Labeled transcript:")
    print(labeled.get('labeled_text', ''))
    print(f"\nSpeaker segments: {len(labeled.get('speaker_segments', []))}")
    
    for segment in labeled.get('speaker_segments', []):
        print(f"  [{segment['speaker']}]: {segment['text'][:50]}...")
    
    return True


def test_sentence_segmentation():
    """Test sentence segmentation"""
    print("\n🧪 Testing Sentence Segmentation")
    print("=" * 60)
    
    processor = get_transcript_processor()
    
    sample_result = {
        'text': 'i might need to step off i have a couple of appointments during this hour so no worries',
        'segments': [],
        'speaker_segments': [
            {
                'speaker': 'Trainer',
                'text': 'i might need to step off i have a couple of appointments during this hour so no worries',
                'start': 0,
                'end': 5
            }
        ]
    }
    
    segmented = processor.segment_sentences(sample_result)
    
    print(f"Original:")
    print(f"  {sample_result['text']}\n")
    print(f"Segmented:")
    for segment in segmented.get('speaker_segments', []):
        for sentence in segment.get('sentences', []):
            print(f"  {sentence}")
    
    return True


def test_training_annotations():
    """Test training annotation detection"""
    print("\n🧪 Testing Training Annotations")
    print("=" * 60)
    
    processor = get_transcript_processor()
    
    sample_result = {
        'text': '',
        'segments': [],
        'speaker_segments': [
            {
                'speaker': 'Aiden',
                'text': 'I can understand the rationale now. You want to start getting healthy, but I suppose for you, why is this something you want to do now as opposed to waiting another 3, 6, or 12 months from now?',
                'start': 0,
                'end': 10,
                'sentences': ['I can understand the rationale now.', 'You want to start getting healthy, but I suppose for you, why is this something you want to do now as opposed to waiting another 3, 6, or 12 months from now?']
            },
            {
                'speaker': 'Cassidy',
                'text': 'I guess I have to do it now or I\'ll just procrastinate.',
                'start': 10,
                'end': 15,
                'sentences': ['I guess I have to do it now or I\'ll just procrastinate.']
            },
            {
                'speaker': 'Trainer',
                'text': 'Awesome! How did that feel, Aiden?',
                'start': 15,
                'end': 17,
                'sentences': ['Awesome!', 'How did that feel, Aiden?']
            }
        ]
    }
    
    annotated = processor.add_training_annotations(sample_result)
    
    print(f"Annotations found: {len(annotated.get('annotations', []))}")
    for annotation in annotated.get('annotations', []):
        print(f"\n  [{annotation['type']} - {annotation['label']}]")
        print(f"    {annotation['description']}")
        print(f"    Position: Segment {annotation['position']}")
    
    print(f"\n📝 Annotated Text:")
    print(annotated.get('annotated_text', ''))
    
    return True


def test_full_pipeline():
    """Test complete preprocessing pipeline"""
    print("\n🧪 Testing Full Preprocessing Pipeline")
    print("=" * 60)
    
    processor = get_transcript_processor()
    
    sample_result = {
        'text': 'i can understand the restaurant now you want to start getting healthy but i suppose for you why is this something you want to do now as opposed to waiting another 3632 months from now cast i guess i have to do it now or weapon just procrastinate awesome how did that feel aiden',
        'segments': [
            {'text': 'i', 'start': 0.0, 'end': 0.1, 'confidence': 0.95, 'speaker_tag': 1},
            {'text': 'can', 'start': 0.1, 'end': 0.3, 'confidence': 0.96, 'speaker_tag': 1},
            {'text': 'understand', 'start': 0.3, 'end': 0.7, 'confidence': 0.97, 'speaker_tag': 1},
            {'text': 'the', 'start': 0.7, 'end': 0.8, 'confidence': 0.98, 'speaker_tag': 1},
            {'text': 'restaurant', 'start': 0.8, 'end': 1.3, 'confidence': 0.85, 'speaker_tag': 1},
            {'text': 'now', 'start': 1.3, 'end': 1.5, 'confidence': 0.96, 'speaker_tag': 1},
        ],
        'confidence': 0.92,
        'language': 'en-US',
        'method': 'google_cloud_stt'
    }
    
    print("Processing transcript through full pipeline...")
    result = processor.process_transcript(sample_result)
    
    print(f"\n✅ Pipeline Complete!")
    print(f"\n📊 Results:")
    print(f"  Corrections Applied: {len(result.get('corrections_applied', []))}")
    print(f"  Speaker Segments: {len(result.get('speaker_segments', []))}")
    print(f"  Annotations: {len(result.get('annotations', []))}")
    print(f"  Sentence Segmented: {result.get('sentence_segmented', False)}")
    
    if result.get('corrections_applied'):
        print(f"\n🔧 Corrections:")
        correction_table = processor.generate_correction_table(result['corrections_applied'])
        print(correction_table)
    
    if result.get('labeled_text'):
        print(f"\n💬 Labeled Transcript:")
        print(result['labeled_text'][:500] + "..." if len(result['labeled_text']) > 500 else result['labeled_text'])
    
    if result.get('annotated_text'):
        print(f"\n📝 Annotated Transcript:")
        print(result['annotated_text'][:500] + "..." if len(result['annotated_text']) > 500 else result['annotated_text'])
    
    return True


def main():
    """Run all tests"""
    print("🧪 Transcript Preprocessing Test Suite")
    print("=" * 60)
    
    tests = [
        ("STT Corrections", test_stt_corrections),
        ("Speaker Diarization", test_speaker_diarization),
        ("Sentence Segmentation", test_sentence_segmentation),
        ("Training Annotations", test_training_annotations),
        ("Full Pipeline", test_full_pipeline),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
