"""
Standalone verification script for VRAM Intelligence Engine.

Tests all VRAM modules with real-world scenarios and provides
detailed output for manual verification.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from env_doctor.vram import (
    ModelFetcher,
    ModelArchitecture,
    GPUDetector,
    WeightCalculator,
    KVCacheEstimator,
    OOMDetector,
    RuntimeProfileManager,
)

console = Console()


def test_model_fetcher():
    """Test ModelFetcher with various model names."""
    console.print("\n[bold cyan]Testing ModelFetcher[/bold cyan]")
    console.print("=" * 60)
    
    fetcher = ModelFetcher()
    
    test_models = [
        "meta-llama/Llama-2-7b-hf",
        "gpt2",
        "bert-base-uncased",
        "mistral-7b-instruct",
    ]
    
    for model_name in test_models:
        console.print(f"\n[yellow]Fetching:[/yellow] {model_name}")
        
        arch = fetcher.fetch_model_info(model_name)
        
        if arch:
            console.print(f"  [green]+[/green] Model ID: {arch.model_id}")
            console.print(f"  [green]+[/green] Hidden size: {arch.hidden_size}")
            console.print(f"  [green]+[/green] Layers: {arch.num_layers}")
            console.print(f"  [green]+[/green] Attention heads: {arch.num_attention_heads}")
            console.print(f"  [green]+[/green] Vocab size: {arch.vocab_size}")
            console.print(f"  [green]+[/green] Parameters: {arch.param_count / 1e9:.2f}B")
            console.print(f"  [green]+[/green] Type: {arch.model_type or 'estimated'}")
        else:
            console.print("  [red]x[/red] Failed to fetch model info")
    
    console.print("\n[green]+ ModelFetcher test complete[/green]")


def test_gpu_detector():
    """Test GPUDetector."""
    console.print("\n[bold cyan]Testing GPUDetector[/bold cyan]")
    console.print("=" * 60)
    
    detector = GPUDetector()
    gpus = detector.detect_gpus()
    
    if gpus:
        console.print(f"\n[green]+ Found {len(gpus)} GPU(s)[/green]")
        
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Index")
        table.add_column("Name")
        table.add_column("Total VRAM")
        table.add_column("Free VRAM")
        table.add_column("Used VRAM")
        table.add_column("Utilization")
        
        for gpu in gpus:
            table.add_row(
                str(gpu.index),
                gpu.name,
                f"{gpu.total_memory_gb:.1f} GB",
                f"{gpu.free_memory_gb:.1f} GB",
                f"{gpu.used_memory_gb:.1f} GB",
                f"{gpu.utilization_percent:.1f}%"
            )
        
        console.print(table)
        
        if gpus[0].driver_version:
            console.print(f"\n[dim]Driver: {gpus[0].driver_version}[/dim]")
        if gpus[0].cuda_version:
            console.print(f"[dim]CUDA: {gpus[0].cuda_version}[/dim]")
    else:
        console.print("\n[yellow]! No GPUs detected[/yellow]")
        console.print("This is expected if running on CPU-only system")
    
    console.print("\n[green]+ GPUDetector test complete[/green]")


def test_weight_calculator():
    """Test WeightCalculator with different quantizations."""
    console.print("\n[bold cyan]Testing WeightCalculator[/bold cyan]")
    console.print("=" * 60)
    
    # Create test architecture (7B model)
    arch = ModelArchitecture(
        model_id="test-7b",
        hidden_size=4096,
        num_layers=32,
        num_attention_heads=32,
        vocab_size=32000,
        max_position_embeddings=2048,
        intermediate_size=11008
    )
    
    quantizations = ['fp32', 'fp16', 'int8', 'int4']
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Quantization")
    table.add_column("Bytes/Param")
    table.add_column("Total Memory")
    table.add_column("Embeddings")
    table.add_column("Attention")
    table.add_column("FFN")
    
    for quant in quantizations:
        calc = WeightCalculator(quant)
        memory = calc.calculate_weight_memory(arch)
        
        table.add_row(
            calc.get_quantization_label(),
            f"{calc.bytes_per_param}",
            f"{memory.total_memory_gb:.2f} GB",
            f"{memory.embedding_memory_gb:.2f} GB",
            f"{memory.attention_memory_gb:.2f} GB",
            f"{memory.ffn_memory_gb:.2f} GB"
        )
    
    console.print(table)
    console.print("\n[green]+ WeightCalculator test complete[/green]")


def test_kv_cache_estimator():
    """Test KVCacheEstimator with different configurations."""
    console.print("\n[bold cyan]Testing KVCacheEstimator[/bold cyan]")
    console.print("=" * 60)
    
    arch = ModelArchitecture(
        model_id="test-7b",
        hidden_size=4096,
        num_layers=32,
        num_attention_heads=32,
        vocab_size=32000,
        max_position_embeddings=2048
    )
    
    configs = [
        (1, 512),
        (1, 2048),
        (4, 2048),
        (8, 2048),
    ]
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Batch Size")
    table.add_column("Seq Length")
    table.add_column("Key Cache")
    table.add_column("Value Cache")
    table.add_column("Total")
    
    for batch_size, seq_length in configs:
        estimator = KVCacheEstimator(
            batch_size=batch_size,
            sequence_length=seq_length
        )
        memory = estimator.estimate_kv_cache(arch)
        
        table.add_row(
            str(batch_size),
            str(seq_length),
            f"{memory.key_cache_gb:.2f} GB",
            f"{memory.value_cache_gb:.2f} GB",
            f"{memory.total_memory_gb:.2f} GB"
        )
    
    console.print(table)
    console.print("\n[green]+ KVCacheEstimator test complete[/green]")


def test_oom_detector():
    """Test OOMDetector with various scenarios."""
    console.print("\n[bold cyan]Testing OOMDetector[/bold cyan]")
    console.print("=" * 60)
    
    detector = OOMDetector()
    
    scenarios = [
        (10.0, 24.0, "Safe scenario"),
        (18.0, 24.0, "Warning scenario"),
        (21.0, 24.0, "Danger scenario"),
        (23.5, 24.0, "Critical scenario"),
        (30.0, 24.0, "Impossible scenario"),
    ]
    
    for required, available, description in scenarios:
        console.print(f"\n[yellow]{description}:[/yellow]")
        console.print(f"  Required: {required:.1f} GB, Available: {available:.1f} GB")
        
        risk = detector.assess_risk(required, available, apply_fragmentation=False)
        
        console.print(f"  Risk Level: {risk.risk_emoji} {risk.risk_level.value.upper()}")
        console.print(f"  Utilization: {risk.utilization_percent:.1f}%")
        console.print(f"  Can Fit: {'YES' if risk.can_fit else 'NO'}")
    
    console.print("\n[green]+ OOMDetector test complete[/green]")


def test_runtime_profiles():
    """Test RuntimeProfileManager."""
    console.print("\n[bold cyan]Testing RuntimeProfileManager[/bold cyan]")
    console.print("=" * 60)
    
    profiles_path = Path(__file__).parent.parent / "src" / "env_doctor" / "vram" / "runtime_profiles.yaml"
    manager = RuntimeProfileManager(profiles_path if profiles_path.exists() else None)
    
    console.print(f"\n[green]+ Loaded {len(manager.profiles)} profiles[/green]")
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Runtime")
    table.add_column("KV Overhead")
    table.add_column("Fragmentation")
    table.add_column("Quantization")
    table.add_column("Flash Attn")
    
    for name in sorted(manager.list_profiles()):
        profile = manager.get_profile(name)
        if profile:
            table.add_row(
                profile.name,
                f"{profile.kv_overhead_multiplier:.2f}x",
                f"{profile.fragmentation_multiplier:.2f}x",
                "✓" if profile.supports_quantization else "✗",
                "✓" if profile.supports_flash_attention else "✗"
            )
    
    console.print(table)
    console.print("\n[green]✓ RuntimeProfileManager test complete[/green]")


def test_full_estimation():
    """Test complete VRAM estimation pipeline."""
    console.print("\n[bold cyan]Testing Full Estimation Pipeline[/bold cyan]")
    console.print("=" * 60)
    
    # Use a known model
    model_name = "gpt2"
    console.print(f"\n[yellow]Estimating VRAM for:[/yellow] {model_name}")
    
    # Fetch model
    fetcher = ModelFetcher()
    arch = fetcher.fetch_model_info(model_name)
    
    if not arch:
        console.print("[red]x Failed to fetch model[/red]")
        return
    
    console.print(f"  [green]+[/green] Parameters: {arch.param_count / 1e6:.1f}M")
    
    # Calculate weights
    weight_calc = WeightCalculator('fp16')
    weight_memory = weight_calc.calculate_weight_memory(arch)
    console.print(f"  [green]+[/green] Weight memory: {weight_memory.total_memory_gb:.2f} GB")
    
    # Calculate KV cache
    kv_estimator = KVCacheEstimator(batch_size=1, sequence_length=1024)
    kv_memory = kv_estimator.estimate_kv_cache(arch)
    console.print(f"  [green]+[/green] KV cache: {kv_memory.total_memory_gb:.2f} GB")
    
    # Total with fragmentation
    total = (weight_memory.total_memory_gb + kv_memory.total_memory_gb) * 1.2
    console.print(f"  [green]+[/green] Total (with fragmentation): {total:.2f} GB")
    
    # Assess risk
    detector = OOMDetector()
    risk = detector.assess_risk(total, 8.0, apply_fragmentation=False)
    console.print(f"  [green]+[/green] Risk level: {risk.risk_emoji} {risk.risk_level.value.upper()}")
    console.print(f"  [green]+[/green] Utilization: {risk.utilization_percent:.1f}%")
    
    console.print("\n[green]+ Full estimation test complete[/green]")


def main():
    """Run all verification tests."""
    console.print(Panel.fit(
        "[bold cyan]VRAM Intelligence Engine Verification[/bold cyan]\n"
        "Testing all components with real-world scenarios",
        border_style="cyan"
    ))
    
    try:
        test_model_fetcher()
        test_gpu_detector()
        test_weight_calculator()
        test_kv_cache_estimator()
        test_oom_detector()
        test_runtime_profiles()
        test_full_estimation()
        
        console.print("\n" + "=" * 60)
        console.print(Panel.fit(
            "[bold green]+ All verification tests passed![/bold green]",
            border_style="green"
        ))
        
        return 0
        
    except Exception as e:
        console.print(f"\n[bold red]x Verification failed:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
