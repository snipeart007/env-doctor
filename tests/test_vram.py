"""
Comprehensive tests for VRAM Intelligence Engine.

Tests all VRAM modules including model fetching, GPU detection,
weight calculation, KV cache estimation, OOM detection, and runtime profiles.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from env_doctor.vram import (
    ModelFetcher,
    ModelArchitecture,
    GPUDetector,
    GPUInfo,
    WeightCalculator,
    WeightMemory,
    KVCacheEstimator,
    KVCacheMemory,
    OOMDetector,
    OOMRiskLevel,
    RuntimeProfileManager,
    RuntimeProfile,
)


class TestModelArchitecture:
    """Test ModelArchitecture dataclass."""
    
    def test_param_count_calculation(self):
        """Test parameter count estimation from architecture."""
        arch = ModelArchitecture(
            model_id="test-model",
            hidden_size=4096,
            num_layers=32,
            num_attention_heads=32,
            vocab_size=32000,
            max_position_embeddings=2048,
            intermediate_size=11008
        )
        
        # Calculate expected params:
        # Embedding: 32000 * 4096 = 131,072,000
        # Per layer: 4 * 4096^2 + 2 * 4096 * 11008 = 67,108,864 + 90,177,536 = 157,286,400
        # Total: 131,072,000 + 32 * 157,286,400 = 5,164,236,800 (~5.16B)
        param_count = arch.param_count
        assert 5e9 < param_count < 5.5e9
    
    def test_param_count_with_gqa(self):
        """Test parameter count with Grouped Query Attention."""
        arch = ModelArchitecture(
            model_id="test-model-gqa",
            hidden_size=4096,
            num_layers=32,
            num_attention_heads=32,
            vocab_size=32000,
            max_position_embeddings=2048,
            num_key_value_heads=8,  # GQA
            intermediate_size=11008
        )
        
        param_count = arch.param_count
        assert param_count > 0


class TestModelFetcher:
    """Test ModelFetcher class."""
    
    def test_extract_param_count_from_name(self):
        """Test parameter count extraction from model names."""
        fetcher = ModelFetcher()
        
        assert fetcher._extract_param_count("llama-7b") == 7e9
        assert fetcher._extract_param_count("model-13b-chat") == 13e9
        assert fetcher._extract_param_count("gpt2") == 124e6
        assert fetcher._extract_param_count("bert-base") == 110e6
    
    def test_estimate_from_name(self):
        """Test architecture estimation from model name."""
        fetcher = ModelFetcher()
        
        arch = fetcher._estimate_from_name("test-7b-model")
        assert arch is not None
        assert arch.hidden_size == 4096
        assert arch.num_layers == 32
        # The estimation gives ~5.16B params with the default architecture
        assert 5e9 < arch.param_count < 5.5e9
    
    @patch('env_doctor.vram.model_fetcher.hf_hub_download')
    def test_fetch_config_from_hub(self, mock_download, tmp_path):
        """Test fetching config from HuggingFace Hub."""
        # Create mock config file
        config_data = {
            'hidden_size': 768,
            'num_hidden_layers': 12,
            'num_attention_heads': 12,
            'vocab_size': 30522,
            'max_position_embeddings': 512
        }
        config_file = tmp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        mock_download.return_value = str(config_file)
        
        fetcher = ModelFetcher(cache_dir=tmp_path)
        config = fetcher._fetch_config_from_hub("bert-base-uncased")
        
        assert config is not None
        assert config['hidden_size'] == 768
    
    def test_parse_config(self):
        """Test parsing config into ModelArchitecture."""
        fetcher = ModelFetcher()
        
        config = {
            'hidden_size': 768,
            'num_hidden_layers': 12,
            'num_attention_heads': 12,
            'vocab_size': 30522,
            'max_position_embeddings': 512,
            'model_type': 'bert'
        }
        
        arch = fetcher._parse_config("bert-base", config)
        
        assert arch is not None
        assert arch.hidden_size == 768
        assert arch.num_layers == 12
        assert arch.model_type == 'bert'


class TestGPUDetector:
    """Test GPUDetector class."""
    
    def test_gpu_info_properties(self):
        """Test GPUInfo property calculations."""
        gpu = GPUInfo(
            index=0,
            name="Test GPU",
            total_memory_mb=24000,
            used_memory_mb=8000,
            free_memory_mb=16000
        )
        
        assert abs(gpu.total_memory_gb - 23.44) < 0.1
        assert abs(gpu.used_memory_gb - 7.81) < 0.1
        assert abs(gpu.free_memory_gb - 15.63) < 0.1
        assert abs(gpu.utilization_percent - 33.33) < 0.1
    
    @patch('subprocess.run')
    def test_detect_with_nvidia_smi(self, mock_run):
        """Test GPU detection with nvidia-smi."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "0, NVIDIA RTX 4090, 24000, 8000, 16000, 535.54\n"
        mock_run.return_value = mock_result
        
        detector = GPUDetector()
        detector._pynvml_available = False  # Force nvidia-smi path
        
        gpus = detector._detect_with_nvidia_smi()
        
        assert len(gpus) == 1
        assert gpus[0].name == "NVIDIA RTX 4090"
        assert gpus[0].total_memory_mb == 24000
    
    def test_get_recommended_gpu(self):
        """Test GPU recommendation logic."""
        detector = GPUDetector()
        
        # Mock GPU list
        gpus = [
            GPUInfo(0, "GPU 1", 8000, 2000, 6000),
            GPUInfo(1, "GPU 2", 24000, 4000, 20000),
            GPUInfo(2, "GPU 3", 16000, 8000, 8000),
        ]
        
        with patch.object(detector, 'detect_gpus', return_value=gpus):
            # Should recommend GPU with most free memory
            gpu = detector.get_recommended_gpu(10.0)
            assert gpu.index == 1  # GPU 2 has most free memory


