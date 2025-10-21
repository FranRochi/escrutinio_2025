// panelista.js — Panel de resultados (Diputados Nacionales, top 4 y subcomandos estilo anterior)

(() => {
  "use strict";

  const API_SUMMARY = "/api/panel/summary/?cargo=Diputados Nacionales";
  const API_SUBCOMANDOS = "/api/panel/subcomandos_diputados/";
  const API_EXPORT_DIP = "/export/mesas_por_cargo.xlsx";

  let chartDip = null;
  const $ = (s, ctx = document) => ctx.querySelector(s);

  // ====== Cargar resumen general ======
  async function cargarResumen() {
    try {
      const res = await fetch(API_SUMMARY, { cache: "no-cache" });
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();

      renderTabla(data.partidos);
      renderGrafico(data.partidos);
      $("#kpiMesas").textContent = `${data.mesas_escrutadas} / ${data.total_mesas}`;
      $("#status").textContent = `Actualizado: ${data.timestamp}`;
    } catch (err) {
      console.error("Error cargando resumen", err);
      $("#status").textContent = "Error al cargar datos.";
    }
  }

  // ====== Tabla: solo top 4 ======
  function renderTabla(partidos) {
    const tbody = $("#tabla tbody");
    tbody.innerHTML = "";
    if (!Array.isArray(partidos)) return;

    const top = partidos.slice(0, 4);
    top.forEach((p, i) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="th-left">${i + 1}. ${p.partido}</td>
        <td>${p.votos.toLocaleString("es-AR")}</td>
        <td>${p.porcentaje.toFixed(2)}%</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ====== Gráfico: solo top 4 ======
  function renderGrafico(partidos) {
    if (!Array.isArray(partidos)) return;

    const top = partidos.slice(0, 4);
    const ctx = $("#grafico_dipu");
    if (!ctx) return;

    const labels = top.map(p => p.partido);
    const dataVals = top.map(p => p.porcentaje);

    if (chartDip) chartDip.destroy();

    chartDip = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "% de votos",
            data: dataVals,
            backgroundColor: [
              "#0040fffb",
              "rgba(0, 200, 83, 0.7)",
              "rgba(255, 193, 7, 0.7)",
              "rgba(244, 67, 54, 0.7)",
            ],
            borderColor: "rgba(255, 255, 255, 0.4)",
            borderWidth: 1,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        scales: {
          x: {
            beginAtZero: true,
            max: 100, // 👈 escala de 0 a 100
            ticks: {
              color: "#ccc",
              callback: value => value + "%",
            },
            grid: { color: "#333" },
          },
          y: { ticks: { color: "#ccc" }, grid: { color: "#333" } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.parsed.x.toFixed(2)}%`,
            },
          },
        },
      },
    });
  }

  // ====== Subcomandos (idéntico al estilo clásico del dashboard anterior) ======
  async function cargarSubcomandos() {
    try {
      const res = await fetch(API_SUBCOMANDOS, { cache: "no-cache" });
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();

      const list = $("#subcmdList");
      list.innerHTML = "";

      const items = data.items || data || [];

      // Respetar orden del backend (sin sort en el JS)
      items.forEach(sub => {
        const pct = Number(sub.porcentaje || 0);
        const total = sub.total || 0;
        const esc = sub.escrutadas || 0;

        const div = document.createElement("div");
        div.className = "subcmd-box";
        div.innerHTML = `
          <div class="subcmd-title">${sub.nombre}</div>
          <div class="progress-bar">
            <div class="fill" style="width:${pct.toFixed(1)}%;
                background: linear-gradient(90deg, #1e88e5, #31b8f0);"></div>
            <span class="pct-label">${esc}/${total} mesas (${pct.toFixed(1)}%)</span>
          </div>
        `;
        list.appendChild(div);
      });
    } catch (err) {
      console.error("Error cargando subcomandos", err);
    }
  }


  // ====== Descargar Excel ======
  function descargarExcel() {
    window.location.href = API_EXPORT_DIP;
  }

  // ====== Auto-refresh ======
  function setupAutoRefresh() {
    const sel = $("#refreshEvery");
    let timer = null;
    function applyInterval() {
      const val = parseInt(sel.value, 10);
      if (timer) clearInterval(timer);
      if (val > 0) timer = setInterval(cargarResumen, val * 1000);
    }
    sel.addEventListener("change", applyInterval);
    applyInterval();
  }

  // ====== Init ======
  document.addEventListener("DOMContentLoaded", () => {
    $("#btnRefresh")?.addEventListener("click", cargarResumen);
    $("#btnDescargarDip")?.addEventListener("click", descargarExcel);
    cargarResumen();
    cargarSubcomandos();
    setupAutoRefresh();
  });
})();
