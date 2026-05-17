/* ── CONSTANTS ── */
const EMOJIS = {
  'áo thun nam':'👕','áo sơ mi nam':'👔','quần jean nam':'👖','áo khoác nam':'🧥','quần short nam':'🩳',
  'váy nữ':'👗','áo thun nữ':'👚','quần jean nữ':'👖','đầm dự tiệc':'👗','áo khoác nữ':'🧥',
  'giày thể thao':'👟','giày sneaker nam':'👟','giày cao gót':'👠','dép nam':'🩴','giày sandal nữ':'👡',
  'điện thoại samsung':'📱','tai nghe bluetooth':'🎧','tai nghe chống ồn':'🎧','loa bluetooth':'🔊',
  'máy tính xách tay':'💻','bàn phím cơ':'⌨️','chuột gaming':'🖱️','màn hình máy tính':'🖥️',
  'đồng hồ nam':'⌚','đồng hồ nữ':'⌚','balo laptop':'🎒','túi xách nữ':'👜','ví nam':'👛',
  'son môi':'💄','kem dưỡng da':'🧴','nước hoa':'🌸','mascara':'👁️','serum dưỡng da':'💊',
  'sách kỹ năng':'📚','sách văn học':'📖','sách kinh doanh':'📊','sách thiếu nhi':'📕',
  'dụng cụ tập gym':'🏋️','áo thể thao':'🏃','bình nước thể thao':'💧','găng tay tập gym':'🥊',
  'đèn led':'💡','nồi chiên không dầu':'🍳','máy lọc không khí':'🌬️','chăn ga gối':'🛏️',
  'bút bi':'✏️','sổ tay':'📓','balo học sinh':'🎒',
};

const CATS = [
  { k: '', l: 'Tất cả', i: '🏠' },
  { k: 'áo thun nam', l: 'Thời trang nam', i: '👕' },
  { k: 'váy nữ', l: 'Thời trang nữ', i: '👗' },
  { k: 'giày thể thao', l: 'Giày dép', i: '👟' },
  { k: 'điện thoại samsung', l: 'Điện thoại', i: '📱' },
  { k: 'máy tính xách tay', l: 'Laptop', i: '💻' },
  { k: 'tai nghe bluetooth', l: 'Âm thanh', i: '🎧' },
  { k: 'đồng hồ nam', l: 'Đồng hồ', i: '⌚' },
  { k: 'son môi', l: 'Làm đẹp', i: '💄' },
  { k: 'sách kỹ năng', l: 'Sách', i: '📚' },
];

const BGCOLS = ['#FFF5F3','#F0FDF4','#FFF7ED','#F5F3FF','#F0F9FF','#FFFBEB','#FFF1F2','#F0FFF4'];

/* ── STATE ── */
let page = 1, curCat = '', sortMode = 'rating', searchMode = false;
let isLoading = false, hasMore = true;
let scrollObserver = null;

/* ── HELPERS ── */
function emo(k) { return EMOJIS[k] || '📦'; }
function fmtP(p) { return p ? Number(p).toLocaleString('vi-VN') + '₫' : '—'; }
function bgc(id) {
  const h = String(id || '').split('').reduce((a, c) => a * 31 + c.charCodeAt(0), 0);
  return BGCOLS[Math.abs(h) % BGCOLS.length];
}
function stars(r) {
  const n = Math.round(r || 0);
  return `<span class="stars">${'★'.repeat(n)}${'☆'.repeat(5 - n)}</span>`;
}
function imgSrc(p) {
  return p.thumbnail_url || `https://picsum.photos/seed/${p.id || p.name}/300/300`;
}