class TestWeightCalculator:
    """Test WeightCalculator class."""
    
    def test_bytes_per_param_mapping(self):
        """Test quantization to bytes per parameter mapping."""
        assert WeightCalculator('fp32').bytes_per_param == 4.0
        assert WeightCalculator('fp16').bytes_per_param == 2.0
        assert WeightCalculator('int8').bytes_per_param == 1.0
        assert WeightCalculator('int4').bytes_per_param == 0.5
    
    def test_calculate_weight_memory(self):
        """Test weight memory calculation."""
        arch = ModelArchitecture(
            model_id="test-7b",
            hidden_size=4096,
            num_layers=32,
            num_attention_heads=32,
            vocab_size=32000,
            max_position_embeddings=2048,
            intermediate_size=11008
        )
        
        calc = WeightCalculator('fp16')
        memory = calc.calculate_weight_memory(arch)
        
        assert isinstance(memory, WeightMemory)
        assert memory.total_memory_gb > 0
        assert memory.embedding_memory_gb > 0
        assert memory.attention_memory_gb > 0
        assert memory.ffn_memory_gb > 0
    
    def test_quantization_label(self):
        """Test quantization label generation."""
        assert WeightCalculator('fp16').get_quantization_label() == 'FP16'
        assert WeightCalculator('int8').get_quantization_label() == 'INT8'
        assert WeightCalculator('nf4').get_quantization_label() == 'NF4'
    
    def test_estimate_memory_savings(self):
        """Test memory savings estimation."""
        new_mem, savings = WeightCalculator.estimate_memory_savings(
            base_memory_gb=14.0,
            from_quant='fp16',
            to_quant='int8'
        )
        
        assert abs(new_mem - 7.0) < 0.1
        assert abs(savings - 50.0) < 0.1


