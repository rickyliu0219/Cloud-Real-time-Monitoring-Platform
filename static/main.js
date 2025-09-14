// static/main.js
console.log("main.js loaded: maint2-20250913");

let chart;
let equipmentData = [];

/* ===================== 即時滑動視窗狀態 ===================== */
let rtState = {
  lastTs: null,      // 最後一個時間戳（ISO字串）
  labels: [],        // x 軸（時間字串）
  total: [],         // 總量（累積）
  perEqp: new Map(), // 各機（累積）：eid -> array
  maxPoints: 40      // 顯示點數（20/40/60）
};

/* ===================== 維修兩階段狀態 ===================== */
let maint = {
  hours: 24,                 // 查詢區間（小時）
  records: [],               // 全部維修區段（後端回傳）
  selectedEqp: null          // 當前詳情中的設備ID
};

/* ===================== 小工具 ===================== */
function animateValue(element, newValue) {
  element.classList.remove("animate__fadeIn"); void element.offsetWidth;
  element.textContent = newValue; element.classList.add("animate__fadeIn");
}
function toLocaleTime(ts) { return new Date(ts).toLocaleTimeString(); }
function buildLabels(items) { return items.map(m => toLocaleTime(m.ts)); }
function toDelta(series) {
  if (!series || series.length === 0) return [];
  const out = [0]; for (let i = 1; i < series.length; i++) out.push(Math.max(series[i] - series[i-1], 0));
  return out;
}
function fmt(ts) { return new Date(ts).toLocaleString(); }
function fmtDur(sec) {
  if (sec == null) return '-';
  const s = Math.max(0, parseInt(sec, 10));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const parts = [];
  if (h) parts.push(`${h}小時`);
  if (m) parts.push(`${m}分`);
  parts.push(`${r}秒`);
  return parts.join('');
}

/* ===================== KPI ===================== */
function updateStatus(status) {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("status");
  const card = document.getElementById("statusCard");
  text.textContent = status || "N/A";
  if (status === "RUN")      { dot.textContent = "🟢"; card.style.borderColor = "#10b981"; }
  else if (status === "IDLE"){ dot.textContent = "🟡"; card.style.borderColor = "#fbbf24"; }
  else if (status === "ERROR"){ dot.textContent = "🔴"; card.style.borderColor = "#ef4444"; }
  else { dot.textContent = "⚪"; card.style.borderColor = "#9ca3af"; }
}

async function fetchSummary() {
  try {
    const res = await fetch('/api/summary', { cache: 'no-store' });
    const data = await res.json();
    animateValue(document.getElementById('dailyProduction'), data.dailyProduction ?? 0);
    animateValue(document.getElementById('efficiency'), (data.efficiency ?? 0).toFixed(2));
    updateStatus(data.status ?? "N/A");
  } catch (e) {
    console.error('fetch /api/summary failed', e);
  }
}

/* ===================== 設備 CRUD ===================== */
async function fetchEquipment() {
  const res = await fetch('/api/equipment');
  equipmentData = await res.json();
  const body = document.getElementById("equipmentTableBody");
  if (body) {
    body.innerHTML = "";
    equipmentData.forEach((m) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${m.equipment_id}</td>
        <td>${m.status}</td>
        <td>${m.production}</td>
        <td>${m.efficiency}</td>
        <td>
          <button onclick="editEquipment(${m.id})">✏️ 編輯</button>
          <button onclick="deleteEquipment(${m.id})">🗑️ 刪除</button>
        </td>`;
      body.appendChild(tr);
    });
  }
  // 同步更新維修「第一頁」的設備清單（若已載入維修資料）
  renderMaintList();
}
async function addEquipment() {
  const input = document.getElementById("newEquipmentId");
  const id = input.value.trim();
  if (!id) return alert("請輸入設備 ID！");
  await fetch('/api/equipment', {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ equipment_id: id })
  });
  input.value = ""; fetchEquipment();
}
async function editEquipment(id) {
  const current = equipmentData.find(e => e.id === id);
  const newId = prompt("修改設備 ID：", current?.equipment_id || "");
  if (newId && newId.trim() !== "") {
    await fetch(`/api/equipment/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ equipment_id: newId })
    });
    fetchEquipment();
  }
}
async function deleteEquipment(id) {
  if (confirm("確定要刪除這個設備嗎？")) {
    await fetch(`/api/equipment/${id}`, { method: "DELETE" });
    fetchEquipment();
  }
}

