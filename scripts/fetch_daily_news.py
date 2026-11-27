import os
import re
import json
import datetime
from zoneinfo import ZoneInfo
import requests
import feedparser

IST = ZoneInfo("Asia/Kolkata")
now_ist = datetime.datetime.now(IST)
today_str = now_ist.strftime("%Y-%m-%d")
month_str = now_ist.strftime("%Y-%m")

MARATHI_MONTHS = {
    1: "जानेवारी", 2: "फेब्रुवारी", 3: "मार्च", 4: "एप्रिल",
    5: "मे", 6: "जून", 7: "जुलै", 8: "ऑगस्ट",
    9: "सप्टेंबर", 10: "ऑक्टोबर", 11: "नोव्हेंबर", 12: "डिसेंबर"
}
mr_date_label = f"{now_ist.day} {MARATHI_MONTHS.get(now_ist.month, '')} {now_ist.year}"

RSS_FEEDS = [
    ("महाराष्ट्र व राज्य", "https://news.google.com/rss/search?q=%E0%A4%AE%E0%A4%B9%E0%A4%BE%E0%A4%B0%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%9F%E0%A5%8D%E0%A4%B0+%E0%A4%B6%E0%A4%BE%E0%A4%B8%E0%A4%A8+%E0%A4%A8%E0%A4%BF%E0%A4%B0%E0%A5%8D%E0%A4%A3%E0%A4%AF+%E0%A4%AF%E0%A5%8B%E0%A4%9C%E0%A4%A8%E0%A4%BE&hl=mr&gl=IN&ceid=IN:mr"),
    ("राष्ट्रीय व आंतरराष्ट्रीय", "https://news.google.com/rss/search?q=MPSC+%E0%A4%9A%E0%A4%BE%E0%A4%B2%E0%A5%82+%E0%A4%98%E0%A4%A1%E0%A4%BE%E0%A4%AE%E0%A5%8B%E0%A4%A1%E0%A5%80+%E0%A4%AD%E0%A4%BE%E0%A4%B0%E0%A4%A4&hl=mr&gl=IN&ceid=IN:mr"),
    ("पुरस्कार, क्रीडा व विज्ञान", "https://news.google.com/rss/search?q=%E0%A4%AA%E0%A5%81%E0%A4%B0%E0%A4%B8%E0%A5%8D%E0%A4%95%E0%A4%BE%E0%A4%B0+%E0%A4%95%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%A1%E0%A4%BE+%E0%A4%87%E0%A4%B8%E0%A5%8D%E0%A4%B0%E0%A5%8B+%E0%A4%AE%E0%A4%B0%E0%A4%BE%E0%A4%A0%E0%A5%80&hl=mr&gl=IN&ceid=IN:mr")
]

def clean_html_text(raw):
    txt = re.sub(r"<[^>]+>", " ", str(raw or ""))
    return re.sub(r"\s+", " ", txt).strip()

def fetch_live_news_items():
    collected = []
    seen_titles = set()
    for cat_label, feed_url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:4]:
                title = clean_html_text(entry.get("title", ""))
                summary = clean_html_text(entry.get("summary", "")) or title
                if not title:
                    continue
                clean_title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
                if clean_title in seen_titles:
                    continue
                seen_titles.add(clean_title)
                collected.append({
                    "id": f"DN-{today_str}-{len(collected)+1}",
                    "date": today_str,
                    "month": month_str,
                    "category": cat_label,
                    "title": clean_title,
                    "summary": summary[:320]
                })
                if len(collected) >= 6:
                    return collected
        except Exception as e:
            print(f"Feed error ({cat_label}):", e)
    return collected

def build_dinvishesh_entry():
    return {
        "id": f"DV-{today_str}-1",
        "date": today_str,
        "month": month_str,
        "category": "दिनविशेष",
        "title": f"दिनविशेष — {mr_date_label}",
        "summary": f"आज {mr_date_label} रोजीच्या महत्त्वाच्या ऐतिहासिक, सामाजिक, सांस्कृतिक व सामान्य ज्ञानाच्या नोंदींचा दैनंदिन आढावा."
    }

os.makedirs("daily-news", exist_ok=True)
archive_file = "daily-news/archive.json"
latest_file = "daily-news/latest.json"

existing = []
if os.path.exists(archive_file):
    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                existing = data
    except Exception:
        existing = []

fresh_items = fetch_live_news_items()
fresh_items.append(build_dinvishesh_entry())

existing_ids = {str(x.get("id", "")).strip() for x in existing}
existing_keys = {f"{x.get('date','')}||{x.get('title','')}" for x in existing}

added_now = []
for item in fresh_items:
    k = f"{item.get('date','')}||{item.get('title','')}"
    if item["id"] not in existing_ids and k not in existing_keys:
        existing.insert(0, item)
        existing_ids.add(item["id"])
        existing_keys.add(k)
        added_now.append(item)

with open(archive_file, "w", encoding="utf-8") as f:
    json.dump(existing[:500], f, ensure_ascii=False, indent=2)

with open(latest_file, "w", encoding="utf-8") as f:
    json.dump(existing[:40], f, ensure_ascii=False, indent=2)

print(f"Total archive items: {len(existing)}, added today: {len(added_now)}")

sb_url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
sb_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
if sb_url and sb_key and added_now:
    try:
        resp = requests.post(
            f"{sb_url}/rest/v1/mpsc_daily_news?on_conflict=id",
            headers={
                "apikey": sb_key,
                "Authorization": f"Bearer {sb_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            },
            json=added_now,
            timeout=20
        )
        print("Supabase mpsc_daily_news status:", resp.status_code)
    except Exception as e:
        print("Supabase sync error:", e)
