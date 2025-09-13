let chart;
let equipmentData = [];

// 🎨 動畫數字
function animateValue(element, newValue) {
  element.classList.remove("animate__fadeIn");
  void element.offsetWidth;
  element.textContent = newValue;
  element.classList.add("animate__fadeIn");
}

// 🟢 狀態更新
function updateStatus(status) {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("status");
  const card = document.getElementById("statusCard");

  text.textContent = status;
  if (status === "RUN") {
    dot.textContent = "🟢";
    card.style.borderColor = "#10b981";
  } else if (status === "IDLE") {
    dot.textContent = "🟡";
    card.style.borderColor = "#fbbf24";
  } else if (status === "ERROR") {
    dot.textContent = "🔴";
    card.style.borderColor = "#ef4444";
    addAlert("ERROR", "設備異常，請檢查！");
  } else {
    dot.textContent = "⚪";
    card.style.borderColor = "#9ca3af";
  }
}

// 🔔 新增告警
function addAlert(level, message) {
  const list = document.getElementById("alertsList");
  const div = document.createElement("div");
  div.classList.add("alert");
  if (level === "ERROR") div.classList.add("error");
  else if (level === "WARN") div.classList.add("warn");
  else div.classList.add("info");
  div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  list.prepend(div);
  if (list.children.length > 5) list.removeChild(list.lastChild);
}

// 📊 渲染設備清單
async function fetchEquipment() {
  const res = await fetch('/api/equipment');
  equipmentData = await res.json();

  const body = document.getElementById("equipmentTableBody");
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
      </td>
    `;
    body.appendChild(tr);
  });
}

// ➕ 新增設備
async function addEquipment() {
  const input = document.getElementById("newEquipmentId");
  const id = input.value.trim();
  if (!id) return alert("請輸入設備ID！");
  await fetch('/api/equipment', {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ equipment_id: id })
  });
  input.value = "";
  fetchEquipment();
}

// ✏️ 編輯設備
async function editEquipment(id) {
  const current = equipmentData.find(e => e.id === id);
  const newId = prompt("修改設備ID：", current.equipment_id);
  if (newId && newId.trim() !== "") {
    await fetch(`/api/equipment/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ equipment_id: newId })
    });
    fetchEquipment();
  }
}

// 🗑️ 刪除設備
async function deleteEquipment(id) {
  if (confirm("確定要刪除嗎？")) {
    await fetch(`/api/equipment/${id}`, { method: "DELETE" });
    fetchEquipment();
  }
}

// 📈 摘要
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

// 📉 趨勢圖
async function fetchMetrics() {
  try {
    const res = await fetch('/api/metrics?limit=20', { cache: 'no-store' });
    const { items } = await res.json();

    const labels = items.map(m => new Date(m.ts).toLocaleTimeString());
    const data = items.map(m => m.production);

    if (!chart) {
      const ctx = document.getElementById('productionChart').getContext('2d');
      chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: '產量',
            data,
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37,99,235,0.2)',
            fill: true,
            tension: 0.3,
            pointRadius: 3
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false }
          },
          scales: {
            x: { title: { display: true, text: '時間' } },
            y: { title: { display: true, text: '產量 (pcs)' } }
          }
        }
      });
    } else {
      chart.data.labels = labels;
      chart.data.datasets[0].data = data;
      chart.update();
    }
  } catch (e) {
    console.error('fetch /api/metrics failed', e);
  }
}

// 🚀 初始化
fetchSummary();
fetchMetrics();
fetchEquipment();
setInterval(fetchSummary, 5000);
setInterval(fetchMetrics, 5000);
setInterval(fetchEquipment, 10000);