/* ===================== 圖表 ===================== */
function ensureChart() {
  if (chart) return;
  const ctx = document.getElementById('productionChart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [] },
    options: {
      responsive: true, animation: false, spanGaps: true,
      plugins: {
        legend: { display: true },
        decimation: { enabled: true, algorithm: 'lttb', samples: 100 }
      },
      scales: {
        x: { title: { display: true, text: '時間' } },
        y: { title: { display: true, text: '產量 (件)' }, beginAtZero: true }
      }
    }
  });
}
function showRealtimeOpts(show) {
  const el = document.getElementById("rtOpts");
  if (el) el.style.display = show ? "inline-flex" : "none";
}
function onRealtimePointsChange() {
  const sel = document.getElementById("realtimePoints");
  rtState.maxPoints = parseInt(sel?.value || "40", 10);
  rtState.lastTs = null; rtState.labels = []; rtState.total = []; rtState.perEqp = new Map();
  fetchMetrics(true);
}

function renderRealtime() {
  ensureChart();
  const seriesMode = document.getElementById("seriesMode")?.value || "total";
  const valueMode  = document.getElementById("valueMode")?.value  || "cumulative";
  chart.data.labels = rtState.labels.slice();

  if (seriesMode === "total") {
    let dataArr = rtState.total.slice();
    if (valueMode === "delta") dataArr = toDelta(dataArr);
    chart.data.datasets = [{
      label: valueMode === "delta" ? '單次產出(總量)' : '總產量(累積)',
      data: dataArr,
      borderColor: '#2563eb',
      backgroundColor: valueMode === "delta" ? 'rgba(37,99,235,0.15)' : 'rgba(37,99,235,0.2)',
      fill: valueMode !== "delta",
      tension: 0.25, pointRadius: 3
    }];
  } else {
    const palette = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#dc2626'];
    const datasets = [];
    let idx = 0;
    for (const [eid, arr] of rtState.perEqp.entries()) {
      let d = arr.slice();
      if (valueMode === "delta") d = toDelta(d);
      datasets.push({
        label: eid, data: d, borderColor: palette[idx % palette.length],
        backgroundColor: 'transparent', fill: false, tension: 0.25, pointRadius: 3, spanGaps: true
      });
      idx++;
    }
    chart.data.datasets = datasets;
  }
  chart.update();
}

function appendRealtime(data) {
  const newPoints = (data.items_total || []).filter(p => !rtState.lastTs || p.ts > rtState.lastTs);
  if (newPoints.length === 0 && rtState.labels.length > 0) return;

  const eqpAtTs = new Map();
  (data.items_by_equipment || []).forEach(series => {
    const eid = series.equipment_id;
    series.points.forEach(p => {
      if (!eqpAtTs.has(p.ts)) eqpAtTs.set(p.ts, new Map());
      eqpAtTs.get(p.ts).set(eid, p.production);
    });
  });

  newPoints.forEach(p => {
    rtState.labels.push(toLocaleTime(p.ts));
    rtState.lastTs = p.ts;
    rtState.total.push(p.production);

    const valMap = eqpAtTs.get(p.ts) || new Map();
    for (const [eid, arr] of rtState.perEqp.entries()) {
      const v = valMap.has(eid) ? valMap.get(eid) : null;
      arr.push(v);
    }
    for (const [eid, v] of valMap.entries()) {
      if (!rtState.perEqp.has(eid)) {
        const blank = new Array(rtState.labels.length - 1).fill(null);
        blank.push(v); rtState.perEqp.set(eid, blank);
      }
    }

    while (rtState.labels.length > rtState.maxPoints) {
      rtState.labels.shift(); rtState.total.shift();
      for (const arr of rtState.perEqp.values()) arr.shift();
    }
  });
}

