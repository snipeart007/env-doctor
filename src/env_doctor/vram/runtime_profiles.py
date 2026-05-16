"""
Runtime profile management for VRAM estimation.

Manages runtime-specific configurations including KV cache overhead,
fragmentation multipliers, and optimization settings for different
ML frameworks and inference engines.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class RuntimeProfile:
    """Runtime-specific configuration profile."""
    
    name: str
    kv_overhead_multiplier: float
    fragmentation_multiplier: float
    supports_quantization: bool
    supports_flash_attention: bool
    description: str
    typical_use_case: str
    
    @property
    def total_overhead_multiplier(self) -> float:
        """Combined overhead multiplier."""
        return self.kv_overhead_multiplier * self.fragmentation_multiplier


class RuntimeProfileManager:
    """Manages runtime profiles for VRAM estimation."""
    
    # Default profiles (used if YAML file not found)
    DEFAULT_PROFILES = {
        'transformers': RuntimeProfile(
            name='transformers',
            kv_overhead_multiplier=1.0,
            fragmentation_multiplier=1.2,
            supports_quantization=True,
            supports_flash_attention=True,
            description='Standard HuggingFace Transformers library',
            typical_use_case='General-purpose model inference and fine-tuning'
        ),
        'vllm': RuntimeProfile(
            name='vllm',
            kv_overhead_multiplier=0.85,
            fragmentation_multiplier=1.1,
            supports_quantization=True,
            supports_flash_attention=True,
            description='vLLM - optimized inference engine with PagedAttention',
            typical_use_case='High-throughput LLM serving with continuous batching'
        ),
        'tgi': RuntimeProfile(
            name='tgi',
            kv_overhead_multiplier=0.9,
            fragmentation_multiplier=1.15,
            supports_quantization=True,
            supports_flash_attention=True,
            description='Text Generation Inference by HuggingFace',
            typical_use_case='Production LLM serving with optimized batching'
        ),
        'text-generation-inference': RuntimeProfile(
            name='text-generation-inference',
            kv_overhead_multiplier=0.9,
            fragmentation_multiplier=1.15,
            supports_quantization=True,
            supports_flash_attention=True,
            description='Text Generation Inference by HuggingFace',
            typical_use_case='Production LLM serving with optimized batching'
        ),
        'deepspeed': RuntimeProfile(
            name='deepspeed',
            kv_overhead_multiplier=1.1,
            fragmentation_multiplier=1.25,
            supports_quantization=True,
            supports_flash_attention=True,
            description='DeepSpeed inference with ZeRO optimization',
            typical_use_case='Large-scale model training and inference'
        ),
        'tensorrt-llm': RuntimeProfile(
            name='tensorrt-llm',
            kv_overhead_multiplier=0.8,
            fragmentation_multiplier=1.05,
            supports_quantization=True,
            supports_flash_attention=True,
            description='NVIDIA TensorRT-LLM optimized inference',
            typical_use_case='Maximum performance NVIDIA GPU inference'
        ),
        'llama.cpp': RuntimeProfile(
            name='llama.cpp',
            kv_overhead_multiplier=0.95,
            fragmentation_multiplier=1.1,
            supports_quantization=True,
            supports_flash_attention=False,
            description='llama.cpp CPU/GPU inference',
            typical_use_case='Efficient inference on consumer hardware'
        ),
        'onnxruntime': RuntimeProfile(
            name='onnxruntime',
            kv_overhead_multiplier=1.0,
            fragmentation_multiplier=1.15,
            supports_quantization=True,
            supports_flash_attention=False,
            description='ONNX Runtime for cross-platform inference',
            typical_use_case='Cross-platform optimized inference'
        ),
    }
    
    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        Initialize runtime profile manager.
        
        Args:
            config_path: Path to runtime profiles YAML file
        """
        self.config_path = config_path
        self.profiles: dict[str, RuntimeProfile] = {}
        self._load_profiles()
    
    def _load_profiles(self) -> None:
        """Load profiles from YAML file or use defaults."""
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    
                if data and 'profiles' in data:
                    for profile_data in data['profiles']:
                        profile = RuntimeProfile(**profile_data)
                        self.profiles[profile.name] = profile
                    return
            except Exception:
                # Fall back to defaults on any error
                pass
        
        # Use default profiles
        self.profiles = self.DEFAULT_PROFILES.copy()
    
    def get_profile(self, runtime_name: str) -> Optional[RuntimeProfile]:
        """
        Get runtime profile by name.
        
        Args:
            runtime_name: Name of the runtime
            
        Returns:
            RuntimeProfile if found, None otherwise
        """
        # Try exact match first
        if runtime_name in self.profiles:
            return self.profiles[runtime_name]
        
        # Try case-insensitive match
        runtime_lower = runtime_name.lower()
        for name, profile in self.profiles.items():
            if name.lower() == runtime_lower:
                return profile
        
        return None
    
    def get_profile_or_default(self, runtime_name: str) -> RuntimeProfile:
        """
        Get runtime profile or return default transformers profile.
        
        Args:
            runtime_name: Name of the runtime
            
        Returns:
            RuntimeProfile (never None)
        """
        profile = self.get_profile(runtime_name)
        if profile:
            return profile
        
        # Return transformers as default
        return self.profiles.get('transformers', self.DEFAULT_PROFILES['transformers'])
    
    def list_profiles(self) -> list[str]:
        """
        List all available profile names.
        
        Returns:
            List of profile names
        """
        return sorted(self.profiles.keys())
    
    def get_all_profiles(self) -> dict[str, RuntimeProfile]:
        """
        Get all profiles.
        
        Returns:
            Dictionary of all profiles
        """
        return self.profiles.copy()
    
    def add_profile(self, profile: RuntimeProfile) -> None:
        """
        Add or update a runtime profile.
        
        Args:
            profile: RuntimeProfile to add
        """
        self.profiles[profile.name] = profile
    
    def save_profiles(self, output_path: Path) -> None:
        """
        Save profiles to YAML file.
        
        Args:
            output_path: Path to save YAML file
        """
        profiles_data = []
        for profile in self.profiles.values():
            profiles_data.append({
                'name': profile.name,
                'kv_overhead_multiplier': profile.kv_overhead_multiplier,
                'fragmentation_multiplier': profile.fragmentation_multiplier,
                'supports_quantization': profile.supports_quantization,
                'supports_flash_attention': profile.supports_flash_attention,
                'description': profile.description,
                'typical_use_case': profile.typical_use_case,
            })
        
        data = {'profiles': profiles_data}
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    @staticmethod
    def create_default_config(output_path: Path) -> None:
        """
        Create default runtime profiles configuration file.
        
        Args:
            output_path: Path to save configuration
        """
        manager = RuntimeProfileManager()
        manager.save_profiles(output_path)

# Made with Bob
