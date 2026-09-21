"""shutuba_past.html (出馬表 5走成績表示) から、出走馬ごとの情報を取得する。

netkeibaの当該ページは以下のテーブル構造を持つ(2026年9月時点で確認済み、JRA/NAR共通):
    <table id="sort_table" class="Shutuba_Table Shutuba_Past5_Table ...">
      <tr> ... <th>枠</th><th>馬番</th><th>印</th><th>馬名/オッズ</th><th>騎手/斤量</th>
                <th>前走</th><th>2走</th><th>3走</th><th>4走</th><th>5走</th> ... </tr>
      <tr> <td class="Waku1">1</td><td class="Waku">1</td><td class="Horse_Select">--</td>
           <td class="Horse_Info">...</td><td class="Jockey">...</td>
           <td class="Past">...(前走の生テキスト)...</td>
           <td class="Rest">...(2走)...</td> ... </tr>
      ...
    </table>

サイト構造が変わった場合はこのファイルの `PAST_TABLE_ID` 及びセレクタを要修正。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

from fetch_race_list import HEADERS, REQUEST_TIMEOUT, REQUEST_INTERVAL_SEC

PAST_TABLE_ID = "sort_table"


@dataclass
class HorseEntry:
    waku: str
    umaban: str
    mark: str
    horse_name: str
    odds_ninki_text: str  # 例: "17.0 (6人気)"
    horse_info_raw: str  # Horse_Infoセル全文(血統・厩舎・脚質・馬体重など)
    jockey_raw: str  # 騎手・斤量
    past_races_raw: list[str]  # 前走〜5走の生テキスト(新しい順)


def fetch_shutuba_past_html(race_id: str, *, nar: bool) -> str:
    domain = "nar.netkeiba.com" if nar else "race.netkeiba.com"
    url = f"https://{domain}/race/shutuba_past.html?race_id={race_id}"
    time.sleep(REQUEST_INTERVAL_SEC)
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "euc-jp"
    return resp.text


def _extract_odds_ninki(horse_info_text: str) -> str:
    m = re.search(r"[\d.]+\s*\(\s*\d+\s*人気\s*\)", horse_info_text)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(0)).strip()


def parse_shutuba_past(html: str) -> list[HorseEntry]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id=PAST_TABLE_ID)
    if table is None:
        # フォールバック: id変更に備えてクラス名でも探す
        table = soup.find("table", class_=re.compile("Shutuba_Past5_Table"))
    if table is None:
        return []

    entries: list[HorseEntry] = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 5:
            continue  # ヘッダ行など

        waku = tds[0].get_text(strip=True)
        umaban = tds[1].get_text(strip=True)
        mark = tds[2].get_text(strip=True)

        horse_info_raw = tds[3].get_text("\n", strip=True)
        horse_name = horse_info_raw.split("\n")[0] if horse_info_raw else ""
        odds_ninki = _extract_odds_ninki(horse_info_raw)

        jockey_raw = tds[4].get_text("\n", strip=True)

        past_races_raw = [
            td.get_text("\n", strip=True) for td in tds[5:] if td.get_text(strip=True)
        ]

        entries.append(
            HorseEntry(
                waku=waku,
                umaban=umaban,
                mark=mark,
                horse_name=horse_name,
                odds_ninki_text=odds_ninki,
                horse_info_raw=horse_info_raw,
                jockey_raw=jockey_raw,
                past_races_raw=past_races_raw,
            )
        )
    return entries


def format_entries_for_prompt(entries: list[HorseEntry]) -> str:
    """Claudeへのプロンプトに埋め込みやすいテキストブロックに整形する。"""
    blocks = []
    for e in entries:
        lines = [
            f"■{e.umaban}番(枠{e.waku}) {e.horse_name}  オッズ:{e.odds_ninki_text or '不明'}",
            f"  馬情報: {e.horse_info_raw.replace(chr(10), ' / ')}",
            f"  騎手: {e.jockey_raw.replace(chr(10), ' ')}",
        ]
        for i, past in enumerate(e.past_races_raw, start=1):
            lines.append(f"  過去{i}走目: {past.replace(chr(10), ' / ')}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


if __name__ == "__main__":
    import sys

    race_id = sys.argv[1] if len(sys.argv) > 1 else "202609040701"
    is_nar = "--nar" in sys.argv
    html = fetch_shutuba_past_html(race_id, nar=is_nar)
    entries = parse_shutuba_past(html)
    print(format_entries_for_prompt(entries))