async function fetchMetrics(forceReload = false) {
  try {
    const timeRange = document.getElementById("timeRange")?.value || "realtime";
    const seriesMode = document.getElementById("seriesMode")?.value || "total";
    const valueMode  = document.getElementById("valueMode")?.value  || "cumulative";

    if (timeRange === "realtime") {
      showRealtimeOpts(true); ensureChart();
      const res = await fetch(`/api/metrics?range=realtime`, { cache: 'no-store' });
      const data = await res.json();

      if (forceReload || !rtState.lastTs) {
        const sel = document.getElementById("realtimePoints");
        rtState.maxPoints = parseInt((sel && sel.value) || "40", 10);
        rtState.labels = []; rtState.total = []; rtState.perEqp = new Map();

        const items = data.items_total || [];
        const take = Math.min(items.length, rtState.maxPoints);
        const startIdx = items.length - take;

        const eqMap = new Map();
        (data.items_by_equipment || []).forEach(series => {
          eqMap.set(series.equipment_id, new Map(series.points.map(pt => [pt.ts, pt.production])));
        });

        for (let i = startIdx; i < items.length; i++) {
          const p = items[i];
          rtState.labels.push(toLocaleTime(p.ts));
          rtState.total.push(p.production);
          for (const [eid] of eqMap.entries()) if (!rtState.perEqp.has(eid)) rtState.perEqp.set(eid, []);
          for (const [eid, arr] of rtState.perEqp.entries()) {
            const m = eqMap.get(eid);
            arr.push(m && m.has(p.ts) ? m.get(p.ts) : null);
          }
          rtState.lastTs = p.ts;
        }
      } else {
        appendRealtime(data);
      }

      renderRealtime();
      return;
    }

    showRealtimeOpts(false);
    rtState.lastTs = null; rtState.labels = []; rtState.total = []; rtState.perEqp = new Map();

    const res = await fetch(`/api/metrics?range=${timeRange}`, { cache: 'no-store' });
    const data = await res.json();
    ensureChart();

    if ((data.items_total || []).length === 0) {
      chart.data.labels = [toLocaleTime(new Date().toISOString())];
      chart.data.datasets = [{ label: '無資料', data: [0] }];
      chart.update(); return;
    }

    const labels = buildLabels(data.items_total);
    const tsKeys = data.items_total.map(p => p.ts);

    if (seriesMode === "total") {
      let series = data.items_total.map(p => p.production);
      if (valueMode === "delta") series = toDelta(series);
      chart.data.labels = labels;
      chart.data.datasets = [{
        label: valueMode === "delta" ? '單次產出(總量)' : '總產量(累積)',
        data: series, borderColor: '#2563eb',
        backgroundColor: valueMode === "delta" ? 'rgba(37,99,235,0.15)' : 'rgba(37,99,235,0.2)',
        fill: valueMode !== "delta", tension: 0.25, pointRadius: 2
      }];
    } else {
      const palette = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#dc2626'];
      const datasets = (data.items_by_equipment || []).map((series, idx) => {
        const map = new Map(series.points.map(p => [p.ts, p.production]));
        let aligned = tsKeys.map(ts => map.get(ts) ?? null);
        if (valueMode === "delta") {
          const diff = [];
          for (let i = 0; i < aligned.length; i++) {
            if (i === 0 || aligned[i] == null || aligned[i-1] == null) diff.push(null);
            else diff.push(Math.max(aligned[i] - aligned[i-1], 0));
          }
          aligned = diff;
        }
        return {
          label: series.equipment_id, data: aligned,
          borderColor: palette[idx % palette.length],
          backgroundColor: 'transparent', fill: false, tension: 0.25, pointRadius: 2, spanGaps: true
        };
      });
      chart.data.labels = labels; chart.data.datasets = datasets;
    }

    chart.update();
  } catch (e) { console.error('fetch /api/metrics failed', e); }
}

/* ===================== 告警 ===================== */
async function fetchAlerts() {
  try {
    const res = await fetch('/api/alerts?hours=12', { cache: 'no-store' });
    const data = await res.json();
    const list = document.getElementById("alertsList");
    list.innerHTML = "";

    if (!data.events || data.events.length === 0) {
      list.innerHTML = '<p class="muted">目前沒有告警。</p>';
      return;
    }

    data.events.forEach(ev => {
      const div = document.createElement("div");
      if (ev.type === "ERROR_START")      div.className = "alert error";
      else if (ev.type === "ERROR_END")   div.className = "alert ok";
      else                                div.className = "alert info";
      const when = fmt(ev.ts);
      const label = (ev.type === "ERROR_START") ? "發生故障" : (ev.type === "ERROR_END") ? "恢復正常" : ev.type;
      div.textContent = `[${when}] ${ev.equipment_id}：${label}`;
      list.appendChild(div);
    });
  } catch (e) { console.error('fetch /api/alerts failed', e); }
}

/* ===================== 維修紀錄（兩階段） ===================== */
async function fetchMaintenanceRecords() {
  try {
    const res = await fetch(`/api/maintenance?hours=${maint.hours}`, { cache: 'no-store' });
    const data = await res.json();
    maint.records = Array.isArray(data.records) ? data.records : [];
    // 根據目前視圖重新渲染
    if (maint.selectedEqp) renderMaintDetail(maint.selectedEqp);
    else renderMaintList();
  } catch (e) { console.error('fetch /api/maintenance failed', e); }
}

