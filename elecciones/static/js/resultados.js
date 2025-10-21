(async () => {
  const $ = s => document.querySelector(s);
  const fmtInt = n => Number(n || 0).toLocaleString('es-AR');

  async function getJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status} en ${url}`);
    return r.json();
  }

  async function fetchDiputados() {
    const data = await getJSON(`/api/panel/summary/?cargo=DIPUTADOS`);
    return Array.isArray(data.partidos) ? data.partidos : [];
  }

  function renderFullTable(rows) {
    const tbody = $("#tablaFull tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    rows.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="partido th-left">${r.partido}</td>
        <td class="num">${fmtInt(r.votos)}</td>
        <td class="pct" style="--pct:${r.porcentaje}%">
          ${Number(r.porcentaje || 0).toFixed(2)}%
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderCards(datos) {
    const cont = document.getElementById('cardsResultados');
    if (!cont) return;

    cont.innerHTML = datos.map(p => `
      <div class="card-partido">
        <div class="card-header">
          <div class="nombre">${p.partido}</div>
        </div>
        <div class="mini-tabla">
          <div class="fila"><span>Votos:</span><strong>${fmtInt(p.votos)}</strong></div>
          <div class="fila"><span>%:</span><strong>${Number(p.porcentaje || 0).toFixed(2)}%</strong></div>
        </div>
      </div>
    `).join('');
  }

  async function renderKPI() {
    const kpi = $("#kpiMesasFull");
    if (!kpi) return;

    try {
      const meta = await getJSON(`/api/panel/metadata/`);
      const total = meta.total_mesas ?? 0;
      const esc   = meta.mesas_escrutadas ?? 0;
      const pct   = Number(meta.porcentaje_escrutadas ?? 0);
      kpi.textContent = total ? `${esc}/${total} (${pct.toFixed(2)}%)` : "—";
      kpi.style.setProperty("--pct", `${Math.max(0, Math.min(100, pct))}%`);
      kpi.classList.add("kpi-bar");
    } catch {
      kpi.textContent = "—";
    }
  }

  try {
    const rows = await fetchDiputados();
    renderFullTable(rows);
    renderCards(rows);   // 👈 ahora también renderiza los cards
    renderKPI();
  } catch (e) {
    console.error(e);
    const tbody = $("#tablaFull tbody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="3" style="opacity:.7">Error al cargar</td></tr>`;
  }
})();
