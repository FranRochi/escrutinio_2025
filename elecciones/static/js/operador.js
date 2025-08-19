/** === Utilidades de formato/validación === **/
function digitsOnly(s) { return String(s || "").replace(/\D/g, ""); }
function clamp350(n) { if (isNaN(n) || n < 0) return 0; if (n > 350) return 350; return n; }
function toNumber(val) { const d = digitsOnly(val); const n = parseInt(d || "0", 10); return clamp350(n); }
function format3(n) { return String(clamp350(n)).padStart(3, "0"); }
function getCookie(name) {
  let cookieArr = document.cookie.split(";");
  for (let i = 0; i < cookieArr.length; i++) {
    let cookie = cookieArr[i].trim();
    if (cookie.startsWith(name + "=")) return cookie.substring(name.length + 1);
  }
  return null;
}

function scrollTopSmooth() {
  try { window.scrollTo({ top: 0, behavior: 'smooth' }); }
  catch { window.scrollTo(0, 0); }
}

document.addEventListener("DOMContentLoaded", function () {
  const mesaSelect = document.getElementById("mesa_select");
  const mensajeError = document.getElementById("mensaje_error_mesa");
  const enviarVotosBtns = Array.from(document.querySelectorAll(".btn-enviar-votos"));
  const savingOverlay = document.getElementById("saving_overlay");

  // Deshabilitar TODOS los botones al inicio
  enviarVotosBtns.forEach(btn => btn.disabled = true);

  // Inputs con 3 dígitos (listas y especiales)
  document.querySelectorAll('.voto_input, .voto_especial_input').forEach((input) => {
    if (!input.placeholder) input.placeholder = '000';

    input.addEventListener('input', () => {
      let d = digitsOnly(input.value).slice(0, 3);
      let n = parseInt(d || "0", 10);
      if (isNaN(n)) n = 0;
      if (n > 350) { d = "350"; n = 350; }
      input.value = d;
      calcularTotales();
    });

    input.addEventListener('blur', () => {
      input.value = format3(toNumber(input.value));
    });
  });

  // Habilitar/deshabilitar envío según mesa seleccionada
  function syncBotonesEnviar() {
    const mesaId = mesaSelect ? (mesaSelect.value || "") : "";
    enviarVotosBtns.forEach(btn => btn.disabled = !mesaId);
    if (mensajeError) mensajeError.textContent = mesaId ? "" : "⚠️ Seleccioná una mesa.";
    const hiddenMesaId = document.getElementById("mesa_id");
    if (hiddenMesaId) hiddenMesaId.value = mesaId;
  }
  if (mesaSelect) mesaSelect.addEventListener("change", syncBotonesEnviar);
  syncBotonesEnviar();

  // Click para TODOS los botones visibles
  enviarVotosBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      if (!btn.disabled) enviarVotos();
    });
  });

  calcularTotales();
});

function calcularTotales() {
  const cargoIdSet = new Set();
  document.querySelectorAll('.voto_input[data-cargo]').forEach(el => {
    if (el.dataset.cargo) cargoIdSet.add(String(el.dataset.cargo));
  });

  const totalesAgrupaciones = {};
  cargoIdSet.forEach(cId => totalesAgrupaciones[cId] = 0);

  document.querySelectorAll('.voto_input[data-cargo]').forEach(input => {
    const cId = String(input.dataset.cargo || "");
    if (!cargoIdSet.has(cId)) return;
    const v = toNumber(input.value);
    totalesAgrupaciones[cId] += v;
  });

  cargoIdSet.forEach(cId => {
    const txt = format3(totalesAgrupaciones[cId] || 0);
    document.querySelectorAll(`[data-total-cargo="${cId}"]`).forEach(el => { if (el) el.value = txt; });
    const byId = document.getElementById(`total_${cId}`);
    if (byId) byId.value = txt;
  });
}

