# host/llm_anthropic.py
# Minimal Anthropic SDK wrapper for chat with context.

import os
from typing import List, Dict
import anthropic

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-1-20250805")

class LLMAnthropic:
    def __init__(self, model: str | None = None, max_tokens: int = 500):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY.")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens

    def chat(self, history: List[Dict[str, str]], user_text: str) -> str:
        """
        history: list of {"role": "user"|"assistant", "content": "text"}
        user_text: the new user message
        returns: assistant text
        """
        msgs = []
        for turn in history:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": user_text})

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=msgs
        )
        parts = []
        for block in resp.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "\n".join(parts).strip() or "(sin respuesta)"