/* ── PRODUCT CARD ── */
function pcard(p, showSim = false) {
  const disc = p.discount || 0;
  const orig = p.original_price > p.price ? p.original_price : 0;
  const sold = p.sold || 0;
  const sim  = p.similarity;
  const pct  = sim != null ? Math.round(sim * 100) : 0;

  // Similarity bar shown only in search / similar results
  const simBar = showSim && sim != null ? `
    <div class="sim-bar-wrap">
      <div class="sim-bar-bg"><div class="sim-bar" style="width:${pct}%"></div></div>
      <span class="sim-label">${pct}% match</span>
    </div>` : '';

  return `<div class="pc" onclick='openDetail(${JSON.stringify(p).replace(/'/g, "\\'")}  )'>
    <div class="thumb" style="background:${bgc(p.id)}">
      <img src="${imgSrc(p)}" loading="lazy"
           onerror="this.onerror=null;this.src='https://picsum.photos/seed/${p.id}/300/300'">
      ${disc > 0 ? `<div class="disc">-${disc}%</div>` : ''}
      ${sold > 200 ? '<div class="hot">HOT</div>' : ''}
    </div>
    <div class="info">
      <div class="name">${p.name || ''}</div>
      <div>
        <span class="price">${fmtP(p.price)}</span>
        ${orig ? `<span class="orig">${fmtP(orig)}</span>` : ''}
      </div>
      <div class="meta">
        ${stars(p.rating)}
        <span>Đã bán ${sold > 1000 ? (sold / 1000).toFixed(1) + 'k' : sold}</span>
      </div>
      ${simBar}
    </div>
  </div>`;
}

/* ── INIT ── */
async function init() {
  // Build category grid
  const cg = document.getElementById('catGrid');
  CATS.forEach(c => {
    const d = document.createElement('div');
    d.className = 'ci' + (c.k === '' ? ' active' : '');
    d.innerHTML = `<div class="ico">${c.i}</div><span>${c.l}</span>`;
    d.onclick = () => filterCat(c.k, d);
    cg.appendChild(d);
  });

  // Setup infinite scroll observer
  scrollObserver = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting && !isLoading && hasMore && !searchMode) {
      loadMoreProds();
    }
  }, { threshold: 0.1 });
  scrollObserver.observe(document.getElementById('scrollEnd'));

  loadProds();
}

/* ── BROWSE ── */
function setSort(s, el) {
  sortMode = s;
  document.querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  resetAndLoad();
}

function filterCat(k, el) {
  curCat = k;
  searchMode = false;
  document.querySelectorAll('.ci').forEach(c => c.classList.remove('active'));
  if (el) {
    el.classList.add('active');
  } else {
    document.querySelectorAll('.ci').forEach((c, i) => {
      if (CATS[i] && CATS[i].k === k) c.classList.add('active');
    });
  }
  const title = k
    ? `${emo(k)} ${k.charAt(0).toUpperCase() + k.slice(1)}`
    : '🔥 Gợi ý hôm nay';
  document.getElementById('secTitle').textContent = title;
  resetAndLoad();
}

// Reset grid and start fresh from page 1
function resetAndLoad() {
  page = 1;
  hasMore = true;
  isLoading = false;
  document.getElementById('pgrid').innerHTML =
    '<div class="loader" style="grid-column:1/-1">Đang tải...</div>';
  document.getElementById('scrollLoader').style.display = 'none';
  loadProds();
}

// Load current page and REPLACE grid (used on first load / filter / sort)
async function loadProds() {
  isLoading = true;
  const url = `/api/products?page=${page}&category=${encodeURIComponent(curCat)}&limit=20&sort=${sortMode}`;
  const d = await fetch(url).then(r => r.json());

  document.getElementById('pgrid').innerHTML = d.items.length
    ? d.items.map(p => pcard(p)).join('')
    : '<div class="empty-state" style="grid-column:1/-1"><div class="ei">🔍</div>Không có sản phẩm</div>';

  hasMore = d.items.length === 20 && page * 20 < d.total;
  isLoading = false;
}

// Append next page (infinite scroll)
async function loadMoreProds() {
  if (isLoading || !hasMore || searchMode) return;
  isLoading = true;
  document.getElementById('scrollLoader').style.display = 'block';

  page++;
  const url = `/api/products?page=${page}&category=${encodeURIComponent(curCat)}&limit=20&sort=${sortMode}`;
  const d = await fetch(url).then(r => r.json());

  if (d.items.length > 0) {
    document.getElementById('pgrid').insertAdjacentHTML('beforeend', d.items.map(p => pcard(p)).join(''));
  }

  hasMore = d.items.length === 20 && page * 20 < d.total;
  isLoading = false;
  document.getElementById('scrollLoader').style.display = hasMore ? 'none' : 'none';
}

