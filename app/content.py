"""Pluggable content generation: deterministic local mode or OpenAI-compatible API."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _local_content(topic: str, audience: str, tone: str) -> dict:
    short = topic.strip().rstrip(".!?")
    title = short[0].upper() + short[1:] if short else "A practical DevOps lesson"
    return {
        "linkedin_post": (
            f"A practical way to think about {title.lower()}: start with the outcome, "
            "then make the path repeatable.\n\n"
            f"For {audience}, that means breaking the work into small steps, automating "
            "the checks, and making failures easy to understand.\n\n"
            "A useful starting point:\n"
            "→ Write down the current workflow\n→ Find the slowest or riskiest handoff\n"
            "→ Automate one repeatable check\n→ Measure whether the change helped\n\n"
            f"The goal is not more tooling. It is a safer, clearer way to deliver {title.lower()}."
        ),
        "instagram_caption": (
            f"{title}: make the workflow repeatable, automate one useful check, "
            "and learn from every run. Small improvements compound."
        ),
        "reel_script": (
            f"Hook: Still struggling with {title.lower()}?\n"
            "Scene 1: Show a messy, manual workflow.\n"
            "Voiceover: Start by mapping the steps you repeat.\n"
            "Scene 2: Highlight one risky or slow handoff.\n"
            "Voiceover: Automate one check and make failures visible.\n"
            "Scene 3: Show a simple green pipeline.\n"
            "Voiceover: Measure the result, then improve the next step.\n"
            "Close: Save this and try it in your next sprint."
        ),
        "storyboard": [
            {"scene": 1, "visual": "Manual workflow with several handoffs", "on_screen_text": "Where does work get stuck?", "duration_seconds": 4},
            {"scene": 2, "visual": "Zoom in on one repeated check", "on_screen_text": "Automate one useful check", "duration_seconds": 6},
            {"scene": 3, "visual": "Clear pipeline with visible result", "on_screen_text": "Measure. Learn. Repeat.", "duration_seconds": 5},
        ],
        "hashtags": ["#DevOps", "#PlatformEngineering", "#Cloud", "#Automation", "#TechLeadership"],
        "cta": "What is one workflow you would automate first? Share it in the comments.",
    }


def _normalize(data: dict) -> dict:
    required = ("linkedin_post", "instagram_caption", "reel_script", "storyboard", "hashtags", "cta")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError("LLM response is missing: " + ", ".join(missing))
    if isinstance(data["storyboard"], str):
        data["storyboard"] = [{"scene": i + 1, "visual": line, "on_screen_text": "", "duration_seconds": 5}
                              for i, line in enumerate(data["storyboard"].splitlines()) if line.strip()]
    if isinstance(data["hashtags"], str):
        data["hashtags"] = data["hashtags"].split()
    return {key: data[key] for key in required}


def generate_content(topic: str, audience: str = "DevOps engineers and cloud architects", tone: str = "practical") -> dict:
    if os.getenv("LLM_PROVIDER", "local").lower() != "openai_compatible":
        return _local_content(topic, audience, tone)
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise ValueError("LLM_API_KEY is required when LLM_PROVIDER=openai_compatible")
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    extra = json.loads(os.getenv("LLM_EXTRA_HEADERS", "{}"))
    schema = {"linkedin_post": "string", "instagram_caption": "string", "reel_script": "string",
              "storyboard": [{"scene": "number", "visual": "string", "on_screen_text": "string", "duration_seconds": "number"}],
              "hashtags": ["string"], "cta": "string"}
    prompt = ("Create useful, specific, technically responsible social content for AI, DevOps, and cloud architecture. "
              "Return only valid JSON matching this shape: " + json.dumps(schema) +
              f"\nTopic: {topic}\nAudience: {audience}\nTone: {tone}\nAvoid unsupported claims and fabricated citations.")
    body = json.dumps({"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "temperature": 0.7,
                       "messages": [{"role": "system", "content": "You are an experienced technical content editor."},
                                    {"role": "user", "content": prompt}]}).encode()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **extra}
    request = Request(base + "/chat/completions", data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=90) as response:
            result = json.loads(response.read())
        message = result["choices"][0]["message"]["content"]
        if isinstance(message, list):
            message = "".join(part.get("text", "") for part in message if isinstance(part, dict))
        message = message.strip()
        if message.startswith("```"):
            message = message.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return _normalize(json.loads(message))
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise ValueError(f"LLM endpoint returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not generate content from configured LLM endpoint: {exc}") from exc