class TestKVCacheEstimator:
    """Test KVCacheEstimator class."""
    
    def test_estimate_kv_cache(self):
        """Test KV cache estimation."""
        arch = ModelArchitecture(
            model_id="test-7b",
            hidden_size=4096,
            num_layers=32,
            num_attention_heads=32,
            vocab_size=32000,
            max_position_embeddings=2048
        )
        
        estimator = KVCacheEstimator(
            batch_size=1,
            sequence_length=2048,
            bytes_per_element=2.0
        )
        
        memory = estimator.estimate_kv_cache(arch)
        
        assert isinstance(memory, KVCacheMemory)
        assert memory.total_memory_gb > 0
        assert memory.key_cache_gb > 0
        assert memory.value_cache_gb > 0
        assert memory.key_cache_gb == memory.value_cache_gb
    
    def test_estimate_for_different_batch_sizes(self):
        """Test estimation for multiple batch sizes."""
        arch = ModelArchitecture(
            model_id="test",
            hidden_size=768,
            num_layers=12,
            num_attention_heads=12,
            vocab_size=30522,
            max_position_embeddings=512
        )
        
        estimator = KVCacheEstimator(batch_size=1, sequence_length=512)
        results = estimator.estimate_for_different_batch_sizes(arch, [1, 2, 4, 8])
        
        assert len(results) == 4
        assert results[2] > results[1]  # Larger batch = more memory
        assert results[8] > results[4]
    
    def test_calculate_max_batch_size(self):
        """Test maximum batch size calculation."""
        arch = ModelArchitecture(
            model_id="test",
            hidden_size=768,
            num_layers=12,
            num_attention_heads=12,
            vocab_size=30522,
            max_position_embeddings=512
        )
        
        estimator = KVCacheEstimator(batch_size=1, sequence_length=512)
        max_batch = estimator.calculate_max_batch_size(
            arch=arch,
            available_memory_gb=24.0,
            weight_memory_gb=2.0
        )
        
        assert max_batch >= 1


class TestOOMDetector:
    """Test OOMDetector class."""
    
    def test_determine_risk_level(self):
        """Test risk level determination."""
        detector = OOMDetector()
        
        assert detector._determine_risk_level(50.0) == OOMRiskLevel.SAFE
        assert detector._determine_risk_level(75.0) == OOMRiskLevel.WARNING
        assert detector._determine_risk_level(90.0) == OOMRiskLevel.DANGER
        assert detector._determine_risk_level(97.0) == OOMRiskLevel.CRITICAL
        assert detector._determine_risk_level(105.0) == OOMRiskLevel.IMPOSSIBLE
    
    def test_assess_risk_safe(self):
        """Test risk assessment for safe scenario."""
        detector = OOMDetector(fragmentation_multiplier=1.2)
        
        risk = detector.assess_risk(
            required_memory_gb=10.0,
            available_memory_gb=24.0,
            apply_fragmentation=True
        )
        
        assert risk.risk_level == OOMRiskLevel.SAFE
        assert risk.can_fit
        assert risk.utilization_percent < 70.0
    
    def test_assess_risk_critical(self):
        """Test risk assessment for critical scenario."""
        detector = OOMDetector()
        
        risk = detector.assess_risk(
            required_memory_gb=23.0,
            available_memory_gb=24.0,
            apply_fragmentation=False
        )
        
        assert risk.risk_level == OOMRiskLevel.CRITICAL
        assert risk.can_fit
        assert risk.utilization_percent > 95.0
    
    def test_assess_risk_impossible(self):
        """Test risk assessment for impossible scenario."""
        detector = OOMDetector()
        
        risk = detector.assess_risk(
            required_memory_gb=30.0,
            available_memory_gb=24.0,
            apply_fragmentation=False
        )
        
        assert risk.risk_level == OOMRiskLevel.IMPOSSIBLE
        assert not risk.can_fit
        assert risk.overflow_gb > 0
    
    def test_get_gpu_recommendations(self):
        """Test GPU recommendations."""
        detector = OOMDetector()
        
        recs = detector.get_gpu_recommendations(10.0)
        assert len(recs) > 0
        
        recs = detector.get_gpu_recommendations(50.0)
        assert len(recs) > 0
        assert any('A100' in rec for rec in recs)
    
    def test_suggest_optimizations(self):
        """Test optimization suggestions."""
        detector = OOMDetector()
        
        suggestions = detector.suggest_optimizations(
            current_memory_gb=20.0,
            target_memory_gb=16.0,
            current_batch_size=4,
            current_seq_length=2048,
            current_quantization='fp16'
        )
        
        assert len(suggestions) > 0
        assert any('batch' in s.lower() for s in suggestions)


