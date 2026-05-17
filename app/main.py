import os, time
import numpy as np
import pandas as pd
import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(ROOT, ".env"))

CHROMA_DIR = os.path.join(ROOT, "data", "chroma")
CSV_FILE   = os.path.join(ROOT, "data", "raw", "tiki_products.csv")
COLLECTION = "tiki_products"

# ── Embedding: chạy local, hoàn toàn miễn phí ──
print("Đang load embedding model...")
_embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
print("Embedding model sẵn sàng!")

# ── LLM: Groq (miễn phí, nhanh, tương thích OpenAI SDK) ──
ai = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
LLM_MODEL = "llama-3.1-8b-instant"

chroma = chromadb.PersistentClient(path=CHROMA_DIR)
col    = chroma.get_collection(COLLECTION)
df     = pd.read_csv(CSV_FILE, encoding="utf-8-sig").dropna(subset=["name"])
for c in ["price","rating","sold"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

app = FastAPI()
STATIC = os.path.join(os.path.dirname(__file__), "..", "frontend", "static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def embed(text: str):
    return _embed_model.encode(text).tolist()

def vsearch(query: str, n: int = 8, category: str = ""):
    vec = embed(query)
    kwargs = dict(query_embeddings=[vec], n_results=min(n*3, 50),
                  include=["metadatas","distances"])
    if category:
        kwargs["where"] = {"keyword": {"$eq": category}}
    r = col.query(**kwargs)
    out = []
    seen = set()
    for i in range(len(r["ids"][0])):
        m = r["metadatas"][0][i]
        name = m.get("name", "")
        if name in seen:
            continue
        seen.add(name)
        out.append({**m, "similarity": round(1 - r["distances"][0][i], 3)})
    # Sort by similarity desc, deduplicated
    out.sort(key=lambda x: x["similarity"], reverse=True)
    return out[:n]


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))

@app.get("/api/stats")
def stats():
    return {
        "products": len(df),
        "categories": int(df["keyword"].nunique()),
        "vector_dim": 1536,
        "index": "HNSW",
        "metric": "Cosine"
    }

LAPTOP_KEYWORDS_LIST = ["laptop", "macbook", "máy tính xách tay", "notebook"]

@app.get("/api/products")
def products(page: int = 1, category: str = "", limit: int = 20, sort: str = "rating"):
    if category:
        fdf = df[df["keyword"] == category]
        # Nếu category là laptop → lọc thêm tên có chứa từ khóa laptop
        if category == "máy tính xách tay":
            pattern = "|".join(LAPTOP_KEYWORDS_LIST)
            fdf = fdf[fdf["name"].str.contains(pattern, case=False, na=False)]
    else:
        fdf = df.copy()

    if sort == "price_asc":
        fdf = fdf[fdf["price"] > 0].sort_values("price", ascending=True)
    elif sort == "price_desc":
        fdf = fdf[fdf["price"] > 0].sort_values("price", ascending=False)
    else:
        fdf = fdf[fdf["rating"] > 0].sort_values("rating", ascending=False)

    total = len(fdf)
    chunk = fdf.iloc[(page-1)*limit : page*limit]
    return {"total": total, "page": page, "items": chunk.fillna("").to_dict(orient="records")}

@app.get("/api/categories")
def categories():
    return sorted(df["keyword"].dropna().unique().tolist())

class SearchReq(BaseModel):
    query: str
    n: int = 8

@app.post("/api/search")
def search(req: SearchReq):
    t0 = time.time()
    try:
        query = req.query
        if len(query.split()) <= 3:
            expand_resp = ai.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role":"user","content":f'Mở rộng query tìm kiếm sản phẩm "{query}" thành mô tả chi tiết hơn (1 câu ngắn tiếng Việt, chỉ trả về câu đó):'}],
                max_tokens=60,
            )
            expanded = expand_resp.choices[0].message.content.strip()
            query = f"{req.query} {expanded}"
        results = vsearch(query, req.n)
        return {"results": results, "elapsed": round(time.time()-t0, 3), "query": query}
    except Exception as e:
        return {"results": [], "elapsed": 0, "query": req.query, "error": str(e)}

@app.post("/api/recommend")
def recommend(req: SearchReq):
    try:
        results = vsearch(req.query, req.n + 1)
        results = [r for r in results if r.get("name") != req.query][:req.n]
        return {"results": results}
    except Exception as e:
        return {"results": [], "error": str(e)}

class ChatReq(BaseModel):
    message: str
    history: list = []   # [{role: "user"|"assistant", content: "..."}]

