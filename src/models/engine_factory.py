"""One place to build a generation / judge engine — local (vLLM) or closed API.

Keeps every Step-N runner's `--engine/--preset` flags identical, and lets generation run on a
pinned closed model (reproducible) while a *different* model does the review (separation of
duties). vLLM is lazy-imported, so an API-only run needs no GPU / torch.

    from src.models.engine_factory import build_engine
    gen = build_engine("api",  "or-claude-sonnet")          # closed, reproducible
    jud = build_engine("api",  "or-gpt-5")                   # cross-vendor reviewer
    loc = build_engine("vllm", "gemma4-31b", tp=2)          # local

Any returned engine exposes `.generate(prompt, max_tokens=, temperature=) -> list[str]`.
"""
from __future__ import annotations

DEFAULT_SEED = 20260620


def build_engine(kind: str, preset: str, tp: int = 2,
                 seed: int = DEFAULT_SEED, gpu_mem: float = 0.9):
    """kind='vllm' → local tensor-parallel VLLMEngine; kind='api' → APIEngine (OpenRouter/
    Gemini preset). `tp`/`seed`/`gpu_mem` apply to vLLM only and are ignored for API."""
    if kind == "vllm":
        from src.models.vllm_engine import VLLMEngine
        return VLLMEngine.from_preset(
            preset, tensor_parallel_size=tp, gpu_memory_utilization=gpu_mem, rng_seed=seed)
    if kind == "api":
        from src.models.api_engine import APIEngine
        return APIEngine.from_preset(preset)
    raise ValueError(f"unknown engine kind {kind!r} (use 'vllm' or 'api')")
