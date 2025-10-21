// operador.js — sin sumas automáticas, sin validaciones cruzadas.
// Todos los inputs numéricos: solo dígitos, tope 350, muestran 3 cifras.
// Además, se neutralizan toasts/validaciones viejas y cualquier listener previo.

(() => {
  "use strict";

  // ===== Config =====
  const MAX = 350;
  const API_SAVE_URL = "/api/guardar-votos/";          // ajustá si tu ruta es otra
  const API_MESA_URL = (id) => `/api/mesa/${id}/`;     // ajustá si tu ruta es otra

  // ===== Utils =====
  const $  = (s, ctx = document) => ctx.querySelector(s);
  const $$ = (s, ctx = document) => Array.from(ctx.querySelectorAll(s));

  const onlyDigits = (v) => (v || "").replace(/\D+/g, "");
  const clamp = (n) => Math.min(MAX, Math.max(0, isNaN(n) ? 0 : n));
  const pad3  = (v) => String(clamp(parseInt(v || 0, 10))).padStart(3, "0");
  const toInt = (v) => {
    const d = onlyDigits(String(v ?? ""));
    return d ? parseInt(d, 10) : 0;
  };

  // ===== CSRF / fetch =====
  const getCookie = (name) => {
    const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
    return m ? decodeURIComponent(m[1]) : null;
  };

  async function postJSON(url, data) {
    const csrftoken = getCookie("csrftoken");
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrftoken ? { "X-CSRFToken": csrftoken } : {}),
      },
      body: JSON.stringify(data),
      cache: "no-cache",
    });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${txt}`);
    }
    return res.json().catch(() => ({}));
  }

  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status} en ${url}`);
    return r.json();
  }

  // ===== Anti-interferencias (mata scripts viejos) =====
  function noop() {}
  function neutralizeToastsAndGlobals() {
    // Si hay toastr, anulamos métodos que podrían mostrar el cartelito
    if (window.toastr) {
      ["warning", "error", "info", "success"].forEach((m) => (window.toastr[m] = noop));
      window.toastr.options = {};
    }
    // Si dejaron helpers globales para validar/sumar, los anulamos
    ["validarTotales", "sumarTotales", "checkCap", "controlElectores", "mostrarToast"]
      .forEach((k) => (window[k] = noop));
  }

  // Detiene otros listeners (validadores viejos) en fase de captura
  function suppressForeignHandlers(el, events) {
    events.forEach((ev) => {
      el.addEventListener(
        ev,
        (e) => {
          // evitamos que otros handlers salten
          e.stopImmediatePropagation();
          // no preventDefault para no romper input normal
        },
        true // capture
      );
    });
  }

  // ===== Cableado: numérico + tope + 3 cifras (y bloquea listeners viejos) =====
  function wireNumericInputs(inputs) {
    inputs.forEach((inp) => {
      // Evitar que otros scripts enganchen estos eventos
      suppressForeignHandlers(inp, ["input", "change", "keyup", "keydown", "keypress", "paste"]);

      // Atributos útiles
      inp.setAttribute("inputmode", "numeric");
      inp.setAttribute("maxlength", "3");
      inp.setAttribute("pattern", "[0-9]*");

      // Al escribir: solo dígitos, máx 3, tope 350 (permitimos vacío mientras escribe)
      inp.addEventListener("input", () => {
        const d = onlyDigits(inp.value).slice(0, 3);
        if (d === "") { inp.value = ""; return; }
        inp.value = String(clamp(parseInt(d, 10)));
      });

      // Enfocar: quitar ceros a la izquierda para editar cómodo
      inp.addEventListener("focus", () => {
        const d = onlyDigits(inp.value);
        inp.value = d.replace(/^0+/, "") || "";
        try { inp.select(); } catch (_) {}
      });

      // Blur: siempre 3 cifras
      inp.addEventListener("blur", () => {
        inp.value = pad3(inp.value);
      });
    });
  }

  // Forzar display con 3 cifras (útil tras precargas)
  function padInputs3(selector = ".voto_input, .voto_especial_input, .total-manual") {
    $$(selector).forEach((inp) => (inp.value = pad3(inp.value)));
  }
  window.padInputs3 = padInputs3; // por si algún template quiere usarla

  // ===== Campos “totales” que NO deben calcularse solos =====
  function unlockManualTotals() {
    // intentamos varios selectores comunes
    const candidates = [
      "#total_agrupaciones",
      "#totalAgrupaciones",
      "input[name='total_agrupaciones']",
      ".total-agrupaciones input",
      "#total_agrup",
      "#total_validos",
      "#total_listas",
      "#total_agrup_politicas",
      // “Total de votos (*)”
      "#total_general",
      "#totalVotos",
      "input[name='total_votos']",
      ".total-votos input",
    ];

    const found = new Set();
    candidates.forEach((sel) => $$(sel).forEach((el) => found.add(el)));

    // A todo lo que encontramos lo tratamos como input manual “normal”
    found.forEach((el) => {
      el.classList.add("total-manual");
      el.removeAttribute("readonly");
      el.removeAttribute("disabled");
    });

    if (found.size) wireNumericInputs(Array.from(found));
  }

  // ===== Recolección de datos =====
  function collectPayload() {
    const mesaId =
      $("#mesaId")?.value ||
      document.body.getAttribute("data-mesa-id") ||
      $("#mesa")?.value ||
      $("#selectMesa")?.value ||
      null;

    const votos_cargo = $$(".voto_input").map((inp) => ({
      partido_postulacion_id: Number(inp.dataset.partido),
      votos: clamp(toInt(inp.value)),
    }));

    const votos_especiales = $$(".voto_especial_input").map((inp) => ({
      tipo: String(inp.dataset.tipo || "").toLowerCase().trim(),
      cargo_postulacion_id: Number(inp.dataset.cargo),
      votos: clamp(toInt(inp.value)),
    }));

    const resumen_mesa = {
      electores_votaron: toInt($("#electores_votaron")?.value),
      sobres_encontrados: toInt($("#sobres_encontrados")?.value),
      diferencia: toInt($("#diferencia")?.value),
    };

    return {
      mesa_id: mesaId ? Number(mesaId) : null,
      votos_cargo,
      votos_especiales,
      resumen_mesa,
    };
  }

  // ===== Guardar =====
  async function guardarMesa() {
    const btn = $("#btnGuardar") || $("#btnEnviar");
    const msg = $("#statusMsg");
    const old = btn?.textContent;

    try {
      if (btn) { btn.disabled = true; btn.textContent = "Guardando…"; }

      const payload = collectPayload();
      if (!payload.mesa_id) throw new Error("Falta mesa_id");

      await postJSON(API_SAVE_URL, payload);

      padInputs3();

      if (msg) {
        msg.textContent = "Guardado correctamente.";
        msg.classList.remove("is-error");
        msg.classList.add("is-ok");
      }
    } catch (e) {
      console.error(e);
      if (msg) {
        msg.textContent = "Error al guardar la mesa.";
        msg.classList.add("is-error");
        msg.classList.remove("is-ok");
      }
      alert("No se pudo guardar. Revisá tu conexión e intentá de nuevo.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = old || "Guardar"; }
    }
  }
  window.operadorGuardar = guardarMesa;

  // ===== Precarga (opcional) =====
  async function cargarMesa(mesaId) {
    if (!mesaId) return;
    try {
      const data = await getJSON(API_MESA_URL(Number(mesaId)));

      if (Array.isArray(data.votos_cargo)) {
        data.votos_cargo.forEach((v) => {
          const inp = document.querySelector(`.voto_input[data-partido="${v.partido_postulacion_id}"]`);
          if (inp) inp.value = clamp(Number(v.votos || 0));
        });
      }

      if (Array.isArray(data.votos_especiales)) {
        data.votos_especiales.forEach((v) => {
          const tipo = String(v.tipo || "").toLowerCase().trim();
          const sel =
            `.voto_especial_input[data-tipo="${tipo}"]` +
            (v.cargo_postulacion_id ? `[data-cargo="${v.cargo_postulacion_id}"]` : "");
          const inp = document.querySelector(sel);
          if (inp) inp.value = clamp(Number(v.votos || 0));
        });
      }

      if (data.resumen) {
        if ($("#electores_votaron"))   $("#electores_votaron").value   = toInt(data.resumen.electores_votaron);
        if ($("#sobres_encontrados"))  $("#sobres_encontrados").value  = toInt(data.resumen.sobres_encontrados);
        if ($("#diferencia"))          $("#diferencia").value          = toInt(data.resumen.diferencia);
      }

      padInputs3();
    } catch (e) {
      console.warn("No se pudo precargar la mesa", e);
    }
  }
  window.cargarMesaOperador = cargarMesa;

  // ===== Init =====
  document.addEventListener("DOMContentLoaded", () => {
    neutralizeToastsAndGlobals();

    // Evita validaciones viejas atadas al form
    const form = document.querySelector("form#formCarga") || document.querySelector("form[data-role='telegrama']");
    if (form) {
      suppressForeignHandlers(form, ["submit"]);
      form.addEventListener("submit", (e) => { e.preventDefault(); guardarMesa(); }, true);
    }

    // Cablear inputs de votos (listas + especiales)
    const baseInputs = $$(".voto_input, .voto_especial_input");
    wireNumericInputs(baseInputs);

    // Desbloquear/neutralizar campos de totales para que NO se calculen solos
    unlockManualTotals();

    // Botón Guardar/Enviar
    $("#btnGuardar")?.addEventListener("click", (ev) => { ev.preventDefault(); guardarMesa(); });
    $("#btnEnviar") ?.addEventListener("click", (ev) => { ev.preventDefault(); guardarMesa(); });

    // Cambio de mesa (si hay selector)
    $("#selectMesa")?.addEventListener("change", (ev) => {
      const mesaId = ev.target.value;
      $("#mesaId") && ($("#mesaId").value = mesaId);
      cargarMesa(mesaId);
    });

    // Precargar si hay mesaId en el DOM
    const startMesaId =
      $("#mesaId")?.value ||
      document.body.getAttribute("data-mesa-id") ||
      $("#selectMesa")?.value ||
      null;
    if (startMesaId) cargarMesa(startMesaId);

    // Asegurar 3 dígitos visibles
    padInputs3();
  });
})();
