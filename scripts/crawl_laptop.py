"""Crawl thêm laptop vào CSV hiện tại, không xóa data cũ."""
import requests, time, os, csv
from datetime import datetime
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "tiki_products.csv")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

LAPTOP_KEYWORDS = [
    "laptop sinh viên", "laptop gaming", "laptop văn phòng",
    "macbook", "laptop dell", "laptop asus", "laptop hp", "laptop lenovo",
    "laptop acer", "laptop msi", "laptop 15 inch", "laptop i5", "laptop i7",
    "laptop giá rẻ", "máy tính xách tay sinh viên",
]

PAGES = 5
WORKERS = 6
DELAY = 0.3

csv_lock = Lock()
seen_ids = set()
total = 0


def load_existing_ids():
    """Đọc ID đã có trong CSV để tránh trùng."""
    if not os.path.exists(OUTPUT_FILE):
        return
    with open(OUTPUT_FILE, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("id"):
                seen_ids.add(str(row["id"]))
    print(f"  Đã load {len(seen_ids)} ID cũ\n")


def fetch(keyword, page):
    try:
        r = requests.get("https://tiki.vn/api/v2/products",
            headers=HEADERS,
            params={"limit": 40, "q": keyword, "page": page, "sort": "top_seller"},
            timeout=15)
        r.raise_for_status()
        items = r.json().get("data", []) or []
        out = []
        for item in items:
            thumbnail = item.get("thumbnail_url", "") or ""
            out.append({
                "id": item.get("id"),
                "name": item.get("name", ""),
                "price": item.get("price", 0),
                "original_price": item.get("original_price", 0),
                "discount": item.get("discount", 0),
                "rating": item.get("rating_average", 0),
                "review_count": item.get("review_count", 0),
                "sold": item.get("quantity_sold", {}).get("value", 0) if item.get("quantity_sold") else 0,
                "brand": item.get("brand_name", ""),
                "thumbnail_url": thumbnail,
                "short_description": item.get("short_description", ""),
                "keyword": "máy tính xách tay",   # Gom vào category laptop
                "url": f"https://tiki.vn/{item.get('url_key', '')}.html",
                "crawled_at": datetime.now().isoformat(),
            })
        return out
    except Exception as e:
        print(f"  [LỖI] {keyword} p{page}: {e}")
        return []


def save(products):
    if not products:
        return
    file_exists = os.path.exists(OUTPUT_FILE)
    with csv_lock:
        with open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=products[0].keys())
            if not file_exists:
                writer.writeheader()
            writer.writerows(products)


def crawl_kw(keyword):
    global total
    count = 0
    for page in range(1, PAGES + 1):
        products = fetch(keyword, page)
        if not products:
            break
        new = []
        with csv_lock:
            for p in products:
                pid = str(p.get("id", ""))
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    new.append(p)
        if new:
            save(new)
            count += len(new)
            total += len(new)
        time.sleep(DELAY)
    print(f"  ✓ '{keyword}': +{count} sản phẩm (tổng mới: {total})")
    return count


def main():
    load_existing_ids()
    print(f"Crawl {len(LAPTOP_KEYWORDS)} keyword laptop — {WORKERS} threads\n")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(crawl_kw, kw): kw for kw in LAPTOP_KEYWORDS}
        for f in as_completed(futures):
            f.result()
    print(f"\nXong! Thêm {total} laptop mới → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
