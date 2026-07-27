from __future__ import annotations

import json
from typing import Any

import httpx

from app.analysis.contract import ANALYSIS_JSON_SCHEMA, AnalysisResult
from app.analysis.prompt import SYSTEM_INSTRUCTIONS
from app.config import Settings


class ProviderError(RuntimeError):
    pass


_LIST_CAPS = {
    "claims": 8,
    "evidence": 12,
    "context_notes": 8,
    "reasoning_flags": 8,
    "fruit_signals": 8,
    "limitations": 8,
}


_UNSUPPORTED_SCHEMA_KEYS = {"maxItems", "minItems", "minimum", "maximum", "multipleOf", "minLength", "maxLength"}


def _sanitize_schema(schema: object) -> object:
    """Structured outputs reject numeric and length constraints; strip them
    from the wire schema and enforce them client-side after parsing."""
    if isinstance(schema, dict):
        return {k: _sanitize_schema(v) for k, v in schema.items() if k not in _UNSUPPORTED_SCHEMA_KEYS}
    if isinstance(schema, list):
        return [_sanitize_schema(item) for item in schema]
    return schema


def analyze_with_anthropic(
    *,
    settings: Settings,
    content: str,
    evidence: list[dict[str, str]],
    safety: dict[str, Any],
    lexical: dict[str, Any] | None = None,
) -> AnalysisResult:
    if not settings.anthropic_api_key:
        raise ProviderError("ANTHROPIC_API_KEY is required for the anthropic analyzer")

    try:
        import anthropic
    except ImportError as exc:
        raise ProviderError("The 'anthropic' package is not installed") from exc

    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.analysis_timeout_seconds,
    )
    payload = json.dumps(
        {
            "community_content": content,
            "approved_biblical_evidence": evidence,
            "platform_safety_assessment": safety,
            "research_layer": lexical or {},
            "strict_corpus_only": settings.archangel_strict_corpus_only,
        },
        ensure_ascii=False,
    )
    try:
        response = client.beta.messages.create(
            model=settings.anthropic_model,
            max_tokens=8192,
            system=SYSTEM_INSTRUCTIONS,
            output_config={"format": {
                "type": "json_schema",
                "schema": _sanitize_schema(ANALYSIS_JSON_SCHEMA),
            }},
            # Safety classifiers can decline a request; the server-side fallback
            # re-runs it on Anthropic's recommended substitute model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": payload}],
        )
    except Exception as exc:
        raise ProviderError(f"Anthropic API call failed: {exc}") from exc

    if response.stop_reason == "refusal":
        raise ProviderError("Anthropic model declined the request (stop_reason=refusal)")

    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise ProviderError("Anthropic response contained no text block")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError("Anthropic response was not valid JSON") from exc
    for field, cap in _LIST_CAPS.items():
        if isinstance(data.get(field), list):
            data[field] = data[field][:cap]
    if isinstance(data.get("confidence"), (int, float)):
        data["confidence"] = min(1.0, max(0.0, float(data["confidence"])))

    result = AnalysisResult.model_validate(data)
    result.analyzer_mode = "anthropic"
    return result


def _extract_responses_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise ProviderError("Model response did not contain output text")


def analyze_with_openai(
    *,
    settings: Settings,
    content: str,
    evidence: list[dict[str, str]],
    safety: dict[str, Any],
) -> AnalysisResult:
    if not settings.openai_api_key or not settings.archangel_model:
        raise ProviderError("OPENAI_API_KEY and ARCHANGEL_MODEL are required")

    request_payload = {
        "model": settings.archangel_model,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": json.dumps(
            {
                "community_content": content,
                "approved_biblical_evidence": evidence,
                "platform_safety_assessment": safety,
                "strict_corpus_only": settings.archangel_strict_corpus_only,
            },
            ensure_ascii=False,
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "archangel_analysis",
                "strict": True,
                "schema": ANALYSIS_JSON_SCHEMA,
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=settings.analysis_timeout_seconds) as client:
        response = client.post(
            f"{settings.openai_base_url.rstrip('/')}/responses",
            headers=headers,
            json=request_payload,
        )
    if response.status_code >= 400:
        raise ProviderError(f"OpenAI Responses API returned {response.status_code}: {response.text[:500]}")

    text = _extract_responses_text(response.json())
    result = AnalysisResult.model_validate_json(text)
    result.analyzer_mode = "openai"
    return result


def analyze_with_local_openai_compatible(
    *,
    settings: Settings,
    content: str,
    evidence: list[dict[str, str]],
    safety: dict[str, Any],
) -> AnalysisResult:
    model = settings.local_llm_model or settings.archangel_model
    if not model:
        raise ProviderError("LOCAL_LLM_MODEL or ARCHANGEL_MODEL is required")

    prompt = json.dumps(
        {
            "instructions": SYSTEM_INSTRUCTIONS,
            "required_json_schema": ANALYSIS_JSON_SCHEMA,
            "community_content": content,
            "approved_biblical_evidence": evidence,
            "platform_safety_assessment": safety,
        },
        ensure_ascii=False,
    )
    headers = {
        "Authorization": f"Bearer {settings.local_llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=settings.analysis_timeout_seconds) as client:
        response = client.post(
            f"{settings.local_llm_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
    if response.status_code >= 400:
        raise ProviderError(f"Local model endpoint returned {response.status_code}: {response.text[:500]}")

    body = response.json()
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Local model response had an unexpected shape") from exc
    result = AnalysisResult.model_validate_json(text)
    result.analyzer_mode = "local_openai_compatible"
    return result
