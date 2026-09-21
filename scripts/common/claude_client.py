"""Anthropic Claude APIを呼び出す薄いラッパー。

必要な環境変数:
    ANTHROPIC_API_KEY

GitHub Actionsでは Repository Secrets に ANTHROPIC_API_KEY を登録し、
ワークフローYAML側で env: に渡して使う。
"""
from __future__ import annotations

import os

try:
    import anthropic
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "anthropicパッケージが見つかりません。requirements.txt を pip install してください。"
    ) from e


DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")


def ask_claude(system_prompt: str, user_prompt: str, *, max_tokens: int = 4000, model: str | None = None) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY が設定されていません。")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    block_types = [b.type for b in response.content]
    print(
        f"    [debug] stop_reason={response.stop_reason} "
        f"blocks={block_types} "
        f"input_tokens={response.usage.input_tokens} "
        f"output_tokens={response.usage.output_tokens}"
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
