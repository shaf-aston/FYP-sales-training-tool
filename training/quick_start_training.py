#!/usr/bin/env python3
"""
Quick Start Script - Adaptive PyTorch Training
One command to analyze and train on your data
"""
import sys
import subprocess
from pathlib import Path
import json

def check_data_exists():
    data_path = Path("training/data/processed/training_pairs.jsonl")
    if not data_path.exists():
        print("❌ Training data not found!")
        print(f"   Expected: {data_path}")
        print()
        print("Please ensure your training data is in:")
        print("  - training/data/processed/training_pairs.jsonl (JSONL format)")
        print("  - training/data/processed/structured_conversations.json (JSON format)")
        print()
        return None
    print("✓ Training data found")
    print(f"  Path: {data_path}")
    print()
    return data_path

def analyze_dataset(data_path):
    print("Step 1: Analyzing dataset...")
    print("-" * 80)
    result = subprocess.run([
        sys.executable,
        "training/train_adaptive.py",
        "--data_path", str(data_path),
        "--save_dataset_stats",
        "--dry_run"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ Dataset analysis failed!")
        print(result.stderr)
        return False
    return True

def main():
    print("=" * 80)
    print("🚀 ADAPTIVE PYTORCH TRAINING - QUICK START")
    print("=" * 80)
    print()
    data_path = check_data_exists()
    if not data_path:
        return 1
    if not analyze_dataset(data_path):
        return 1
    stats_path = Path("training/models/fine-tuned/dataset_stats.json")
    if stats_path.exists():
        with open(stats_path) as f:
            stats = json.load(f)
        
        print()
        print("📊 Dataset Analysis Results:")
        print(f"  ├─ Total samples: {stats['total_samples']}")
        print(f"  ├─ Unique personas: {len(stats['personas'])}")
        print(f"  ├─ Avg input length: {stats['avg_input_length']:.1f} tokens")
        print(f"  ├─ Avg output length: {stats['avg_output_length']:.1f} tokens")
        print(f"  ├─ Recommended batch size: {stats['recommended_batch_size']}")
        print(f"  ├─ Recommended max length: {stats['recommended_max_length']}")
        print(f"  └─ Est. training time: {stats['estimated_training_time_minutes']:.1f} minutes")
        print()
    
    # Step 2: Choose training mode
    print("Step 2: Select training mode")
    print("-" * 80)
    print("  1. Quick Test (1 epoch, fast iteration)")
    print("  2. Automatic (optimal settings from dataset analysis)")
    print("  3. Production (full training with monitoring)")
    print("  4. Custom (specify parameters)")
    print()
    
    choice = input("Enter choice [1-4, default=2]: ").strip() or "2"
    
    cmd = [sys.executable, "training/train_adaptive.py", "--data_path", str(data_path)]
    
    if choice == "1":
        print("\n🏃 Starting quick test training...")
        cmd.extend(["--preset", "quick_test"])
    elif choice == "2":
        print("\n🤖 Starting automatic training...")
        cmd.extend(["--preset", "auto"])
    elif choice == "3":
        print("\n🏭 Starting production training...")
        cmd.extend(["--preset", "production"])
    elif choice == "4":
        print("\n⚙️  Custom configuration")
        epochs = input("  Epochs [3]: ").strip() or "3"
        batch_size = input("  Batch size [4]: ").strip() or "4"
        lr = input("  Learning rate [2e-5]: ").strip() or "2e-5"
        
        cmd.extend([
            "--epochs", epochs,
            "--batch_size", batch_size,
            "--learning_rate", lr
        ])
    else:
        print("❌ Invalid choice!")
        return 1
    
    # Add output directory
    output_dir = input("\nOutput directory [training/models/sales_model]: ").strip()
    if output_dir:
        cmd.extend(["--output_dir", output_dir])
    
    print()
    print("=" * 80)
    print("🎓 Starting Training")
    print("=" * 80)
    print()
    print("Command:", " ".join(cmd))
    print()
    print("Press Ctrl+C to stop training at any time (checkpoint will be saved)")
    print()
    
    # Step 3: Train
    try:
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print()
            print("=" * 80)
            print("✅ TRAINING COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print()
            print("Your trained model is ready!")
            print(f"Location: {output_dir or 'training/models/fine-tuned'}")
            print()
            print("Next steps:")
            print("  1. Test your model with the chat service")
            print("  2. View training metrics in TensorBoard")
            print("  3. Deploy to production")
            print()
            return 0
        else:
            print()
            print("❌ Training failed or was interrupted")
            print("Check the error messages above for details")
            return 1
    
    except KeyboardInterrupt:
        print()
        print("⚠️  Training interrupted by user")
        print("Checkpoint should be saved - you can resume training later")
        return 1


if __name__ == "__main__":
    sys.exit(main())
