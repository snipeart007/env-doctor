"""
KV cache memory estimator for transformer models.

Estimates memory requirements for key-value cache during inference,
taking into account model architecture, batch size, sequence length,
and runtime optimizations.
"""

from dataclasses import dataclass
from typing import Optional

from .model_fetcher import ModelArchitecture


@dataclass
class KVCacheMemory:
    """Memory breakdown for KV cache."""
    
    key_cache_gb: float
    value_cache_gb: float
    overhead_gb: float
    
    @property
    def total_memory_gb(self) -> float:
        """Total KV cache memory in GB."""
        return self.key_cache_gb + self.value_cache_gb + self.overhead_gb


class KVCacheEstimator:
    """Estimates KV cache memory requirements."""
    
    def __init__(
        self,
        batch_size: int = 1,
        sequence_length: int = 2048,
        bytes_per_element: float = 2.0,  # FP16 by default
        runtime_multiplier: float = 1.0
    ) -> None:
        """
        Initialize KV cache estimator.
        
        Args:
            batch_size: Batch size for inference
            sequence_length: Maximum sequence length
            bytes_per_element: Bytes per activation element (2 for FP16, 4 for FP32)
            runtime_multiplier: Runtime-specific overhead multiplier
        """
        self.batch_size = batch_size
        self.sequence_length = sequence_length
        self.bytes_per_element = bytes_per_element
        self.runtime_multiplier = runtime_multiplier
    
    def estimate_kv_cache(self, arch: ModelArchitecture) -> KVCacheMemory:
        """
        Estimate KV cache memory for a model architecture.
        
        The KV cache stores key and value tensors for each attention layer.
        For each layer, we need to store:
        - Keys: [batch_size, num_heads, seq_len, head_dim]
        - Values: [batch_size, num_heads, seq_len, head_dim]
        
        Args:
            arch: Model architecture details
            
        Returns:
            KVCacheMemory breakdown
        """
        # Calculate head dimension
        head_dim = arch.hidden_size // arch.num_attention_heads
        
        # For GQA (Grouped Query Attention), K and V use fewer heads
        num_kv_heads = arch.num_key_value_heads or arch.num_attention_heads
        
        # Key cache per layer: batch * num_kv_heads * seq_len * head_dim * bytes
        key_elements_per_layer = (
            self.batch_size * 
            num_kv_heads * 
            self.sequence_length * 
            head_dim
        )
        key_bytes_per_layer = key_elements_per_layer * self.bytes_per_element
        total_key_bytes = key_bytes_per_layer * arch.num_layers
        key_cache_gb = total_key_bytes / (1024 ** 3)
        
        # Value cache is same size as key cache
        value_cache_gb = key_cache_gb
        
        # Apply runtime multiplier for framework overhead
        base_cache_gb = key_cache_gb + value_cache_gb
        overhead_gb = base_cache_gb * (self.runtime_multiplier - 1.0)
        
        return KVCacheMemory(
            key_cache_gb=key_cache_gb,
            value_cache_gb=value_cache_gb,
            overhead_gb=max(0.0, overhead_gb)
        )
    
    def estimate_total_memory_gb(self, arch: ModelArchitecture) -> float:
        """
        Estimate total KV cache memory in GB.
        
        Args:
            arch: Model architecture details
            
        Returns:
            Total memory in GB
        """
        kv_memory = self.estimate_kv_cache(arch)
        return kv_memory.total_memory_gb
    
    def estimate_for_different_batch_sizes(
        self,
        arch: ModelArchitecture,
        batch_sizes: list[int]
    ) -> dict[int, float]:
        """
        Estimate KV cache for different batch sizes.
        
        Args:
            arch: Model architecture details
            batch_sizes: List of batch sizes to estimate
            
        Returns:
            Dictionary mapping batch_size to memory in GB
        """
        results = {}
        original_batch_size = self.batch_size
        
        for batch_size in batch_sizes:
            self.batch_size = batch_size
            results[batch_size] = self.estimate_total_memory_gb(arch)
        
        self.batch_size = original_batch_size
        return results
    
    def estimate_for_different_seq_lengths(
        self,
        arch: ModelArchitecture,
        seq_lengths: list[int]
    ) -> dict[int, float]:
        """
        Estimate KV cache for different sequence lengths.
        
        Args:
            arch: Model architecture details
            seq_lengths: List of sequence lengths to estimate
            
        Returns:
            Dictionary mapping seq_length to memory in GB
        """
        results = {}
        original_seq_length = self.sequence_length
        
        for seq_length in seq_lengths:
            self.sequence_length = seq_length
            results[seq_length] = self.estimate_total_memory_gb(arch)
        
        self.sequence_length = original_seq_length
        return results
    
    def calculate_max_batch_size(
        self,
        arch: ModelArchitecture,
        available_memory_gb: float,
        weight_memory_gb: float
    ) -> int:
        """
        Calculate maximum batch size that fits in available memory.
        
        Args:
            arch: Model architecture details
            available_memory_gb: Available VRAM in GB
            weight_memory_gb: Memory used by model weights
            
        Returns:
            Maximum batch size (at least 1)
        """
        # Memory available for KV cache
        kv_budget_gb = available_memory_gb - weight_memory_gb
        
        if kv_budget_gb <= 0:
            return 1
        
        # Calculate KV cache per batch
        original_batch_size = self.batch_size
        self.batch_size = 1
        kv_per_batch_gb = self.estimate_total_memory_gb(arch)
        self.batch_size = original_batch_size
        
        if kv_per_batch_gb <= 0:
            return 1
        
        # Calculate max batch size
        max_batch = int(kv_budget_gb / kv_per_batch_gb)
        return max(1, max_batch)
    
    def calculate_max_sequence_length(
        self,
        arch: ModelArchitecture,
        available_memory_gb: float,
        weight_memory_gb: float
    ) -> int:
        """
        Calculate maximum sequence length that fits in available memory.
        
        Args:
            arch: Model architecture details
            available_memory_gb: Available VRAM in GB
            weight_memory_gb: Memory used by model weights
            
        Returns:
            Maximum sequence length
        """
        # Memory available for KV cache
        kv_budget_gb = available_memory_gb - weight_memory_gb
        
        if kv_budget_gb <= 0:
            return 512  # Minimum reasonable sequence length
        
        # Calculate KV cache per token
        original_seq_length = self.sequence_length
        self.sequence_length = 1
        kv_per_token_gb = self.estimate_total_memory_gb(arch)
        self.sequence_length = original_seq_length
        
        if kv_per_token_gb <= 0:
            return 512
        
        # Calculate max sequence length
        max_seq_len = int(kv_budget_gb / kv_per_token_gb)
        return max(512, max_seq_len)
    
    @staticmethod
    def get_bytes_per_element(dtype: str) -> float:
        """
        Get bytes per element for a data type.
        
        Args:
            dtype: Data type (fp32, fp16, bf16, etc.)
            
        Returns:
            Bytes per element
        """
        dtype_map = {
            'fp32': 4.0,
            'float32': 4.0,
            'fp16': 2.0,
            'float16': 2.0,
            'half': 2.0,
            'bf16': 2.0,
            'bfloat16': 2.0,
            'int8': 1.0,
        }
        return dtype_map.get(dtype.lower(), 2.0)

# Made with Bob