def parse_intent(message: str) -> dict:
    """Phân tích intent: sản phẩm, danh mục, ngân sách, đối tượng."""
    known_cats = sorted(df["keyword"].dropna().unique().tolist())
    cats_str = "\n".join(f"- {c}" for c in known_cats)

    resp = ai.chat.completions.create(
        model=LLM_MODEL,
        messages=[{
            "role": "user",
            "content": f"""Phân tích yêu cầu mua sắm sau và trả về JSON.
Yêu cầu: "{message}"

Danh mục sản phẩm có sẵn trong hệ thống:
{cats_str}

Trả về JSON với các field:
- search_query: mô tả sản phẩm chi tiết để tìm kiếm ngữ nghĩa (không dùng tên danh mục, dùng đặc điểm sản phẩm)
- category: tên danh mục khớp CHÍNH XÁC từ danh sách trên (null nếu không rõ hoặc câu hỏi chung)
- max_price: ngân sách tối đa (số nguyên VND, null nếu không đề cập)
- min_price: giá tối thiểu (null nếu không đề cập)
- use_case: mục đích sử dụng ngắn gọn
- target: đối tượng (nam/nữ/sinh viên/...)

Ví dụ:
- "điện thoại tầm trung chụp ảnh đẹp" → {{"search_query":"smartphone màn hình đẹp camera tốt pin trâu","category":"điện thoại samsung","max_price":null,"min_price":null,"use_case":"chụp ảnh","target":""}}
- "sách kỹ năng hay" → {{"search_query":"sách phát triển bản thân tư duy kỹ năng sống","category":"sách kỹ năng","max_price":null,"min_price":null,"use_case":"đọc sách","target":""}}
- "laptop sinh viên 15 triệu" → {{"search_query":"laptop mỏng nhẹ pin tốt hiệu năng cao","category":"máy tính xách tay","max_price":15000000,"min_price":null,"use_case":"học tập","target":"sinh viên"}}
- "quà tặng bạn gái 500k" → {{"search_query":"quà tặng nữ thời trang phụ kiện dễ thương","category":null,"max_price":500000,"min_price":null,"use_case":"quà tặng","target":"nữ"}}

Chỉ trả về JSON, không giải thích."""
        }],
        max_tokens=250,
        response_format={"type": "json_object"},
    )
    import json
    try:
        return json.loads(resp.choices[0].message.content)
    except:
        return {"search_query": message, "category": None, "max_price": None, "min_price": None}

def vsearch_smart(query: str, n: int = 8, max_price: float = None,
                  min_price: float = None, category: str = None):
    """Search với filter danh mục + giá nếu có."""
    vec = embed(query)
    fetch_n = min(n * 5, 100)

    kwargs = dict(query_embeddings=[vec], n_results=fetch_n,
                  include=["metadatas", "distances"])

    # Xây dựng điều kiện where
    conditions = []
    if category:
        conditions.append({"keyword": {"$eq": category}})
    if max_price and min_price:
        conditions.append({"price": {"$lte": max_price}})
        conditions.append({"price": {"$gte": min_price}})
    elif max_price:
        conditions.append({"price": {"$lte": max_price}})
    elif min_price:
        conditions.append({"price": {"$gte": min_price}})

    if len(conditions) > 1:
        kwargs["where"] = {"$and": conditions}
    elif len(conditions) == 1:
        kwargs["where"] = conditions[0]

    try:
        r = col.query(**kwargs)
    except Exception:
        # Fallback: bỏ filter nếu lỗi (ví dụ category không tồn tại)
        kwargs.pop("where", None)
        r = col.query(**kwargs)

    out, seen = [], set()
    for i in range(len(r["ids"][0])):
        m = r["metadatas"][0][i]
        name = m.get("name", "")
        if name in seen:
            continue
        seen.add(name)
        price = float(m.get("price", 0) or 0)
        sim = round(1 - r["distances"][0][i], 3)
        if max_price and price <= max_price:
            sim = min(sim + 0.05, 1.0)
        out.append({**m, "similarity": sim})

    out.sort(key=lambda x: x["similarity"], reverse=True)
    return out[:n]

