(() => {
  const $ = s => document.querySelector(s);
  let currentPage = 1;
  const pageSize = 15;
  let currentSearch = "";

  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status} en ${url}`);
    return r.json();
  }

  function renderUsuarios(resp) {
    const tbody = $("#tablaUsuarios tbody");
    tbody.innerHTML = "";

    if (!resp.usuarios || !resp.usuarios.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="opacity:.7">— Sin usuarios —</td></tr>`;
      return;
    }

    resp.usuarios.forEach(u => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><span class="online-dot ${u.online ? "online" : "offline"}"></span></td>
        <td>${u.username}</td>
        <td>${u.nombre || ""}</td>
        <td>${u.email || ""}</td>
        <td>${u.role || ""}</td>
        <td>${u.escuela || "—"}</td>
        <td>${u.subcomando || "—"}</td>
        <td>${u.celular || ""}</td>
      `;
      tbody.appendChild(tr);
    });

    $("#statusUsuarios").textContent =
      `Página ${resp.page} de ${Math.ceil(resp.total / resp.page_size)} (Total: ${resp.total})`;
  }

  async function refreshUsuarios() {
    try {
      const url = `/api/panel/usuarios_tabla/?page=${currentPage}&page_size=${pageSize}&search=${encodeURIComponent(currentSearch)}`;
      const data = await getJSON(url);
      renderUsuarios(data);
    } catch (e) {
      console.error("Error usuarios:", e);
      $("#statusUsuarios").textContent = "Error al actualizar";
    }
  }

  $("#btnPrev")?.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      refreshUsuarios();
    }
  });
  $("#btnNext")?.addEventListener("click", () => {
    currentPage++;
    refreshUsuarios();
  });
  $("#btnSearch")?.addEventListener("click", () => {
    currentSearch = $("#searchInput").value.trim();
    currentPage = 1;
    refreshUsuarios();
  });

  refreshUsuarios();
})();
