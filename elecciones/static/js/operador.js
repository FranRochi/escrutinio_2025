/** === Utilidades de formato/validación (actualizadas) === **/
function digitsOnly(s) { return String(s || "").replace(/\D/g, ""); }

/** Devuelve el E efectivo para validar inputs (0 si vacío o inválido). */
function getElectoresCap() {
  const el = document.getElementById("electores_votaron");
  const d = digitsOnly(el?.value);
  const n = parseInt(d || "0", 10);
  // E no puede ser negativo
  return isNaN(n) || n < 0 ? 0 : n;
}

/** 
 * Reglas nuevas para inputs de votos:
 * - Máximo permitido por input = E (electores que votaron)
 * - Si el usuario pone >350 en un input, NO clampa: se vuelve 000
 * - Si pone >E, también 000
 */
function sanitizeVoteForInputs(val) {
  const d = digitsOnly(val).slice(0, 3);       // sólo 3 dígitos
  if (!d) return 0;
  const n = parseInt(d, 10);
  const E = getElectoresCap();

  // Si escribe >350 -> 000 (regla pedida)
  if (n > 350) return 0;

  // Si E=0, ningún input puede tener valor >0
  if (E <= 0) return 0;

  // Si escribe >E -> 000
  if (n > E) return 0;

  // Acepta n entre 0..min(E,350) pero SIN clamping hacia arriba
  return n;
}

/** Formato “000” para mostrar */
function format3(n) {
  const x = (isNaN(n) || n < 0) ? 0 : n;
  return String(x).padStart(3, "0");
}

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

/** Parse para campos del resumen (0..350) */
function toNumber350(val) {
  const d = digitsOnly(val).slice(0, 3);
  let n = parseInt(d || "0", 10);
  if (isNaN(n) || n < 0) n = 0;
  if (n > 350) n = 350;
  return n;
}

/** Devuelve el valor numérico vigente de un input de votos, aplicando tus reglas */
function getVoteValue(input) {
  return sanitizeVoteForInputs(input.value);
}

function getEffectiveCap() {
  // E ya lo limitás a 0..350 en los handlers del input
  return Math.min(getElectoresCap(), 350);
}

function showNotification(msg, timeout=3000) {
  const container = document.getElementById("noti-container");
  if (!container) return;

  const div = document.createElement("div");
  div.className = "noti";
  div.textContent = msg;
  container.appendChild(div);

  // forzar reflow para que la animación funcione
  void div.offsetWidth;
  div.classList.add("show");

  setTimeout(() => {
    div.classList.remove("show");
    setTimeout(() => div.remove(), 300);
  }, timeout);
}

// Para evitar notificaciones repetidas mientras la columna se mantenga en CAP
const notifiedAtCap = new Set(); // guarda ids de cargo (cId) que ya notificaron


