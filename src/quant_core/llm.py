"""
LLM服务 - 支持多种Provider: OpenRouter, OpenAI, Google Gemini, DeepSeek, Grok, Custom, MiniMax
"""
import json
import os
import requests
from typing import Dict, Any, List
from enum import Enum

from quant_core import config

logger = print


class LLMProvider(Enum):
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    GROK = "grok"
    CUSTOM = "custom"
    MINIMAX = "minimax"


PROVIDER_CONFIGS = {
    LLMProvider.OPENROUTER: {"base_url": "https://openrouter.ai/api/v1", "default_model": "openai/gpt-4o", "fallback_model": "openai/gpt-4o-mini"},
    LLMProvider.OPENAI: {"base_url": "https://api.openai.com/v1", "default_model": "gpt-4o", "fallback_model": "gpt-4o-mini"},
    LLMProvider.GOOGLE: {"base_url": "https://generativelanguage.googleapis.com/v1beta", "default_model": "gemini-1.5-flash", "fallback_model": "gemini-1.5-flash"},
    LLMProvider.DEEPSEEK: {"base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-chat", "fallback_model": "deepseek-chat"},
    LLMProvider.GROK: {"base_url": "https://api.x.ai/v1", "default_model": "grok-beta", "fallback_model": "grok-beta"},
    LLMProvider.CUSTOM: {"base_url": "", "default_model": "", "fallback_model": ""},
    LLMProvider.MINIMAX: {"base_url": "https://api.minimax.io/v1", "default_model": "MiniMax-M2.7", "fallback_model": "MiniMax-M2.7-highspeed"},
}


