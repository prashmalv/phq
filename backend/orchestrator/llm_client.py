"""
LLM client — wraps local Llama 3 via llama-cpp-python.
Falls back to a mock response in dev mode if model file not found.
"""
import os
from typing import Optional

from loguru import logger

from backend.config import settings


class LLMClient:
    def __init__(self):
        self._llm = None
        self._mock_mode = False
        self._load_model()

    def _load_model(self):
        model_path = settings.LLM_MODEL_PATH
        if not os.path.exists(model_path):
            logger.warning(
                f"LLM model not found at {model_path}. "
                "Running in MOCK mode — suitable for dev/testing only. "
                "Download Meta-Llama-3-8B-Instruct.Q4_K_M.gguf and set LLM_MODEL_PATH."
            )
            self._mock_mode = True
            return

        try:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=model_path,
                n_ctx=settings.LLM_N_CTX,
                n_gpu_layers=settings.LLM_N_GPU_LAYERS,
                verbose=False,
            )
            logger.info(f"Llama model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load Llama model: {e}")
            self._mock_mode = True

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        if self._mock_mode:
            return self._mock_response(prompt)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["</s>", "[/INST]"],
        )
        return response["choices"][0]["message"]["content"].strip()

    def _mock_response(self, prompt: str) -> str:
        """Dev mode stub — replace with actual model in production."""
        if "JSON" in prompt or "json" in prompt:
            return '{"district": null, "time_range_days": 365, "event_type": null, "persons": [], "analysis_type": "incident", "keywords": ["incident"], "language": "en"}'
        return (
            "[MOCK LLM] Based on the available evidence, relevant incidents were found. "
            "Please configure LLM_MODEL_PATH to enable real AI-generated answers. "
            "Confidence: Low"
        )
