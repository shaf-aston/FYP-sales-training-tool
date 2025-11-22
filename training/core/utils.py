"""
Utility functions for training
"""
import random
import numpy as np
import torch
import os
import random
import sys

def set_seed(seed: int):
    if not (0 <= seed <= 2**32 - 1):
        raise ValueError(f"Seed must be between 0 and 2**32 - 1, but got {seed}")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

def get_device():
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        device = torch.device("cpu")
        print("Using CPU")
    return device