class LLMService:
    def __init__(self, provider: str = None):
        self._provider_override = provider

    @property
    def provider(self) -> LLMProvider:
        if self._provider_override:
            try:
                return LLMProvider(self._provider_override.lower())
            except ValueError:
                pass

        provider_name = config.LLM_PROVIDER
        if provider_name:
            try:
                return LLMProvider(provider_name.lower())
            except ValueError:
                pass

        priority_order = [LLMProvider.DEEPSEEK, LLMProvider.GROK, LLMProvider.MINIMAX, LLMProvider.OPENAI, LLMProvider.GOOGLE, LLMProvider.OPENROUTER]
        for p in priority_order:
            if self.get_api_key(p):
                return p
        return LLMProvider.MINIMAX

    def get_api_key(self, provider: LLMProvider = None) -> str:
        p = provider or self.provider
        key_map = {
            LLMProvider.OPENROUTER: config.OPENROUTER_API_KEY,
            LLMProvider.OPENAI: config.OPENAI_API_KEY,
            LLMProvider.GOOGLE: config.GOOGLE_API_KEY,
            LLMProvider.DEEPSEEK: config.DEEPSEEK_API_KEY,
            LLMProvider.GROK: config.GROK_API_KEY,
            LLMProvider.CUSTOM: os.getenv("CUSTOM_API_KEY", ""),
            LLMProvider.MINIMAX: config.MINIMAX_API_KEY,
        }
        return key_map.get(p, "") or ""

    def get_base_url(self, provider: LLMProvider = None) -> str:
        p = provider or self.provider
        url_map = {
            LLMProvider.OPENROUTER: config.OPENROUTER_BASE_URL,
            LLMProvider.OPENAI: "https://api.openai.com/v1",
            LLMProvider.GOOGLE: "https://generativelanguage.googleapis.com/v1beta",
            LLMProvider.DEEPSEEK: "https://api.deepseek.com/v1",
            LLMProvider.GROK: "https://api.x.ai/v1",
            LLMProvider.CUSTOM: os.getenv("CUSTOM_API_URL", "http://localhost:11434/v1"),
            LLMProvider.MINIMAX: config.MINIMAX_BASE_URL,
        }
        return url_map.get(p, "") or ""

    def get_default_model(self, provider: LLMProvider = None) -> str:
        p = provider or self.provider
        model_map = {
            LLMProvider.OPENROUTER: config.OPENROUTER_MODEL,
            LLMProvider.OPENAI: config.OPENAI_MODEL,
            LLMProvider.GOOGLE: config.GOOGLE_MODEL,
            LLMProvider.DEEPSEEK: config.DEEPSEEK_MODEL,
            LLMProvider.GROK: config.GROK_API_KEY or "grok-beta",
            LLMProvider.CUSTOM: os.getenv("CUSTOM_MODEL", "llama3.2"),
            LLMProvider.MINIMAX: config.MINIMAX_MODEL,
        }
        return model_map.get(p, "") or PROVIDER_CONFIGS[p]["default_model"]

    def _call_openai_compatible(self, messages: list, model: str, temperature: float, api_key: str, base_url: str, timeout: int, use_json_mode: bool = True) -> str:
        url = f"{base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        if "openrouter" in base_url:
            headers["HTTP-Referer"] = "https://quantcore.ai"
            headers["X-Title"] = "QuantCore Analysis"

        data = {"model": model, "messages": messages, "temperature": temperature}
        if use_json_mode:
            data["response_format"] = {"type": "json_object"}

        response = requests.post(url, headers=headers, json=data, timeout=timeout)
        if response.status_code >= 400:
            raise ValueError(f"API {response.status_code}: {response.text[:300]}")
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            if not content:
                raise ValueError(f"Model {model} returned empty content")
            return content
        raise ValueError("API response missing 'choices'")

    def _call_google_gemini(self, messages: list, model: str, temperature: float, api_key: str, base_url: str, timeout: int) -> str:
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        contents = []
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
            elif msg["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
        data = {"contents": contents, "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"}}
        if system_instruction:
            data["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, json=data, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        if "candidates" in result and len(result["candidates"]) > 0:
            candidate = result["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                text = candidate["content"]["parts"][0].get("text", "")
                if text:
                    return text
        raise ValueError("Gemini API response missing content")

    def call_llm_api(self, messages: list, model: str = None, temperature: float = 0.7, use_fallback: bool = True, provider: LLMProvider = None, use_json_mode: bool = True) -> str:
        p = provider or self.provider
        api_key = self.get_api_key(p)
        base_url = self.get_base_url(p)
        custom_ok_without_key = p == LLMProvider.CUSTOM and bool(base_url)
        if not api_key and not custom_ok_without_key:
            raise ValueError(f"API key not configured for provider: {p.value}")
        original_model = model
        model = model or self.get_default_model(p)
        timeout = 120
        models_to_try = [model]
        if use_fallback:
            fallback = PROVIDER_CONFIGS[p].get("fallback_model")
            if fallback and fallback != model:
                models_to_try.append(fallback)
        for current_model in models_to_try:
            try:
                if p == LLMProvider.GOOGLE:
                    return self._call_google_gemini(messages, current_model, temperature, api_key, base_url, timeout)
                else:
                    return self._call_openai_compatible(messages, current_model, temperature, api_key, base_url, timeout, use_json_mode)
            except Exception as e:
                logger(f"{p.value} API error ({current_model}): {e}")
                if current_model == models_to_try[-1]:
                    raise
        raise Exception(f"All model calls failed")

    def safe_call_llm(self, system_prompt: str, user_prompt: str, default_structure: Dict[str, Any], model: str = None) -> Dict[str, Any]:
        response_text = ""
        try:
            response_text = self.call_llm_api([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], model=model)
            clean_text = response_text.strip()
            if clean_text.startswith("```"):
                first_newline = clean_text.find("\n")
                if first_newline != -1:
                    clean_text = clean_text[first_newline+1:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            return json.loads(clean_text)
        except json.JSONDecodeError:
            try:
                if response_text:
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    if start >= 0 and end > start:
                        return json.loads(response_text[start:end])
            except:
                pass
            default_structure['report'] = f"Failed to parse result. Raw: {response_text[:500] if response_text else 'N/A'}"
            return default_structure
        except Exception as e:
            default_structure['report'] = f"Analysis failed: {e}"
            return default_structure

    @classmethod
    def get_available_providers(cls) -> List[Dict[str, Any]]:
        providers = []
        for p in LLMProvider:
            service = cls()
            api_key = service.get_api_key(p)
            providers.append({"id": p.value, "name": p.value.title(), "configured": bool(api_key), "default_model": PROVIDER_CONFIGS[p]["default_model"]})
        return providers


def get_llm_service(provider: str = None) -> LLMService:
    return LLMService(provider)
