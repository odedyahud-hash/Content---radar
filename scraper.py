"""
Content Radar — סורק תוכן אישי
סורק ספרים חדשים, מאמרי מערכת וכתבי עת, ושולח עדכון יומי במייל
"""

import os
import json
import hashlib
import smtplib
import feedparser
import requests
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from pathlib import Path

# ─── קובץ מצב (מה כבר נראה) ───────────────────────────────────────────────
STATE_FILE = Path("seen_items.json")

def load_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()

def save_seen(seen: set):
    STATE_FILE.write_text(json.dumps(list(seen)))

def item_id(url: str, title: str) -> str:
    return hashlib.md5(f"{url}|{title}".encode()).hexdigest()

# ─── RSS (עיתונות אמריקאית) ────────────────────────────────────────────────
RSS_SOURCES = [
    {
        "name": "Washington Post — מאמרי מערכת",
        "url": "https://feeds.washingtonpost.com/rss/opinions",
        "filter": "Editorial Board",   # מסנן רק מאמרי מערכת, לא כל דעה
    },
    {
        "name": "New York Times — דעות",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml",
        "filter": None,
    },
    {
        "name": "Wall Street Journal — דעות",
        "url": "https://feeds.content.dowjones.io/public/rss/RSSOpinion",
        "filter": None,
    },
]

def fetch_rss(source: dict) -> list:
    results = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            author = entry.get("author", "")
            # אם יש סינון — בדוק שהמחבר תואם
            if source["filter"] and source["filter"].lower() not in author.lower():
                continue
            results.append({
                "source": source["name"],
                "title": title,
                "author": author,
                "url": link,
            })
    except Exception as e:
        print(f"שגיאה ב-{source['name']}: {e}")
    return results

# ─── SCRAPING (הוצאות ישראליות וכתבי עת) ──────────────────────────────────
SCRAPE_SOURCES = [
    # הוצאות ספרים
    {
        "name": "הוצאת מאגנס",
        "url": "https://www.magnespress.co.il/books?sort=date_desc",
        "item_selector": ".product-item, .book-item, article",
        "title_selector": "h2, h3, .title",
        "link_selector": "a",
        "base_url": "https://www.magnespress.co.il",
    },
    {
        "name": "הוצאת אוניברסיטת תל אביב",
        "url": "https://www.tau.ac.il/yediot/",
        "item_selector": ".book, article, .product",
        "title_selector": "h2, h3, .title",
        "link_selector": "a",
        "base_url": "https://www.tau.ac.il",
    },
    {
        "name": "הוצאת אוניברסיטת בר אילן",
        "url": "https://bip.co.il/new-books/",
        "item_selector": "article, .book-item, .product-item",
        "title_selector": "h2, h3, .entry-title",
        "link_selector": "a",
        "base_url": "https://bip.co.il",
    },
    {
        "name": "הוצאת מכון שז״ר",
        "url": "https://www.shazarbooks.org.il/new-books/",
        "item_selector": "article, .book, .product",
        "title_selector": "h2, h3, .title",
        "link_selector": "a",
        "base_url": "https://www.shazarbooks.org.il",
    },
    {
        "name": "הוצאת עם עובד",
        "url": "https://www.am-oved.co.il/category/new/",
        "item_selector": "article, .book-item, .product",
        "title_selector": "h2, h3, .title",
        "link_selector": "a",
        "base_url": "https://www.am-oved.co.il",
    },
    {
        "name": "הוצאת ידיעות אחרונות",
        "url": "https://www.ybook.co.il/new-books",
        "item_selector": "article, .book, .product-item",
        "title_selector": "h2, h3, .title",
        "link_selector": "a",
        "base_url": "https://www.ybook.co.il",
    },
    {
        "name": "הוצאת שלם",
        "url": "https://www.shalem.org.il/publications/books/",
        "item_selector": "article, .book, .publication",
        "title_selector": "h2, h3, .title",
        "link_selector": "a",
        "base_url": "https://www.shalem.org.il",
    },
    {
        "name": "הוצאת רסלינג",
        "url": "https://www.resling.co.il/new-books/",
        "item_selector": "article, .book-item, .product",
        "title_selector": "h2, h3, .title",
        "link_selector": "a",
        "base_url": "https://www.resling.co.il",
    },
    # כתבי עת
    {
        "name": "משפטים — האוניברסיטה העברית",
        "url": "https://lawjournal.huji.ac.il",
        "item_selector": "article, .article, .publication, li",
        "title_selector": "h2, h3, .title, a",
        "link_selector": "a",
        "base_url": "https://lawjournal.huji.ac.il",
    },
    {
        "name": "שנתון המשפט העברי",
        "url": "https://law.huji.ac.il/shnaton",
        "item_selector": "article, .article, li",
        "title_selector": "h2, h3, a",
        "link_selector": "a",
        "base_url": "https://law.huji.ac.il",
    },
    {
        "name": "עיוני משפט — אוניברסיטת תל אביב",
        "url": "https://www.tau.ac.il/law/iyunei-mishpat/",
        "item_selector": "article, .article, li",
        "title_selector": "h2, h3, a",
        "link_selector": "a",
        "base_url": "https://www.tau.ac.il",
    },
    {
        "name": "דיני ישראל — אוניברסיטת תל אביב",
        "url": "https://www.tau.ac.il/law/dine-israel/",
        "item_selector": "article, .article, li",
        "title_selector": "h2, h3, a",
        "link_selector": "a",
        "base_url": "https://www.tau.ac.il",
    },
    {
        "name": "מחקרי משפט — אוניברסיטת בר אילן",
        "url": "https://law.biu.ac.il/he/mishpat",
        "item_selector": "article, .article, li",
        "title_selector": "h2, h3, a",
        "link_selector": "a",
        "base_url": "https://law.biu.ac.il",
    },
    {
        "name": "תרביץ — האוניברסיטה העברית",
        "url": "https://tarbiz.huji.ac.il",
        "item_selector": "article, .article, li",
        "title_selector": "h2, h3, a",
        "link_selector": "a",
        "base_url": "https://tarbiz.huji.ac.il",
    },
    {
        "name": "דעות — נאמני תורה ועבודה",
        "url": "https://www.ne.org.il/category/deot/",
        "item_selector": "article, .post",
        "title_selector": "h2, h3, .entry-title",
        "link_selector": "a",
        "base_url": "https://www.ne.org.il",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ContentRadar/1.0; personal RSS reader)"
}

