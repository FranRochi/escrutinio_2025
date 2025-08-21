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

function updateMesaOptionAppearance(mesaId, escrutada = true) {
  const sel = document.getElementById("mesa_select");
  if (!sel) return;
  const opt = Array.from(sel.options).find(o => String(o.value) === String(mesaId));
  if (!opt) return;
  opt.dataset.escrutada = escrutada ? "1" : "0";
  // normalizar el texto (sin duplicar el "✓")
  const baseText = opt.textContent.replace(/\s*\(✓\s*escrutada\)\s*$/i, "");
  opt.textContent = escrutada ? `${baseText} (✓ escrutada)` : baseText;
}

let IS_PAINTING = false;
let IS_SAVING = false; //candado para evitar doble submit

function getActiveRoot() {
  const desk = document.querySelector('.only-landscape');
  const mob  = document.querySelector('.only-mobile');

  const isVisible = el => !!(el && el.offsetParent !== null);
  // Si desktop está visible, usalo; si no, mobile.
  return isVisible(desk) ? desk : mob || document;
}

/* === OFFLINE QUEUE (IndexedDB) – helpers en ventana === */
(function(){
  const DB = 'votos-offline';
  const STORE = 'queue';
  function openDB(){
    return new Promise((res, rej)=>{
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }
  async function tx(mode, fn){
    const db = await openDB();
    return new Promise((ok,ko)=>{
      const t = db.transaction(STORE, mode);
      const s = t.objectStore(STORE);
      fn(s, t);
      t.oncomplete = ok;
      t.onerror = () => ko(t.error);
    });
  }
  window.OfflineQueue = {
    add: (rec) => tx('readwrite', s => s.add({ ...rec, status:'pending', createdAt: Date.now() })),
    list: () => new Promise(async ok=>{
      const db = await openDB(); const t = db.transaction(STORE,'readonly'); const s=t.objectStore(STORE);
      const r = s.getAll(); r.onsuccess=()=>ok(r.result||[]);
    }),
    get: (id) => new Promise(async ok=>{
      const db = await openDB(); const t = db.transaction(STORE,'readonly'); const s=t.objectStore(STORE);
      const r = s.get(id); r.onsuccess=()=>ok(r.result||null);
    }),
    update: (id, patch) => tx('readwrite', (s)=> s.get(id).onsuccess = (e) => s.put({ ...e.target.result, ...patch })),
    remove: (id) => tx('readwrite', s => s.delete(id)),
  };
})();

/* === Service Worker: registro + utilidades === */
async function drainNow(){
  if (navigator.serviceWorker?.controller) {
    navigator.serviceWorker.controller.postMessage({ type:'DRAIN_NOW' });
    try {
      const reg = await navigator.serviceWorker.ready;
      if ('sync' in reg) await reg.sync.register('send-votos');
    } catch {}
  } else {
    // fallback: no hay SW controlando todavía
    manualDrainFromPage();
  }
}

// Cuando el SW pida confirmación (409), mostramos confirm y reintentamos con overwrite
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw-votos.js').catch(()=>{});
  navigator.serviceWorker.addEventListener('message', async (ev) => {
    if (ev.data?.type === 'NEEDS_CONFIRM') {
      const { id, message } = ev.data;
      const it = await OfflineQueue.get(id);
      if (!it) return;
      const ok = confirm(message || "La mesa ya fue escrutada. ¿Sobrescribir con esta carga?");
      if (ok) {
        await OfflineQueue.update(id, { status:'pending', payload: { ...it.payload, overwrite:true } });
        drainNow();
      } else {
        await OfflineQueue.update(id, { status:'cancelled' });
      }
    }
  });
  window.addEventListener('online', drainNow);
}

// Fallback (sin SW): drenar desde la misma página
async function manualDrainFromPage(){
  const items = await OfflineQueue.list();
  for (const it of items.filter(x => x.status==='pending')) {
    try {
      const res = await fetch("/operador/guardar-votos/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": it.csrf || ""
        },
        body: JSON.stringify(it.payload),
      });
      const data = await res.json().catch(()=>({}));
      if (res.ok && data.status === "ok") {
        await OfflineQueue.remove(it.id);
      } else if (res.status === 409) {
        const ok = confirm((data.message || "La mesa ya está escrutada. ¿Sobrescribir?"));
        if (ok) {
          await OfflineQueue.update(it.id, { status:'pending', payload: { ...it.payload, overwrite:true } });
          return manualDrainFromPage();
        } else {
          await OfflineQueue.update(it.id, { status:'cancelled' });
        }
      } else if (res.status === 403) {
        await OfflineQueue.update(it.id, { status:'blocked_auth' });
      }
    } catch (e) {
      // sigue pending
    }
  }
}


