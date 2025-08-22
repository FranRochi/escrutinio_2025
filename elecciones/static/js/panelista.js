(() => {
  // ===== util =====
  const $ = s => document.querySelector(s);
  const fmtInt = n => Number(n || 0).toLocaleString('es-AR');
  const toNum = v => (v === null || v === undefined ? 0 : Number(v));

  async function getJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status} en ${url}`);
    return r.json();
  }

  // Spinner en el botón Actualizar
  function setBusy(on) {
    const b = $("#btnRefresh");
    if (!b) return;
    b.classList.toggle("is-busy", !!on);
  }

  // Trae el resumen por cargo (por nombre o id)
  async function fetchCargo(key) {
    const qs = typeof key === 'number' ? `cargo_id=${key}` : `cargo=${encodeURIComponent(key)}`;
    return getJSON(`/api/panel/summary/?${qs}`);
  }

  // Une dos resúmenes por partido (diputados + concejales)
  function mergeByPartido(dipu, conce) {
    const map = new Map();
    const push = (row, type) => {
      const name = row.partido;
      if (!map.has(name)) map.set(name, { partido: name, dipu: 0, conce: 0, pd: 0, pc: 0 });
      const obj = map.get(name);
      if (type === 'd') { obj.dipu = toNum(row.votos); obj.pd = toNum(row.porcentaje); }
      else { obj.conce = toNum(row.votos); obj.pc = toNum(row.porcentaje); }
    };
    (dipu.partidos || []).forEach(r => push(r, 'd'));
    (conce.partidos || []).forEach(r => push(r, 'c'));
    return Array.from(map.values()).sort((a,b) => (b.dipu + b.conce) - (a.dipu + a.conce));
  }

  // Render tabla combinada
  // Render tabla (con opción de límite)
  function renderTable(rows) {
    const tbody = document.querySelector("#tabla tbody");
    const table = document.getElementById("tabla");
    if (!tbody || !table) return;

    // Si el <table> trae data-limit, recortamos
    const limitAttr = table.getAttribute("data-limit");
    const limit = limitAttr ? Number(limitAttr) : 0;
    const toRender = (limit && Number.isFinite(limit)) ? rows.slice(0, limit) : rows;

    tbody.innerHTML = "";
    for (const r of toRender) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="partido th-left">${r.partido}</td>
        <td class="num">${fmtInt(r.dipu)}</td>
        <td class="pct" style="--pct:${r.pd}%">${r.pd.toFixed(2)}%</td>
        <td class="num">${fmtInt(r.conce)}</td>
        <td class="pct" style="--pct:${r.pc}%">${r.pc.toFixed(2)}%</td>
      `;
      tbody.appendChild(tr);
    }
  }

  // % centrado dentro de la barra + valor arriba de la barra
  const BarLabelsPlugin = {
    id: 'barLabels',
    afterDatasetsDraw(chart, args, opts) {
      if (!chart || !chart.chartArea) return;

      const { ctx, chartArea } = chart;
      const totals = (opts && opts.totals) || [];

      const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
      const fmtPct1 = n =>
        (Number(n) || 0).toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

      ctx.save();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = 'bold 11px system-ui, -apple-system, Segoe UI, Roboto, Arial';

      chart.data.datasets.forEach((ds, di) => {
        const meta = chart.getDatasetMeta(di);
        if (!meta) return;

        // total por dataset (o el provisto por opciones)
        const total = Number.isFinite(totals[di])
          ? totals[di]
          : ds.data.reduce((a, b) => a + (Number(b) || 0), 0);

        meta.data.forEach((elem, idx) => {
          if (!elem) return;

          const v = Number(ds.data[idx] || 0);
          if (!total || v <= 0) return;

          const x      = elem.x;
          const yTop   = elem.y;       // tope de la barra (menor y = más alto)
          const yBase  = elem.base;    // base de la barra
          const yMid   = (yTop + yBase) / 2;

          // ---- 1) % centrado dentro de la barra ----
          const pctText = `${fmtPct1((v * 100) / total)}%`;
          ctx.fillStyle   = '#ffffff';
          ctx.shadowColor = 'rgba(0,0,0,.65)';
          ctx.shadowBlur  = 2;

          const yPct = clamp(yMid, chartArea.top + 10, chartArea.bottom - 10);
          ctx.fillText(pctText, x, yPct);

          // ---- 2) Valor (votos) arriba de la barra ----
          // si queda muy pegado al borde superior, lo ponemos adentro apenas
          let yVal = yTop - 10;
          let insideTop = false;
          if (yVal < chartArea.top + 8) {
            yVal = yTop + 12;  // lo pintamos “dentro” arriba
            insideTop = true;
          }

          // estilo para el valor: afuera texto claro, adentro texto blanco con sombra
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


  // --- dentro de renderChart, deja TODO igual salvo este bloque ---
  // --- dentro de renderChart ---
  let chart = null;
  function renderChart(rows) {
    const top = rows.slice(0, 3);   // solo las 3 primeras
    const labels = top.map(r => r.partido);
    const dataD  = top.map(r => r.dipu);
    const dataC  = top.map(r => r.conce);
    const canvas = document.getElementById("grafico");
    if (!canvas) return;

    try {
      const ctx = canvas.getContext("2d");

      const totalD = dataD.reduce((a,b)=>a + (Number(b)||0), 0);
      const totalC = dataC.reduce((a,b)=>a + (Number(b)||0), 0);
      const maxVal = Math.max(1, ...dataD, ...dataC);

      if (chart) { chart.destroy(); chart = null; }

      chart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            { label: 'Diputados',  data: dataD, backgroundColor: 'rgba(49,184,240,0.6)' },
            { label: 'Concejales', data: dataC, backgroundColor: 'rgba(148,163,184,0.45)' }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#cbd5e1', font: { weight: 'bold' } } },
            title:  { display: false },
            tooltip:{ callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmtInt(ctx.parsed.y)}` } },
            barLabels: {
              totals: [totalD, totalC],
              show: 'both'
            }
          },
          scales: {
            x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.15)' } },
            y: {
              beginAtZero: true,
              suggestedMax: Math.ceil(maxVal * 1.15),
              ticks: { color: '#94a3b8' },
              grid:  { color: 'rgba(148,163,184,.15)' }
            }
          }
        },
        plugins: [BarLabelsPlugin]
      });
    } catch (err) {
      console.error('Chart error:', err);
    }
  }


  // ===== Subcomandos =====
  // Intenta varias rutas típicas; si ninguna responde, devolvemos null
  async function fetchSubcommands() {
    const tries = [
      '/api/panel/subcomandos/',
      '/api/panel/subcomandos/metadata/',
      '/api/panel/subcomando/metadata/',
      '/api/panel/subcommands/'
    ];
    for (const url of tries) {
      try {
        const data = await getJSON(url);
        if (data) return data;
      } catch (e) { /* sigue intentando */ }
    }
    return null;
  }

  // Normaliza formatos habituales:
  //  - { items:[{nombre, escrutadas, total, porcentaje}, ...] }
  //  - [{name, mesas_escrutadas, total_mesas, pct}, ...]
  function normalizeSubcmdPayload(payload) {
    if (!payload) return [];
    const list = Array.isArray(payload) ? payload
              : (payload.items || payload.data || payload.results || []);
    return (list || []).map(it => {
      const nombre = it.nombre || it.name || it.subcomando || it.label || '—';
      const escru  = it.escrutadas ?? it.mesas_escrutadas ?? it.escrutado ?? it.done ?? 0;
      const total  = it.total ?? it.total_mesas ?? it.mesas ?? it.cantidad ?? 0;
      let pct = it.porcentaje ?? it.pct ?? (total ? (escru * 100 / total) : 0);
      pct = Number.isFinite(+pct) ? +pct : 0;
      return { nombre, escru: +escru || 0, total: +total || 0, pct };
    }).sort((a,b) => b.pct - a.pct);
  }

  function renderSubcommands(list) {
    const el = document.getElementById('subcmdList');
    const card = document.querySelector('.card-subcmd');
    if (!el || !card) return;

    if (!list.length) {
      card.style.display = 'none';
      return;
    }
    card.style.display = '';

    el.innerHTML = '';
    list.forEach(item => {
      const li = document.createElement('li');
      li.className = 'subcmd-item';
      const pctTxt = `${item.pct.toFixed(1)}%`;
      li.innerHTML = `
        <div class="subcmd-row">
          <span class="subcmd-name">${item.nombre}</span>
          <span class="subcmd-val">${item.escru}/${item.total}</span>
        </div>
        <div class="subcmd-bar" aria-label="Avance ${item.nombre}">
          <div class="subcmd-fill" style="--pct:${item.pct}%"></div>
          <span class="subcmd-pct">${pctTxt}</span>
        </div>
      `;
      el.appendChild(li);
    });
  }

  // Usuarios + KPI  (metadata correcta)
  async function renderUsersAndKPI() {
    try {
      const [usersRes, meta] = await Promise.all([
        getJSON(`/api/panel/online-users/`),
        getJSON(`/api/panel/metadata/`)
      ]);

      // usuarios (acepta users o online_users)
      const listRaw = usersRes.users || usersRes.online_users || [];
      const list = listRaw.map(u => typeof u === 'string' ? { username: u, online: true } : u);
      const onlineCount = list.filter(u => u.online).length;
      const totalCount  = (typeof usersRes.total === 'number' ? usersRes.total : list.length) || 100;

      // Pintar lista
      const ul = $("#users");
      if (ul) {
        ul.innerHTML = "";
        list.forEach(u => {
          const li = document.createElement("li");
          li.innerHTML = `<span class="online-dot ${u.online ? 'online' : 'offline'}"></span>${u.username}`;
          ul.appendChild(li);
        });
      }

      // Actualizar título "Usuarios conectados (x/y)"
      const usersTitle = document.querySelector('.card-users h3');
      if (usersTitle) {
        usersTitle.textContent = `Usuarios conectados (${onlineCount}/${totalCount})`;
      }

      // KPI de mesas + efecto reflejo celeste
      const kpis = $("#kpiMesas");
      if (kpis && meta) {
        const total = meta.total_mesas ?? meta.total ?? 0;
        const escru = meta.mesas_escrutadas ?? meta.escrutadas ?? 0;
        const pct   = Number(meta.porcentaje_escrutadas ?? meta.pct ?? 0);
        const pctTxt = Number.isFinite(pct) ? pct.toFixed(2) : pct;

        kpis.textContent = total ? `${escru}/${total} (${pctTxt}%)` : "—";
        const clamped = Math.max(0, Math.min(100, pct));
        kpis.style.setProperty('--pct', `${clamped}%`);
        kpis.classList.add('kpi-bar');
      }
    } catch (err) {
      console.error('Usuarios/KPI:', err);
      const ul = $("#users"); if (ul) ul.innerHTML = '<li style="opacity:.7">—</li>';
      const usersTitle = document.querySelector('.card-users h3');
      if (usersTitle) usersTitle.textContent = 'Usuarios conectados (—/—)';
      const kpis = $("#kpiMesas"); if (kpis) { kpis.textContent = '—'; kpis.classList.remove('kpi-bar'); }
    }
  }

  // Ciclo principal
  async function refreshAll() {
    try {
      setBusy(true);

      // Resúmenes por cargo y render
      const [dip, con] = await Promise.all([
        fetchCargo('DIPUTADOS'),
        fetchCargo('CONCEJALES')
      ]);
      const rows = mergeByPartido(dip, con);
      renderTable(rows, 4);
      renderChart(rows);

      // Usuarios + KPI
      await renderUsersAndKPI();

      // Subcomandos (avance)
      const subcmdRaw = await fetchSubcommands();
      const subcmds   = normalizeSubcmdPayload(subcmdRaw);
      renderSubcommands(subcmds);

      $("#status") && ($("#status").textContent =
        `Última actualización: ${dip.timestamp || con.timestamp || ''}`);
    } catch (e) {
      console.error(e);
      $("#status") && ($("#status").textContent = 'Error al actualizar');
    } finally {
      setBusy(false);
    }
  }

  // Auto refresh
  let timer = null;
  function programarAuto() {
    if (timer) clearInterval(timer);
    const s = Number($("#refreshEvery")?.value || 0);
    if (s > 0) timer = setInterval(refreshAll, s * 1000);
  }

  // Eventos
  $("#btnRefresh")?.addEventListener("click", refreshAll);
  $("#refreshEvery")?.addEventListener("change", programarAuto);
  $("#btnDescargarDip")?.addEventListener("click", e => {
    e.preventDefault(); window.location = `/export/summary.xlsx?cargo=DIPUTADOS`;
  });
  $("#btnDescargarCon")?.addEventListener("click", e => {
    e.preventDefault(); window.location = `/export/summary.xlsx?cargo=CONCEJALES`;
  });

  // Init
  refreshAll();
  programarAuto();
})();
