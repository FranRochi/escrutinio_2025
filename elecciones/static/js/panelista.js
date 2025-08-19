document.addEventListener("DOMContentLoaded", () => {
  // Si no hay datos o Chart.js no está, salir sin error
  if (typeof votosData === "undefined" || !window.Chart) return;

  // ---------- Gráfico stacked general (si existe el canvas) ----------
  const cvGeneral = document.getElementById("graficoVotos");
  if (cvGeneral) {
    const ctxGeneral = cvGeneral.getContext("2d");

    const cargos = Object.keys(votosData);
    const partidosSet = new Set();
    cargos.forEach(cargo => {
      Object.keys(votosData[cargo] || {}).forEach(p => partidosSet.add(p));
    });

    const partidos = Array.from(partidosSet);
    const colores = [
      "#3e95cd","#8e5ea2","#3cba9f","#e8c3b9",
      "#c45850","#f1c40f","#2ecc71","#3498db"
    ];

    const datasets = partidos.map((partido, i) => ({
      label: partido,
      data: cargos.map(cargo => (votosData[cargo] && votosData[cargo][partido]) ? votosData[cargo][partido] : 0),
      backgroundColor: colores[i % colores.length]
    }));

    new Chart(ctxGeneral, {
      type: "bar",
      data: { labels: cargos, datasets },
      options: {
        responsive: true,
        plugins: {
          title: { display: true, text: "Distribución de votos por cargo y partido" },
          tooltip: { mode: "index", intersect: false }
        },
        interaction: { mode: "nearest", axis: "x", intersect: false },
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true }
        }
      }
    });
  }

  // ---------- Gráficos por cargo (si existe el contenedor) ----------
  const contenedor = document.getElementById("graficos-por-cargo");
  if (!contenedor) return;

  const entries = Object.entries(votosData || {});
  entries.forEach(([cargo, partidos], index) => {
    // crear canvas
    const canvas = document.createElement("canvas");
    canvas.id = `grafico-cargo-${index}`;
    canvas.style.width  = "600px"; // estilo visual
    canvas.style.height = "300px"; // estilo visual
    contenedor.appendChild(canvas);

    const ctx = canvas.getContext("2d");

    // alta resolución
    const scale = window.devicePixelRatio || 1;
    canvas.width = 600 * scale;
    canvas.height = 300 * scale;
    ctx.scale(scale, scale);

    const labels = Object.keys(partidos || {});
    const data   = Object.values(partidos || {}).map(v => Number(v) || 0);

    new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: `${cargo}`,
          data,
          backgroundColor: "rgba(54, 162, 235, 0.7)",
          borderColor:     "rgba(54, 162, 235, 1)",
          borderWidth: 1
        }]
      },
      options: {
        responsive: false, // evitamos conflictos con el escalado manual
        plugins: {
          title: { display: true, text: cargo, font: { size: 18 } },
          legend: { display: false }
        },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } }
        }
      }
    });
  });
});