document.addEventListener("DOMContentLoaded", function () {
  // Marcar visualmente las mesas que ya vienen escrutadas desde el servidor
  const selMesa = document.getElementById("mesa_select");
  if (selMesa) {
    Array.from(selMesa.options).forEach(o => {
      if (o.dataset.escrutada === "1") updateMesaOptionAppearance(o.value, true);
    });
  }

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
  if (mesaSelect) {
  mesaSelect.addEventListener("change", () => {
    const mesaId = mesaSelect.value;
    if (!mesaId) { limpiarFormulario(); return; }

    IS_PAINTING = true;                 // ⬅️ ACTIVAR

    limpiarFormulario();

    fetch(`/operador/mesa/${mesaId}/datos/`, {
      method: "GET",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
    .then(r => r.json())
    .then(data => {
      if (data?.status !== "ok") return;

      updateMesaOptionAppearance(mesaId, String(data.escrutada) === "1");

      // resumen
      const rv = data.resumen || {};
      const el1 = document.getElementById("electores_votaron");
      const el2 = document.getElementById("sobres_encontrados");
      const el3 = document.getElementById("diferencia_sobres");
      if (el1) el1.value = rv.electores_votaron ?? "";
      if (el2) el2.value = rv.sobres_encontrados ?? "";
      if (el3) el3.value = rv.diferencia ?? "";

      // agrupaciones
      (data.votos_cargo || []).forEach(v => {
        document.querySelectorAll(
          `.voto_input[data-cargo="${v.cargo_id}"][data-partido="${v.partido_postulacion_id}"]`
        ).forEach(inp => { inp.value = format3(v.votos); });
      });

      // especiales
      (data.votos_especiales || []).forEach(v => {
        document.querySelectorAll(
          `.voto_especial_input[data-cargo="${v.cargo_postulacion_id}"][data-tipo="${v.tipo}"]`
        ).forEach(inp => { inp.value = format3(v.votos); });
      });

    })
    .catch(err => {
      console.error("Error cargando mesa:", err);
    })
    .finally(() => {
      IS_PAINTING = false;              // ⬅️ DESACTIVAR
      // Al terminar de pintar: solo recalcular totales, SIN enforcement destructivo ni notificación
      calcularTotales();
    });
  });

}


  // Click para TODOS los botones visibles
  enviarVotosBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      if (!btn.disabled && !IS_SAVING) enviarVotos();
    });
  });

  /**
   * Recorre todos los inputs y aplica la regla: si valor > E o >350 => 000
   */
  function sanitizeAllVotesAgainstE() {
    const root = getActiveRoot();
    root.querySelectorAll('.voto_input, .voto_especial_input').forEach((input) => {
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
    if (IS_PAINTING) return;

    const CAP = getEffectiveCap();
    const root = getActiveRoot();

    if (CAP <= 0) {
      root.querySelectorAll('.voto_input, .voto_especial_input')
        .forEach(inp => { inp.value = ""; });
      return;
    }

    const inputsByCargo = new Map();
    root.querySelectorAll('.voto_input[data-cargo], .voto_especial_input[data-cargo]').forEach(inp => {
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
          dominantIndex = idx;
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
    if (IS_PAINTING) return;

    const CAP = getEffectiveCap();
    const root = getActiveRoot();
    const cargos = new Map();

    root.querySelectorAll('.voto_input[data-cargo], .voto_especial_input[data-cargo]').forEach(inp => {
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
    });
  }

  /** Chequea que la suma de (partidos + blancos + impugnados) no pase E
   *  y muestra una notificación sutil SOLO la primera vez que una columna llega EXACTA a E.
   */
  function enforceGlobalSumByCargo(silent = false) {
    if (IS_PAINTING) return;

    const CAP = getEffectiveCap();
    if (CAP <= 0) return;

    const root = getActiveRoot();
    const cargos = new Map();

    root.querySelectorAll('.voto_input[data-cargo], .voto_especial_input[data-cargo]').forEach(inp => {
      const cId = String(inp.dataset.cargo || "");
      if (!cargos.has(cId)) cargos.set(cId, []);
      cargos.get(cId).push(inp);
    });

    cargos.forEach((inputs, cId) => {
      let sum = 0;
      inputs.forEach(inp => { sum += getVoteValue(inp); });

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

      // recalcular tras ajustes
      let total = 0;
      inputs.forEach(inp => { total += getVoteValue(inp); });

      // notificación respetando "silent"
      if (total === CAP) {
        if (!silent && !notifiedAtCap.has(cId)) {
          showNotification("⚠️ Se alcanzó la cantidad de electores que han votado");
          notifiedAtCap.add(cId);
        }
      } else {
        if (notifiedAtCap.has(cId)) notifiedAtCap.delete(cId);
      }
    });
  }

  calcularTotales();
});


function calcularTotales() {
  const root = getActiveRoot();

  const cargoIdSet = new Set();
  root.querySelectorAll('.voto_input[data-cargo]').forEach(el => {
    if (el.dataset.cargo) cargoIdSet.add(String(el.dataset.cargo));
  });

  const totalesAgrupaciones = {};
  cargoIdSet.forEach(cId => totalesAgrupaciones[cId] = 0);

  // Sólo inputs visibles del scope activo
  root.querySelectorAll('.voto_input[data-cargo]').forEach(input => {
    const cId = String(input.dataset.cargo || "");
    if (!cargoIdSet.has(cId)) return;
    const v = getVoteValue(input);
    totalesAgrupaciones[cId] += v;
  });

  cargoIdSet.forEach(cId => {
    const txt = format3(totalesAgrupaciones[cId] || 0);
    root.querySelectorAll(`[data-total-cargo="${cId}"]`).forEach(el => { if (el) el.value = txt; });
    const byId = root.querySelector(`#total_${cId}`);
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
  if (IS_SAVING) return;
  IS_SAVING = true;

  const mesaIdEl = document.getElementById("mesa_id");
  if (!mesaIdEl || !mesaIdEl.value) {
    alert("Seleccioná una mesa");
    IS_SAVING = false;
    return;
  }

  const votosCargo = [];
  const votosEspeciales = [];

  document.querySelectorAll(".voto_input").forEach(input => {
    const cantidad = getVoteValue(input);
    if (cantidad === 0) return;
    votosCargo.push({
      partido_postulacion_id: Number(input.dataset.partido),
      cargo_id: Number(input.dataset.cargo),
      votos: cantidad,
    });
  });

  document.querySelectorAll(".voto_especial_input").forEach(input => {
    const cantidad = getVoteValue(input);
    if (cantidad === 0) return;
    votosEspeciales.push({
      tipo: input.dataset.tipo,
      cargo_postulacion_id: Number(input.dataset.cargo),
      votos: cantidad,
    });
  });

  const resumenMesa = {
    electores_votaron: toNumber350(document.getElementById("electores_votaron")?.value),
    sobres_encontrados: toNumber350(document.getElementById("sobres_encontrados")?.value),
    diferencia: toNumber350(document.getElementById("diferencia_sobres")?.value),
  };

  const payload = {
    mesa_id: Number(mesaIdEl.value),
    votos_cargo: votosCargo,
    votos_especiales: votosEspeciales,
    resumen_mesa: resumenMesa,
  };

  // UI: overlay y botones
  document.getElementById("saving_overlay")?.removeAttribute("hidden");
  document.querySelectorAll(".btn-enviar-votos").forEach(b => b.disabled = true);

  // === Rama OFFLINE / error de red: guardar en cola ===
  const queueAndFinish = async () => {
    await OfflineQueue.add({ payload, csrf: getCookie('csrftoken') });
    showNotification("📶 Sin conexión: mesa guardada localmente. Se enviará automáticamente.", 4000);
    // mantenemos el formulario como está para que el operador decida
    document.getElementById("saving_overlay")?.setAttribute("hidden", "");
    const mid = document.getElementById("mesa_id")?.value || "";
    document.querySelectorAll(".btn-enviar-votos").forEach(b => b.disabled = !mid);
    IS_SAVING = false;
    drainNow(); // por si volvió la red
  };

  // Si ya estamos offline, directo a cola
  if (!navigator.onLine) {
    queueAndFinish();
    return;
  }

  // Intento online normal
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
      const mesaId = document.getElementById("mesa_id")?.value;
      if (mesaId) updateMesaOptionAppearance(mesaId, true);
      limpiarFormulario();
      const sel = document.getElementById("mesa_select");
      if (sel) sel.value = "";
      const hiddenMesaId = document.getElementById("mesa_id");
      if (hiddenMesaId) hiddenMesaId.value = "";
      document.querySelectorAll(".btn-enviar-votos").forEach(b => b.disabled = true);
      scrollTopSmooth();
      const msg = document.getElementById("mensaje_validacion");
      if (msg) {
        msg.style.display = "block";
        msg.style.color = "green";
        msg.textContent = "Mesa guardada. Volvé a seleccionarla para editar/sobrescribir.";
      }
      return;
    }

    if (res.status === 409) {
      // mismo flujo de confirmación online de siempre
      const confirmar = confirm((data.message || "La mesa ya está escrutada. ¿Querés sobrescribir los datos con esta nueva carga?"));
      if (confirmar) {
        payload.overwrite = true;
        return fetch("/operador/guardar-votos/", {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            "X-Requested-With": "XMLHttpRequest"
          },
          body: JSON.stringify(payload),
        })
        .then(r => r.json().then(d => ({ ok: r.ok, status: r.status, data: d })))
        .then(async ({ ok, status, data }) => {
          if (ok && data.status === "ok") {
            alert("✅ Mesa sobrescrita correctamente");
            const mesaId = document.getElementById("mesa_id")?.value;
            if (mesaId) updateMesaOptionAppearance(mesaId, true);
            limpiarFormulario();
            const sel2 = document.getElementById("mesa_select"); if (sel2) sel2.value = "";
            const hiddenMesaId2 = document.getElementById("mesa_id"); if (hiddenMesaId2) hiddenMesaId2.value = "";
            document.querySelectorAll(".btn-enviar-votos").forEach(b => b.disabled = true);
            scrollTopSmooth();
            const msg2 = document.getElementById("mensaje_validacion");
            if (msg2) { msg2.style.display = "block"; msg2.style.color = "green"; msg2.textContent = "Cambios guardados. Volvé a seleccionar la mesa para seguir editando."; }
            return;
          }
          alert("❌ No se pudo sobrescribir: " + (data?.message || `HTTP ${status}`));
        });
      }
      return;
    }

    // cualquier otro código → mandamos a cola
    await queueAndFinish();
  })
  .catch(async (err) => {
    console.error("Error al enviar votos:", err);
    await queueAndFinish();
  })
  .finally(() => {
    document.getElementById("saving_overlay")?.setAttribute("hidden", "");
    const mesaId = document.getElementById("mesa_id")?.value || "";
    document.querySelectorAll(".btn-enviar-votos").forEach(b => b.disabled = !mesaId);
    IS_SAVING = false;
  });
}
