"""
Out-of-Memory (OOM) risk detector for VRAM estimation.

Analyzes memory requirements against available VRAM and provides
risk assessment with percentage-based thresholds.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OOMRiskLevel(Enum):
    """OOM risk levels based on memory utilization percentage."""
    
    SAFE = "safe"           # < 70%
    WARNING = "warning"     # 70-85%
    DANGER = "danger"       # 85-95%
    CRITICAL = "critical"   # > 95%
    IMPOSSIBLE = "impossible"  # > 100%


@dataclass
class OOMRiskAssessment:
    """OOM risk assessment result."""
    
    required_memory_gb: float
    available_memory_gb: float
    utilization_percent: float
    risk_level: OOMRiskLevel
    risk_emoji: str
    risk_color: str
    recommendation: str
    can_fit: bool
    
    @property
    def free_memory_gb(self) -> float:
        """Remaining free memory in GB."""
        return max(0.0, self.available_memory_gb - self.required_memory_gb)
    
    @property
    def overflow_gb(self) -> float:
        """Memory overflow in GB (if any)."""
        return max(0.0, self.required_memory_gb - self.available_memory_gb)


class OOMDetector:
    """Detects OOM risk based on memory requirements and availability."""
    
    # Threshold percentages for risk levels
    SAFE_THRESHOLD = 70.0
    WARNING_THRESHOLD = 85.0
    DANGER_THRESHOLD = 95.0
    
    def __init__(self, fragmentation_multiplier: float = 1.2) -> None:
        """
        Initialize OOM detector.
        
        Args:
            fragmentation_multiplier: Multiplier for memory fragmentation overhead
        """
        self.fragmentation_multiplier = fragmentation_multiplier
    
    def assess_risk(
        self,
        required_memory_gb: float,
        available_memory_gb: float,
        apply_fragmentation: bool = True
    ) -> OOMRiskAssessment:
        """
        Assess OOM risk for given memory requirements.
        
        Args:
            required_memory_gb: Required memory in GB
            available_memory_gb: Available VRAM in GB
            apply_fragmentation: Whether to apply fragmentation multiplier
            
        Returns:
            OOMRiskAssessment with detailed analysis
        """
        # Apply fragmentation overhead if requested
        if apply_fragmentation:
            effective_required_gb = required_memory_gb * self.fragmentation_multiplier
        else:
            effective_required_gb = required_memory_gb
        
        # Calculate utilization percentage
        if available_memory_gb > 0:
            utilization_percent = (effective_required_gb / available_memory_gb) * 100.0
        else:
            utilization_percent = 100.0 if effective_required_gb > 0 else 0.0
        
        # Determine risk level
        risk_level = self._determine_risk_level(utilization_percent)
        
        # Get risk metadata
        risk_emoji = self._get_risk_emoji(risk_level)
        risk_color = self._get_risk_color(risk_level)
        recommendation = self._get_recommendation(
            risk_level,
            effective_required_gb,
            available_memory_gb
        )
        
        # Check if model can fit
        can_fit = effective_required_gb <= available_memory_gb
        
        return OOMRiskAssessment(
            required_memory_gb=effective_required_gb,
            available_memory_gb=available_memory_gb,
            utilization_percent=utilization_percent,
            risk_level=risk_level,
            risk_emoji=risk_emoji,
            risk_color=risk_color,
            recommendation=recommendation,
            can_fit=can_fit
        )
    
    def _determine_risk_level(self, utilization_percent: float) -> OOMRiskLevel:
        """Determine risk level from utilization percentage."""
        if utilization_percent > 100.0:
            return OOMRiskLevel.IMPOSSIBLE
        elif utilization_percent > self.DANGER_THRESHOLD:
            return OOMRiskLevel.CRITICAL
        elif utilization_percent > self.WARNING_THRESHOLD:
            return OOMRiskLevel.DANGER
        elif utilization_percent > self.SAFE_THRESHOLD:
            return OOMRiskLevel.WARNING
        else:
            return OOMRiskLevel.SAFE
    
    def _get_risk_emoji(self, risk_level: OOMRiskLevel) -> str:
        """Get emoji for risk level."""
        emoji_map = {
            OOMRiskLevel.SAFE: "🟢",
            OOMRiskLevel.WARNING: "🟡",
            OOMRiskLevel.DANGER: "🟠",
            OOMRiskLevel.CRITICAL: "🔴",
            OOMRiskLevel.IMPOSSIBLE: "❌",
        }
        return emoji_map.get(risk_level, "❓")
    
    def _get_risk_color(self, risk_level: OOMRiskLevel) -> str:
        """Get Rich color for risk level."""
        color_map = {
            OOMRiskLevel.SAFE: "green",
            OOMRiskLevel.WARNING: "yellow",
            OOMRiskLevel.DANGER: "yellow",
            OOMRiskLevel.CRITICAL: "red",
            OOMRiskLevel.IMPOSSIBLE: "red",
        }
        return color_map.get(risk_level, "white")
    
    def _get_recommendation(
        self,
        risk_level: OOMRiskLevel,
        required_gb: float,
        available_gb: float
    ) -> str:
        """Get recommendation based on risk level."""
        if risk_level == OOMRiskLevel.SAFE:
            return (
                f"Model should run comfortably with {available_gb - required_gb:.1f}GB "
                "headroom for other processes."
            )
        
        elif risk_level == OOMRiskLevel.WARNING:
            return (
                "Model may run but with limited headroom. Consider:\n"
                "• Reducing batch size\n"
                "• Using gradient checkpointing (if training)\n"
                "• Monitoring memory usage closely"
            )
        
        elif risk_level == OOMRiskLevel.DANGER:
            return (
                "High risk of OOM. Strongly recommend:\n"
                "• Reducing batch size to 1\n"
                "• Using INT8 or INT4 quantization\n"
                "• Reducing sequence length\n"
                "• Using memory-efficient attention (e.g., Flash Attention)"
            )
        
        elif risk_level == OOMRiskLevel.CRITICAL:
            overflow = required_gb - available_gb
            return (
                f"Very high OOM risk ({overflow:.1f}GB over budget). Required actions:\n"
                "• Use INT4 quantization\n"
                "• Reduce sequence length significantly\n"
                "• Consider model sharding or offloading\n"
                "• Use a smaller model variant"
            )
        
        else:  # IMPOSSIBLE
            overflow = required_gb - available_gb
            return (
                f"Model cannot fit ({overflow:.1f}GB over budget). You must:\n"
                "• Use aggressive quantization (INT4/NF4)\n"
                "• Use model sharding across multiple GPUs\n"
                "• Use CPU offloading\n"
                "• Switch to a smaller model\n"
                "• Upgrade GPU hardware"
            )
    
    def get_gpu_recommendations(self, required_memory_gb: float) -> list[str]:
        """
        Get GPU recommendations for required memory.
        
        Args:
            required_memory_gb: Required memory in GB
            
        Returns:
            List of suitable GPU models
        """
        recommendations = []
        
        # Consumer GPUs
        if required_memory_gb <= 8:
            recommendations.extend([
                "NVIDIA RTX 3070 (8GB)",
                "NVIDIA RTX 4060 Ti (8GB)",
                "AMD RX 7600 XT (16GB)",
            ])
        
        if required_memory_gb <= 12:
            recommendations.extend([
                "NVIDIA RTX 3060 (12GB)",
                "NVIDIA RTX 4070 (12GB)",
            ])
        
        if required_memory_gb <= 16:
            recommendations.extend([
                "NVIDIA RTX 4070 Ti (16GB)",
                "AMD RX 7900 XT (20GB)",
            ])
        
        if required_memory_gb <= 24:
            recommendations.extend([
                "NVIDIA RTX 3090 (24GB)",
                "NVIDIA RTX 4090 (24GB)",
                "AMD RX 7900 XTX (24GB)",
            ])
        
        # Datacenter GPUs
        if required_memory_gb <= 40:
            recommendations.extend([
                "NVIDIA A100 40GB",
                "NVIDIA A6000 (48GB)",
            ])
        
        if required_memory_gb <= 80:
            recommendations.extend([
                "NVIDIA A100 80GB",
                "NVIDIA H100 (80GB)",
            ])
        
        if required_memory_gb > 80:
            recommendations.extend([
                "Multiple GPUs with model sharding",
                "NVIDIA H100 (80GB) with offloading",
            ])
        
        return recommendations
    
    def suggest_optimizations(
        self,
        current_memory_gb: float,
        target_memory_gb: float,
        current_batch_size: int = 1,
        current_seq_length: int = 2048,
        current_quantization: str = "fp16"
    ) -> list[str]:
        """
        Suggest optimizations to reduce memory usage.
        
        Args:
            current_memory_gb: Current memory requirement
            target_memory_gb: Target memory budget
            current_batch_size: Current batch size
            current_seq_length: Current sequence length
            current_quantization: Current quantization
            
        Returns:
            List of optimization suggestions
        """
        suggestions = []
        reduction_needed = current_memory_gb - target_memory_gb
        
        if reduction_needed <= 0:
            return ["No optimizations needed - model fits in budget"]
        
        # Quantization suggestions
        if current_quantization.lower() in ('fp32', 'float32'):
            suggestions.append(
                f"• Switch to FP16: ~50% memory reduction (~{current_memory_gb * 0.5:.1f}GB)"
            )
        if current_quantization.lower() in ('fp32', 'float32', 'fp16', 'float16'):
            suggestions.append(
                f"• Switch to INT8: ~75% reduction from FP32 (~{current_memory_gb * 0.25:.1f}GB)"
            )
            suggestions.append(
                f"• Switch to INT4: ~87.5% reduction from FP32 (~{current_memory_gb * 0.125:.1f}GB)"
            )
        
        # Batch size suggestions
        if current_batch_size > 1:
            suggestions.append(
                f"• Reduce batch size from {current_batch_size} to 1: "
                f"~{(1 - 1/current_batch_size) * 100:.0f}% KV cache reduction"
            )
        
        # Sequence length suggestions
        if current_seq_length > 1024:
            new_seq = current_seq_length // 2
            suggestions.append(
                f"• Reduce sequence length from {current_seq_length} to {new_seq}: "
                "~50% KV cache reduction"
            )
        
        # Advanced optimizations
        suggestions.extend([
            "• Enable gradient checkpointing (if training)",
            "• Use Flash Attention for memory-efficient attention",
            "• Enable CPU offloading for less-used layers",
            "• Use model sharding across multiple GPUs",
        ])
        
        return suggestions

# Made with Bob
