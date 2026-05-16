"""
VRAM Intelligence Engine for env-doctor.

Provides accurate VRAM estimation for ML models using HuggingFace Hub integration,
GPU detection, and sophisticated memory calculations.
"""

from .model_fetcher import ModelFetcher, ModelArchitecture
from .gpu_detector import GPUDetector, GPUInfo
from .weight_calculator import WeightCalculator, WeightMemory
from .kv_cache_estimator import KVCacheEstimator, KVCacheMemory
from .oom_detector import OOMDetector, OOMRiskAssessment, OOMRiskLevel
from .runtime_profiles import RuntimeProfileManager, RuntimeProfile

__all__ = [
    'ModelFetcher',
    'ModelArchitecture',
    'GPUDetector',
    'GPUInfo',
    'WeightCalculator',
    'WeightMemory',
    'KVCacheEstimator',
    'KVCacheMemory',
    'OOMDetector',
    'OOMRiskAssessment',
    'OOMRiskLevel',
    'RuntimeProfileManager',
    'RuntimeProfile',
]

# Made with Bob
