import os, time
import numpy as np
import pandas as pd
import plotly.express as px
import chromadb
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(ROOT, ".env"))

CHROMA_DIR = os.path.join(ROOT, "data", "chroma")
CSV_FILE   = os.path.join(ROOT, "data", "raw", "tiki_products.csv")
COLLECTION = "tiki_products"

st.set_page_config(page_title="ShopAI – Vector DB Demo", page_icon="🛍️", layout="wide")

# ── GLOBAL CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Header */
.hero { background: linear-gradient(135deg,#1565C0,#0288D1);
        color:white; padding:28px 32px; border-radius:16px; margin-bottom:24px; }
.hero h1 { margin:0; font-size:2rem; font-weight:700; }
.hero p  { margin:6px 0 0; opacity:.85; font-size:1rem; }

/* Stats bar */
.stat-bar { display:flex; gap:16px; margin-bottom:20px; }
.stat { background:#f0f4ff; border-radius:10px; padding:12px 20px; flex:1; text-align:center; }
.stat .num { font-size:1.6rem; font-weight:700; color:#1565C0; }
.stat .lbl { font-size:.75rem; color:#666; margin-top:2px; }

/* Product card */
.pcard { border:1px solid #e8ecf0; border-radius:12px; padding:14px;
         margin-bottom:10px; background:white; transition:.2s; }
.pcard:hover { box-shadow:0 6px 20px rgba(0,0,0,.08); border-color:#90CAF9; }
.pcard.selected { border:2px solid #1565C0; background:#e3f2fd; }
.pcard .pname { font-weight:600; font-size:.9rem; color:#1a1a2e; line-height:1.4; }
.pcard .pprice { color:#e53935; font-weight:700; font-size:1rem; margin-top:4px; }
.pcard .pmeta { font-size:.75rem; color:#888; margin-top:4px; }
.tag { background:#e8f5e9; color:#2e7d32; border-radius:20px;
       padding:2px 10px; font-size:.7rem; font-weight:600; }
.tag-blue { background:#e3f2fd; color:#1565C0; }

/* Similarity badge */
.badge { display:inline-block; border-radius:20px; padding:3px 10px;
         font-size:.75rem; font-weight:700; }
.badge-green { background:#e8f5e9; color:#2e7d32; }
.badge-orange{ background:#fff3e0; color:#e65100; }
.badge-red   { background:#ffebee; color:#c62828; }

/* Compare columns */
.col-kw  { background:#fff8f8; border:1px solid #ffcdd2;
            border-radius:12px; padding:16px; }
.col-sem { background:#f0f8ff; border:1px solid #90CAF9;
            border-radius:12px; padding:16px; }

/* Pipeline step */
.step { display:flex; align-items:flex-start; gap:12px; margin-bottom:10px; }
.step-icon { background:#1565C0; color:white; border-radius:50%;
              width:28px; height:28px; display:flex; align-items:center;
              justify-content:center; font-weight:700; flex-shrink:0; font-size:.8rem; }
.step-content { background:#f8f9fa; border-radius:8px; padding:8px 14px; flex:1; font-size:.85rem; }

/* Chat */
.chat-user { background:#1565C0; color:white; border-radius:16px 16px 4px 16px;
              padding:10px 16px; margin:8px 0 8px 40px; font-size:.9rem; }
.chat-ai   { background:#f0f4ff; border-radius:16px 16px 16px 4px;
              padding:10px 16px; margin:8px 40px 8px 0; font-size:.9rem; }
.chat-label{ font-size:.7rem; color:#999; margin:2px 0; }
</style>
""", unsafe_allow_html=True)


# ── CACHE ────────────────────────────────────────────────────────────
@st.cache_resource
def get_clients():
    ai  = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    chroma = chromadb.PersistentClient(path=CHROMA_DIR)
    col = chroma.get_collection(COLLECTION)
    return ai, col

@st.cache_data
def load_df():
    df = pd.read_csv(CSV_FILE, encoding="utf-8-sig")
    df = df.dropna(subset=["name"])
    for c in ["price","rating","sold"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

ai, col = get_clients()
df = load_df()
CATEGORIES = sorted(df["keyword"].dropna().unique().tolist())


# ── HELPERS ──────────────────────────────────────────────────────────
def embed(text: str):
    return ai.embeddings.create(model="text-embedding-3-small", input=text).data[0].embedding

def vsearch(query: str, n: int = 6, where: dict = None):
    vec = embed(query)
    kwargs = dict(query_embeddings=[vec], n_results=n,
                  include=["documents","metadatas","distances"])
    if where: kwargs["where"] = where
    r = col.query(**kwargs)
    out = []
    for i in range(len(r["ids"][0])):
        m = r["metadatas"][0][i]
        out.append({**m, "sim": round(1 - r["distances"][0][i], 3),
                    "doc": r["documents"][0][i]})
    return out

def kwsearch(q: str, n: int = 6):
    return df[df["name"].str.contains(q, case=False, na=False)].head(n)

def badge(s):
    p = int(s*100)
    cls = "badge-green" if p>=75 else "badge-orange" if p>=55 else "badge-red"
    return f'<span class="badge {cls}">{p}%</span>'

def pcard(p: dict, selected=False):
    name  = str(p.get("name",""))[:65]
    price = f"{int(p.get('price',0) or 0):,} ₫"
    kw    = p.get("keyword","")
    rat   = p.get("rating",0) or 0
    sold  = int(p.get("sold",0) or 0)
    cls   = "pcard selected" if selected else "pcard"
    sim   = f'&nbsp;{badge(p["sim"])}' if "sim" in p else ""
    st.markdown(f"""
    <div class="{cls}">
      <div class="pname">{name}{sim}</div>
      <div class="pprice">{price}</div>
      <div class="pmeta">
        <span class="tag tag-blue">{kw}</span>
        &nbsp;⭐ {rat}&nbsp;·&nbsp;Đã bán {sold:,}
      </div>
    </div>""", unsafe_allow_html=True)


# ── HERO ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <h1>🛍️ ShopAI — Vector Database Demo</h1>
  <p>Semantic Search · Product Recommendation · RAG Shopping Assistant</p>
</div>
<div class="stat-bar">
  <div class="stat"><div class="num">{len(df):,}</div><div class="lbl">Sản phẩm</div></div>
  <div class="stat"><div class="num">{len(CATEGORIES)}</div><div class="lbl">Danh mục</div></div>
  <div class="stat"><div class="num">1,536</div><div class="lbl">Chiều vector</div></div>
  <div class="stat"><div class="num">HNSW</div><div class="lbl">Index algorithm</div></div>
  <div class="stat"><div class="num">Cosine</div><div class="lbl">Similarity metric</div></div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Tìm kiếm & Gợi ý",
    "⚡ Keyword vs Semantic",
    "🤖 RAG – Trợ lý mua sắm",
    "🗺️ Vector Space",
])


# ════════════════════════════════════════════════════════
# TAB 1 — SEARCH + RECOMMENDATION
# ════════════════════════════════════════════════════════
with tab1:
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown("### Tìm kiếm sản phẩm")
        q = st.text_input("", placeholder="Gõ mô tả: áo mặc đi biển, tai nghe chống ồn giá rẻ...", key="q1")
        c1, c2 = st.columns([2,1])
        cat_filter = c1.selectbox("Danh mục", ["Tất cả"] + CATEGORIES, key="cat1")
        top_n = c2.slider("Số kết quả", 3, 12, 6, key="n1")

        if q:
            with st.spinner("Đang tìm..."):
                t0 = time.time()
                results = vsearch(q, top_n)
                elapsed = time.time() - t0

            st.success(f"✅ **{len(results)} kết quả** · `{elapsed:.2f}s`")
            for r in results:
                pcard(r)
                if st.button("💡 Gợi ý tương tự", key=f"s_{r.get('url','')}_{r.get('sim')}"):
                    st.session_state["sel"] = r
        else:
            fdf = df if cat_filter=="Tất cả" else df[df["keyword"]==cat_filter]
            fdf = fdf[fdf["rating"]>0].sort_values("rating", ascending=False)
            page = st.number_input("Trang", 1, max(1, len(fdf)//9), 1, key="pg1")
            chunk = fdf.iloc[(page-1)*9: page*9]
            cols = st.columns(3)
            for i, (_, row) in enumerate(chunk.iterrows()):
                with cols[i%3]:
                    pcard(row.to_dict())
                    if st.button("💡 Gợi ý", key=f"g_{row['id']}_{i}"):
                        st.session_state["sel"] = row.to_dict()

    with right:
        st.markdown("### 💡 Gợi ý tương tự")
        sel = st.session_state.get("sel")
        if sel:
            st.markdown("**Sản phẩm đang xem:**")
            pcard(sel, selected=True)
            st.divider()
            with st.spinner("Vector DB đang tìm..."):
                recs = vsearch(f"{sel.get('name','')} {sel.get('keyword','')}", 7)
                recs = [r for r in recs if r.get("name") != sel.get("name")][:5]
            st.markdown(f"**{len(recs)} sản phẩm tương tự:**")
            for r in recs:
                pcard(r)
        else:
            st.markdown("""
<div style="text-align:center;padding:40px;color:#aaa">
  <div style="font-size:3rem">👆</div>
  <div style="margin-top:8px">Click <b>Gợi ý tương tự</b><br>trên bất kỳ sản phẩm nào</div>
</div>""", unsafe_allow_html=True)
            with st.expander("Vector DB hoạt động thế nào?"):
                st.markdown("""
1. Sản phẩm bạn chọn → embed thành **vector 1536 chiều**
2. ChromaDB tính **cosine similarity** với toàn bộ database
3. Thuật toán **HNSW** tìm top-K gần nhất cực nhanh
4. Trả về sản phẩm có **ngữ nghĩa tương đồng** nhất
                """)


# ════════════════════════════════════════════════════════
# TAB 2 — KEYWORD vs SEMANTIC
# ════════════════════════════════════════════════════════
with tab2:
    st.markdown("### ⚡ Keyword Search vs Semantic Search")
    st.caption("Gõ mô tả tự nhiên — xem sự khác biệt rõ rệt")

    q2  = st.text_input("", placeholder="đồ dùng cho người chạy bộ buổi sáng", key="q2")
    n2  = st.slider("Số kết quả", 3, 8, 5, key="n2")

    if q2:
        kw_res  = kwsearch(q2, n2)
        with st.spinner("Semantic searching..."):
            t0 = time.time()
            sem_res = vsearch(q2, n2)
            elapsed = time.time() - t0

        col_k, col_s = st.columns(2, gap="medium")

        with col_k:
            st.markdown('<div class="col-kw">', unsafe_allow_html=True)
            st.markdown("#### ❌ Keyword Search")
            st.caption("Tìm đúng chuỗi ký tự trong tên")
            if kw_res.empty:
                st.error(f"Không tìm thấy sản phẩm nào chứa **'{q2}'**")
            else:
                st.info(f"{len(kw_res)} kết quả")
                for _, r in kw_res.iterrows():
                    pcard(r.to_dict())
            st.markdown('</div>', unsafe_allow_html=True)

        with col_s:
            st.markdown('<div class="col-sem">', unsafe_allow_html=True)
            st.markdown("#### ✅ Semantic Search (Vector DB)")
            st.caption(f"Hiểu ngữ nghĩa · {elapsed:.2f}s")
            st.success(f"{len(sem_res)} kết quả")
            for r in sem_res:
                pcard(r)
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("#### Pipeline xử lý")
        steps = [
            ("1", "Nhận query", f'"{q2}"'),
            ("2", "Embedding Model", "text → vector 1536 chiều (OpenAI)"),
            ("3", "HNSW Index", f"Tìm top-{n2} nearest neighbors trong {len(df):,} vectors"),
            ("4", "Kết quả", f"Trả về trong {elapsed:.3f}s"),
        ]
        for num, title, detail in steps:
            st.markdown(f"""
            <div class="step">
              <div class="step-icon">{num}</div>
              <div class="step-content"><b>{title}:</b> {detail}</div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("💡 Thử: *'quà tặng sinh nhật bạn gái'* · *'đồ dùng văn phòng tiện lợi'* · *'đồ chơi cho bé 3 tuổi'*")


# ════════════════════════════════════════════════════════
# TAB 3 — RAG SHOPPING ASSISTANT
# ════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 🤖 RAG – Trợ lý mua sắm AI")
    st.caption("Hỏi tự nhiên → Vector DB tìm sản phẩm → AI tổng hợp câu trả lời")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render lịch sử chat
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-label">Bạn</div><div class="chat-user">{msg["content"]}</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-label">🤖 ShopAI</div><div class="chat-ai">{msg["content"]}</div>',
                        unsafe_allow_html=True)

    user_input = st.chat_input("Hỏi gì đó: tôi cần quà tặng bạn gái thích thể thao budget 500k...")

    if user_input:
        st.session_state.messages.append({"role":"user","content":user_input})
        st.markdown(f'<div class="chat-label">Bạn</div><div class="chat-user">{user_input}</div>',
                    unsafe_allow_html=True)

        with st.spinner("🔍 Đang tìm sản phẩm liên quan..."):
            # RETRIEVAL
            hits = vsearch(user_input, n=5)
            context = "\n".join([
                f"- {h['name']} | Giá: {int(h.get('price',0)):,}đ | Rating: {h.get('rating',0)} | Category: {h.get('keyword','')}"
                for h in hits
            ])

        with st.spinner("🤖 AI đang tổng hợp câu trả lời..."):
            # GENERATION
            system_prompt = """Bạn là trợ lý mua sắm thông minh của ShopAI.
Dựa vào danh sách sản phẩm được cung cấp, hãy tư vấn cho khách hàng.
Trả lời ngắn gọn, thân thiện, bằng tiếng Việt.
Luôn đề cập giá cụ thể và lý do gợi ý."""

            response = ai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":system_prompt},
                    {"role":"user","content":f"Câu hỏi: {user_input}\n\nSản phẩm tìm được:\n{context}"}
                ],
                max_tokens=500,
            )
            answer = response.choices[0].message.content

        st.session_state.messages.append({"role":"assistant","content":answer})
        st.markdown(f'<div class="chat-label">🤖 ShopAI</div><div class="chat-ai">{answer}</div>',
                    unsafe_allow_html=True)

        with st.expander("🔍 Xem sản phẩm Vector DB tìm được"):
            for h in hits:
                pcard(h)

    if not st.session_state.messages:
        st.markdown("""
<div style="text-align:center;padding:30px;color:#888">
  <div style="font-size:2.5rem">🤖</div>
  <b>Trợ lý mua sắm AI</b><br>
  <small>Hoạt động theo pipeline RAG đầy đủ</small>
</div>""", unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        with c1:
            if st.button("🎁 Quà tặng bạn gái thích thể thao budget 500k"):
                st.session_state["prefill"] = "Quà tặng bạn gái thích thể thao budget 500k"
        with c2:
            if st.button("💻 Laptop sinh viên giá rẻ dưới 15 triệu"):
                st.session_state["prefill"] = "Laptop sinh viên giá rẻ dưới 15 triệu"
        with c3:
            if st.button("👟 Giày chạy bộ êm chân cho nam"):
                st.session_state["prefill"] = "Giày chạy bộ êm chân cho nam"

    if st.button("🗑️ Xóa lịch sử chat"):
        st.session_state.messages = []
        st.rerun()


# ════════════════════════════════════════════════════════
# TAB 4 — VECTOR SPACE
# ════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 🗺️ Vector Space Visualization")
    st.caption("PCA chiếu vector 1536D → 2D. Sản phẩm cùng nhóm cluster gần nhau.")

    c1, c2 = st.columns([1,2])
    n_vis = c1.slider("Số sản phẩm", 200, 1500, 500, 100, key="nvis")
    q_vis = c2.text_input("Thêm query vào biểu đồ", placeholder="áo đi biển mùa hè", key="qvis")

    if st.button("🚀 Vẽ Vector Space", type="primary"):
        with st.spinner(f"Lấy {n_vis} vectors từ ChromaDB..."):
            res = col.get(limit=n_vis, include=["embeddings","metadatas"])
            embs = np.array(res["embeddings"])
            metas = res["metadatas"]

        with st.spinner("PCA giảm chiều..."):
            from sklearn.decomposition import PCA
            pca = PCA(n_components=2, random_state=42)
            xy  = pca.fit_transform(embs)

        plot_df = pd.DataFrame({
            "x": xy[:,0], "y": xy[:,1],
            "name":     [m.get("name","")[:40] for m in metas],
            "category": [m.get("keyword","?") for m in metas],
            "price":    [m.get("price",0) for m in metas],
            "marker":   ["product"]*len(metas)
        })

        if q_vis:
            with st.spinner("Embedding query..."):
                qv = np.array([embed(q_vis)])
                qxy = pca.transform(qv)[0]
            plot_df = pd.concat([plot_df, pd.DataFrame([{
                "x":qxy[0],"y":qxy[1],"name":f"🔍 {q_vis}",
                "category":"⭐ Query","price":0,"marker":"query"
            }])], ignore_index=True)

        fig = px.scatter(
            plot_df, x="x", y="y", color="category",
            hover_name="name", hover_data={"price":True,"x":False,"y":False},
            symbol="marker", symbol_map={"product":"circle","query":"star"},
            title=f"Vector Space — {n_vis} sản phẩm Tiki",
            height=580,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_traces(marker=dict(size=7, opacity=0.75))
        if q_vis:
            fig.update_traces(
                selector=dict(legendgroup="⭐ Query"),
                marker=dict(size=20, color="red", symbol="star")
            )
        fig.update_layout(
            plot_bgcolor="#fafafa",
            paper_bgcolor="white",
            legend_title="Danh mục",
        )
        st.plotly_chart(fig, use_container_width=True)
        var = pca.explained_variance_ratio_.sum()*100
        st.caption(f"PCA giữ lại **{var:.1f}%** thông tin từ vector 1536 chiều gốc")
        st.info("💡 Sản phẩm cùng danh mục cluster gần nhau. Query ⭐ nằm gần cluster phù hợp nhất.")
    else:
        st.info("Nhấn **'Vẽ Vector Space'** để visualize không gian vector")
