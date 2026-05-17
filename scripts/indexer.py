import os
import csv
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

CSV_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "tiki_products.csv")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma")
COLLECTION_NAME = "tiki_products"
BATCH_SIZE = 100  # Số sản phẩm embed mỗi lần gọi API

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)


def make_text(row: dict) -> str:
    """Tạo text đại diện cho sản phẩm để embed."""
    parts = []
    if row.get("name"):
        parts.append(f"Tên: {row['name']}")
    if row.get("keyword"):
        parts.append(f"Danh mục: {row['keyword']}")
    if row.get("brand"):
        parts.append(f"Thương hiệu: {row['brand']}")
    if row.get("price"):
        parts.append(f"Giá: {float(row['price']):,.0f} VND")
    if row.get("rating") and float(row.get("rating", 0)) > 0:
        parts.append(f"Đánh giá: {row['rating']}/5")
    if row.get("sold") and int(row.get("sold", 0)) > 0:
        parts.append(f"Đã bán: {row['sold']}")
    return " | ".join(parts)


def embed_batch(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


def load_csv() -> list[dict]:
    products = []
    with open(CSV_FILE, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("name"):  # Bỏ qua row trống
                products.append(row)
    return products


def index():
    print("Đọc CSV...")
    products = load_csv()
    print(f"  {len(products)} sản phẩm\n")

    # Tạo hoặc reset collection
    chroma_client.delete_collection(COLLECTION_NAME) if COLLECTION_NAME in [c.name for c in chroma_client.list_collections()] else None
    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    total = 0
    for i in range(0, len(products), BATCH_SIZE):
        batch = products[i : i + BATCH_SIZE]

        texts = [make_text(p) for p in batch]
        ids = [str(p["id"]) if p.get("id") else f"idx_{i+j}" for j, p in enumerate(batch)]
        metadatas = [
            {
                "name": p.get("name", ""),
                "price": float(p.get("price", 0) or 0),
                "original_price": float(p.get("original_price", 0) or 0),
                "discount": int(p.get("discount", 0) or 0),
                "rating": float(p.get("rating", 0) or 0),
                "sold": int(p.get("sold", 0) or 0),
                "brand": p.get("brand", ""),
                "keyword": p.get("keyword", ""),
                "thumbnail_url": p.get("thumbnail_url", ""),
                "url": p.get("url", ""),
            }
            for p in batch
        ]

        print(f"Embedding batch {i // BATCH_SIZE + 1} ({len(batch)} sản phẩm)...")
        embeddings = embed_batch(texts)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        total += len(batch)
        print(f"  Đã index {total}/{len(products)} sản phẩm")

    print(f"\nHoàn thành! {total} sản phẩm đã lưu vào ChromaDB tại {CHROMA_DIR}")


if __name__ == "__main__":
    index()
