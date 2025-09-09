#!/usr/bin/env python3
"""
Test script to check RunPod capabilities for LLM hosting
"""

import torch
import sys
import os
import subprocess

print("=== RunPod LLM Environment Test ===")
print(f"Python version: {sys.version}")
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU count: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        gpu_name = torch.cuda.get_device_name(i)
        gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
        print(f"GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")
else:
    print("No CUDA GPUs available")

# Check available disk space
print("\n=== Storage Information ===")
try:
    result = subprocess.run(['df', '-h'], capture_output=True, text=True)
    print(result.stdout)
except:
    print("Could not get disk usage information")

# Check if common LLM libraries are available
print("\n=== LLM Library Check ===")
libraries = ['transformers', 'accelerate', 'bitsandbytes', 'vllm', 'torch']
for lib in libraries:
    try:
        __import__(lib)
        print(f"✅ {lib} is available")
    except ImportError:
        print(f"❌ {lib} is NOT available")

print("\n=== Environment Ready for LLM Hosting ===")
