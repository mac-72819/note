"""note.com にそのままコピペできる形式に本文を整形するヘルパー。

note.comは記事投稿用の公式APIを提供していないため、この自動化では
「記事の中身を作るところまで」を自動化し、実際にnote.comの編集画面に
貼り付けて公開する操作は手動で行う設計にしている。

note.comのエディタは以下のMarkdown的な記法をある程度認識する:
  - "# " "## " "### " → 見出し
  - "- " → 箇条書き
  - "1. " → 番号付きリスト
  - "> " → 引用
太字(**text**)などはそのまま貼り付けるとアスタリスクが残ってしまうことがあるため、
強調したい語は【】で囲むなど記号で表現している。
"""
from __future__ import annotations

from datetime import datetime

KEIBA_DISCLAIMER = (
    "※本記事は競馬に関する情報提供・分析の共有を目的としたものであり、"
    "馬券の購入を勧誘するものではありません。予想の的中や利益を保証するものではなく、"
    "馬券の購入は自己責任・余剰資金の範囲で行ってください。20歳未満の方は馬券を購入できません。"
)

AI_CONTENT_NOTE = (
    "※本記事はAIによる分析・下書き生成を含みます。公開前に内容の事実確認と "
    "最終的な表現の調整を行ってください。"
)


def _issue_header(kind: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"<!-- generated_at: {now} JST目安 / kind: {kind} -->\n"


def build_issue_body(
    *,
    kind: str,
    note_title: str,
    note_tags: list[str],
    note_body_markdown: str,
    extra_notes: str = "",
) -> str:
    """GitHub Issue本文全体を組み立てる。

    Issue本文には「コピペ用の記事タイトル」「タグ」「本文」を分かりやすく分割して入れる。
    """
    tags_line = " ".join(f"#{t}" for t in note_tags) if note_tags else "(タグなし)"

    parts = [
        _issue_header(kind),
        "## この下書きの使い方",
        "1. 下記の「note用タイトル」をコピーし、note.comの新規記事タイトル欄に貼り付ける",
        "2. 「note用本文」をコピーし、本文欄に貼り付ける（見出しや箇条書きは自動整形されます）",
        "3. 内容を確認・必要に応じて手直しし、タグを追加してから公開する",
        "",
        "---",
        "",
        "## note用タイトル",
        "```",
        note_title,
        "```",
        "",
        "## note用タグ",
        tags_line,
        "",
        "## note用本文",
        "```markdown",
        note_body_markdown.strip(),
        "```",
    ]
    if extra_notes:
        parts += ["", "## 補足・生成時のメモ", extra_notes.strip()]

    return "\n".join(parts)


def format_keiba_draft(
    *,
    target_date: str,
    track_summaries: list[dict],
) -> tuple[str, list[str], str]:
    """競馬予想のnote下書き (title, tags, body_markdown) を組み立てる。

    track_summaries: [{"track": "佐賀", "races": [{"race_no":.., "race_name":.., "picks_markdown":..}]}]
    """
    title = f"{target_date} 本日の競馬予想【AI×v4ロジック】"
    tags = ["競馬予想", "地方競馬", "AI予想"]

    body_lines = [
        f"# {target_date} の注目レース予想",
        "",
        AI_CONTENT_NOTE,
        "",
    ]
    for track in track_summaries:
        body_lines.append(f"## {track['track']}競馬場")
        body_lines.append("")
        for race in track["races"]:
            body_lines.append(f"### {race['race_no']} {race.get('race_name', '')}".rstrip())
            body_lines.append(race["picks_markdown"].strip())
            body_lines.append("")
    body_lines += ["---", "", KEIBA_DISCLAIMER]

    return title, tags, "\n".join(body_lines)


def format_article_draft(*, topic_title: str, topic_tags: list[str], sections: list[dict]) -> tuple[str, list[str], str]:
    """羅針盤ノート記事(AIリテラシー/競馬コラム等)のnote下書きを組み立てる。

    sections: [{"heading": "...", "body": "..."}]
    """
    body_lines = [f"# {topic_title}", "", AI_CONTENT_NOTE, ""]
    for sec in sections:
        if sec.get("heading"):
            body_lines.append(f"## {sec['heading']}")
        body_lines.append(sec["body"].strip())
        body_lines.append("")

    if any("競馬" in t for t in topic_tags):
        body_lines += ["---", "", KEIBA_DISCLAIMER]

    return topic_title, topic_tags, "\n".join(body_lines)