class TestRuntimeProfileManager:
    """Test RuntimeProfileManager class."""
    
    def test_default_profiles_loaded(self):
        """Test that default profiles are loaded."""
        manager = RuntimeProfileManager()
        
        assert 'transformers' in manager.profiles
        assert 'vllm' in manager.profiles
        assert 'tgi' in manager.profiles
    
    def test_get_profile(self):
        """Test getting a profile by name."""
        manager = RuntimeProfileManager()
        
        profile = manager.get_profile('transformers')
        assert profile is not None
        assert profile.name == 'transformers'
        assert profile.kv_overhead_multiplier > 0
    
    def test_get_profile_case_insensitive(self):
        """Test case-insensitive profile lookup."""
        manager = RuntimeProfileManager()
        
        profile = manager.get_profile('VLLM')
        assert profile is not None
        assert profile.name == 'vllm'
    
    def test_get_profile_or_default(self):
        """Test getting profile with fallback to default."""
        manager = RuntimeProfileManager()
        
        # Existing profile
        profile = manager.get_profile_or_default('vllm')
        assert profile.name == 'vllm'
        
        # Non-existing profile should return transformers
        profile = manager.get_profile_or_default('nonexistent')
        assert profile.name == 'transformers'
    
    def test_list_profiles(self):
        """Test listing all profile names."""
        manager = RuntimeProfileManager()
        
        profiles = manager.list_profiles()
        assert len(profiles) > 0
        assert 'transformers' in profiles
        assert 'vllm' in profiles
    
    def test_add_profile(self):
        """Test adding a new profile."""
        manager = RuntimeProfileManager()
        
        new_profile = RuntimeProfile(
            name='custom',
            kv_overhead_multiplier=1.0,
            fragmentation_multiplier=1.1,
            supports_quantization=True,
            supports_flash_attention=True,
            description='Custom runtime',
            typical_use_case='Testing'
        )
        
        manager.add_profile(new_profile)
        
        assert 'custom' in manager.profiles
        assert manager.get_profile('custom') == new_profile
    
    def test_save_and_load_profiles(self, tmp_path):
        """Test saving and loading profiles from YAML."""
        config_path = tmp_path / "profiles.yaml"
        
        # Create and save profiles
        manager1 = RuntimeProfileManager()
        manager1.save_profiles(config_path)
        
        assert config_path.exists()
        
        # Load profiles
        manager2 = RuntimeProfileManager(config_path)
        
        assert len(manager2.profiles) == len(manager1.profiles)
        assert 'transformers' in manager2.profiles


class TestIntegration:
    """Integration tests for VRAM estimation pipeline."""
    
    def test_full_estimation_pipeline(self):
        """Test complete VRAM estimation pipeline."""
        # Create mock architecture
        arch = ModelArchitecture(
            model_id="test-7b",
            hidden_size=4096,
            num_layers=32,
            num_attention_heads=32,
            vocab_size=32000,
            max_position_embeddings=2048,
            intermediate_size=11008
        )
        
        # Calculate weights
        weight_calc = WeightCalculator('fp16')
        weight_memory = weight_calc.calculate_weight_memory(arch)
        
        # Calculate KV cache
        kv_estimator = KVCacheEstimator(
            batch_size=1,
            sequence_length=2048,
            runtime_multiplier=1.0
        )
        kv_memory = kv_estimator.estimate_kv_cache(arch)
        
        # Calculate total with fragmentation
        total_memory = (weight_memory.total_memory_gb + kv_memory.total_memory_gb) * 1.2
        
        # Assess OOM risk
        oom_detector = OOMDetector()
        risk = oom_detector.assess_risk(
            required_memory_gb=total_memory,
            available_memory_gb=24.0,
            apply_fragmentation=False
        )
        
        assert total_memory > 0
        assert risk.risk_level in OOMRiskLevel
        assert risk.utilization_percent >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
