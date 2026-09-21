"""本日の競馬予想を生成し、note.com投稿用の下書きをGitHub Issueに保存するメインスクリプト。

実行方法:
    python scripts/keiba/generate_prediction.py

デフォルトでは、その日開催している「地方競馬(NAR)の全競馬場」+「JRA中央競馬の全競馬場」を
自動検出して、すべて予想対象にする。環境変数を指定すれば絞り込みも可能:
    KEIBA_NAR_TRACKS="佐賀,大井"   … 地方競馬(NAR)の対象競馬場をカンマ区切りで指定して絞り込む。
                                     "none"を指定するとNARを対象外にできる。
                                     未指定ならその日開催の全NAR競馬場が自動的に対象になる。
    KEIBA_INCLUDE_JRA="false"      … JRA中央競馬を対象から外したい場合に指定
                                     (未指定時はtrue。土日・祝日のみ開催で、
                                     平日はレースが無いため自動的にスキップされる)
    KEIBA_JRA_TRACKS="阪神"        … JRAの対象競馬場をカンマ区切りで指定して絞り込む
                                     (未指定ならその日開催の全JRA競馬場が対象)
    KEIBA_TARGET_DATE="20260921"  … 対象日を指定(未指定なら実行日=JSTの今日)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))

from fetch_race_list import (  # noqa: E402
    fetch_jra_races,
    fetch_nar_races,
    fetch_all_nar_races,
    RaceInfo,
)
from fetch_shutuba_past import (  # noqa: E402
    fetch_shutuba_past_html,
    parse_shutuba_past,
    format_entries_for_prompt,
)
from v4_rules import V4_SYSTEM_PROMPT, LOTO5_SYSTEM_PROMPT  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from claude_client import ask_claude  # noqa: E402
from note_format import build_issue_body, format_keiba_draft  # noqa: E402
from github_issue import create_draft_issue  # noqa: E402

JST = timezone(timedelta(hours=9))


def _target_date() -> str:
    override = os.environ.get("KEIBA_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y%m%d")


def _target_nar_tracks() -> list[str] | None:
    """戻り値: None=自動検出(全競馬場) / []=NAR対象外 / それ以外=指定された競馬場のみ"""
    raw = os.environ.get("KEIBA_NAR_TRACKS")
    if raw and raw.strip():
        if raw.strip().lower() == "none":
            return []
        return [t.strip() for t in raw.split(",") if t.strip()]
    return None


def _include_jra() -> bool:
    # 未指定時はデフォルトでJRAも対象に含める(平日はレースが無いため自動的に0件になるだけ)
    return os.environ.get("KEIBA_INCLUDE_JRA", "true").lower() in ("1", "true", "yes")


def _target_jra_tracks() -> list[str] | None:
    raw = os.environ.get("KEIBA_JRA_TRACKS")
    if raw:
        return [t.strip() for t in raw.split(",") if t.strip()]
    return None


def analyze_race(race: RaceInfo, *, nar: bool) -> str:
    html = fetch_shutuba_past_html(race.race_id, nar=nar)
    entries = parse_shutuba_past(html)
    if not entries:
        return "（出馬表データを取得できませんでした。手動で確認してください）"

    horses_text = format_entries_for_prompt(entries)
    user_prompt = f"""\
以下は{race.track}競馬場 {race.race_no} {race.race_name}
（{race.course} {race.head_count} 発走{race.start_time}）の出走馬データです。

{horses_text}

上記データをもとに、v4ロジックに従って◎○▲△と根拠を出力してください。
"""
    return ask_claude(V4_SYSTEM_PROMPT, user_prompt, max_tokens=2000)


def build_loto5_summary(race_analyses: list[dict]) -> str:
    joined = "\n\n".join(
        f"[{r['track']} {r['race_no']}]\n{r['analysis']}" for r in race_analyses
    )
    user_prompt = f"""\
本日の各レース分析結果は以下の通りです。

{joined}

Loto5アルゴリズムv3に従って、購入すべきレース・式別・点数の方針をまとめてください。
"""
    return ask_claude(LOTO5_SYSTEM_PROMPT, user_prompt, max_tokens=1500)


def main() -> None:
    target_date = _target_date()
    date_disp = f"{target_date[0:4]}/{target_date[4:6]}/{target_date[6:8]}"

    all_races: list[tuple[RaceInfo, bool]] = []  # (race, is_nar)

    nar_tracks = _target_nar_tracks()
    if nar_tracks is None:
        # 未指定 → その日開催しているNAR全競馬場を自動検出
        races = fetch_all_nar_races(target_date)
        all_races += [(r, True) for r in races]
    else:
        for track in nar_tracks:
            races = fetch_nar_races(target_date, track)
            all_races += [(r, True) for r in races]

    if _include_jra():
        races = fetch_jra_races(target_date, _target_jra_tracks())
        all_races += [(r, False) for r in races]

    if not all_races:
        print(f"{date_disp}: 対象競馬場のレース開催がありませんでした。処理を終了します。")
        return

    race_analyses: list[dict] = []
    for race, is_nar in all_races:
        print(f"分析中: {race.track} {race.race_no} {race.race_name} ({race.race_id})")
        analysis = analyze_race(race, nar=is_nar)
        race_analyses.append(
            {
                "track": race.track,
                "race_no": race.race_no,
                "race_name": race.race_name,
                "analysis": analysis,
            }
        )

    loto5_summary = build_loto5_summary(race_analyses) if race_analyses else ""

    # track_summaries を組み立て (note_format.format_keiba_draft用)
    tracks: dict[str, list[dict]] = {}
    for r in race_analyses:
        tracks.setdefault(r["track"], []).append(
            {
                "race_no": r["race_no"],
                "race_name": r["race_name"],
                "picks_markdown": r["analysis"],
            }
        )
    track_summaries = [{"track": t, "races": rs} for t, rs in tracks.items()]

    title, tags, body_md = format_keiba_draft(
        target_date=date_disp, track_summaries=track_summaries
    )
    if loto5_summary:
        body_md += "\n\n## Loto5戦略メモ（社内検討用・note非公開でも可）\n" + loto5_summary

    track_names = sorted({r.track for r, _ in all_races})
    issue_body = build_issue_body(
        kind="keiba-prediction",
        note_title=title,
        note_tags=tags,
        note_body_markdown=body_md,
        extra_notes=f"対象日: {date_disp} / 対象競馬場: {track_names}",
    )

    issue_url = create_draft_issue(title=f"[note下書き] {title}", body=issue_body)
    print(f"Issueを作成しました: {issue_url}")


if __name__ == "__main__":
    main()