document.addEventListener("DOMContentLoaded", function () {
  const mesaSelect = document.getElementById("mesa_select");
  const mensajeError = document.getElementById("mensaje_error_mesa");
  const enviarVotosBtns = Array.from(document.querySelectorAll(".btn-enviar-votos"));
  const savingOverlay = document.getElementById("saving_overlay");

  // Deshabilitar TODOS los botones al inicio
  enviarVotosBtns.forEach(btn => btn.disabled = true);

  // Inputs de votos (agrupaciones y especiales)
  function bindVoteInputs() {
    document.querySelectorAll('.voto_input, .voto_especial_input').forEach((input) => {
      if (!input.placeholder) input.placeholder = '000';

      input.addEventListener('input', () => {
        const n = sanitizeVoteForInputs(input.value);
        input.value = digitsOnly(String(n)).slice(0, 3);
        // Aplica la regla de dominancia por cargo (si alguien iguala E, los demás a 000)
        enforceCapAndDominanceByCargo();
        enforceMaxSumByCargo();
        enforceGlobalSumByCargo(true)
        calcularTotales();
      });

      input.addEventListener('blur', () => {
        const n = sanitizeVoteForInputs(input.value);
        input.value = format3(n);
        enforceCapAndDominanceByCargo();
        enforceMaxSumByCargo();
        enforceGlobalSumByCargo()
        calcularTotales();
      });
    });
  }
  bindVoteInputs();

  // Cuando cambia "Cantidad de electores que han votado" (E), revalida todo
  const elElectores = document.getElementById("electores_votaron");
  if (elElectores) {
    elElectores.addEventListener('input', () => {
      // opcional: si querés limitar E a 350 en el resumen:
      const d = digitsOnly(elElectores.value).slice(0, 3);
      let n = parseInt(d || "0", 10);
      if (isNaN(n) || n < 0) n = 0;
      if (n > 350) n = 350; // mantener 350 como máximo en el resumen
      elElectores.value = n ? String(n) : "";
      // Revalida todos los inputs con el nuevo E
      sanitizeAllVotesAgainstE();
      enforceCapAndDominanceByCargo();
      enforceMaxSumByCargo();
      enforceGlobalSumByCargo()
      calcularTotales();
      notifiedAtCap.clear();
    });

    elElectores.addEventListener('blur', () => {
      // Formato normal (sin ceros a la izquierda) en el resumen
      const d = digitsOnly(elElectores.value).slice(0, 3);
      let n = parseInt(d || "0", 10);
      if (isNaN(n) || n < 0) n = 0;
      if (n > 350) n = 350;
      elElectores.value = n ? String(n) : "";
      sanitizeAllVotesAgainstE();
      enforceCapAndDominanceByCargo();
      enforceMaxSumByCargo();
      enforceGlobalSumByCargo(false)
      calcularTotales();
      notifiedAtCap.clear();
    });
  }

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

  /**
   * Recorre todos los inputs y aplica la regla: si valor > E o >350 => 000
   */
  function sanitizeAllVotesAgainstE() {
    const E = getElectoresCap();
    document.querySelectorAll('.voto_input, .voto_especial_input').forEach((input) => {
      const n = sanitizeVoteForInputs(input.value);
      input.value = n ? digitsOnly(String(n)).slice(0, 3) : "";
    });
  }

  /**
   * Por cada cargo:
   *  - Si algún input == E (y E>0), los demás inputs de ese cargo => "000".
   *  - En cualquier caso, valores >E o >350 ya quedan en "000" por sanitizeVoteForInputs.
   */
  function enforceCapAndDominanceByCargo() {
    const CAP = getEffectiveCap();
    if (CAP <= 0) {
      document.querySelectorAll('.voto_input, .voto_especial_input').forEach(inp => { inp.value = ""; });
      return;
    }

    // Agrupar inputs por columna/cargo
    const inputsByCargo = new Map();
    document.querySelectorAll('.voto_input[data-cargo], .voto_especial_input[data-cargo]').forEach(inp => {
      const cId = String(inp.dataset.cargo || "");
      if (!inputsByCargo.has(cId)) inputsByCargo.set(cId, []);
      inputsByCargo.get(cId).push(inp);
    });

    inputsByCargo.forEach((inputs) => {
      let dominantIndex = -1;

      inputs.forEach((inp, idx) => {
        const n = sanitizeVoteForInputs(inp.value);
        inp.value = n ? digitsOnly(String(n)).slice(0, 3) : "";
        if (n === CAP && dominantIndex === -1) {
          dominantIndex = idx; // el primero que iguala E domina la columna
        }
      });

      if (dominantIndex >= 0) {
        inputs.forEach((inp, idx) => {
          if (idx !== dominantIndex) inp.value = "";
        });
      }
    });
  }

  /**
   * Por cada cargo:
   * - La suma de inputs (agrupaciones + especiales) no puede pasar 350
   * - Si pasa, se van ajustando los últimos valores ingresados a 000
   */
  function enforceMaxSumByCargo() {
    const CAP = getEffectiveCap();
    const cargos = new Map();

    // Reunir inputs por cargo (partidos + especiales)
    document.querySelectorAll('.voto_input[data-cargo], .voto_especial_input[data-cargo]').forEach(inp => {
      const cId = String(inp.dataset.cargo || "");
      if (!cargos.has(cId)) cargos.set(cId, []);
      cargos.get(cId).push(inp);
    });

    cargos.forEach((inputs) => {
      let sum = 0;
      const valores = inputs.map(inp => getVoteValue(inp));
      valores.forEach(v => sum += v);

      if (sum > CAP) {
        let overshoot = sum - CAP;

        // Reducimos desde el último input con valor > 0 hacia arriba
        for (let i = inputs.length - 1; i >= 0 && overshoot > 0; i--) {
          const inp = inputs[i];
          const n = getVoteValue(inp);
          if (n > 0) {
            const quitar = Math.min(n, overshoot);
            const nuevo = n - quitar;          // clamp hacia abajo
            inp.value = nuevo ? format3(nuevo) : ""; // “000” si quedó en 0
            overshoot -= quitar;
          }
        }
      }
    });
  }

  /** Chequea que la suma de (partidos + blancos + impugnados) no pase E
   *  y muestra una notificación sutil SOLO la primera vez que una columna llega EXACTA a E.
   */
  function enforceGlobalSumByCargo() {
    const CAP = getEffectiveCap();
    if (CAP <= 0) return;

    const cargos = new Map();
    document.querySelectorAll('.voto_input[data-cargo], .voto_especial_input[data-cargo]').forEach(inp => {
      const cId = String(inp.dataset.cargo || "");
      if (!cargos.has(cId)) cargos.set(cId, []);
      cargos.get(cId).push(inp);
    });

    cargos.forEach((inputs, cId) => {
      // 1) Suma actual
      let sum = 0;
      inputs.forEach(inp => { sum += getVoteValue(inp); });

      // 2) Si se excede, ajustamos desde el último input hacia arriba
      if (sum > CAP) {
        let overshoot = sum - CAP;
        for (let i = inputs.length - 1; i >= 0 && overshoot > 0; i--) {
          const inp = inputs[i];
          const n = getVoteValue(inp);
          if (n > 0) {
            const quitar = Math.min(n, overshoot);
            const nuevo = n - quitar;
            inp.value = nuevo ? format3(nuevo) : "";
            overshoot -= quitar;
          }
        }
      }

      // 3) Recalcular suma tras posibles ajustes
      let total = 0;
      inputs.forEach(inp => { total += getVoteValue(inp); });

      // 4) Notificar solo una vez por columna cuando llega EXACTO a E
      if (total === CAP) {
        if (!notifiedAtCap.has(cId)) {
          showNotification("⚠️ Se alcanzó la cantidad de electores que han votado");
          notifiedAtCap.add(cId);
        }
      } else {
        // Si baja de E, permitir notificar nuevamente cuando vuelva a llegar
        if (notifiedAtCap.has(cId)) notifiedAtCap.delete(cId);
      }
    });
  }

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
    const v = getVoteValue(input); // <<<<
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
  // 1) votos de agrupaciones
  document.querySelectorAll(".voto_input").forEach(input => {
    const cantidad = getVoteValue(input);  // <<<< antes: toNumber(...)
    if (cantidad === 0) return;
    const partidoId = input.dataset.partido;
    const cargoId = input.dataset.cargo;
    votosCargo.push({
      partido_postulacion_id: Number(partidoId),
      cargo_id: Number(cargoId),
      votos: cantidad,
    });
  });

  // 2) especiales
  document.querySelectorAll(".voto_especial_input").forEach(input => {
    const cantidad = getVoteValue(input);  // <<<< antes: toNumber(...)
    if (cantidad === 0) return;
    const tipoVoto = input.dataset.tipo;
    const cargoId = input.dataset.cargo;
    votosEspeciales.push({
      tipo: tipoVoto,
      cargo_postulacion_id: Number(cargoId),
      votos: cantidad,
    });
  });

  // 3) resumen
  const resumenMesa = {
    electores_votaron: toNumber350(document.getElementById("electores_votaron")?.value), // <<<<
    sobres_encontrados: toNumber350(document.getElementById("sobres_encontrados")?.value), // <<<<
    diferencia: toNumber350(document.getElementById("diferencia_sobres")?.value),          // <<<<
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
