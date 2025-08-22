(async () => {
  const $ = s => document.querySelector(s);
  const fmtInt = n => Number(n || 0).toLocaleString('es-AR');
  const toNum  = v => (v === null || v === undefined ? 0 : Number(v));

  async function getJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status} en ${url}`);
    return r.json();
  }

  // Fallback: pide ambos cargos y une por partido
  async function fetchAndMergeFallback() {
    const [dip, con] = await Promise.all([
      getJSON(`/api/panel/summary/?cargo=DIPUTADOS`),
      getJSON(`/api/panel/summary/?cargo=CONCEJALES`)
    ]);
    const map = new Map();
    const push = (row, type) => {
      const name = row.partido;
      if (!map.has(name)) map.set(name, { partido: name, votos_dip: 0, pct_dip: 0, votos_con: 0, pct_con: 0 });
      const obj = map.get(name);
      if (type === 'd') { obj.votos_dip = toNum(row.votos); obj.pct_dip = toNum(row.porcentaje); }
      else { obj.votos_con = toNum(row.votos); obj.pct_con = toNum(row.porcentaje); }
    };
    (dip.partidos || []).forEach(r => push(r, 'd'));
    (con.partidos || []).forEach(r => push(r, 'c'));
    return Array.from(map.values()).sort((a,b) =>
      (b.votos_dip + b.votos_con) - (a.votos_dip + a.votos_con)
    );
  }

  function renderFullTable(rows) {
    const tbody = $("#tablaFull tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    rows.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="partido th-left">${r.partido}</td>
        <td class="num">${fmtInt(r.votos_dip)}</td>
        <td class="pct" style="--pct:${r.pct_dip}%">${Number(r.pct_dip || 0).toFixed(2)}%</td>
        <td class="num">${fmtInt(r.votos_con)}</td>
        <td class="pct" style="--pct:${r.pct_con}%">${Number(r.pct_con || 0).toFixed(2)}%</td>
      `;
      tbody.appendChild(tr);
    });
  }

  try {
    let data = null;
    let rows = [];

    // Intento 1: endpoint combinado
    try {
      data = await getJSON(`/api/panel/summary_both/`);
      rows = Array.isArray(data.rows) ? data.rows : [];
      console.log('summary_both rows:', rows.length);
    } catch (e) {
      console.warn('summary_both no disponible, usando fallback…', e.message || e);
      rows = await fetchAndMergeFallback();
    }

    // Si vino muy corto, igualmente usamos fallback
    if (!rows.length || rows.length < 5) {
      console.warn('Muy pocas filas desde combinado, usando fallback merge…');
      rows = await fetchAndMergeFallback();
    }

    renderFullTable(rows);

    // KPI mesas (si vino de summary_both, lo usamos; si no, tratamos de pedir metadata)
    const kpi = $("#kpiMesasFull");
    if (kpi) {
      if (data && (data.total_mesas || data.mesas_escrutadas)) {
        const total = (data.total_mesas ?? 0);
        const esc   = (data.mesas_escrutadas ?? 0);
        const pct   = Number(data.porcentaje_mesas ?? 0);
        kpi.textContent = total ? `${esc}/${total} (${pct.toFixed(2)}%)` : '—';
        kpi.style.setProperty('--pct', `${Math.max(0, Math.min(100, pct))}%`);
        kpi.classList.add('kpi-bar');
      } else {
        // opcional: meta global
        try {
          const meta = await getJSON(`/api/panel/metadata/`);
          const total = meta.total_mesas ?? 0;
          const esc   = meta.mesas_escrutadas ?? 0;
          const pct   = Number(meta.porcentaje_escrutadas ?? 0);
          kpi.textContent = total ? `${esc}/${total} (${pct.toFixed(2)}%)` : '—';
          kpi.style.setProperty('--pct', `${Math.max(0, Math.min(100, pct))}%`);
          kpi.classList.add('kpi-bar');
        } catch {
          kpi.textContent = '—';
        }
      }
    }
  } catch (e) {
    console.error(e);
    const tbody = $("#tablaFull tbody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="opacity:.7">Error al cargar</td></tr>`;
  }
})();
