"""
VRAM estimation command for env-doctor CLI.

Estimates VRAM requirements for ML models based on model size, runtime, and configuration.
Uses HuggingFace Hub integration for accurate model architecture details.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from env_doctor.vram import (
    ModelFetcher,
    GPUDetector,
    WeightCalculator,
    KVCacheEstimator,
    OOMDetector,
    RuntimeProfileManager,
)

console = Console()


def estimate_vram(
    model: str = typer.Option(..., "--model", help="HuggingFace model ID (e.g., meta-llama/Llama-2-7b-hf)"),
    config_file: Optional[Path] = typer.Option(None, "--config", help="Local config.json file to use for architecture"),
    runtime: str = typer.Option("transformers", "--runtime", help="Runtime: transformers, vllm, tgi, etc."),
    quantization: Optional[str] = typer.Option(None, "--quant", help="Quantization: fp16, int8, int4, etc."),
    batch_size: int = typer.Option(1, "--batch", help="Batch size"),
    seq_length: int = typer.Option(2048, "--seq-len", help="Sequence length"),
    gpu: Optional[int] = typer.Option(None, "--gpu", help="Target GPU index (default: auto-detect best)"),
    show_gpus: bool = typer.Option(False, "--show-gpus", help="Show available GPUs and exit"),
) -> None:
    """
    Estimate VRAM requirements for a model.
    
    Calculates memory requirements for running ML models based on model parameters,
    runtime overhead, quantization, and inference configuration. Helps determine
    if a model will fit in available GPU memory.
    
    Examples:
        env-doctor vram --model meta-llama/Llama-2-7b-hf
        env-doctor vram --model custom-model --config ./config.json
        env-doctor vram --model gpt2 --runtime vllm --quant int8
        env-doctor vram --model bert-base-uncased --batch 32 --seq-len 512
        env-doctor vram --show-gpus
    """
    try:
        # Show GPUs if requested
        if show_gpus:
            _show_available_gpus()
            return
        
        console.print(f"[bold blue]Estimating VRAM for:[/bold blue] {model}")
        if config_file:
            console.print(f"[dim]Using local config: {config_file}[/dim]")
        console.print()
        
        # Initialize components
        model_fetcher = ModelFetcher()
        gpu_detector = GPUDetector()
        
        # Fetch model architecture
        arch = None
        from env_doctor.vram.model_fetcher import GatedModelError, ModelNotFoundError, ModelFetcherError
        
        try:
            if config_file:
                with console.status("[bold blue]Loading local config...[/bold blue]"):
                    arch = model_fetcher.fetch_model_info_from_file(config_file)
            
            if not arch:
                with console.status("[bold blue]Fetching model information...[/bold blue]"):
                    arch = model_fetcher.fetch_model_info(model)
        except GatedModelError:
            console.print(
                Panel(
                    f"[yellow]Model '{model}' is gated or private.[/yellow]\n\n"
                    "To access this model, please:\n"
                    "1. Request access on the HuggingFace Hub page\n"
                    "2. Set the [bold]HF_TOKEN[/bold] environment variable\n"
                    "3. Or provide a local config with [bold]--config[/bold]",
                    title="🔓 Gated Model",
                    border_style="yellow"
                )
            )
            raise typer.Exit(code=1)
        except ModelNotFoundError:
            console.print(
                Panel(
                    f"[red]Model '{model}' was not found on HuggingFace Hub.[/red]\n\n"
                    "Please verify the model ID is correct.",
                    title="❌ Not Found",
                    border_style="red"
                )
            )
            raise typer.Exit(code=1)
        except ModelFetcherError as e:
            console.print(f"[bold red]Error fetching model:[/bold red] {e}")
            raise typer.Exit(code=1)
        
        if not arch:
            console.print(
                Panel(
                    "[yellow]Could not extract architecture from config.json.[/yellow]\n\n"
                    "The configuration file might be missing required fields (hidden_size, num_layers, etc.).",
                    title="⚠️  Invalid Config",
                    border_style="yellow"
                )
            )
            raise typer.Exit(code=1)
        
        console.print(f"[dim]Model: {arch.model_id}[/dim]")
        console.print(f"[dim]Architecture: {arch.model_type or 'unknown'}[/dim]")
        console.print(f"[dim]Parameters: {arch.param_count / 1e9:.2f}B[/dim]")
        console.print(f"[dim]Hidden size: {arch.hidden_size}, Layers: {arch.num_layers}[/dim]")
        console.print()
        
        # Load runtime profile
        profiles_path = Path(__file__).parent.parent / "vram" / "runtime_profiles.yaml"
        profile_manager = RuntimeProfileManager(profiles_path)
        profile = profile_manager.get_profile_or_default(runtime)
        
        console.print(f"[dim]Runtime: {profile.name} ({profile.description})[/dim]")
        console.print()
        
        # Calculate weight memory
        quant = quantization or "fp16"
        weight_calc = WeightCalculator(quantization=quant)
        weight_memory = weight_calc.calculate_weight_memory(arch)
        
        # Calculate KV cache memory
        kv_estimator = KVCacheEstimator(
            batch_size=batch_size,
            sequence_length=seq_length,
            bytes_per_element=2.0,  # FP16 for activations
            runtime_multiplier=profile.kv_overhead_multiplier
        )
        kv_memory = kv_estimator.estimate_kv_cache(arch)
        
        # Calculate total memory with fragmentation
        base_memory_gb = weight_memory.total_memory_gb + kv_memory.total_memory_gb
        total_memory_gb = base_memory_gb * profile.fragmentation_multiplier
        fragmentation_gb = total_memory_gb - base_memory_gb
        
        # Display memory breakdown
        table = Table(title="VRAM Estimation Breakdown", show_header=True, header_style="bold cyan")
        table.add_column("Component", style="cyan")
        table.add_column("Memory (GB)", justify="right", style="green")
        table.add_column("Details", style="dim")
        
        table.add_row(
            "Model Weights",
            f"{weight_memory.total_memory_gb:.2f}",
            f"{arch.param_count / 1e9:.2f}B params × {weight_calc.bytes_per_param} bytes ({weight_calc.get_quantization_label()})"
        )
        table.add_row(
            "  ├─ Embeddings",
            f"{weight_memory.embedding_memory_gb:.2f}",
            f"vocab_size={arch.vocab_size}"
        )
        table.add_row(
            "  ├─ Attention",
            f"{weight_memory.attention_memory_gb:.2f}",
            f"{arch.num_layers} layers"
        )
        table.add_row(
            "  └─ FFN",
            f"{weight_memory.ffn_memory_gb:.2f}",
            f"intermediate_size={arch.intermediate_size or 'estimated'}"
        )
        table.add_row(
            "KV Cache",
            f"{kv_memory.total_memory_gb:.2f}",
            f"batch={batch_size}, seq_len={seq_length}"
        )
        table.add_row(
            "  ├─ Keys",
            f"{kv_memory.key_cache_gb:.2f}",
            f"{arch.num_layers} layers"
        )
        table.add_row(
            "  ├─ Values",
            f"{kv_memory.value_cache_gb:.2f}",
            f"{arch.num_layers} layers"
        )
        table.add_row(
            "  └─ Runtime Overhead",
            f"{kv_memory.overhead_gb:.2f}",
            f"{profile.kv_overhead_multiplier}x multiplier"
        )
        table.add_row(
            "Fragmentation",
            f"{fragmentation_gb:.2f}",
            f"{profile.fragmentation_multiplier}x overhead"
        )
        table.add_row(
            "[bold]Total Required[/bold]",
            f"[bold]{total_memory_gb:.2f}[/bold]",
            ""
        )
        
        console.print(table)
        console.print()
        
        # Detect available GPUs
        gpus = gpu_detector.detect_gpus()
        
        if gpus:
            # Select target GPU
            if gpu is not None and 0 <= gpu < len(gpus):
                target_gpu = gpus[gpu]
            else:
                target_gpu = gpu_detector.get_recommended_gpu(total_memory_gb)
            
            if target_gpu:
                console.print(f"[bold cyan]Target GPU:[/bold cyan] {target_gpu.name} (GPU {target_gpu.index})")
                console.print(f"[dim]Total VRAM: {target_gpu.total_memory_gb:.1f}GB, "
                            f"Free: {target_gpu.free_memory_gb:.1f}GB, "
                            f"Used: {target_gpu.used_memory_gb:.1f}GB[/dim]")
                console.print()
                
                # Assess OOM risk
                oom_detector = OOMDetector(fragmentation_multiplier=1.0)  # Already applied
                risk = oom_detector.assess_risk(
                    required_memory_gb=total_memory_gb,
                    available_memory_gb=target_gpu.total_memory_gb,
                    apply_fragmentation=False
                )
                
                # Display risk assessment
                console.print(
                    Panel(
                        f"[bold]OOM Risk:[/bold] {risk.risk_emoji} {risk.risk_level.value.upper()}\n"
                        f"[bold]Utilization:[/bold] {risk.utilization_percent:.1f}%\n\n"
                        f"{risk.recommendation}",
                        title="💡 Risk Assessment",
                        border_style=risk.risk_color
                    )
                )
                
                # Show optimization suggestions if needed
                if not risk.can_fit or risk.utilization_percent > 70:
                    console.print()
                    console.print("[bold cyan]Optimization Suggestions:[/bold cyan]")
                    suggestions = oom_detector.suggest_optimizations(
                        current_memory_gb=total_memory_gb,
                        target_memory_gb=target_gpu.total_memory_gb * 0.7,  # Target 70% utilization
                        current_batch_size=batch_size,
                        current_seq_length=seq_length,
                        current_quantization=quant
                    )
                    for suggestion in suggestions[:5]:  # Show top 5
                        console.print(f"  {suggestion}")
                
                # Show GPU recommendations if model doesn't fit
                if not risk.can_fit:
                    console.print()
                    console.print("[bold cyan]Recommended GPUs:[/bold cyan]")
                    gpu_recs = oom_detector.get_gpu_recommendations(total_memory_gb)
                    for rec in gpu_recs[:5]:  # Show top 5
                        console.print(f"  • {rec}")
        else:
            console.print("[yellow]No GPUs detected. Showing theoretical requirements only.[/yellow]")
            console.print()
            
            # Show generic recommendations
            oom_detector = OOMDetector()
            gpu_recs = oom_detector.get_gpu_recommendations(total_memory_gb)
            
            console.print("[bold cyan]Recommended GPUs:[/bold cyan]")
            for rec in gpu_recs[:5]:
                console.print(f"  • {rec}")
        
        console.print()
        
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Estimation cancelled by user[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1)


def _show_available_gpus() -> None:
    """Show available GPUs and their specifications."""
    gpu_detector = GPUDetector()
    gpus = gpu_detector.detect_gpus()
    
    if not gpus:
        console.print("[yellow]No GPUs detected.[/yellow]")
        console.print()
        console.print("Make sure you have:")
        console.print("  • NVIDIA GPU installed")
        console.print("  • NVIDIA drivers installed")
        console.print("  • nvidia-smi accessible in PATH")
        return
    
    console.print(f"[bold green]Found {len(gpus)} GPU(s):[/bold green]")
    console.print()
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Index", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Total VRAM", justify="right")
    table.add_column("Free VRAM", justify="right")
    table.add_column("Used VRAM", justify="right")
    table.add_column("Utilization", justify="right")
    
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
    console.print()
    
    if gpus[0].driver_version:
        console.print(f"[dim]Driver Version: {gpus[0].driver_version}[/dim]")
    if gpus[0].cuda_version:
        console.print(f"[dim]CUDA Version: {gpus[0].cuda_version}[/dim]")


# Made with Bob