/* ── SEARCH ── */
async function doSearch() {
  const q = document.getElementById('mainQ').value.trim();
  if (!q) return;
  searchMode = true;
  document.getElementById('pgrid').innerHTML =
    '<div class="loader" style="grid-column:1/-1">🔍 Đang tìm kiếm...</div>';
  document.getElementById('pager').style.display = 'none';

  const t0 = Date.now();
  const d = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: q, n: 20 }),
  }).then(r => r.json());

  const elapsed = ((Date.now() - t0) / 1000).toFixed(2);
  document.getElementById('secTitle').innerHTML =
    `🔍 "${q}" — <span style="color:var(--orange)">${d.results.length} kết quả</span>` +
    ` <span style="font-size:.72rem;color:var(--muted)">⚡${elapsed}s</span>`;
  document.getElementById('pgrid').innerHTML = d.results.map(p => pcard(p, true)).join('');
}

/* ── PRODUCT DETAIL ── */
let simProducts = [];   // toàn bộ sản phẩm tương tự đã fetch
let simShown = 0;       // số đã hiện
let simObserver = null; // IntersectionObserver cho sentinel
const SIM_BATCH = 10;

async function openDetail(p) {
  document.getElementById('homePage').style.display = 'none';
  const dp = document.getElementById('detailPage');
  dp.classList.add('open');
  dp.scrollTop = 0;

  document.getElementById('detailBread').textContent =
    `${emo(p.keyword)} ${p.keyword || ''} › ${(p.name || '').substring(0, 40)}`;

  const disc = p.discount || 0;
  const orig = p.original_price > p.price ? p.original_price : 0;

  document.getElementById('detailTop').innerHTML = `
    <div class="detail-imgs">
      <img class="detail-main-img" src="${imgSrc(p)}"
           onerror="this.onerror=null;this.src='https://picsum.photos/seed/${p.id}/400/400'">
      <div class="detail-thumbs">
        <img class="detail-thumb active" src="${imgSrc(p)}"
             onerror="this.onerror=null;this.src='https://picsum.photos/seed/${p.id}/300/300'">
      </div>
    </div>
    <div class="detail-info">
      <div class="detail-tags">
        <span class="dtag">${emo(p.keyword)} ${p.keyword || ''}</span>
        ${p.brand ? `<span class="dtag">${p.brand}</span>` : ''}
      </div>
      <div class="detail-name">${p.name || ''}</div>
      <div class="detail-rating">
        ${stars(p.rating)}
        <span style="color:var(--orange);font-weight:700">${p.rating || 0}</span>
        <span>|</span>
        <span>${(p.review_count || 0).toLocaleString()} đánh giá</span>
        <span>|</span>
        <span>Đã bán ${(p.sold || 0).toLocaleString()}</span>
      </div>
      <div class="detail-price-box">
        <span class="detail-price">${fmtP(p.price)}</span>
        ${orig ? `<span class="detail-orig">${fmtP(orig)}</span><span class="detail-disc">-${disc}%</span>` : ''}
      </div>
      <div class="detail-meta">
        <div class="row"><span class="lbl">Thương hiệu</span><span class="val">${p.brand || 'Đang cập nhật'}</span></div>
        <div class="row"><span class="lbl">Danh mục</span><span class="val">${p.keyword || ''}</span></div>
        <div class="row"><span class="lbl">Đánh giá</span><span class="val">${stars(p.rating)} ${p.rating || 0}/5</span></div>
      </div>
      <button class="btn-buy" onclick="window.open('${p.url || '#'}', '_blank')">🔗 Xem trên Tiki</button>
    </div>`;

  // Reset similar products state
  simProducts = [];
  simShown = 0;
  if (simObserver) simObserver.disconnect();
  document.getElementById('simLoader').style.display = 'none';

  document.getElementById('simSection').innerHTML = `
    <div class="sim-head">
      <h3>🧠 Sản phẩm tương tự</h3>
      <span class="sim-badge">Powered by Vector DB</span>
    </div>
    <div class="loader">Đang tìm sản phẩm tương đồng...</div>`;

  // Fetch 50 similar products upfront
  const rec = await fetch('/api/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: `${p.name} ${p.keyword}`, n: 51 }),
  }).then(r => r.json());

  simProducts = rec.results.filter(r => r.name !== p.name);

  // Render header + empty grid
  document.getElementById('simSection').innerHTML = `
    <div class="sim-head">
      <h3>🧠 Sản phẩm tương tự</h3>
      <span class="sim-badge">Vector DB · ${simProducts.length} gợi ý</span>
    </div>
    <div class="sim-grid" id="simGrid"></div>`;

  // Show first batch
  appendSimBatch();

  // Watch sentinel for infinite scroll inside detail overlay
  simObserver = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting && simShown < simProducts.length) {
      appendSimBatch();
    }
  }, { root: document.getElementById('detailPage'), threshold: 0.1 });
  simObserver.observe(document.getElementById('simSentinel'));
}

