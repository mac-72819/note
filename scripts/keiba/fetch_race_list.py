"""netkeibaのレース一覧ページから、指定日の開催レースを取得する。

対応:
  - JRA中央競馬: race.netkeiba.com
  - 地方競馬(NAR): nar.netkeiba.com （競馬場ごとに kaisai_id が異なるため2段階で取得）

注意:
  レース情報の本体は "race_list_sub.html" という別URLからJavaScript経由で
  読み込まれる仕組みになっているため、race_list.html ではなく race_list_sub.html を
  直接取得する必要がある(race_list.htmlは外枠だけで中身が空)。
  netkeibaのページ構造は予告なく変更されることがある。取得件数が0件になる場合は
  まずこのファイルのセレクタ(クラス名)やURL形式を実際のページと突き合わせて更新すること。
  また、GitHub Actionsの実行環境(海外データセンターのIP)からのアクセスが
  弾かれる/CAPTCHA化される可能性がある点は既知のリスクとしてREADMEに明記している。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"}
REQUEST_TIMEOUT = 20
REQUEST_INTERVAL_SEC = 1.5  # サイト負荷軽減のための最低待機時間


@dataclass
class RaceInfo:
    race_id: str
    race_no: str  # "1R" など
    race_name: str  # 例: "2歳未勝利"
    start_time: str  # 例: "10:00"
    course: str  # 例: "ダ1800m"
    head_count: str  # 例: "8頭"
    track: str  # 例: "阪神" / "佐賀"


def _get(url: str) -> str:
    time.sleep(REQUEST_INTERVAL_SEC)
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "euc-jp"
    return resp.text


def _parse_race_list_html(html: str) -> list[RaceInfo]:
    soup = BeautifulSoup(html, "html.parser")
    races: list[RaceInfo] = []

    for dl in soup.select("dl.RaceList_DataList"):
        title_el = dl.select_one("p.RaceList_DataTitle")
        if not title_el:
            continue
        # 例: "4回 阪神 7日目" -> 競馬場名だけを抜き出す
        title_text = " ".join(title_el.stripped_strings)
        track_match = re.sub(r"^\d+回\s*", "", title_text)
        track_match = re.sub(r"\s*\d+日目$", "", track_match).strip()

        for li in dl.select("li.RaceList_DataItem"):
            a = li.find("a", href=True)
            if not a:
                continue
            m = re.search(r"race_id=(\d+)", a["href"])
            if not m:
                continue
            race_id = m.group(1)

            race_num_el = li.select_one("div.Race_Num")
            race_no = ""
            if race_num_el:
                race_no = "".join(
                    s for s in race_num_el.stripped_strings if s.endswith("R")
                ) or race_num_el.get_text(strip=True)

            race_name_el = li.select_one("span.ItemTitle")
            race_name = race_name_el.get_text(strip=True) if race_name_el else ""

            time_el = li.select_one("span.RaceList_Itemtime")
            start_time = time_el.get_text(strip=True) if time_el else ""

            course_el = li.select_one("span.RaceList_ItemLong")
            course = course_el.get_text(strip=True) if course_el else ""

            head_el = li.select_one("span.RaceList_Itemnumber")
            head_count = head_el.get_text(strip=True) if head_el else ""

            races.append(
                RaceInfo(
                    race_id=race_id,
                    race_no=race_no,
                    race_name=race_name,
                    start_time=start_time,
                    course=course,
                    head_count=head_count,
                    track=track_match,
                )
            )
    return races


def fetch_jra_races(kaisai_date: str, track_names: list[str] | None = None) -> list[RaceInfo]:
    """JRA中央競馬の指定日のレース一覧を取得する。kaisai_date は 'YYYYMMDD'。

    track_names: ["阪神", "中山"] のように競馬場名を指定すると、その競馬場だけに絞り込む。
    Noneまたは空リストの場合は、その日開催している全競馬場を返す。
    """
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={kaisai_date}"
    html = _get(url)
    races = _parse_race_list_html(html)
    if track_names:
        races = [r for r in races if r.track in track_names]
    return races


def _find_nar_track_kaisai_ids(html: str) -> dict[str, str]:
    """NARのレース一覧ページから「競馬場名 -> kaisai_id」の対応を取得する。"""
    soup = BeautifulSoup(html, "html.parser")
    mapping: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"[?&]kaisai_id=(\d+)", href)
        if m and "rf=race_list" in href:
            name = a.get_text(strip=True)
            if name:
                mapping[name] = m.group(1)
    return mapping


def fetch_all_nar_races(kaisai_date: str) -> list[RaceInfo]:
    """地方競馬(NAR)の指定日に開催している「全競馬場」のレースを自動検出して取得する。

    その日のトップページに表示される競馬場タブ(水沢・金沢・佐賀 等)をすべて検出し、
    競馬場ごとにレース一覧を取得して結合する。競馬場を指定する必要はない。
    """
    base_url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={kaisai_date}"
    html = _get(base_url)

    track_ids = _find_nar_track_kaisai_ids(html)
    if not track_ids:
        return []

    all_races: list[RaceInfo] = []
    for track_name, kaisai_id in track_ids.items():
        url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_id={kaisai_id}&kaisai_date={kaisai_date}"
        html2 = _get(url)
        all_races += _parse_race_list_html(html2)
    return all_races


def fetch_nar_races(kaisai_date: str, track_name: str) -> list[RaceInfo]:
    """地方競馬(NAR)の指定日・指定競馬場のレース一覧を取得する。

    track_name: "佐賀" "大井" "船橋" など、その日のタブに表示される競馬場名と完全一致させる。
    該当競馬場がその日開催していない場合は空リストを返す。
    """
    base_url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={kaisai_date}"
    html = _get(base_url)

    track_ids = _find_nar_track_kaisai_ids(html)
    if track_name not in track_ids:
        # その日は指定競馬場の開催が無い
        return []

    kaisai_id = track_ids[track_name]
    url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_id={kaisai_id}&kaisai_date={kaisai_date}"
    html2 = _get(url)
    return _parse_race_list_html(html2)


def shutuba_past_url(race_id: str, *, nar: bool) -> str:
    domain = "nar.netkeiba.com" if nar else "race.netkeiba.com"
    return f"https://{domain}/race/shutuba_past.html?race_id={race_id}"


if __name__ == "__main__":
    import sys
    import json

    date = sys.argv[1] if len(sys.argv) > 1 else "20260921"
    track = sys.argv[2] if len(sys.argv) > 2 else None
    if track:
        result = fetch_nar_races(date, track)
    else:
        result = fetch_jra_races(date)
    print(json.dumps([r.__dict__ for r in result], ensure_ascii=False, indent=2))