function renderMaintList() {
  const listView = document.getElementById("maintViewList");
  const detailView = document.getElementById("maintViewDetail");
  const grid = document.getElementById("maintDeviceGrid");
  const floatingBack = document.getElementById("floatingBack");
  if (!grid) return;

  listView.style.display = "";
  detailView.style.display = "none";
  floatingBack.style.display = "none";
  maint.selectedEqp = null;

  grid.innerHTML = "";
  // 顯示所有設備（即使沒有維修紀錄也顯示）
  const eqIds = equipmentData.map(e => e.equipment_id).sort();
  const nowOngoing = new Map(); // eid -> ongoing count
  const countPerEq = new Map(); // eid -> record count
  maint.records.forEach(r => {
    countPerEq.set(r.equipment_id, (countPerEq.get(r.equipment_id) || 0) + 1);
    if (r.ongoing) nowOngoing.set(r.equipment_id, (nowOngoing.get(r.equipment_id) || 0) + 1);
  });

  eqIds.forEach(eid => {
    const count = countPerEq.get(eid) || 0;
    const ongo = nowOngoing.get(eid) || 0;

    const a = document.createElement("button");
    a.className = "device-chip";
    a.onclick = () => maintShowDetail(eid);
    a.innerHTML = `
      ${eid}
      ${ongo ? `<span class="badge">${ongo}</span>` : (count ? `<span class="badge badge-ok">${count}</span>` : "")}
    `;
    grid.appendChild(a);
  });

  // 若沒有任何設備（理論上不會），顯示空狀態
  if (eqIds.length === 0) {
    grid.innerHTML = `<div class="muted">尚無設備，請先於下方「設備清單」新增。</div>`;
  }
}

function renderMaintDetail(eid) {
  const listView = document.getElementById("maintViewList");
  const detailView = document.getElementById("maintViewDetail");
  const tbody = document.getElementById("maintDetailBody");
  const title = document.getElementById("maintTitle");
  const floatingBack = document.getElementById("floatingBack");
  if (!tbody) return;

  maint.selectedEqp = eid;
  listView.style.display = "none";
  detailView.style.display = "";
  floatingBack.style.display = "inline-block";
  title.textContent = `${eid} 維修紀錄（最近 ${maint.hours} 小時）`;

  // 過濾該設備的紀錄（新到舊）
  const rows = maint.records.filter(r => r.equipment_id === eid)
                            .sort((a,b) => (b.start_ts || "").localeCompare(a.start_ts || ""));

  tbody.innerHTML = "";
  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" class="muted">沒有維修紀錄</td></tr>`;
    document.getElementById("maintTotalDur").textContent = "-";
    return;
  }

  let total = 0;
  rows.forEach(rec => {
    total += Math.max(0, parseInt(rec.duration_sec || 0, 10));
    const tr = document.createElement("tr");
    const start = fmt(rec.start_ts);
    const end = rec.end_ts ? fmt(rec.end_ts) : '進行中…';
    const dur = fmtDur(rec.duration_sec);
    tr.innerHTML = `<td>${start}</td><td>${end}</td><td>${dur}</td>`;
    tbody.appendChild(tr);
  });
  document.getElementById("maintTotalDur").textContent = fmtDur(total);
}

/* 供 HTML 呼叫的切換函式 */
function maintShowDetail(eid) { renderMaintDetail(eid); }
function maintShowList() { renderMaintList(); }

/* 支援鍵盤 ESC 一鍵返回清單 */
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const detailVisible = document.getElementById("maintViewDetail")?.style.display !== "none";
    if (detailVisible) maintShowList();
  }
});

/* ===================== 初始化與排程 ===================== */
(function init() {
  fetchSummary();
  fetchMetrics(true);
  fetchEquipment();           // 載入設備後也會 renderMaintList()
  fetchAlerts();
  fetchMaintenanceRecords();  // 會渲染維修第一頁

  setInterval(fetchSummary, 5000);
  setInterval(fetchMetrics, 5000);
  setInterval(fetchEquipment, 10000);
  setInterval(fetchAlerts, 5000);
  setInterval(fetchMaintenanceRecords, 10000);
})();

/* ===================== 對外（給 HTML 使用的按鈕） ===================== */
window.addEquipment = addEquipment;
window.editEquipment = editEquipment;
window.deleteEquipment = deleteEquipment;
window.onRealtimePointsChange = onRealtimePointsChange;
window.maintShowDetail = maintShowDetail;
window.maintShowList = maintShowList;
