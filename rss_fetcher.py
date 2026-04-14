import feedparser
import urllib.request
import json
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# GitHub Actions 서버 환경에서 봇 차단을 피하기 위한 브라우저 User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_html(raw_html):
    if not raw_html:
        return "N/A"
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=' ', strip=True)
    return text[:1200]

def safe_parse_rss(url):
    """User-Agent 헤더를 주입하여 RSS 피드를 안전하게 파싱"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
        feed = feedparser.parse(data)
        return feed
    except Exception as e:
        print(f"  [수집 실패] {url}: {e}")
        return None

def fetch_rss_sources(limit_per_source=8):
    """
    무료 RSS 피드를 수집합니다. 각 소스별로 오류 처리를 독립적으로 수행하여
    하나의 사이트가 막혀도 전체 프로세스가 중단되지 않습니다.
    """
    sources = [
        {"name": "Reddit - r/gachagaming", "url": "https://www.reddit.com/r/gachagaming/hot.rss?limit=25", "country": "미국"},
        {"name": "Reddit - r/anime", "url": "https://www.reddit.com/r/anime/hot.rss?limit=25", "country": "미국"},
        {"name": "Reddit - r/gaming", "url": "https://www.reddit.com/r/gaming/hot.rss?limit=25", "country": "미국"},
        {"name": "Anime News Network", "url": "https://www.animenewsnetwork.com/all/rss.xml?ann-edition=us", "country": "미국"},
        {"name": "Gematsu (게임 뉴스)", "url": "https://www.gematsu.com/feed", "country": "미국"},
        {"name": "Siliconera (일본겜 특화)", "url": "https://www.siliconera.com/feed/", "country": "일본"},
        # 사용자가 요청한 패미통 주소 (RSS가 아닐 경우를 위해 에러 핸들링 강화)
        {"name": "Famitsu (패미통)", "url": "https://www.famitsu.com/", "country": "일본"},
    ]

    raw_data = []

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📋 총 {len(sources)}개 소스 수집 시작")
    print("-" * 50)

    for source in sources:
        try:
            print(f"  ▶ {source['name']} 수집 중...")
            feed = safe_parse_rss(source['url'])

            if not feed or not hasattr(feed, 'entries') or not feed.entries:
                print(f"    ⚠️ {source['name']}: 데이터가 없거나 유효한 RSS 피드가 아닙니다.")
                continue

            count = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    content = entry.get('content', [{'value': ''}])[0]['value'] if 'content' in entry else entry.get('summary', '')
                    clean_text = clean_html(content)

                    dt_utc = datetime.now(timezone.utc)
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        dt_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                    item = {
                        "source_country": source["country"],
                        "platform": source["name"],
                        "title": str(entry.get('title', '제목 없음')),
                        "content_url": str(entry.get('link', '#')),
                        "timestamp": dt_utc.strftime("%Y-%m-%d %H:%M:%S"),
                        "engagement_score": 0,
                        "raw_text": clean_text
                    }
                    raw_data.append(item)
                    count += 1
                except Exception as inner_e:
                    print(f"    ❌ 개별 항목 파싱 오류 ({entry.get('title','?')[:20]}...): {inner_e}")

            print(f"    ✅ {source['name']} 성공: {count}건 수집 완료 (현재 누적: {len(raw_data)}건)")

        except Exception as outer_e:
            print(f"    🚨 {source['name']} 중단 오류: {outer_e} (다음 소스로 건너뜁니다)")

    print("-" * 50)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🏁 최종 수집 완료: 총 {len(raw_data)}건")
    return raw_data

if __name__ == "__main__":
    fetch_rss_sources(2)
