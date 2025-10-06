let chartElectores = null;
let chartAdherentes = null;
let chartTotales = null;
let chartEdades = null;

// ========================
// Gráficos principales
// ========================
async function cargarVotantes() {
  const r = await fetch("/api/panel/votantes/");
  const data = await r.json();

  // --- Electores ---
  const canvas1 = document.getElementById("graficoElectores");
  if (canvas1) {
    const ctx1 = canvas1.getContext("2d");
    if (!chartElectores) {
      chartElectores = new Chart(ctx1, {
        type: "doughnut",
        data: {
          labels: ["Votaron", "No votaron"],
          datasets: [{
            data: [data.electores.votaron, data.electores.total - data.electores.votaron],
            backgroundColor: ["#3b82f6", "#1e293b"],
          }]
        },
        options: {
          plugins: {
            legend: { position: "bottom", labels: { color: "#e5e7eb" } },
            datalabels: {
              color: "#fff",
              font: { weight: "bold", size: 12 },
              formatter: (value, ctx) => {
                const sum = ctx.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                const pct = ((value / sum) * 100).toFixed(1);
                return `${value} (${pct}%)`;
              }
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    } else {
      chartElectores.data.datasets[0].data = [
        data.electores.votaron,
        data.electores.total - data.electores.votaron
      ];
      chartElectores.update();
    }
    document.getElementById("infoElectores").textContent =
      `Total: ${data.electores.total} | Votaron: ${data.electores.votaron}`;
  }

  // --- Adherentes ---
  const canvas2 = document.getElementById("graficoAdherentes");
  if (canvas2) {
    const ctx2 = canvas2.getContext("2d");
    if (!chartAdherentes) {
      chartAdherentes = new Chart(ctx2, {
        type: "doughnut",
        data: {
          labels: ["Votaron", "No votaron"],
          datasets: [{
            data: [data.adherentes.votaron, data.adherentes.total - data.adherentes.votaron],
            backgroundColor: ["#22c55e", "#1e293b"],
          }]
        },
        options: {
          plugins: {
            legend: { position: "bottom", labels: { color: "#e5e7eb" } },
            datalabels: {
              color: "#fff",
              font: { weight: "bold", size: 12 },
              formatter: (value, ctx) => {
                const sum = ctx.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                const pct = ((value / sum) * 100).toFixed(1);
                return `${value} (${pct}%)`;
              }
            }
          }
        },
        plugins: [ChartDataLabels]
      });
    } else {
      chartAdherentes.data.datasets[0].data = [
        data.adherentes.votaron,
        data.adherentes.total - data.adherentes.votaron
      ];
      chartAdherentes.update();
    }
    document.getElementById("infoAdherentes").textContent =
      `Total: ${data.adherentes.total} | Votaron: ${data.adherentes.votaron}`;
  }
}

// ========================
// Gráfico Totales + Edades
// ========================
async function cargarVotantesDetalle() {
  try {
    const r = await fetch("/api/votantes_detalle/");
    const data = await r.json();

    // --- Totales Nativos/Extranjeros ---
    const canvas = document.getElementById("graficoTotales");
    if (canvas) {
      const ctx = canvas.getContext("2d");
      if (!chartTotales) {
        chartTotales = new Chart(ctx, {
          type: "doughnut",
          data: {
            labels: ["Nativos", "Extranjeros"],
            datasets: [{
              data: [data.nativos.total, data.extranjeros.total],
              backgroundColor: ["#3b82f6", "#f97316"],
            }]
          },
          options: {
            cutout: "70%",
            plugins: {
              legend: { position: "bottom", labels: { color: "#e5e7eb" } },
              datalabels: {
                color: "#fff",
                font: { weight: "bold", size: 12 },
                formatter: (value, ctx) => {
                  const sum = ctx.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                  const pct = ((value / sum) * 100).toFixed(1);
                  return `${value} (${pct}%)`;
                }
              }
            }
          },
          plugins: [ChartDataLabels]
        });
      } else {
        chartTotales.data.datasets[0].data = [
          data.nativos.total,
          data.extranjeros.total
        ];
        chartTotales.update();
      }
      document.getElementById("infoTotales").textContent =
        `Nativos: ${data.nativos.total} (${data.nativos.porcentaje}%) | ` +
        `Extranjeros: ${data.extranjeros.total} (${data.extranjeros.porcentaje}%)`;
    }

    // --- Edades ---
    const edadesCanvas = document.getElementById("graficoEdades");
    if (edadesCanvas) {
      const ctx = edadesCanvas.getContext("2d");
      const labels = Object.keys(data.edades);
      const values = Object.values(data.edades);

      if (!chartEdades) {
        chartEdades = new Chart(ctx, {
          type: "bar",
          data: {
            labels,
            datasets: [{
              label: "% de votantes por edad",
              data: values,
              backgroundColor: "#10b981"
            }]
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
              x: { ticks: { color: "#e5e7eb" } },
              y: { ticks: { color: "#e5e7eb", callback: v => v + "%" } }
            }
          }
        });
      } else {
        chartEdades.data.datasets[0].data = values;
        chartEdades.update();
      }
    }
  } catch (e) {
    console.error("Error cargando detalle de votantes:", e);
  }
}

// ========================
// Paleta de colores para escuelas
// ========================
const coloresEscuelas = [
  "#ef4444", "#f97316", "#eab308", "#22c55e",
  "#3b82f6", "#6366f1", "#a855f7", "#ec4899"
];
const cacheColores = {};

function colorEscuela(nombre) {
  if (!cacheColores[nombre]) {
    const idx = Object.keys(cacheColores).length % coloresEscuelas.length;
    cacheColores[nombre] = coloresEscuelas[idx];
  }
  return cacheColores[nombre];
}

// ========================
// Últimos votantes estilo chat
// ========================
async function cargarVotantesMarcados() {
  try {
    const r = await fetch("/api/votantes_marcados/");
    const data = await r.json();

    const container = document.getElementById("chat-votantes");
    container.innerHTML = "";

    if (!data.votantes || data.votantes.length === 0) {
      container.innerHTML = "<p style='color:#555;'>Nadie marcado aún</p>";
      return;
    }

    data.votantes.forEach(v => {
      const div = document.createElement("div");
      div.className = "chat-line";
      div.style.setProperty("--color", colorEscuela(v.escuela));
      div.innerHTML = `
        <span class="escuela">${v.escuela}</span>
        <span class="detalle">Mesa ${v.mesa} — Orden ${v.orden}</span>
      `;
      container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
  } catch (e) {
    console.error("Error cargando votantes marcados:", e);
  }
}

// ========================
// Inicialización
// ========================
document.addEventListener("DOMContentLoaded", () => {
  cargarVotantes();
  setInterval(cargarVotantes, 60000);

  cargarVotantesDetalle();
  setInterval(cargarVotantesDetalle, 60000);

  cargarVotantesMarcados();
  setInterval(cargarVotantesMarcados, 10000);
});
