"""
HuggingFace Hub integration for fetching model architecture details.

Queries the HuggingFace Hub API to extract model configuration including
hidden_size, num_layers, num_attention_heads, and other architecture parameters.
Falls back to heuristic estimation if API is unavailable.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass
import time

from huggingface_hub import HfApi, hf_hub_download
try:
    from huggingface_hub.errors import HfHubHTTPError, RepositoryNotFoundError
except ImportError:
    # Fallback for older versions
    from huggingface_hub.utils import HfHubHTTPError, RepositoryNotFoundError  # type: ignore
import httpx


@dataclass
class ModelArchitecture:
    """Model architecture details extracted from HuggingFace Hub."""
    
    model_id: str
    hidden_size: int
    num_layers: int
    num_attention_heads: int
    vocab_size: int
    max_position_embeddings: int
    num_key_value_heads: Optional[int] = None  # For GQA models
    intermediate_size: Optional[int] = None
    model_type: Optional[str] = None
    
    # MoE (Mixture of Experts) fields
    num_experts: Optional[int] = None
    num_experts_per_tok: Optional[int] = None
    moe_intermediate_size: Optional[int] = None
    num_shared_experts: Optional[int] = None

    @property
    def param_count(self) -> float:
        """Estimate parameter count from architecture including MoE and GQA."""
        # 1. Embedding layer: vocab_size * hidden_size
        embedding_params = self.vocab_size * self.hidden_size
        
        # 2. Attention parameters per layer
        # Standard: 4 * hidden^2
        # GQA: Q_proj (hidden^2) + K_proj (hidden*kv_hidden) + V_proj (hidden*kv_hidden) + O_proj (hidden^2)
        head_dim = self.hidden_size // self.num_attention_heads
        num_kv_heads = self.num_key_value_heads or self.num_attention_heads
        
        q_params = self.hidden_size * self.hidden_size
        kv_params = 2 * (self.hidden_size * (num_kv_heads * head_dim))
        o_params = self.hidden_size * self.hidden_size
        attention_params = q_params + kv_params + o_params
        
        # 3. FFN parameters per layer (including MoE)
        intermediate = self.intermediate_size or (4 * self.hidden_size)
        
        if self.num_experts:
            # Mixture of Experts: sum of all routed and shared experts
            # Routed expert params
            moe_inter = self.moe_intermediate_size or intermediate
            routed_params = self.num_experts * (2 * self.hidden_size * moe_inter)
            
            # Shared expert params (if any)
            shared_params = (self.num_shared_experts or 0) * (2 * self.hidden_size * intermediate)
            
            # Gate params (hidden_size * num_experts)
            gate_params = self.hidden_size * self.num_experts
            
            ffn_params = routed_params + shared_params + gate_params
        else:
            # Standard Dense FFN: 2 * hidden * intermediate
            ffn_params = 2 * self.hidden_size * intermediate
        
        # Total parameters: embedding + layers * (attention + ffn)
        total_params = embedding_params + (self.num_layers * (attention_params + ffn_params))
        return float(total_params)


class ModelFetcherError(Exception):
    """Base exception for ModelFetcher."""
    pass


class GatedModelError(ModelFetcherError):
    """Exception raised when a model is gated and access is denied."""
    pass


class ModelNotFoundError(ModelFetcherError):
    """Exception raised when a model is not found on the Hub."""
    pass


class ModelFetcher:
    """Fetches model architecture details from HuggingFace Hub."""
    
    def __init__(self, cache_dir: Optional[Path] = None, token: Optional[str] = None):
        """
        Initialize ModelFetcher.
        
        Args:
            cache_dir: Directory to cache model information
            token: HuggingFace API token for private models
        """
        self.api = HfApi(token=token)
        self.token = token
        self.cache_dir = cache_dir or Path.home() / ".cache" / "env-doctor" / "models"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_model_info_from_file(self, file_path: Path) -> Optional[ModelArchitecture]:
        """
        Fetch model architecture information from a local config.json file.
        
        Args:
            file_path: Path to a local config.json file
            
        Returns:
            ModelArchitecture if successful, None otherwise
        """
        try:
            if not file_path.exists():
                return None
                
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            if config:
                # Use filename stem as model_id
                model_id = f"local-{file_path.parent.name}"
                return self._parse_config(model_id, config)
        except Exception:
            return None
        return None

    def fetch_model_info(self, model_id: str) -> Optional[ModelArchitecture]:
        """
        Fetch model architecture information.
        
        Prioritizes verified config.json data over any other source.
        
        Args:
            model_id: HuggingFace model ID (e.g., "meta-llama/Llama-2-7b-hf")
            
        Returns:
            ModelArchitecture if successful, None otherwise
        """
        # 1. Check local cache for previously verified config
        cached = self._load_from_cache(model_id)
        if cached:
            return cached
        
        # 2. Fetch config.json from HuggingFace Hub (The Source of Truth)
        try:
            config = self._fetch_config_from_hub(model_id)
            if config:
                arch = self._parse_config(model_id, config)
                if arch:
                    self._save_to_cache(model_id, arch)
                    return arch
        except (GatedModelError, ModelNotFoundError):
            raise
        except Exception:
            pass
        
        return None
    
    def _fetch_config_from_hub(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Fetch config.json from HuggingFace Hub."""
        try:
            # Try to download config.json
            config_path = hf_hub_download(
                repo_id=model_id,
                filename="config.json",
                token=self.token,
                cache_dir=str(self.cache_dir / "hub_cache")
            )
            
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except RepositoryNotFoundError:
            raise ModelNotFoundError(f"Model '{model_id}' not found on HuggingFace Hub.")
        except HfHubHTTPError as e:
            if e.response is not None and e.response.status_code in (401, 403):
                raise GatedModelError(f"Model '{model_id}' is gated or private. Access denied.")
            raise ModelFetcherError(f"HTTP error fetching config: {e}")
        except FileNotFoundError:
            # This might happen if repo exists but config.json is missing
            raise ModelFetcherError(f"config.json not found in repository '{model_id}'.")
        except Exception as e:
            raise ModelFetcherError(f"Unexpected error: {e}")
    
    def _parse_config(self, model_id: str, config: Dict[str, Any]) -> Optional[ModelArchitecture]:
        """Parse config.json into ModelArchitecture, handling nested structures."""
        try:
            # 1. Handle multimodal/nested configs
            # Models like Kimi, Llava, etc. often nest the LLM config
            target_config = config
            for key in ["text_config", "llm_config", "model_config"]:
                if key in config and isinstance(config[key], dict):
                    target_config = config[key]
                    break
            
            # 2. Extract common fields
            # Some models use 'd_model' instead of 'hidden_size'
            # Some models use 'num_hidden_layers' instead of 'n_layer'
            hidden_size = target_config.get('hidden_size') or target_config.get('d_model')
            num_layers = (
                target_config.get('num_hidden_layers') or 
                target_config.get('n_layer') or 
                target_config.get('num_layers')
            )
            num_attention_heads = (
                target_config.get('num_attention_heads') or 
                target_config.get('n_head')
            )
            vocab_size = target_config.get('vocab_size')
            
            # Fallback for vocab_size (some multimodal models keep it in top level even with text_config)
            if vocab_size is None:
                vocab_size = config.get('vocab_size')
                
            max_position_embeddings = (
                target_config.get('max_position_embeddings') or 
                target_config.get('n_positions') or 
                target_config.get('max_seq_len') or
                config.get('max_position_embeddings') or
                2048  # Default
            )
            
            # Robust mapping for intermediate_size (FFN)
            intermediate_size = (
                target_config.get('intermediate_size') or 
                target_config.get('ffn_dim') or 
                target_config.get('d_ff') or
                (4 * hidden_size if hidden_size else None)
            )
            
            # 3. MoE Specific fields
            num_experts = (
                target_config.get('num_local_experts') or 
                target_config.get('n_routed_experts') or 
                target_config.get('num_experts')
            )
            num_experts_per_tok = (
                target_config.get('num_experts_per_tok') or 
                target_config.get('n_routed_experts_per_tok') or
                target_config.get('num_selected_experts')
            )
            moe_intermediate_size = target_config.get('moe_intermediate_size')
            num_shared_experts = target_config.get('num_shared_experts') or target_config.get('n_shared_experts')
            
            if not all([hidden_size, num_layers, num_attention_heads, vocab_size]):
                return None
            
            return ModelArchitecture(
                model_id=model_id,
                hidden_size=int(hidden_size),
                num_layers=int(num_layers),
                num_attention_heads=int(num_attention_heads),
                vocab_size=int(vocab_size),
                max_position_embeddings=int(max_position_embeddings),
                num_key_value_heads=target_config.get('num_key_value_heads'),
                intermediate_size=int(intermediate_size) if intermediate_size else None,
                model_type=config.get('model_type') or target_config.get('model_type'),
                num_experts=int(num_experts) if num_experts else None,
                num_experts_per_tok=int(num_experts_per_tok) if num_experts_per_tok else None,
                moe_intermediate_size=int(moe_intermediate_size) if moe_intermediate_size else None,
                num_shared_experts=int(num_shared_experts) if num_shared_experts else None
            )
            
        except (KeyError, ValueError, TypeError):
            return None
    
    def _load_from_cache(self, model_id: str) -> Optional[ModelArchitecture]:
        """Load model info from cache."""
        cache_file = self.cache_dir / f"{model_id.replace('/', '_')}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            # Check if cache is older than 7 days
            if time.time() - cache_file.stat().st_mtime > 7 * 24 * 3600:
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return ModelArchitecture(**data)
        except Exception:
            return None
    
    def _save_to_cache(self, model_id: str, arch: ModelArchitecture) -> None:
        """Save model info to cache."""
        cache_file = self.cache_dir / f"{model_id.replace('/', '_')}.json"
        
        try:
            data = {
                'model_id': arch.model_id,
                'hidden_size': arch.hidden_size,
                'num_layers': arch.num_layers,
                'num_attention_heads': arch.num_attention_heads,
                'vocab_size': arch.vocab_size,
                'max_position_embeddings': arch.max_position_embeddings,
                'num_key_value_heads': arch.num_key_value_heads,
                'intermediate_size': arch.intermediate_size,
                'model_type': arch.model_type,
                'num_experts': arch.num_experts,
                'num_experts_per_tok': arch.num_experts_per_tok,
                'moe_intermediate_size': arch.moe_intermediate_size,
                'num_shared_experts': arch.num_shared_experts,
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Silently fail cache writes

# Made with Bob
