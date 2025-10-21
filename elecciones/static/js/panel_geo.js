function initPanel(tipo) {
  const targetId =
    tipo === "secciones" ? "seccionList"
    : tipo === "circuitos_diputados" ? "circuitoListDip"
    : tipo === "subcomandos_concejales" ? "subcomandoListCon"
    : tipo === "subcomandos_diputados" ? "subcomandoListDip"
    : tipo === "subcomandos_extranjeros_concejales" ? "subcomandoListExtCon"
    : tipo === "subcomandos_extranjeros_diputados" ? "subcomandoListExtDip"
    : tipo === "subcomandos" ? "subcomandoList"
    : "circuitoList";

  const headId =
    tipo === "secciones" ? "seccionHead"
    : tipo === "circuitos_diputados" ? "circuitoHeadDip"
    : tipo === "subcomandos_concejales" ? "subcomandoHeadCon"
    : tipo === "subcomandos_diputados" ? "subcomandoHeadDip"
    : tipo === "subcomandos_extranjeros_concejales" ? "subcomandoHeadExtCon"
    : tipo === "subcomandos_extranjeros_diputados" ? "subcomandoHeadExtDip"
    : tipo === "subcomandos" ? "subcomandoHead"
    : "circuitoHead";

  const paginationId =
    tipo === "secciones"
      ? "paginationControlsSecciones"
      : tipo === "circuitos_diputados"
      ? "paginationControlsDip"
      : tipo === "subcomandos"
      ? "paginationControlsSub"
      : tipo === "subcomandos_concejales"
      ? "paginationControlsSubCon"
      : tipo === "subcomandos_diputados"
      ? "paginationControlsSubDip"
      : tipo === "subcomandos_extranjeros_concejales"
      ? "paginationControlsSubExtCon"
      : tipo === "subcomandos_extranjeros_diputados"
      ? "paginationControlsSubExtDip"
      : "paginationControls";

  const apiUrl =
    tipo === "secciones" ? "/api/panel/secciones/"
    : tipo === "circuitos_diputados" ? "/api/panel/circuitos_diputados/"
    : tipo === "subcomandos_concejales" ? "/api/panel/subcomandos_concejales/"
    : tipo === "subcomandos_diputados" ? "/api/panel/subcomandos_diputados/"
    : tipo === "subcomandos_extranjeros_concejales" ? "/api/panel/subcomandos_extranjeros_concejales/"
    : tipo === "subcomandos_extranjeros_diputados" ? "/api/panel/subcomandos_extranjeros_diputados/"
    : tipo === "subcomandos" ? "/api/panel/subcomandos/"
    : "/api/panel/circuitos/";

  // --- Paginación ---
  let currentPage = 1;
  const perPage =
    tipo === "subcomandos" || tipo === "subcomandos_concejales" || tipo === "subcomandos_diputados"
      ? 5
      : 10;
  let dataCache = [];
  let globalOrder = [];

  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`Error HTTP ${r.status}`);
    return r.json();
  }

  function paginate(arr, page) {
    const start = (page - 1) * perPage;
    return arr.slice(start, start + perPage);
  }

  function renderPagination(totalItems) {
    const totalPages = Math.ceil(totalItems / perPage);
    const nav = document.getElementById(paginationId);
    if (!nav) return;
    nav.innerHTML = `
      <button ${currentPage === 1 ? "disabled" : ""} id="btnPrev_${tipo}">Anterior</button>
      <span>Página ${currentPage} de ${totalPages}</span>
      <button ${currentPage === totalPages ? "disabled" : ""} id="btnNext_${tipo}">Siguiente</button>
    `;
    document.getElementById(`btnPrev_${tipo}`)?.addEventListener("click", () => {
      if (currentPage > 1) {
        currentPage--;
        renderAvance(dataCache);
      }
    });
    document.getElementById(`btnNext_${tipo}`)?.addEventListener("click", () => {
      if (currentPage < totalPages) {
        currentPage++;
        renderAvance(dataCache);
      }
    });
  }

  function renderAvance(list) {
    // === LISTA LATERAL (Avance por Sección o Subcomando) ===
    const listaEl =
      tipo === "secciones"
        ? document.getElementById("seccionList")
        : document.getElementById("subcomandoList");

    if (listaEl) {
      listaEl.innerHTML = "";
      list.forEach((item) => {
        const li = document.createElement("li");
        li.className = "seccion-item";
        li.innerHTML = `
          <div class="seccion-row">
            <span class="seccion-name">${item.nombre}</span>
            <span class="seccion-val">${item.escrutadas}/${item.total}</span>
          </div>
          <div class="seccion-bar">
            <div class="seccion-fill" style="--pct:${item.porcentaje}%"></div>
            <span class="seccion-pct">${Number(item.porcentaje).toFixed(1)}%</span>
          </div>
        `;
        if (tipo === "secciones") {
          li.addEventListener("click", () => loadDetalle(item.nombre));
        } else if (tipo.includes("subcomandos")) {
          li.addEventListener("click", () => loadDetalleSubcomando(item.nombre));
        }
        listaEl.appendChild(li);
      });
    }

    // === TABLAS DE RESULTADOS (solo Diputados Nacionales: Circuitos y Subcomandos) ===
    if (tipo === "circuitos_diputados" || tipo === "subcomandos_diputados") {
      const tbody = document.getElementById(
        tipo === "circuitos_diputados" ? "circuitoListDip" : "subcomandoListDip"
      );
      const head = document.getElementById(
        tipo === "circuitos_diputados" ? "circuitoHeadDip" : "subcomandoHeadDip"
      );
      if (!tbody || !head) return;

      // Calcular orden global de partidos
      if (list.length > 0) {
        const totales = {};
        list.forEach((row) => {
          (row.partidos || []).forEach((p) => {
            totales[p.sigla] = (totales[p.sigla] || 0) + (p.votos || 0);
          });
        });
        globalOrder = Object.entries(totales)
          .map(([sigla, votos]) => {
            const ejemplo = list.find((r) =>
              r.partidos.some((p) => p.sigla === sigla)
            );
            return {
              sigla,
              nombre: ejemplo.partidos.find((p) => p.sigla === sigla).nombre,
              votos,
            };
          })
          .sort((a, b) => b.votos - a.votos);
      }

      // Encabezado
      if (list.length > 0 && globalOrder.length > 0) {
        head.innerHTML = `
          <tr class="thead-group">
            <th class="th-left">${
              tipo === "subcomandos_diputados" ? "SUBCOMANDO" : "CIRCUITO"
            }</th>
            ${globalOrder
              .map(
                (p) =>
                  `<th colspan="2"><span class="sigla" data-nombre="${p.nombre}">${p.sigla}</span></th>`
              )
              .join("")}
          </tr>
          <tr class="thead-sub">
            <th></th>
            ${globalOrder.map(() => `<th>VOTOS</th><th>%</th>`).join("")}
          </tr>
        `;
      }

      const paginated = paginate(list, currentPage);
      tbody.innerHTML = "";

      paginated.forEach((item) => {
        const tr = document.createElement("tr");
        const label = `${item.nombre} ${item.escrutadas || 0}/${item.total || 0} (${Number(item.porcentaje).toFixed(1)}%)`;

        const mapPartidos = {};
        item.partidos.forEach((p) => {
          mapPartidos[p.sigla] = p;
        });

        const cols = globalOrder
          .map((ref) => {
            const p = mapPartidos[ref.sigla] || { votos: 0, porcentaje: 0 };
            return `
              <td class="num">${p.votos}</td>
              <td class="pct">${Number(p.porcentaje).toFixed(1)}%</td>
            `;
          })
          .join("");

        tr.innerHTML = `<td>${label}</td>${cols}`;
        tbody.appendChild(tr);
      });

      renderPagination(list.length);

      // Tooltips
      document.querySelectorAll(".sigla").forEach((el) => {
        el.addEventListener("mouseenter", () => {
          const tip = document.createElement("div");
          tip.className = "tooltip-sigla";
          tip.textContent = el.dataset.nombre;
          document.body.appendChild(tip);
          const rect = el.getBoundingClientRect();
          tip.style.left = rect.left + "px";
          tip.style.top = rect.top - 28 + "px";
          el._tooltip = tip;
        });
        el.addEventListener("mouseleave", () => el._tooltip?.remove());
      });
    }

  }


  // === Helpers gráfico con solapas ===
  let chart = null;
  function renderChart(labels, data, cargoLabel) {
    const ctx = document.getElementById("graficoDetalle").getContext("2d");
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels,
        datasets: [
          {
            data,
            backgroundColor: [
              "rgb(59,130,246)",
              "rgba(118,0,253,1)",
              "rgb(34,197,94)",
              "rgb(250,204,21)",
              "rgba(255,11,161,1)",
              "rgb(6,182,212)",
              "rgb(244,114,182)",
              "rgb(251,146,60)"
            ],
            borderColor: "#0b1220",
            borderWidth: 2,
            hoverOffset: 18,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#e5e7eb", padding: 16, font: { size: 14, weight: "bold" } },
          },
          title: { display: true, text: cargoLabel, color: "#e5e7eb" },
        },
      },
    });
  }

  async function loadDetalle(seccionNombre) {
    try {
      const detalle = await getJSON(`/api/panel/seccion/${seccionNombre}/`);

      // --- Gráfico de Diputados ---
      const labels = detalle.filas.map(p => p.partido);
      const data = detalle.filas.map(p => p.diputados);
      renderChart(labels, data, "Diputados Nacionales");

      // --- Marcar activa la sección seleccionada ---
      document.querySelectorAll(".seccion-item").forEach(el => el.classList.remove("active"));
      const selected = Array.from(document.querySelectorAll(".seccion-item"))
        .find(li => li.querySelector(".seccion-name").textContent === seccionNombre);
      if (selected) selected.classList.add("active");

      // --- Listado de partidos y votos ---
      const ul = document.getElementById("detallePartidos");
      ul.innerHTML = "";
      detalle.filas.forEach(p => {
        const li = document.createElement("li");
        li.innerHTML = `<span>${p.partido}</span> <span>Votos: ${p.diputados}</span>`;
        ul.appendChild(li);
      });

      // --- Listado de circuitos con avance ---
      const ulc = document.getElementById("detalleCircuitos");
      ulc.innerHTML = "";
      detalle.circuitos.forEach(c => {
        const li = document.createElement("li");
        li.textContent = `Circuito ${c.codigo} – ${c.escrutadas}/${c.total} (${Number(c.porcentaje).toFixed(1)}%)`;
        ulc.appendChild(li);
      });

      document.getElementById("detalleTitulo").textContent = `Detalle de ${seccionNombre}`;
      document.getElementById("seccionDetalle").style.display = "grid";
    } catch (err) {
      console.error("Error detalle sección:", err);
    }
  }


  async function loadDetalleSubcomando(subNombre) {
    try {
      const detalle = await getJSON(`/api/panel/subcomando/${subNombre}/`);
      const labels = detalle.filas.map(p => p.partido);
      const data = detalle.filas.map(p => p.diputados);

      renderChart(labels, data, "Diputados Nacionales");

      // Marcar activo el subcomando seleccionado
      document.querySelectorAll(".seccion-item").forEach(el => el.classList.remove("active"));
      const selected = Array.from(document.querySelectorAll(".seccion-item"))
        .find(li => li.querySelector(".seccion-name").textContent === subNombre);
      if (selected) selected.classList.add("active");

      // Lista de partidos con votos
      const ul = document.getElementById("detallePartidos");
      ul.innerHTML = "";
      detalle.filas.forEach(p => {
        const li = document.createElement("li");
        li.innerHTML = `<span>${p.partido}</span> <span>Diputados: ${p.diputados}</span>`;
        ul.appendChild(li);
      });

      // Lista de escuelas con avance
      const ulc = document.getElementById("detalleEscuelas");
      ulc.innerHTML = "";
      detalle.escuelas.forEach(e => {
        const li = document.createElement("li");
        li.textContent = `Escuela ${e.nombre} – ${e.escrutadas}/${e.total} (${Number(e.porcentaje).toFixed(1)}%)`;
        ulc.appendChild(li);
      });

      document.getElementById("detalleTitulo").textContent = `Detalle de ${subNombre}`;
      document.getElementById("subcomandoDetalle").style.display = "grid";
    } catch (err) {
      console.error("Error detalle subcomando:", err);
    }
  }


  async function refresh() {
    try {
      const data = await getJSON(apiUrl);
      dataCache = data.items || [];

      if (tipo === "circuitos" || tipo === "circuitos_diputados") {
        const totales = {};
        dataCache.forEach((circ) => {
          (circ.partidos || []).forEach((p) => {
            totales[p.sigla] = (totales[p.sigla] || 0) + (p.votos || 0);
          });
        });
        globalOrder = Object.entries(totales)
          .map(([sigla, votos]) => {
            const partidoEj = dataCache.find((c) =>
              c.partidos?.some((p) => p.sigla === sigla)
            );
            const nombre = partidoEj
              ? partidoEj.partidos.find((p) => p.sigla === sigla).nombre
              : sigla;
            return { sigla, nombre, votos };
          })
          .sort((a, b) => b.votos - a.votos);
      }

      renderAvance(dataCache);
    } catch (err) {
      console.error(err);
    }
  }

  refresh();
  setInterval(refresh, 60000);
}
