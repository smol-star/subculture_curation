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
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
        feed = feedparser.parse(data)
        return feed
    except Exception as e:
        print(f"  [헤더 방식 실패] {url}: {e}")
        # 폴백: feedparser 기본 파싱 시도
        try:
            return feedparser.parse(url)
        except Exception as e2:
            print(f"  [기본 방식도 실패] {url}: {e2}")
            return None

def fetch_rss_sources(limit_per_source=5):
    """
    무료 RSS 피드를 User-Agent 헤더와 함께 수집합니다.
    봇 차단을 피하기 위해 브라우저 헤더를 주입합니다.
    """
    sources = [
        # 미국 - 커뮤니티 (Reddit RSS는 .rss 엔드포인트 지원)
        {"name": "Reddit - r/gachagaming", "url": "https://www.reddit.com/r/gachagaming/hot.rss?limit=25", "country": "미국"},
        {"name": "Reddit - r/anime", "url": "https://www.reddit.com/r/anime/hot.rss?limit=25", "country": "미국"},
        {"name": "Reddit - r/gaming", "url": "https://www.reddit.com/r/gaming/hot.rss?limit=25", "country": "미국"},
        # 미국 - 전문 웹진 (안정적인 RSS)
        {"name": "Anime News Network", "url": "https://www.animenewsnetwork.com/all/rss.xml?ann-edition=us", "country": "미국"},
        {"name": "Gematsu (게임 뉴스)", "url": "https://www.gematsu.com/feed", "country": "미국"},
        # 일본 (영미권/현지 믹스)
        {"name": "Siliconera (일본겜 특화)", "url": "https://www.siliconera.com/feed/", "country": "일본"},
        {"name": "Famitsu (현지 원문)", "url": "https://www.famitsu.com/rss/fcom_all.rdf", "country": "일본"},
    ]

    raw_data = []

    for source in sources:
        print(f"  [{source['name']}] 수집 시도...")
        feed = safe_parse_rss(source['url'])

        if not feed or not feed.entries:
            print(f"  [{source['name']}] ⚠️ 데이터 없음 (스킵)")
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
            except Exception as e:
                print(f"  [{source['name']}] 개별 항목 파싱 오류: {e}")

        print(f"  [{source['name']}] ✅ {count}건 수집")

    print(f"\n[RSS 수집 완료] 총 {len(raw_data)}건")
    return raw_data

if __name__ == "__main__":
    records = fetch_rss_sources(3)
    for r in records:
        print(f"[{r['platform']}] {r['title'][:60]}")