function appendSimBatch() {
  const batch = simProducts.slice(simShown, simShown + SIM_BATCH);
  if (!batch.length) return;
  document.getElementById('simGrid').insertAdjacentHTML('beforeend', batch.map(r => pcard(r, true)).join(''));
  simShown += batch.length;
  document.getElementById('simLoader').style.display =
    simShown < simProducts.length ? 'block' : 'none';
}

function closeDetail() {
  document.getElementById('detailPage').classList.remove('open');
  document.getElementById('homePage').style.display = 'block';
}

function goHome() {
  closeDetail();
  curCat = '';
  searchMode = false;
  document.getElementById('mainQ').value = '';
  document.getElementById('secTitle').textContent = '🔥 Gợi ý hôm nay';
  document.querySelectorAll('.ci').forEach((c, i) => {
    c.classList.toggle('active', i === 0);
  });
  resetAndLoad();
}

/* ── CHAT ── */
const chatHistory = [];   // [{role, content}] — gửi lên backend mỗi lần chat

function toggleChat() {
  document.getElementById('cpanel').classList.toggle('open');
}

function addMsg(role, html) {
  const container = document.getElementById('cmsgs');
  const d = document.createElement('div');
  d.className = `cm ${role}`;
  d.innerHTML = role === 'u'
    ? `<div class="b">${html}</div><div class="a">👤</div>`
    : `<div class="a">🤖</div><div class="b">${html}</div>`;
  container.appendChild(d);
  container.scrollTop = 9999;
  return d;
}

// Mini product card bấm được trong chat
function chatCard(s) {
  const p = JSON.stringify(s).replace(/'/g, "\\'");
  return `<div onclick='openDetail(${p})' class="chat-card">
    <img src="${imgSrc(s)}"
         onerror="this.onerror=null;this.src='https://picsum.photos/seed/${s.id}/80/80'">
    <div class="chat-card-info">
      <div class="chat-card-name">${(s.name || '').substring(0, 38)}</div>
      <div class="chat-card-price">${fmtP(s.price)}</div>
    </div>
    <span class="chat-card-arrow">›</span>
  </div>`;
}

async function sendChat() {
  const inp = document.getElementById('cinp');
  const q = inp.value.trim();
  if (!q) return;
  inp.value = '';
  addMsg('u', q);

  // Lưu tin nhắn user vào history
  chatHistory.push({ role: 'user', content: q });

  const typingEl = addMsg('ai', '<div class="typing"><span></span><span></span><span></span></div>');

  const d = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // Gửi kèm 8 lượt hội thoại gần nhất (trừ tin nhắn vừa thêm)
    body: JSON.stringify({ message: q, history: chatHistory.slice(0, -1) }),
  }).then(r => r.json());

  // Lưu câu trả lời vào history
  chatHistory.push({ role: 'assistant', content: d.answer });

  // Render mini-cards sản phẩm
  const cardsHtml = d.sources.length
    ? `<div style="margin-top:8px">${d.sources.map(s => chatCard(s)).join('')}</div>`
    : '';

  typingEl.querySelector('.b').innerHTML =
    `<div style="margin-bottom:4px">${d.answer.replace(/\n/g, '<br>')}</div>` + cardsHtml;

  document.getElementById('cmsgs').scrollTop = 9999;
}

function qchat(q) {
  document.getElementById('cinp').value = q;
  sendChat();
}

/* ── START ── */
init();
