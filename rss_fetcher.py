import feedparser
from datetime import datetime, timezone
import re
from bs4 import BeautifulSoup

def clean_html(raw_html):
    if not raw_html:
        return "N/A"
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=' ', strip=True)
    return text[:1000]

def fetch_rss_sources(limit_per_source=5):
    """
    무료 RSS 피드를 활용하여 서브컬처 정보를 수집합니다.
    """
    sources = [
        {"name": "Reddit - r/gachagaming", "url": "https://www.reddit.com/r/gachagaming/hot.rss", "country": "미국"},
        {"name": "Reddit - r/anime", "url": "https://www.reddit.com/r/anime/hot.rss", "country": "미국"},
        {"name": "Anime News Network", "url": "https://www.animenewsnetwork.com/all/rss.xml", "country": "미국"},
        {"name": "Polygon Gaming", "url": "https://www.polygon.com/rss/index.xml", "country": "미국"}
    ]
    
    raw_data = []
    
    for source in sources:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {source['name']} RSS 파싱 중...")
        try:
            feed = feedparser.parse(source['url'])
            for entry in feed.entries[:limit_per_source]:
                # 레딧의 경우 URL에서 포스트 ID나 기본 정보를 얻을 수 있음.
                score = 0
                
                # 원문 내용 (HTML 태그 제거)
                content = entry.get('content', [{'value': ''}])[0]['value'] if 'content' in entry else entry.get('summary', '')
                clean_text = clean_html(content)
                
                dt_utc = datetime.now(timezone.utc)
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    dt_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                
                item = {
                    "source_country": source["country"],
                    "platform": source["name"],
                    "title": entry.title,
                    "content_url": entry.link,
                    "timestamp": dt_utc.strftime("%Y-%m-%d %H:%M:%S"),
                    "engagement_score": score,  # RSS에서는 기본적으로 트래픽 수를 알 수 없어 0으로 처리
                    "raw_text": clean_text
                }
                raw_data.append(item)
        except Exception as e:
            print(f"[RSS Fetch Error - {source['name']}]: {e}")
            
    print(f"[RSS] 총 {len(raw_data)}건의 데이터를 성공적으로 수집했습니다.")
    return raw_data

if __name__ == "__main__":
    records = fetch_rss_sources(2)
    for r in records:
        print(f"[{r['platform']}] {r['title']}")
