import hashlib
import json
import os
import time
from typing import Any

import yaml
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class GoogleGenAILLM:
    def __init__(self, config_dir: str, cache_dir: str = ".cache/llm", enable_cache: bool = True, mock: bool = False, run_trace: list | None = None):
        models_file = os.path.join(config_dir, "models.yaml")
        if os.path.exists(models_file):
            with open(models_file) as f:
                self.models = yaml.safe_load(f)
        else:
            self.models = {}
        self.cache_dir = cache_dir
        self.enable_cache = enable_cache
        self.mock = mock
        self.run_trace = run_trace if run_trace is not None else []
        if not self.mock:
            self.client = genai.Client() # Uses GEMINI_API_KEY from environment
        else:
            self.client = None
        if self.enable_cache:
            os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_key(self, model: str, system: str, prompt: str, schema: Any) -> str:
        s = f"{model}|{system}|{prompt}|{schema}"
        return hashlib.sha256(s.encode()).hexdigest()

    def complete(self, prompt: str, *, system: str | None = None, model_role: str = 'generator', json_schema: type[BaseModel] | None = None, temperature: float = 0.0) -> str | BaseModel:
        if self.mock:
            return self._mock_complete(prompt, system, model_role, json_schema)
            
        role_cfg = self.models.get(model_role, self.models.get("generator", {}))
        primary_model = role_cfg.get("primary", "gemini-1.5-pro")
        fallback_model = role_cfg.get("fallback", "gemini-1.5-flash")

        try:
            return self._complete_with_retries(primary_model, prompt, system, json_schema, temperature)
        except Exception as e:
            self.run_trace.append({"event": "fallback_triggered", "reason": str(e), "fallback": fallback_model})
            return self._complete_with_retries(fallback_model, prompt, system, json_schema, temperature)

    def _complete_with_retries(self, model: str, prompt: str, system: str | None, json_schema: type[BaseModel] | None, temperature: float) -> str | BaseModel:
        schema_str = json_schema.model_json_schema() if json_schema else None
        cache_key = self._get_cache_key(model, system or "", prompt, schema_str)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if self.enable_cache and os.path.exists(cache_file):
            with open(cache_file) as f:
                data = json.load(f)
                if json_schema:
                    return json_schema.model_validate(data["response"])
                return data["response"]

        @retry(
            retry=retry_if_exception_type(APIError),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10)
        )
        def call_api(current_prompt: str, is_retry: bool = False):
            start_t = time.time()
            config = types.GenerateContentConfig(
                temperature=temperature,
                http_options={'timeout': 60.0}
            )
            if system:
                config.system_instruction = system
            if json_schema:
                config.response_mime_type = "application/json"
                config.response_schema = json_schema

            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=current_prompt,
                    config=config,
                )
            except APIError as e:
                if e.code in [429] or (e.code >= 500):
                    raise
                else:
                    raise RuntimeError(f"Non-retriable API error: {e}") from e

            latency = time.time() - start_t
            usage = response.usage_metadata
            tokens = usage.total_token_count if usage else 0

            self.run_trace.append({
                "event": "llm_call",
                "model": model,
                "latency": latency,
                "tokens": tokens,
                "is_repair_retry": is_retry
            })

            text = response.text
            if json_schema:
                try:
                    return json_schema.model_validate_json(text), text
                except ValidationError:
                    return None, text
            return text, text

        res, raw_text = call_api(prompt, False)
        if json_schema and res is None:
            repair_prompt = f"The previous response failed schema validation. Please fix it. Original prompt: {prompt}\n\nInvalid response:\n{raw_text}"
            res, raw_text = call_api(repair_prompt, True)
            if res is None:
                raise ValueError("Failed to produce valid JSON after repair.")

        if self.enable_cache:
            with open(cache_file, "w") as f:
                json.dump({"response": res.model_dump() if json_schema else res}, f)

        return res

    def _mock_complete(self, prompt: str, system: str | None, model_role: str, json_schema: type[BaseModel] | None) -> str | BaseModel:
        self.run_trace.append({
            "event": "llm_call",
            "model": "mock",
            "latency": 0.01,
            "tokens": 10,
            "is_repair_retry": False
        })
        if json_schema:
            try:
                return json_schema()
            except Exception:
                return json_schema.construct()
        return "Mock Response"
