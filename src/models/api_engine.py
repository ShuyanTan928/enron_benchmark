"""
OpenAI-compatible API engine for profile analysis and generation.
Supports Google Gemini, OpenRouter, and any OpenAI-compatible endpoint.
Includes automatic retry with exponential backoff for rate limits.
"""
import os
import re
import time
from typing import Union

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Per-model API usage accumulated across a run (exact token counts; `cost` is OpenRouter's own $ if it
# reports one). Read with usage_report() at the end of a run.
_USAGE: dict = {}


def usage_report() -> dict:
    return _USAGE


# Pre-defined API provider configurations.
# Set the matching env vars, then pass the preset name to from_preset().
API_PRESETS = {
    # Google Gemini via OpenAI-compatible endpoint
    "gemini-flash": {
        "model_name": "gemini-2.0-flash",
        "api_key_env": "GOOGLE_API_KEY",
        "base_url_env": "GOOGLE_BASE_URL",
    },
    "gemini-flash-lite": {
        "model_name": "gemini-2.0-flash-lite",
        "api_key_env": "GOOGLE_API_KEY",
        "base_url_env": "GOOGLE_BASE_URL",
    },
    "gemini-pro": {
        "model_name": "gemini-2.5-pro-preview-05-06",
        "api_key_env": "GOOGLE_API_KEY",
        "base_url_env": "GOOGLE_BASE_URL",
    },
    # OpenRouter — set OPENROUTER_API_KEY + OPENROUTER_BASE_URL
    "or-claude-sonnet": {
        "model_name": "anthropic/claude-sonnet-4.6",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
    },
    "or-llama-70b": {
        "model_name": "meta-llama/llama-3.3-70b-instruct",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
    },
    "or-qwen3-235b": {
        "model_name": "qwen/qwen3-235b-a22b",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
    },
    # Cross-vendor REVIEWER models (judge / CHECK / blind-probe — keep ≠ the generator).
    # NOTE: confirm the exact OpenRouter slug for your account before a paid run.
    "or-gpt-5": {
        "model_name": "openai/gpt-5.6-terra",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
    },
    "or-gemini-pro": {
        "model_name": "google/gemini-3-pro",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
    },
}


def list_api_presets() -> str:
    lines = []
    for key, cfg in API_PRESETS.items():
        lines.append(
            f"  {key:<22s}  model={cfg['model_name']}  "
            f"key_env={cfg['api_key_env']}"
        )
    return "\n".join(lines)


class APIEngine:
    def __init__(
        self,
        model_name: str = "gemini-2.0-flash",
        api_key: str | None = None,
        base_url: str | None = None,
        system_prompt: str | None = None,
        max_retries: int = 5,
        retry_base_delay: float = 60.0,
        reasoning: str | None = None,
    ):
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.reasoning = reasoning            # OpenRouter reasoning effort: "low"|"medium"|"high"

        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
        )

    @classmethod
    def from_preset(
        cls,
        preset: str,
        system_prompt: str | None = None,
        **overrides,
    ) -> "APIEngine":
        if preset not in API_PRESETS:
            if "/" in preset:            # raw OpenRouter slug, e.g. "google/gemini-2.5-pro"
                return cls(
                    model_name=overrides.get("model_name", preset),
                    api_key=os.environ.get("OPENROUTER_API_KEY"),
                    base_url=os.environ.get("OPENROUTER_BASE_URL"),
                    system_prompt=system_prompt,
                    reasoning=overrides.get("reasoning"),
                )
            raise ValueError(
                f"Unknown preset '{preset}'. Available presets:\n{list_api_presets()}"
            )
        cfg = API_PRESETS[preset]
        api_key = os.environ.get(cfg["api_key_env"])
        base_url = os.environ.get(cfg["base_url_env"])
        return cls(
            model_name=overrides.get("model_name", cfg["model_name"]),
            api_key=api_key,
            base_url=base_url,
            system_prompt=system_prompt,
            reasoning=overrides.get("reasoning"),
        )

    def _build_messages(self, prompt: str) -> list[dict]:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        messages = self._build_messages(prompt)
        extra = {"reasoning": {"effort": self.reasoning}} if self.reasoning else None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra_body=extra,
                )
                u = getattr(response, "usage", None)
                if u:
                    rec = _USAGE.setdefault(self.model_name, {"calls": 0, "in": 0, "out": 0, "cost": 0.0})
                    rec["calls"] += 1
                    rec["in"] += getattr(u, "prompt_tokens", 0) or 0
                    rec["out"] += getattr(u, "completion_tokens", 0) or 0
                    rec["cost"] += float(getattr(u, "cost", 0) or 0)   # OpenRouter reports $ here
                return (response.choices[0].message.content or "").strip()
            except Exception as e:
                err = str(e)
                is_rate_limit = (
                    "429" in err
                    or "RESOURCE_EXHAUSTED" in err
                    or "RateLimitError" in type(e).__name__
                )
                if is_rate_limit:
                    match = re.search(r"retry in (\d+\.?\d*)", err, re.IGNORECASE)
                    wait = float(match.group(1)) + 5 if match else self.retry_base_delay * (attempt + 1)
                    print(f"    [Rate limit] Waiting {wait:.0f}s before retry {attempt+1}/{self.max_retries}...")
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError(
            f"API call failed after {self.max_retries} retries for model {self.model_name}"
        )

    def generate(
        self,
        prompts: Union[str, list[str]],
        max_tokens: int = 1024,
        temperature: float = 0.2,
        **kwargs,
    ) -> list[str]:
        if isinstance(prompts, str):
            prompts = [prompts]
        return [self._call_api(p, max_tokens, temperature) for p in prompts]
