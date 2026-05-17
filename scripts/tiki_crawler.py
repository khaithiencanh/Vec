import requests
import time
import os
import csv
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "tiki_products.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://tiki.vn/",
}

KEYWORDS = [
    # Thời trang nam
    "áo thun nam", "áo sơ mi nam", "quần jean nam", "áo khoác nam", "quần short nam",
    # Thời trang nữ
    "váy nữ", "áo thun nữ", "quần jean nữ", "đầm dự tiệc", "áo khoác nữ",
    # Giày dép
    "giày thể thao", "giày sneaker nam", "giày cao gót", "dép nam", "giày sandal nữ",
    # Điện tử
    "điện thoại samsung", "tai nghe bluetooth", "tai nghe chống ồn", "loa bluetooth",
    "máy tính xách tay", "bàn phím cơ", "chuột gaming", "màn hình máy tính",
    # Phụ kiện
    "đồng hồ nam", "đồng hồ nữ", "balo laptop", "túi xách nữ", "ví nam",
    # Làm đẹp
    "son môi", "kem dưỡng da", "nước hoa", "mascara", "serum dưỡng da",
    # Sách
    "sách kỹ năng", "sách văn học", "sách kinh doanh", "sách thiếu nhi",
    # Thể thao
    "dụng cụ tập gym", "áo thể thao", "bình nước thể thao", "găng tay tập gym",
    # Nhà cửa
    "đèn led", "nồi chiên không dầu", "máy lọc không khí", "chăn ga gối",
    # Văn phòng
    "bút bi", "sổ tay", "balo học sinh",
]

PAGES_PER_KEYWORD = 5   # 5 trang x 40 sp = 200 sp/từ khóa
MAX_WORKERS = 8         # 8 thread chạy song song
DELAY = 0.3             # delay nhỏ giữa các request trong cùng thread

csv_lock = Lock()
seen_ids = set()
total_count = 0


def search_page(keyword: str, page: int) -> list[dict]:
    url = "https://tiki.vn/api/v2/products"
    params = {"limit": 40, "q": keyword, "page": page, "sort": "top_seller"}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        items = r.json().get("data", []) or []
        products = []
        for item in items:
            # Lấy ảnh thumbnail
            thumbnail = item.get("thumbnail_url", "") or ""
            if not thumbnail:
                badges = item.get("badges_new", []) or []
                for b in badges:
                    if b.get("image"):
                        thumbnail = b["image"]
                        break

            product = {
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
                "keyword": keyword,
                "url": f"https://tiki.vn/{item.get('url_key', '')}.html",
                "crawled_at": datetime.now().isoformat(),
            }
            products.append(product)
        return products
    except Exception as e:
        print(f"  [LỖI] '{keyword}' trang {page}: {e}")
        return []


def crawl_keyword(keyword: str) -> int:
    global total_count
    count = 0
    for page in range(1, PAGES_PER_KEYWORD + 1):
        products = search_page(keyword, page)
        if not products:
            break

        # Lọc trùng id
        new_products = []
        with csv_lock:
            for p in products:
                pid = str(p.get("id", ""))
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    new_products.append(p)

        if new_products:
            save_to_csv(new_products)
            count += len(new_products)
            total_count += len(new_products)

        time.sleep(DELAY)

    print(f"  ✓ '{keyword}': {count} sản phẩm (tổng: {total_count})")
    return count


def save_to_csv(products: list[dict]):
    if not products:
        return
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.exists(OUTPUT_FILE)
    with csv_lock:
        with open(OUTPUT_FILE, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=products[0].keys())
            if not file_exists:
                writer.writeheader()
            writer.writerows(products)


def crawl():
    # Xóa file cũ để crawl lại từ đầu
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        print("Đã xóa file cũ, crawl lại từ đầu\n")

    print(f"Crawl {len(KEYWORDS)} từ khóa x {PAGES_PER_KEYWORD} trang — {MAX_WORKERS} threads song song\n")
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(crawl_keyword, kw): kw for kw in KEYWORDS}
        for future in as_completed(futures):
            future.result()

    elapsed = time.time() - start
    print(f"\nHoàn thành! {total_count} sản phẩm trong {elapsed:.0f}s → {OUTPUT_FILE}")


if __name__ == "__main__":
    crawl()
