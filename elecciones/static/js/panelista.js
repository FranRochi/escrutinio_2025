(() => {
  // ===== util =====
  const $ = s => document.querySelector(s);
  const fmtInt = n => Number(n || 0).toLocaleString('es-AR');
  const fmtPct1 = n =>
    (Number(n) || 0).toLocaleString('es-AR', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1
    });

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

  // Trae el resumen por cargo
  async function fetchCargo(key) {
    const qs =
      typeof key === "number"
        ? `cargo_id=${key}`
        : `cargo=${encodeURIComponent(key)}`;
    return getJSON(`/api/panel/summary/?${qs}`);
  }

  // ===== Render tabla combinada (Diputados + Concejales) =====
  function renderTable(dip, con) {
    const tbody = document.querySelector("#tabla tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    const map = {};
    dip.partidos.forEach((p) => {
      map[p.partido_id] = {
        nombre: p.partido,
        dip: p,
        con: { votos: 0, porcentaje: 0 },
      };
    });
    con.partidos.forEach((p) => {
      if (!map[p.partido_id]) {
        map[p.partido_id] = {
          nombre: p.partido,
          dip: { votos: 0, porcentaje: 0 },
          con: p,
        };
      } else {
        map[p.partido_id].con = p;
      }
    });

    const filas = Object.values(map).sort(
      (a, b) => b.dip.votos + b.con.votos - (a.dip.votos + a.con.votos)
    );

    const limitAttr = document.querySelector("#tabla")?.dataset.limit;
    const limite = limitAttr ? Number(limitAttr) : filas.length;

    filas.slice(0, limite).forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="td-left">${row.nombre}</td>
        <td>${fmtInt(row.dip.votos)}</td>
        <td>${row.dip.porcentaje}%</td>
        <td>${fmtInt(row.con.votos)}</td>
        <td>${row.con.porcentaje}%</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ===== Render gráfico horizontal con % en las barras =====
  function renderSingleChart(canvasId, label, rows) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (!rows || rows.length === 0) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.font = "bold 14px system-ui, sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.textAlign = "center";
      ctx.fillText("Sin datos", canvas.width / 2, canvas.height / 2);
      return;
    }

    const labels = rows.map((r) =>
      r.partido.length > 25 ? r.partido.slice(0, 25) + "…" : r.partido
    );
    const data = rows.map((r) => r.votos);
    const total = data.reduce((a, b) => a + (Number(b) || 0), 0);

    new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label, data, backgroundColor: "#3b82f6" }
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (c) => {
                const v = c.parsed.x;
                const pct = total ? fmtPct1((v * 100) / total) : "0.0";
                return `${fmtInt(v)} votos (${pct}%)`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#94a3b8" },
            grid: { color: "rgba(148,163,184,.15)" },
          },
          y: {
            ticks: { color: "#94a3b8" },
            grid: { color: "rgba(148,163,184,.15)" },
          },
        },
      },
      plugins: [
        {
          id: "barLabels",
          afterDatasetsDraw(chart) {
            const { ctx } = chart;
            ctx.save();
            chart.data.datasets.forEach((ds, di) => {
              const meta = chart.getDatasetMeta(di);
              meta.data.forEach((elem, idx) => {
                const v = ds.data[idx];
                if (!v) return;
                const pct = total ? fmtPct1((v * 100) / total) : "0.0";
                ctx.fillStyle = "#e5e7eb";
                ctx.font = "bold 11px system-ui";
                ctx.textAlign = "left";
                ctx.textBaseline = "middle";
                ctx.fillText(`${fmtInt(v)} (${pct}%)`, elem.x + 6, elem.y);
              });
            });
            ctx.restore();
          },
        },
      ],
    });
  }

  // ===== Subcomandos =====
  async function fetchSubcommands() {
    const tries = [
      "/api/panel/subcomandos/",
      "/api/panel/subcomandos/metadata/",
      "/api/panel/subcomando/metadata/",
      "/api/panel/subcommands/",
    ];
    for (const url of tries) {
      try {
        const data = await getJSON(url);
        if (data) return data;
      } catch (e) {}
    }
    return null;
  }

  function normalizeSubcmdPayload(payload) {
    if (!payload) return [];
    const list = Array.isArray(payload)
      ? payload
      : payload.items || payload.data || payload.results || [];
    return (list || []).map((it) => {
      const nombre =
        it.nombre || it.name || it.subcomando || it.label || "—";
      const escru =
        it.escrutadas ??
        it.mesas_escrutadas ??
        it.escrutado ??
        it.done ??
        0;
      const total =
        it.total ??
        it.total_mesas ??
        it.mesas ??
        it.cantidad ??
        0;
      let pct =
        it.porcentaje ?? it.pct ?? (total ? (escru * 100) / total : 0);
      pct = Number.isFinite(+pct) ? +pct : 0;
      return { nombre, escru: +escru || 0, total: +total || 0, pct };
    });
  }

  function renderSubcommands(list) {
    const el = document.getElementById("subcmdList");
    el.innerHTML = "";

    list.forEach((item) => {
      const li = document.createElement("li");
      li.className = "subcmd-item";
      li.innerHTML = `
        <div class="subcmd-row">
          <span class="subcmd-name">${item.nombre}</span>
          <span class="subcmd-val">${item.escru}/${item.total}</span>
        </div>
        <div class="subcmd-bar">
          <div class="subcmd-fill" style="--pct:${item.pct}%"></div>
          <span class="subcmd-pct">${item.pct.toFixed(1)}%</span>
        </div>
      `;
      el.appendChild(li);
    });
  }

  // ===== Usuarios + KPI =====
  async function renderUsersAndKPI() {
    try {
      const [usersRes, meta] = await Promise.all([
        getJSON(`/api/panel/online-users/`),
        getJSON(`/api/panel/metadata/`),
      ]);

      const listRaw = usersRes.users || usersRes.online_users || [];
      const list = listRaw.map((u) =>
        typeof u === "string" ? { username: u, online: true } : u
      );
      const onlineCount = list.filter((u) => u.online).length;
      const totalCount =
        typeof usersRes.total === "number" ? usersRes.total : list.length || 100;

      const ul = $("#users");
      if (ul) {
        ul.innerHTML = "";
        list.forEach((u) => {
          const li = document.createElement("li");
          li.innerHTML = `<span class="online-dot ${
            u.online ? "online" : "offline"
          }"></span>${u.username}`;
          ul.appendChild(li);
        });
      }

      const usersTitle = document.querySelector(".card-users h3");
      if (usersTitle) {
        usersTitle.textContent = `Usuarios conectados (${onlineCount}/${totalCount})`;
      }

      const kpis = $("#kpiMesas");
      if (kpis && meta) {
        const total = meta.total_mesas ?? meta.total ?? 0;
        const escru = meta.mesas_escrutadas ?? meta.escrutadas ?? 0;
        const pct = Number(meta.porcentaje_escrutadas ?? meta.pct ?? 0);
        const pctTxt = Number.isFinite(pct) ? pct.toFixed(2) : pct;

        kpis.textContent = total ? `${escru}/${total} (${pctTxt}%)` : "—";
        const clamped = Math.max(0, Math.min(100, pct));
        kpis.style.setProperty("--pct", `${clamped}%`);
        kpis.classList.add("kpi-bar");
      }
    } catch (err) {
      console.error("Usuarios/KPI:", err);
    }
  }

  // ===== Ciclo principal =====
  async function refreshAll() {
    try {
      setBusy(true);

      const [dip, con] = await Promise.all([
        fetchCargo("DIPUTADOS"),
        fetchCargo("CONCEJALES"),
      ]);

      renderTable(dip, con);

      renderSingleChart("grafico_dipu", "Diputados", dip.partidos.slice(0, 3));
      renderSingleChart("grafico_conce", "Concejales", con.partidos.slice(0, 3));

      await renderUsersAndKPI();

      const subcmdRaw = await fetchSubcommands();
      const subcmds = normalizeSubcmdPayload(subcmdRaw);
      renderSubcommands(subcmds);

      $("#status") &&
        ($("#status").textContent = `Última actualización: ${
          dip.timestamp || con.timestamp || ""
        }`);
    } catch (e) {
      console.error(e);
      $("#status") &&
        ($("#status").textContent = "Error al actualizar");
    } finally {
      setBusy(false);
    }
  }

  // ===== Auto refresh =====
  let timer = null;
  function programarAuto() {
    if (timer) clearInterval(timer);
    const s = Number($("#refreshEvery")?.value || 0);
    if (s > 0) timer = setInterval(refreshAll, s * 1000);
  }

  // ===== Eventos =====
  $("#btnRefresh")?.addEventListener("click", refreshAll);
  $("#refreshEvery")?.addEventListener("change", programarAuto);

  $("#btnDescargarDip")?.addEventListener("click", (e) => {
    e.preventDefault();
    window.location = `/export/summary.xlsx?cargo=DIPUTADOS`;
  });
  $("#btnDescargarCon")?.addEventListener("click", (e) => {
    e.preventDefault();
    window.location = `/export/summary.xlsx?cargo=CONCEJALES`;
  });

  // Init
  refreshAll();
  programarAuto();
})();
