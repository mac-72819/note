"""GitHub Issue に note.com 投稿用の下書きを保存するヘルパー。

GitHub Actions 上で実行する場合、GITHUB_TOKEN と GITHUB_REPOSITORY は
デフォルトで環境変数に自動設定されるため、追加のシークレット登録は不要。
ローカルで試す場合は下記2つを環境変数に設定してから実行する。
    GITHUB_TOKEN=ghp_xxxxx
    GITHUB_REPOSITORY=your-account/your-repo
"""
from __future__ import annotations

import os
import sys
import json
import urllib.request
import urllib.error


class GitHubIssueError(RuntimeError):
    pass


def _api_request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "note-automation-script")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise GitHubIssueError(f"GitHub API error {e.code}: {detail}") from e


def create_draft_issue(title: str, body: str, labels: list[str] | None = None) -> str:
    """note.com投稿用の下書きをGitHub Issueとして作成し、IssueのURLを返す。"""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise GitHubIssueError(
            "GITHUB_TOKEN / GITHUB_REPOSITORY が設定されていません。"
            "GitHub Actions上で実行するか、ローカルではこの2つの環境変数を設定してください。"
        )
    url = f"https://api.github.com/repos/{repo}/issues"
    payload = {
        "title": title,
        "body": body,
        "labels": labels or ["note-draft"],
    }
    result = _api_request("POST", url, token, payload)
    html_url = result.get("html_url")
    if not html_url:
        raise GitHubIssueError(f"Issue作成に失敗しました: {result}")
    return html_url


if __name__ == "__main__":
    # 手動テスト用: python github_issue.py "タイトル" "本文"
    if len(sys.argv) < 3:
        print("usage: python github_issue.py <title> <body>")
        sys.exit(1)
    print(create_draft_issue(sys.argv[1], sys.argv[2]))
