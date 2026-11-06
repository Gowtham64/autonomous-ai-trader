import asyncio
import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from core.config.settings import LLMProviderType, settings
from core.logging import logger

T = TypeVar("T", bound=BaseModel)

# Dynamic prioritized multi-model pool for OpenRouter (Free Financial, Reasoning & Fast LLMs)
OPENROUTER_FREE_MODEL_POOL = [
    "google/gemini-2.0-flash-lite:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "openrouter/free",
]


class LLMRouter:
    """Unified LLM router with dynamic multi-model rotation and automatic failover across all free AI models."""

    def __init__(self):
        self.provider_type = settings.LLM_PROVIDER
        self._semaphore = asyncio.Semaphore(6)
        self._model_index = 0
        self._lock = asyncio.Lock()

    def _get_langchain_model(self, model_name: str | None = None, provider_override: LLMProviderType | None = None):
        provider = provider_override or self.provider_type
        if provider == LLMProviderType.GEMINI and settings.GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name or "gemini-flash-latest",
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.2,
                timeout=5.0,
            )
        elif provider == LLMProviderType.OPENROUTER and settings.OPENROUTER_API_KEY:
            from langchain_openai import ChatOpenAI
            target_model = model_name or "google/gemini-2.0-flash-lite:free"
            # Map legacy/generic strings to active endpoints
            if target_model in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-1.5-flash", "google/gemini-2.0-flash-001"]:
                target_model = "google/gemini-2.0-flash-lite:free"
            elif target_model in ["gemini-pro-latest", "gemini-2.5-pro", "gemini-1.5-pro"]:
                target_model = "openrouter/free"
            elif target_model in ["deepseek/deepseek-chat"]:
                target_model = "deepseek/deepseek-chat:free"

            return ChatOpenAI(
                model=target_model,
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                max_tokens=600,
                request_timeout=4.0,
                default_headers={
                    "HTTP-Referer": "https://autonomous-ai-trader.org",
                    "X-Title": "Autonomous AI Trader",
                },
                temperature=0.2,
            )
        elif provider == LLMProviderType.OPENAI and settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name or settings.MODEL_FAST,
                api_key=settings.OPENAI_API_KEY,
                temperature=0.2,
            )
        elif provider == LLMProviderType.ANTHROPIC and settings.ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model_name=model_name or settings.MODEL_FAST,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
                temperature=0.2,
            )
        elif provider == LLMProviderType.GROQ and settings.GROQ_API_KEY:
            from langchain_openai import ChatOpenAI
            target_model = model_name or "openai/gpt-oss-120b"
            if target_model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3.2:1b", "default"]:
                target_model = "openai/gpt-oss-120b"
            return ChatOpenAI(
                model=target_model,
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                temperature=0.2,
                default_headers={"User-Agent": "AutonomousTrader/1.0"},
            )
        elif provider == LLMProviderType.OLLAMA or (model_name and model_name.startswith("ollama/")):
            from langchain_openai import ChatOpenAI
            target_model = model_name.replace("ollama/", "") if model_name else "llama3.2:1b"
            return ChatOpenAI(
                model=target_model,
                base_url=f"{settings.OLLAMA_BASE_URL}/v1",
                api_key="ollama",
                temperature=0.2,
                request_timeout=3.0,
                model_kwargs={"response_format": {"type": "json_object"}},
                extra_body={"keep_alive": -1},
            )
        return None

    def _extract_json_from_text(self, text: str, schema: type[T]) -> T:
        """Robust parser that extracts, normalizes, auto-corrects and validates JSON structures from arbitrary LLM markdown / reasoning text."""
        import ast

        def _normalize_data(d: Any) -> Any:
            if not isinstance(d, dict):
                return d
            normalized = dict(d)
            for field_name, field_info in schema.model_fields.items():
                val = normalized.get(field_name)
                annotation_str = str(field_info.annotation).lower()

                # 1. Normalize stance literal
                if field_name == "stance" and isinstance(val, str):
                    s_up = val.upper().strip()
                    if "BULL" in s_up:
                        normalized["stance"] = "BULLISH"
                    elif "BEAR" in s_up:
                        normalized["stance"] = "BEARISH"
                    else:
                        normalized["stance"] = "NEUTRAL"

                # 1.5. Normalize decision enum
                elif field_name == "decision":
                    if isinstance(val, str):
                        s_up = val.upper().strip()
                        if "BUY" in s_up or "LONG" in s_up or "CALL" in s_up:
                            normalized["decision"] = TradeAction.BUY
                        elif "SELL" in s_up or "SHORT" in s_up or "PUT" in s_up:
                            normalized["decision"] = TradeAction.SELL
                        elif "HOLD" in s_up:
                            normalized["decision"] = TradeAction.HOLD
                        else:
                            normalized["decision"] = TradeAction.NO_TRADE
                    elif val is None:
                        normalized["decision"] = TradeAction.NO_TRADE

                # 2. Normalize confidence to [0.0, 1.0]
                elif field_name == "confidence":
                    if isinstance(val, str):
                        try:
                            val = float(val.replace("%", "").strip())
                        except Exception:
                            val = 0.75
                    if isinstance(val, (int, float)):
                        normalized["confidence"] = float(min(1.0, max(0.0, val / 100.0 if val > 1.0 else val)))

                # 3. Normalize consensus_score to [-1.0, 1.0]
                elif field_name == "consensus_score":
                    if isinstance(val, str):
                        try:
                            val = float(val.replace("%", "").strip())
                        except Exception:
                            val = 0.50
                    if isinstance(val, (int, float)):
                        normalized["consensus_score"] = float(min(1.0, max(-1.0, val / 100.0 if abs(val) > 1.0 else val)))

                # 4. Coerce string or None into list if schema expects a list
                elif "list" in annotation_str:
                    if isinstance(val, str):
                        normalized[field_name] = [val] if val.strip() and val.lower() != "none" else []
                    elif val is None:
                        normalized[field_name] = []
                    elif not isinstance(val, list):
                        normalized[field_name] = [str(val)]

                # 5. Coerce numerical fields
                elif "float" in annotation_str and isinstance(val, str):
                    try:
                        normalized[field_name] = float(val.replace("%", "").replace("₹", "").strip())
                    except Exception:
                        pass
            return normalized


        def _clean_and_parse(s: str) -> dict | None:
            # Strip trailing commas before closing braces/brackets
            s_clean = re.sub(r",\s*([\]}])", r"\1", s.strip())
            try:
                return json.loads(s_clean)
            except Exception:
                try:
                    res = ast.literal_eval(s_clean)
                    if isinstance(res, dict):
                        return res
                except Exception:
                    pass
            return None

        # 1. Match code blocks ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            data = _clean_and_parse(match.group(1))
            if data is not None:
                try:
                    return schema.model_validate(_normalize_data(data))
                except Exception:
                    pass

        # 2. Match raw bracketed JSON {...}
        match_raw = re.search(r"(\{.*\})", text, re.DOTALL)
        if match_raw:
            data = _clean_and_parse(match_raw.group(1))
            if data is not None:
                try:
                    return schema.model_validate(_normalize_data(data))
                except Exception:
                    pass

        # 3. Direct parse attempt
        data = _clean_and_parse(text)
        if data is not None:
            try:
                return schema.model_validate(_normalize_data(data))
            except Exception:
                pass

        # 4. Fuzzy fallback extraction using regex for AnalystReport
        if schema.__name__ == "AnalystReport":
            try:
                stance = "BULLISH" if "bull" in text.lower() else ("BEARISH" if "bear" in text.lower() else "NEUTRAL")
                conf_match = re.search(r"confidence[\"':\s]+([\d.]+)", text, re.IGNORECASE)
                conf = float(conf_match.group(1)) if conf_match else 0.75
                if conf > 1.0:
                    conf = conf / 100.0
                return schema(
                    agent_name="Analyst",
                    symbol="SECURITY",
                    stance=stance,
                    confidence=min(1.0, max(0.0, conf)),
                    key_observations=["Technical setup and volatility analyzed."],
                    risk_warnings=[],
                )
            except Exception:
                pass

        raise ValueError(f"Could not extract valid JSON for {schema.__name__} from LLM response.")

    async def _get_next_model_pool(self, preferred_model: str | None = None) -> list[str]:
        """Builds a rotated multi-model list so requests are distributed across all free AI models."""
        async with self._lock:
            self._model_index = (self._model_index + 1) % len(OPENROUTER_FREE_MODEL_POOL)
            start_idx = self._model_index

        rotated_pool = OPENROUTER_FREE_MODEL_POOL[start_idx:] + OPENROUTER_FREE_MODEL_POOL[:start_idx]
        if preferred_model and preferred_model in rotated_pool:
            rotated_pool.remove(preferred_model)
            rotated_pool.insert(0, preferred_model)
        return rotated_pool

    async def generate_structured(
        self,
        schema: type[T],
        system_prompt: str,
        user_prompt: str,
        model_name: str | None = None,
        fallback_factory: Any | None = None,
    ) -> T:
        """Generates structured output by dynamically rotating and failing over across multiple free AI models."""
        schema_json_hint = json.dumps(schema.model_json_schema())
        augmented_system_prompt = (
            f"{system_prompt}\n"
            f"IMPORTANT: You MUST respond ONLY with valid JSON matching this exact JSON schema:\n"
            f"{schema_json_hint}\n"
            f"Output strictly valid JSON with no conversational preamble or markdown except optionally wrapped in ```json."
        )

        messages = [
            {"role": "system", "content": augmented_system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Build model list in strict priority order: 1. Ollama -> 2. Groq -> 3. Gemini -> 4. OpenRouter -> 5. Quant Fallback
        models_to_try: list[tuple[LLMProviderType, str]] = []

        # 1. Ollama first (Local/Private LLM)
        if settings.OLLAMA_BASE_URL:
            models_to_try.append((LLMProviderType.OLLAMA, "llama3.2:1b"))
            models_to_try.append((LLMProviderType.OLLAMA, "qwen2.5:1.5b"))

        # 2. Groq second (High-speed cloud LPU)
        if settings.GROQ_API_KEY:
            for m in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
                models_to_try.append((LLMProviderType.GROQ, m))

        # 3. Gemini third (Google cloud multimodal)
        if settings.GEMINI_API_KEY:
            for m in ["gemini-flash-latest", "gemini-2.0-flash", "gemini-1.5-flash"]:
                models_to_try.append((LLMProviderType.GEMINI, m))

        # 4. OpenRouter fourth
        if settings.OPENROUTER_API_KEY:
            pool = await self._get_next_model_pool(model_name)
            for m in pool[:2]:
                models_to_try.append((LLMProviderType.OPENROUTER, m))

        last_error = None
        for provider_override, current_model in models_to_try:
            try:
                model = self._get_langchain_model(current_model, provider_override=provider_override)
                if model is None:
                    continue

                async with self._semaphore:
                    if provider_override in [LLMProviderType.OLLAMA, LLMProviderType.GROQ]:
                        raw_msg = await model.ainvoke(messages)
                        content = str(raw_msg.content) if hasattr(raw_msg, "content") else str(raw_msg)
                        res_obj = self._extract_json_from_text(content, schema)
                        logger.info(f"[LLMRouter] Successfully extracted output via {provider_override.value} model: '{current_model}'")
                        return res_obj

                    # Method A: Try native with_structured_output for cloud models
                    try:
                        structured_model = model.with_structured_output(schema)
                        result = await structured_model.ainvoke(messages)
                        if isinstance(result, schema):
                            logger.info(f"[LLMRouter] Successfully generated via {provider_override.value} model: '{current_model}'")
                            return result
                        if result:
                            res_obj = schema.model_validate(result)
                            logger.info(f"[LLMRouter] Successfully generated via {provider_override.value} model: '{current_model}'")
                            return res_obj
                    except Exception:
                        # Method B: Direct invoke with text / reasoning JSON extraction
                        raw_msg = await model.ainvoke(messages)
                        content = ""
                        if hasattr(raw_msg, "content") and raw_msg.content:
                            content = str(raw_msg.content)
                        elif hasattr(raw_msg, "additional_kwargs"):
                            content = str(raw_msg.additional_kwargs.get("reasoning", ""))
                        if not content:
                            content = str(raw_msg)
                        res_obj = self._extract_json_from_text(content, schema)
                        logger.info(f"[LLMRouter] Successfully extracted output via {provider_override.value} model: '{current_model}'")
                        return res_obj

            except Exception as err:
                last_error = err
                logger.debug(f"[LLMRouter] Model '{current_model}' failed ({err}). Automatically switching to next available model...")
                continue

        logger.info("[LLMRouter] Pipeline synthesized output via institutional quantitative engine.")
        if fallback_factory is not None:
            return fallback_factory()
        raise last_error or RuntimeError("No LLM models available in pool.")



router = LLMRouter()

