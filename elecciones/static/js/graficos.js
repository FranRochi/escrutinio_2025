// ====== Plugin para etiquetas dentro/arriba de las barras ======
const BarLabelsPlugin = {
  id: 'barLabels',
  afterDatasetsDraw(chart, args, opts) {
    if (!chart || !chart.chartArea) return;
    const { ctx, chartArea } = chart;
    const totals = (opts && opts.totals) || [];

    const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
    const fmtInt = n => Number(n || 0).toLocaleString('es-AR');
    const fmtPct1 = n =>
      (Number(n) || 0).toLocaleString('es-AR', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
      });

    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = 'bold 11px system-ui, -apple-system, Segoe UI, Roboto, Arial';

    chart.data.datasets.forEach((ds, di) => {
      const meta = chart.getDatasetMeta(di);
      if (!meta) return;

      const total = Number.isFinite(totals[di])
        ? totals[di]
        : ds.data.reduce((a, b) => a + (Number(b) || 0), 0);

      meta.data.forEach((elem, idx) => {
        if (!elem) return;
        const v = Number(ds.data[idx] || 0);
        if (!total || v <= 0) return;

        const x = elem.x;
        const yTop = elem.y;
        const yBase = elem.base;
        const yMid = (yTop + yBase) / 2;

        // % centrado dentro de la barra
        const pctText = `${fmtPct1((v * 100) / total)}%`;
        ctx.fillStyle   = '#ffffff';
        ctx.shadowColor = 'rgba(0,0,0,.65)';
        ctx.shadowBlur  = 2;
        ctx.fillText(pctText, x, clamp(yMid, chartArea.top + 10, chartArea.bottom - 10));

        // valor absoluto arriba (o dentro si no hay espacio)
        let yVal = yTop - 10;
        let insideTop = false;
        if (yVal < chartArea.top + 8) {
          yVal = yTop + 12;
          insideTop = true;
        }
        if (insideTop) {
          ctx.fillStyle   = '#ffffff';
          ctx.shadowColor = 'rgba(0,0,0,.65)';
          ctx.shadowBlur  = 2;
        } else {
          ctx.fillStyle   = '#e5e7eb';
          ctx.shadowColor = 'rgba(0,0,0,.45)';
          ctx.shadowBlur  = 1;
        }
        ctx.fillText(fmtInt(v), x, yVal);
      });
    });

    ctx.restore();
  }
};

async function fetchCargo(cargo) {
  const res = await fetch(`/api/panel/summary/?cargo=${cargo}`);
  if (!res.ok) throw new Error("Error al traer datos");
  return await res.json();
}

function renderSingleChart(canvasId, label, rows) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const labels = rows.map(r => r.partido);
  const data   = rows.map(r => r.votos);
  const total  = data.reduce((a,b)=>a+(Number(b)||0),0);
  const maxVal = Math.max(1,...data);

  new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label, data, backgroundColor: 'rgba(49,184,240,0.6)' }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#cbd5e1', font: { weight: 'bold' } } },
        tooltip:{ callbacks:{ label:(ctx)=>`${ctx.dataset.label}: ${ctx.parsed.y}` }},
        barLabels: { totals:[total], show:'both' }
      },
      scales: {
        x:{ ticks:{ color:'#94a3b8' }, grid:{ color:'rgba(148,163,184,.15)' } },
        y:{ beginAtZero:true, suggestedMax:Math.ceil(maxVal*1.15), ticks:{ color:'#94a3b8' }, grid:{ color:'rgba(148,163,184,.15)' } }
      }
    },
    plugins:[BarLabelsPlugin]
  });
}

async function renderFullCharts() {
  try {
    const dip = await fetchCargo("DIPUTADOS");
    const con = await fetchCargo("CONCEJALES");

    renderSingleChart("grafico_dipu","Diputados",dip.partidos);
    renderSingleChart("grafico_conce","Concejales",con.partidos);
  } catch(err) {
    console.error(err);
  }
}

document.addEventListener("DOMContentLoaded", renderFullCharts);
