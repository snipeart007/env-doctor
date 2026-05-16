"""
Weight memory calculator for precise model weight memory estimation.

Calculates memory requirements for model weights based on actual architecture
parameters and quantization settings.
"""

from dataclasses import dataclass
from typing import Optional

from .model_fetcher import ModelArchitecture


@dataclass
class WeightMemory:
    """Memory breakdown for model weights."""
    
    embedding_memory_gb: float
    attention_memory_gb: float
    ffn_memory_gb: float
    other_memory_gb: float
    
    @property
    def total_memory_gb(self) -> float:
        """Total weight memory in GB."""
        return (
            self.embedding_memory_gb +
            self.attention_memory_gb +
            self.ffn_memory_gb +
            self.other_memory_gb
        )


class WeightCalculator:
    """Calculates precise weight memory requirements."""
    
    # Bytes per parameter for different quantization levels
    BYTES_PER_PARAM = {
        'fp32': 4.0,
        'float32': 4.0,
        'fp16': 2.0,
        'float16': 2.0,
        'half': 2.0,
        'bf16': 2.0,
        'bfloat16': 2.0,
        'int8': 1.0,
        '8bit': 1.0,
        'int4': 0.5,
        '4bit': 0.5,
        'nf4': 0.5,  # NormalFloat4
        'fp4': 0.5,  # Float4
    }
    
    def __init__(self, quantization: Optional[str] = None) -> None:
        """
        Initialize weight calculator.
        
        Args:
            quantization: Quantization format (fp32, fp16, int8, int4, etc.)
        """
        self.quantization = (quantization or 'fp16').lower()
        self.bytes_per_param = self.BYTES_PER_PARAM.get(self.quantization, 2.0)
    
    def calculate_weight_memory(self, arch: ModelArchitecture) -> WeightMemory:
        """
        Calculate weight memory for a model architecture, handling MoE and GQA.
        
        Args:
            arch: Model architecture details
            
        Returns:
            WeightMemory breakdown
        """
        # 1. Embedding layer: vocab_size * hidden_size
        embedding_params = arch.vocab_size * arch.hidden_size
        embedding_memory_gb = (embedding_params * self.bytes_per_param) / (1024 ** 3)
        
        # 2. Attention parameters per layer
        # Handle GQA/MQA by reducing KV head projections
        head_dim = arch.hidden_size // arch.num_attention_heads
        num_kv_heads = arch.num_key_value_heads or arch.num_attention_heads
        
        q_params = arch.hidden_size * arch.hidden_size
        kv_params = 2 * (arch.hidden_size * (num_kv_heads * head_dim))
        o_params = arch.hidden_size * arch.hidden_size
        
        attention_params_per_layer = q_params + kv_params + o_params
        total_attention_params = attention_params_per_layer * arch.num_layers
        attention_memory_gb = (total_attention_params * self.bytes_per_param) / (1024 ** 3)
        
        # 3. FFN (Feed-Forward Network) parameters per layer
        # Handle MoE architectures
        intermediate = arch.intermediate_size or (4 * arch.hidden_size)
        
        if arch.num_experts:
            # Mixture of Experts: sum of all routed and shared experts
            # Routed experts: num_experts * (2 * hidden * moe_inter)
            moe_inter = arch.moe_intermediate_size or intermediate
            routed_params = arch.num_experts * (2 * arch.hidden_size * moe_inter)
            
            # Shared experts (if any): num_shared * (2 * hidden * inter)
            shared_params = (arch.num_shared_experts or 0) * (2 * arch.hidden_size * intermediate)
            
            # Gating mechanism
            gate_params = arch.hidden_size * arch.num_experts
            
            ffn_params_per_layer = routed_params + shared_params + gate_params
        else:
            # Standard Dense FFN
            ffn_params_per_layer = 2 * arch.hidden_size * intermediate
            
        total_ffn_params = ffn_params_per_layer * arch.num_layers
        ffn_memory_gb = (total_ffn_params * self.bytes_per_param) / (1024 ** 3)
        
        # 4. Other parameters (layer norms, positional embeddings, etc.)
        # Estimate as 1% of the core parameters
        other_params = (embedding_params + total_attention_params + total_ffn_params) * 0.01
        other_memory_gb = (other_params * self.bytes_per_param) / (1024 ** 3)
        
        return WeightMemory(
            embedding_memory_gb=embedding_memory_gb,
            attention_memory_gb=attention_memory_gb,
            ffn_memory_gb=ffn_memory_gb,
            other_memory_gb=other_memory_gb
        )
    
    def calculate_total_memory_gb(self, arch: ModelArchitecture) -> float:
        """
        Calculate total weight memory in GB.
        
        Args:
            arch: Model architecture details
            
        Returns:
            Total memory in GB
        """
        weight_memory = self.calculate_weight_memory(arch)
        return weight_memory.total_memory_gb
    
    def get_quantization_label(self) -> str:
        """Get human-readable quantization label."""
        labels = {
            'fp32': 'FP32',
            'float32': 'FP32',
            'fp16': 'FP16',
            'float16': 'FP16',
            'half': 'FP16',
            'bf16': 'BF16',
            'bfloat16': 'BF16',
            'int8': 'INT8',
            '8bit': 'INT8',
            'int4': 'INT4',
            '4bit': 'INT4',
            'nf4': 'NF4',
            'fp4': 'FP4',
        }
        return labels.get(self.quantization, self.quantization.upper())
    
    @staticmethod
    def estimate_memory_savings(
        base_memory_gb: float,
        from_quant: str,
        to_quant: str
    ) -> tuple[float, float]:
        """
        Estimate memory savings from quantization.
        
        Args:
            base_memory_gb: Base memory in GB
            from_quant: Current quantization
            to_quant: Target quantization
            
        Returns:
            Tuple of (new_memory_gb, savings_percent)
        """
        from_bytes = WeightCalculator.BYTES_PER_PARAM.get(from_quant.lower(), 2.0)
        to_bytes = WeightCalculator.BYTES_PER_PARAM.get(to_quant.lower(), 2.0)
        
        ratio = to_bytes / from_bytes
        new_memory_gb = base_memory_gb * ratio
        savings_percent = (1 - ratio) * 100
        
        return new_memory_gb, savings_percent

# Made with Bob
