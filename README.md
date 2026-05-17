# ShopAI – Vector Database Demo

Ứng dụng demo **RAG pipeline** và **Vector Database** áp dụng vào hệ thống thương mại điện tử, mô phỏng giao diện Shopee/Tiki. Dữ liệu sản phẩm thực từ Tiki, tìm kiếm ngữ nghĩa bằng ChromaDB + OpenAI Embeddings.

---

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Backend | FastAPI (Python) |
| Vector Database | ChromaDB (HNSW index, Cosine Similarity) |
| Embedding Model | OpenAI `text-embedding-3-small` (1,536 chiều) |
| LLM | OpenAI `gpt-4o-mini` |
| Frontend | HTML + CSS + JavaScript (thuần) |
| Dữ liệu | Tiki API (crawl ~7,000+ sản phẩm) |

---

## Yêu cầu

- Python 3.10+
- Node.js (không bắt buộc, chỉ dùng nếu build frontend)
- OpenAI API Key

---

## Cài đặt

```bash
# 1. Clone project
git clone <repo-url>
cd shopai

# 2. Tạo môi trường ảo
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Tạo file .env
echo OPENAI_API_KEY=sk-... > .env
```

---

## Flow chạy

### Bước 1 — Thu thập dữ liệu (Crawl)

Crawl sản phẩm từ Tiki API, lưu vào CSV:

```bash
# Crawl toàn bộ danh mục (~7,000 sản phẩm)
python scripts/tiki_crawler.py


> Dữ liệu lưu tại: `data/raw/tiki_products.csv`

---

### Bước 2 — Tạo Embedding & Đánh chỉ mục vào Vector DB (Index)

Chuyển đổi từng sản phẩm thành vector 1,536 chiều và lưu vào ChromaDB:

```bash
python scripts/indexer.py
```

Quá trình này sẽ:
1. Đọc CSV → tạo text mô tả cho mỗi sản phẩm
2. Gọi OpenAI Embeddings API theo batch 100 sản phẩm
3. Lưu vector + metadata vào ChromaDB với HNSW index

> Vector DB lưu tại: `data/chroma/`

---

### Bước 3 — Chạy ứng dụng

```bash
uvicorn app.main:app --reload
```

Mở trình duyệt: **http://localhost:8000**

---

## Cấu trúc thư mục

```
shopai/
├── app/
│   └── main.py              # FastAPI backend + toàn bộ API
├── frontend/
│   └── static/
│       ├── index.html       # Giao diện chính
│       ├── style.css        # CSS
│       └── app.js           # JavaScript
├── scripts/
│   ├── tiki_crawler.py      # Crawl toàn bộ danh mục
│   ├── crawl_laptop.py      # Crawl thêm laptop
│   └── indexer.py           # Tạo embedding + lưu ChromaDB
├── data/
│   ├── raw/
│   │   └── tiki_products.csv
│   └── chroma/              # Vector DB (tự tạo sau khi index)
├── .env                     # OPENAI_API_KEY
└── requirements.txt
```

---

## RAG Pipeline — 5 bước hoạt động

```
┌─────────────────────────────────────────────────────────┐
│                     RAG PIPELINE                        │
│                                                         │
│  Bước 1: EMBEDDING                                      │
│  Sản phẩm Tiki → make_text() → OpenAI Embedding API    │
│  → Vector 1,536 chiều                                   │
│                         │                               │
│  Bước 2: INDEXING       ▼                               │
│  Vector → ChromaDB → HNSW Index (Cosine Similarity)    │
│                         │                               │
│  Bước 3: QUERY          ▼                               │
│  User input → GPT parse intent → embed(query)          │
│  → Query vector 1,536 chiều                             │
│                         │                               │
│  Bước 4: SIMILARITY SEARCH ▼                            │
│  ChromaDB.query() → Cosine Distance → Top-K results    │
│  + Filter: category, max_price, min_price              │
│                         │                               │
│  Bước 5: RAG ANSWER     ▼                               │
│  Top-K products + chat history → GPT-4o-mini           │
│  → Câu trả lời tư vấn dựa trên dữ liệu thực            │
└─────────────────────────────────────────────────────────┘
```

---

## API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/` | Trang chủ |
| GET | `/api/products` | Danh sách sản phẩm (phân trang) |
| GET | `/api/categories` | Danh sách danh mục |
| GET | `/api/stats` | Thống kê Vector DB |
| POST | `/api/search` | **Semantic search** (Vector DB) |
| POST | `/api/recommend` | **Gợi ý tương tự** (Vector DB) |
| POST | `/api/chat` | **RAG Chatbot** (Intent + Vector + GPT) |

---

## Tính năng nổi bật

### Semantic Search
Tìm kiếm theo ngữ nghĩa — không cần đúng từ khóa:
- `"quần áo mùa đông ấm áp"` → tìm được áo khoác, áo phao
- `"thiết bị nghe nhạc không dây"` → tìm được tai nghe Bluetooth

### Similar Products
Mỗi sản phẩm có phần *Sản phẩm tương tự* — ChromaDB tìm vector gần nhất trong không gian toán học, không cần trùng từ khóa hay cùng danh mục.

### RAG Chatbot
Chatbot hiểu ngữ cảnh hội thoại:
- Parse intent: tách loại sản phẩm, ngân sách, đối tượng từ câu hỏi tự nhiên
- Filter theo giá + danh mục trước khi tìm vector
- Ghi nhớ lịch sử 8 lượt hội thoại — hỏi tiếp "cái nào rẻ hơn?" vẫn hiểu đúng

### Similarity Score
Mỗi kết quả tìm kiếm hiển thị thanh `% match` — đây là giá trị **Cosine Similarity** thực tế từ ChromaDB.

---

## So sánh với Industry

| Tính năng | Project | Công ty thực tế |
|---|---|---|
| Semantic Search | ChromaDB + OpenAI | Elasticsearch, Pinecone (Amazon, Shopee) |
| Recommendation | Vector similarity | Netflix, Spotify, Pinterest |
| RAG Chatbot | GPT-4o-mini + context | ChatGPT Enterprise, Notion AI |
| Filtered ANN Search | Category + price filter | Airbnb, Booking.com, LinkedIn |

---

## requirements.txt

```
fastapi
uvicorn[standard]
openai
chromadb
pandas
numpy
python-dotenv
requests
scikit-learn
```
