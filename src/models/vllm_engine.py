"""
vLLM inference engine for local model deployment.
Mirrors the interface of APIEngine so callers are engine-agnostic.
"""
import re

from transformers import AutoTokenizer
from vllm import LLM, SamplingParams


PHI4_REASONING_SYSTEM_PROMPT = (
    "You are Phi, a language model trained by Microsoft to help users. "
    "Your role as an assistant involves thoroughly exploring questions through "
    "a systematic thinking process before providing the final precise and "
    "accurate solutions. This requires engaging in a comprehensive cycle of "
    "analysis, summarizing, exploration, reassessment, reflection, backtracing, "
    "and iteration to develop well-considered thinking process. Please structure "
    "your response into two main sections: Thought and Solution using the "
    "specified format: <think> {Thought section} </think> {Solution section}. "
    "In the Thought section, detail your reasoning process in steps. In the "
    "Solution section, present the final solution that you deem correct. "
    "Now, try to solve the following question through the above guidelines:"
)

MODEL_CONFIGS = {
    # ── Qwen3 family ──────────────────────────────────────────────────────────
    "qwen3-14b": {
        "model_name": "Qwen/Qwen3-14B",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    "qwen3-32b": {
        "model_name": "Qwen/Qwen3-32B",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    "qwen3-32b-4bit": {
        "model_name": "JunHowie/Qwen3-32B-GPTQ-Int4",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": "gptq_marlin",
    },
    "qwen3-235b-4bit": {
        "model_name": "Qwen/Qwen3-235B-A22B-GPTQ-Int4",
        "tensor_parallel_size": 2,
        "max_model_len": 32768,
        "quantization": "gptq_marlin",
    },
    "qwen3-235b-fp8": {
        "model_name": "Qwen/Qwen3-235B-A22B-FP8",
        "tensor_parallel_size": 4,
        "max_model_len": 32768,
        "quantization": "fp8",
    },
    # ── Qwen3.5 family (released Feb 2026, 262K native context) ──────────────
    "qwen3.5-4b": {
        "model_name": "Qwen/Qwen3.5-4B",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    "qwen3.5-9b": {
        "model_name": "Qwen/Qwen3.5-9B",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    "qwen3.5-27b": {
        # ~54 GB fp16 — fits on 1× A100 80 GB; use tp=2 override on A800 40 GB
        "model_name": "Qwen/Qwen3.5-27B",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    # ── Qwen3.6 family (released Apr 2026, 262K native context) ──────────────
    "qwen3.6-27b": {
        # ~54 GB fp16 — fits on 1× A100 80 GB
        "model_name": "Qwen/Qwen3.6-27B",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    "qwen3.6-35b-a3b": {
        # MoE: 35B total params (~70 GB fp16) — requires 2 GPUs
        "model_name": "Qwen/Qwen3.6-35B-A3B",
        "tensor_parallel_size": 2,
        "max_model_len": 32768,
        "quantization": None,
    },
    # ── Gemma 3 family ────────────────────────────────────────────────────────
    "gemma3-4b": {
        "model_name": "google/gemma-3-4b-it",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    "gemma3-27b": {
        "model_name": "google/gemma-3-27b-it",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    "gemma3-12b": {
        "model_name": "google/gemma-3-12b-it",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    # ── Gemma 4 family (released Apr 2026, 256K context) ─────────────────────
    "gemma4-e4b": {
        # Edge 4B — for quick pipeline tests; already cached
        "model_name": "google/gemma-4-E4B-it",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    "gemma4-31b": {
        # Dense 31B (~62 GB fp16) — fits on 1× A100 80 GB; use tp=2 for more KV cache headroom
        "model_name": "google/gemma-4-31B-it",
        "tensor_parallel_size": 2,
        "max_model_len": 32768,
        "quantization": None,
    },
    "gemma4-26b": {
        # MoE: 26B total / 4B active (~52 GB fp16) — fits on 1× A100 80 GB
        "model_name": "google/gemma-4-26B-A4B-it",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
    },
    # ── Llama 4 Maverick ──────────────────────────────────────────────────────
    "llama4-maverick-fp8": {
        "model_name": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "tensor_parallel_size": 4,
        "max_model_len": 32768,
        "quantization": "fp8",
    },
    # ── GPT-oss (reasoning models) ────────────────────────────────────────────
    "gpt-oss-20b": {
        "model_name": "openai/gpt-oss-20b",
        "tensor_parallel_size": 4,
        "max_model_len": 131072,
        "quantization": None,
        "is_reasoning": True,
        "reasoning_format": "gptoss",
    },
    "gpt-oss-120b": {
        "model_name": "openai/GPT-oss-120B",
        "tensor_parallel_size": 4,
        "max_model_len": 131072,
        "quantization": None,
        "is_reasoning": True,
        "reasoning_format": "gptoss",
    },
    # ── Phi-4 reasoning plus ──────────────────────────────────────────────────
    "phi4-reasoning-plus": {
        "model_name": "microsoft/Phi-4-reasoning-plus",
        "tensor_parallel_size": 1,
        "max_model_len": 32768,
        "quantization": None,
        "is_reasoning": True,
        "reasoning_format": "phi4",
        "system_prompt": PHI4_REASONING_SYSTEM_PROMPT,
        "sampling": {"temperature": 0.8, "top_p": 0.95, "top_k": 50},
    },
}


def list_presets() -> str:
    lines = []
    for key, cfg in MODEL_CONFIGS.items():
        q = cfg.get("quantization") or "none"
        r = " [reasoning]" if cfg.get("is_reasoning") else ""
        lines.append(
            f"  {key:<25s} tp={cfg['tensor_parallel_size']}  "
            f"quant={q:<15s} {cfg['model_name']}{r}"
        )
    return "\n".join(lines)


class VLLMEngine:
    def __init__(
        self,
        model_name: str,
        tensor_parallel_size: int = 1,
        max_model_len: int = 32768,
        gpu_memory_utilization: float = 0.9,
        enable_thinking: bool = False,
        quantization: str | None = None,
        is_reasoning: bool = False,
        reasoning_format: str | None = None,
        system_prompt: str | None = None,
        default_sampling: dict | None = None,
        rng_seed: int | None = None,
    ):
        self.model_name = model_name
        self.max_model_len = max_model_len
        self.enable_thinking = enable_thinking
        self.is_reasoning = is_reasoning
        self.reasoning_format = reasoning_format
        self.system_prompt = system_prompt
        self.default_sampling = default_sampling or {}
        # If set, every generate() call uses (rng_seed + call_counter) as the
        # SamplingParams seed, so successive calls are still varied but the
        # *run* is reproducible. Leave None to inherit vLLM's default
        # deterministic behaviour.
        self.rng_seed = rng_seed
        self._call_counter = 0

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        llm_kwargs = dict(
            model=model_name,
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
        )
        if quantization:
            llm_kwargs["quantization"] = quantization

        self.llm = LLM(**llm_kwargs)

    @classmethod
    def from_preset(
        cls,
        preset: str,
        gpu_memory_utilization: float = 0.9,
        enable_thinking: bool = False,
        rng_seed: int | None = None,
        **overrides,
    ) -> "VLLMEngine":
        if preset not in MODEL_CONFIGS:
            raise ValueError(
                f"Unknown preset '{preset}'. Available presets:\n{list_presets()}"
            )
        config = {**MODEL_CONFIGS[preset], **overrides}
        return cls(
            model_name=config["model_name"],
            tensor_parallel_size=config["tensor_parallel_size"],
            max_model_len=config["max_model_len"],
            gpu_memory_utilization=gpu_memory_utilization,
            enable_thinking=enable_thinking,
            quantization=config.get("quantization"),
            is_reasoning=config.get("is_reasoning", False),
            reasoning_format=config.get("reasoning_format"),
            system_prompt=config.get("system_prompt"),
            default_sampling=config.get("sampling"),
            rng_seed=rng_seed,
        )

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def _apply_chat_template(self, prompt: str) -> str:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self.is_reasoning:
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        return self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=self.enable_thinking,
        )

    @staticmethod
    def _strip_thinking(text: str) -> str:
        match = re.search(r"</think>\s*(.*)", text, flags=re.DOTALL)
        if match and match.group(1).strip():
            return match.group(1).strip()
        stripped = re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip()
        return stripped or ""

    @staticmethod
    def _strip_gptoss(text: str) -> str:
        match = re.search(r"assistantfinal\s*(.*)", text, flags=re.DOTALL)
        if match and match.group(1).strip():
            return match.group(1).strip()
        return text

    def _clean_output(self, text: str) -> str:
        if not self.is_reasoning:
            return text
        if self.reasoning_format == "gptoss":
            return self._strip_gptoss(text)
        if self.reasoning_format == "phi4":
            clean = self._strip_thinking(text)
            return clean if clean else text
        return text

    def generate(
        self,
        prompts: str | list[str],
        max_tokens: int = 1024,
        temperature: float = 0.2,
        top_p: float = 1.0,
        top_k: int = -1,
        stop: list[str] | None = None,
        **kwargs,
    ) -> list[str]:
        if isinstance(prompts, str):
            prompts = [prompts]

        formatted = [self._apply_chat_template(p) for p in prompts]

        if self.is_reasoning and max_tokens < 16384:
            max_tokens = 16384

        final_temp = self.default_sampling.get("temperature", temperature)
        final_top_p = self.default_sampling.get("top_p", top_p)
        final_top_k = self.default_sampling.get("top_k", top_k)
        if temperature != 0.0:
            final_temp = temperature

        if self.enable_thinking and not self.is_reasoning and temperature == 0.0:
            final_temp, final_top_p, final_top_k = 0.6, 0.95, 20

        sampling_kwargs = dict(
            max_tokens=max_tokens,
            temperature=final_temp,
            top_p=final_top_p,
            top_k=final_top_k,
            stop=stop,
        )
        if self.rng_seed is not None:
            sampling_kwargs["seed"] = self.rng_seed + self._call_counter
            self._call_counter += 1
        params = SamplingParams(**sampling_kwargs)
        outputs = self.llm.generate(formatted, params, use_tqdm=True)

        results = []
        for out in outputs:
            text = out.outputs[0].text
            if self.is_reasoning:
                text = self._clean_output(text)
            results.append(text)
        return results
