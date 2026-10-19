from ..config import (
    GEMINI_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_MODEL,
    require_gemini_key,
    require_openai_key,
)


def call_openai_llm(prompt: str) -> str:
    """OpenAI Chat Completions backend used by --mode local."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "openai is required for --mode local. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    client = OpenAI(api_key=require_openai_key())
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def call_ollama_llm(prompt: str) -> str:
    """Ollama Chat Completions backend used for 100% offline local LLM."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "openai is required for Ollama local mode. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=2048,
        extra_body={"options": {"num_ctx": 8192, "num_predict": 2048}},
    )
    return response.choices[0].message.content or ""


def call_gemini_llm(prompt: str) -> str:
    """Gemini backend used by --mode local when LLM_PROVIDER=gemini."""
    try:
        from google import genai  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "google-genai is required for LLM_PROVIDER=gemini. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    client = genai.Client(api_key=require_gemini_key())
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
            "max_output_tokens": 8192,
        },
    )
    return response.text or ""


def call_local_llm(prompt: str) -> str:
    """Dispatch to the configured local LLM provider."""
    provider = (LLM_PROVIDER or "ollama").strip().lower()
    if provider == "openai":
        return call_openai_llm(prompt)
    if provider == "ollama":
        return call_ollama_llm(prompt)
    if provider == "gemini":
        return call_gemini_llm(prompt)
    raise RuntimeError(
        f"Unknown LLM_PROVIDER={provider!r}. Use 'ollama', 'gemini', or 'openai'."
    )


def check_ollama_ready() -> None:
    """Check that Ollama server is running and configured model is available."""
    import json
    import urllib.request
    from urllib.parse import urlparse

    parsed = urlparse(OLLAMA_BASE_URL)
    tags_url = f"{parsed.scheme}://{parsed.netloc}/api/tags"

    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "into_short_clips"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(
            f"Ollama server is not responding at {tags_url} ({e}).\n"
            f"Please ensure Ollama is installed and running ('ollama serve') "
            f"or run through run.ps1 / run.bat / run.sh."
        ) from e

    installed_models = [m.get("name", "") for m in data.get("models", [])]
    target = OLLAMA_MODEL.strip().lower()
    matches = any(
        m.lower() == target or m.lower().startswith(f"{target}:") or f"{target}:latest" == m.lower()
        for m in installed_models
    )
    if not matches and installed_models:
        base_target = target.split(":")[0]
        matches = any(m.lower().startswith(f"{base_target}:") for m in installed_models)

    if not matches:
        raise RuntimeError(
            f"Configured Ollama model {OLLAMA_MODEL!r} is not installed locally.\n"
            f"Installed models: {installed_models or 'None'}\n"
            f"Please download it by running:\n"
            f"    ollama pull {OLLAMA_MODEL}"
        )


def verify_llm_provider_readiness() -> None:
    """Validate that the configured LLM provider and credentials/server are ready before processing."""
    provider = (LLM_PROVIDER or "ollama").strip().lower()
    if provider == "ollama":
        check_ollama_ready()
    elif provider == "gemini":
        require_gemini_key()
    elif provider == "openai":
        require_openai_key()
    else:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER={provider!r}. Supported providers: 'ollama', 'gemini', 'openai'."
        )