def fetch_scrape(source: dict) -> list:
    results = []
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select(source["item_selector"])[:30]
        seen_titles = set()

        for item in items:
            # חיפוש כותרת
            title_el = item.select_one(source["title_selector"])
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 4 or title in seen_titles:
                continue
            seen_titles.add(title)

            # חיפוש קישור
            link_el = item.select_one(source["link_selector"])
            link = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("http"):
                    link = href
                elif href.startswith("/"):
                    link = source["base_url"] + href
                else:
                    link = source["base_url"] + "/" + href

            if not link:
                link = source["url"]

            results.append({
                "source": source["name"],
                "title": title,
                "author": "",
                "url": link,
            })
    except Exception as e:
        print(f"שגיאה ב-{source['name']}: {e}")
    return results

# ─── סינון חדשים ──────────────────────────────────────────────────────────
def filter_new(items: list, seen: set) -> tuple[list, set]:
    new_items = []
    new_seen = set()
    for item in items:
        iid = item_id(item["url"], item["title"])
        if iid not in seen:
            new_items.append(item)
            new_seen.add(iid)
    return new_items, new_seen

# ─── בניית אימייל HTML ────────────────────────────────────────────────────
def build_email_html(new_items: list) -> str:
    today = date.today().strftime("%d.%m.%Y")
    
    # קיבוץ לפי מקור
    by_source = {}
    for item in new_items:
        by_source.setdefault(item["source"], []).append(item)

    sections = ""
    for source, items in by_source.items():
        rows = ""
        for item in items:
            author_str = f"<span style='color:#666;font-size:13px'> — {item['author']}</span>" if item["author"] else ""
            rows += f"""
            <tr>
              <td style="padding:8px 0; border-bottom:1px solid #f0f0f0;">
                <a href="{item['url']}" style="color:#1a1a8c;text-decoration:none;font-size:15px">{item['title']}</a>
                {author_str}
              </td>
            </tr>"""

        sections += f"""
        <div style="margin-bottom:28px">
          <h2 style="font-size:16px;color:#444;border-right:4px solid #1a1a8c;padding-right:10px;margin-bottom:12px">{source}</h2>
          <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        </div>"""

    if not sections:
        sections = "<p style='color:#888'>אין פריטים חדשים היום.</p>"

    return f"""
    <html dir="rtl"><body style="font-family:Arial,sans-serif;max-width:650px;margin:auto;padding:20px;color:#222">
      <div style="background:#1a1a8c;color:white;padding:16px 20px;border-radius:6px;margin-bottom:24px">
        <h1 style="margin:0;font-size:20px">📚 רדאר תוכן — {today}</h1>
        <p style="margin:4px 0 0;font-size:13px;opacity:0.85">{len(new_items)} פריטים חדשים</p>
      </div>
      {sections}
      <p style="font-size:11px;color:#aaa;margin-top:30px;text-align:center">נשלח אוטומטית על ידי Content Radar</p>
    </body></html>
    """

# ─── שליחת אימייל ────────────────────────────────────────────────────────
def send_email(html: str, count: int):
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    recipient = os.environ["EMAIL_RECIPIENT"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📚 רדאר תוכן — {count} פריטים חדשים ({date.today().strftime('%d.%m.%Y')})"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"✅ אימייל נשלח ל-{recipient}")

# ─── הרצה ראשית ──────────────────────────────────────────────────────────
def main():
    print(f"🔍 מתחיל סריקה — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    seen = load_seen()
    all_items = []

    # RSS
    for source in RSS_SOURCES:
        print(f"  RSS: {source['name']}")
        all_items.extend(fetch_rss(source))

    # Scraping
    for source in SCRAPE_SOURCES:
        print(f"  Scraping: {source['name']}")
        all_items.extend(fetch_scrape(source))

    print(f"סה״כ נמצאו: {len(all_items)} פריטים")

    new_items, new_seen = filter_new(all_items, seen)
    print(f"פריטים חדשים: {len(new_items)}")

    if new_items:
        html = build_email_html(new_items)
        send_email(html, len(new_items))
        save_seen(seen | new_seen)
    else:
        print("אין חדש — אימייל לא נשלח")
        # עדכן בכל מקרה כדי למנוע שליחה כפולה בהרצה הבאה
        save_seen(seen | new_seen)

if __name__ == "__main__":
    main()