@app.post("/api/chat")
def chat(req: ChatReq):
    # Bước 1: Phân tích intent từ tin nhắn hiện tại
    intent = parse_intent(req.message)
    search_query = intent.get("search_query", req.message)
    max_price = intent.get("max_price")
    min_price = intent.get("min_price")

    # Bước 2: Smart search với filter danh mục + giá
    category = intent.get("category")
    hits = vsearch_smart(search_query, n=8, max_price=max_price,
                         min_price=min_price, category=category)

    # Bước 3: Build context sản phẩm
    budget_note = f"\nNgân sách: tối đa {int(max_price):,}đ" if max_price else ""
    context = "\n".join([
        f"[{i+1}] {h['name']} | Giá: {int(h.get('price',0) or 0):,}đ | "
        f"Rating: {h.get('rating',0)}/5 | Đã bán: {int(h.get('sold',0)):,} | "
        f"Thương hiệu: {h.get('brand','?')} | Danh mục: {h.get('keyword','')}"
        for i, h in enumerate(hits)
    ])

    system = """Bạn là trợ lý mua sắm ShopAI — thông minh, thân thiện, tư vấn bằng tiếng Việt.

Nguyên tắc:
1. CHỈ gợi ý sản phẩm có trong danh sách [1]..[8] được cung cấp, tuyệt đối không bịa
2. Nếu có ngân sách → loại ngay sản phẩm vượt giá, chỉ gợi ý trong tầm tiền
3. Giải thích NGẮN GỌN tại sao phù hợp (rating cao, bán chạy, thương hiệu tốt...)
4. Nhớ toàn bộ lịch sử hội thoại — nếu user hỏi "cái nào rẻ hơn?", "còn gì khác không?", "cái đầu tiên giá bao nhiêu?" thì trả lời dựa trên ngữ cảnh trước
5. Trả lời tự nhiên 2-3 câu, không liệt kê dài dòng
6. Không có sản phẩm phù hợp → thành thật nói và gợi ý từ khoá tìm kiếm khác"""

    # Ghép lịch sử hội thoại (tối đa 8 lượt gần nhất)
    messages = [{"role": "system", "content": system}]
    for h in req.history[-8:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})

    # Tin nhắn hiện tại kèm context sản phẩm
    user_content = f"Yêu cầu: {req.message}{budget_note}"
    if intent.get("use_case"): user_content += f"\nMục đích: {intent['use_case']}"
    if intent.get("target"):   user_content += f"\nĐối tượng: {intent['target']}"
    user_content += f"\n\nSản phẩm tìm được:\n{context}"
    messages.append({"role": "user", "content": user_content})

    response = ai.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=450,
    )
    return {
        "answer": response.choices[0].message.content,
        "sources": hits[:4],
        "intent": intent,
    }

@app.get("/api/keyword-search")
def keyword_search(q: str, n: int = 8):
    results = df[df["name"].str.contains(q, case=False, na=False)].head(n)
    return {"results": results.fillna("").to_dict(orient="records"), "total": len(results)}

_viz_cache = {}

@app.get("/api/visualize")
def visualize(n: int = 600, method: str = "umap"):
    cache_key = f"{n}_{method}"
    if cache_key in _viz_cache:
        return _viz_cache[cache_key]

    res  = col.get(limit=n, include=["embeddings","metadatas"])
    embs = np.array(res["embeddings"])

    if method == "umap":
        try:
            import umap
            reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
            xy = reducer.fit_transform(embs)
            variance = 100.0
        except ImportError:
            from sklearn.decomposition import PCA
            pca = PCA(n_components=2, random_state=42)
            xy = pca.fit_transform(embs)
            variance = float(pca.explained_variance_ratio_.sum()*100)
            method = "pca"
    else:
        from sklearn.decomposition import PCA
        pca = PCA(n_components=2, random_state=42)
        xy  = pca.fit_transform(embs)
        variance = float(pca.explained_variance_ratio_.sum()*100)

    points = [
        {"x": float(xy[i,0]), "y": float(xy[i,1]),
         "name": res["metadatas"][i].get("name","")[:50],
         "category": res["metadatas"][i].get("keyword","?"),
         "price": res["metadatas"][i].get("price", 0),
         "id": str(res["ids"][i])}
        for i in range(len(res["metadatas"]))
    ]
    result = {"points": points, "variance": variance, "method": method}
    _viz_cache[cache_key] = result
    return result

class VizQueryReq(BaseModel):
    query: str
    n: int = 600
    method: str = "umap"

@app.post("/api/visualize-query")
def visualize_query(req: VizQueryReq):
    """Embed query và trả về tọa độ gần đúng dựa trên nearest neighbors."""
    base = visualize(req.n, req.method)
    hits = vsearch(req.query, 8)
    hit_names = {h.get("name","")[:50] for h in hits}
    # Tính centroid của top hits trong viz space
    hit_pts = [p for p in base["points"] if p["name"] in hit_names]
    if hit_pts:
        cx = sum(p["x"] for p in hit_pts) / len(hit_pts)
        cy = sum(p["y"] for p in hit_pts) / len(hit_pts)
    else:
        cx = cy = 0.0
    return {
        "query_x": cx, "query_y": cy,
        "hit_names": list(hit_names),
        "hits": hits,
    }