function limpiarFormulario() {
  document.querySelectorAll('.voto_input, .voto_especial_input').forEach(i => { i.value = ""; });
  document.querySelectorAll('[data-total-cargo]').forEach(i => { i.value = ""; });
  document.querySelectorAll('input[id^="total_"]').forEach(i => { i.value = ""; });

  const el1 = document.getElementById('electores_votaron');
  const el2 = document.getElementById('sobres_encontrados');
  const el3 = document.getElementById('diferencia_sobres');
  if (el1) el1.value = "";
  if (el2) el2.value = "";
  if (el3) el3.value = "";

  const msg = document.getElementById('mensaje_validacion');
  if (msg && msg.classList) msg.classList.remove('input-error');

  calcularTotales();
}

function enviarVotos() {
  const mesaIdEl = document.getElementById("mesa_id");
  if (!mesaIdEl || !mesaIdEl.value) {
    alert("Seleccioná una mesa");
    return;
  }

  const votosCargo = [];
  const votosEspeciales = [];

  // Enviar SOLO valores > 0 (reduce payload y trabajo en DB)
  document.querySelectorAll(".voto_input").forEach(input => {
    const cantidad = toNumber(input.value);
    if (cantidad === 0) return; // filtra ceros
    const partidoId = input.dataset.partido;
    const cargoId = input.dataset.cargo;
    votosCargo.push({
      partido_postulacion_id: Number(partidoId),
      cargo_id: Number(cargoId),
      votos: cantidad,
    });
  });

  document.querySelectorAll(".voto_especial_input").forEach(input => {
    const cantidad = toNumber(input.value);
    if (cantidad === 0) return; // filtra ceros
    const tipoVoto = input.dataset.tipo;
    const cargoId = input.dataset.cargo;
    votosEspeciales.push({
      tipo: tipoVoto,
      cargo_postulacion_id: Number(cargoId),
      votos: cantidad,
    });
  });

  const resumenMesa = {
    electores_votaron: toNumber(document.getElementById("electores_votaron")?.value),
    sobres_encontrados: toNumber(document.getElementById("sobres_encontrados")?.value),
    diferencia: toNumber(document.getElementById("diferencia_sobres")?.value),
  };

  const payload = {
    mesa_id: Number(mesaIdEl.value),
    votos_cargo: votosCargo,
    votos_especiales: votosEspeciales,
    resumen_mesa: resumenMesa,
  };

  // Feedback visual: overlay + deshabilitar botones
  document.getElementById("saving_overlay")?.removeAttribute("hidden");
  document.querySelectorAll(".btn-enviar-votos").forEach(b => b.disabled = true);

  fetch("/operador/guardar-votos/", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie('csrftoken'),
      "X-Requested-With": "XMLHttpRequest"
    },
    body: JSON.stringify(payload),
  })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.status === "ok") {
        alert("✅ Votos guardados correctamente");

        // Quitar mesa del select y limpiar
        const mesaSelect = document.getElementById("mesa_select");
        if (mesaSelect) {
          mesaSelect.remove(mesaSelect.selectedIndex);
          const hiddenMesaId = document.getElementById("mesa_id");
          if (hiddenMesaId) hiddenMesaId.value = "";
        }

        limpiarFormulario();
        scrollTopSmooth();

        const msg = document.getElementById("mensaje_validacion");
        if (msg) {
          msg.style.display = "block";
          msg.style.color = "green";
          msg.textContent = "Mesa guardada y marcada como escrutada. Seleccioná otra mesa.";
        }
      } else {
        if (res.status === 409) {
          alert(data.message || "La mesa ya fue escrutada y no puede modificarse.");
        } else if (res.status === 401 || res.status === 403) {
          alert("Sesión no válida o sin permisos. Volvé a iniciar sesión.");
        } else {
          alert("❌ Error al guardar votos: " + (data.message || `HTTP ${res.status}`));
        }
        console.error("Guardar votos - respuesta:", res.status, data);
      }
    })
    .catch(err => {
      console.error("Error al enviar votos:", err);
      alert("❌ Error de red o servidor");
    })
    .finally(() => {
      // Ocultar overlay y re-habilitar según mesa
      document.getElementById("saving_overlay")?.setAttribute("hidden", "");
      const mesaId = document.getElementById("mesa_id")?.value || "";
      document.querySelectorAll(".btn-enviar-votos").forEach(b => b.disabled = !mesaId);
    });
}
