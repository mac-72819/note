"""羅針盤ノート(note.com投稿用)の記事下書きを生成し、GitHub Issueに保存するメインスクリプト。

実行方法:
    python scripts/article/generate_article.py

ローテーションは scripts/article/topics.py の TOPIC_POOL からランダムに選ぶ。
特定のお題を指定したい場合は環境変数 ARTICLE_TOPIC_INDEX (0始まり)で固定できる。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))

from topics import PERSONA_SYSTEM_PROMPT, TOPIC_POOL, pick_topic  # noqa: E402
from claude_client import ask_claude  # noqa: E402
from note_format import build_issue_body, format_article_draft  # noqa: E402
from github_issue import create_draft_issue  # noqa: E402


def _select_topic() -> dict:
    idx = os.environ.get("ARTICLE_TOPIC_INDEX")
    if idx is not None and idx.isdigit() and int(idx) < len(TOPIC_POOL):
        return TOPIC_POOL[int(idx)]
    return pick_topic()


def generate_article_text(topic: dict) -> tuple[str, list[dict]]:
    user_prompt = f"""\
今日のお題: {topic['prompt_hint']}

上記のお題で、羅針盤ノートの記事を1本書いてください。
出力は以下の形式にしてください。

タイトル: <32文字前後の記事タイトル>

## <見出し1>
本文...

## <見出し2>
本文...

(見出しは2〜4個程度、全体で800〜1200文字程度)
"""
    raw = ask_claude(PERSONA_SYSTEM_PROMPT, user_prompt, max_tokens=2500)

    title = "羅針盤ノート 新着記事"
    lines = raw.splitlines()
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("タイトル:") or line.strip().startswith("タイトル："):
            title = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            body_start = i + 1
            break

    body_text = "\n".join(lines[body_start:]).strip()

    # "## 見出し" ごとにセクション分割(整形用。そのままnote本文にも使うので厳密でなくてよい)
    sections: list[dict] = []
    current_heading = ""
    current_body: list[str] = []
    for line in body_text.splitlines():
        if line.startswith("## "):
            if current_body:
                sections.append({"heading": current_heading, "body": "\n".join(current_body).strip()})
            current_heading = line[3:].strip()
            current_body = []
        else:
            current_body.append(line)
    if current_body:
        sections.append({"heading": current_heading, "body": "\n".join(current_body).strip()})

    if not sections:
        sections = [{"heading": "", "body": body_text}]

    return title, sections


def main() -> None:
    topic = _select_topic()
    title, sections = generate_article_text(topic)

    note_title, note_tags, body_md = format_article_draft(
        topic_title=title, topic_tags=topic["tags"], sections=sections
    )

    issue_body = build_issue_body(
        kind="note-article",
        note_title=note_title,
        note_tags=note_tags,
        note_body_markdown=body_md,
        extra_notes=f"お題: {topic['prompt_hint']}",
    )

    issue_url = create_draft_issue(title=f"[note下書き] {note_title}", body=issue_body)
    print(f"Issueを作成しました: {issue_url}")


if __name__ == "__main__":
    main()
