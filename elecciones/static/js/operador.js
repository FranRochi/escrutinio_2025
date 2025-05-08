function loginUsuario(username, password) {
  fetch('/api/login/', {
    method: 'POST',
    body: JSON.stringify({ username: username, password: password }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(res => res.json())
    .then(data => {
      if (data.access_token) {
        sessionStorage.setItem("jwt_token", data.access_token);
        window.location.href = "/panel_operador";  // Redirigir correctamente
      } else {
        alert("Error en la autenticación");
      }
    })
    .catch(err => {
      console.error("Error al hacer login:", err);
    });
}

function getCookie(name) {
  let cookieArr = document.cookie.split(";");
  for (let i = 0; i < cookieArr.length; i++) {
    let cookie = cookieArr[i].trim();
    if (cookie.startsWith(name + "=")) {
      return cookie.substring(name.length + 1);
    }
  }
  return null;
}

document.addEventListener("DOMContentLoaded", function () {
  const inputMesa = document.getElementById("mesa_input");
  const inputCircuito = document.getElementById("circuito_input");
  const inputEscuela = document.getElementById("escuela_input");
  const mensajeError = document.getElementById("mensaje_error_mesa");
  const buscarMesaBtn = document.getElementById("buscar_mesa_btn");

  function buscarMesa() {
    const numeroMesa = inputMesa.value;

    if (numeroMesa.length < 1) {
      inputEscuela.value = "";
      inputCircuito.value = "";
      mensajeError.textContent = "";
      return;
    }

    if (isNaN(numeroMesa)) {
      mensajeError.textContent = "⚠️ El número de mesa debe ser numérico.";
      return;
    }

    mensajeError.textContent = "Buscando mesa...";

    fetch(`/api/obtener_datos_mesa/?numero_mesa=${numeroMesa}`)
      .then(res => res.json())
      .then(data => {
        console.log("Datos de la mesa recibidos:", data);
        if (data.error || !data.escuela || !data.circuito) {
          inputEscuela.value = "Mesa no encontrada";
          inputCircuito.value = "";
          mensajeError.textContent = "⚠️ Mesa no encontrada. Verifica el número de mesa.";
          document.getElementById("mesa_id").value = "";  // limpia si no se encuentra
        } else {
          inputEscuela.value = data.escuela;
          inputCircuito.value = data.circuito;
          document.getElementById("mesa_id").value = numeroMesa;
          mensajeError.textContent = "";
        }
      })
      .catch((err) => {
        console.error("Error al obtener los datos de la mesa:", err);
        inputEscuela.value = "Error al obtener datos";
        inputCircuito.value = "";
        mensajeError.textContent = "⚠️ Hubo un error al obtener los datos de la mesa. Intenta nuevamente.";
      });
  }

  buscarMesaBtn.addEventListener("click", buscarMesa);

  document.querySelectorAll("input").forEach((input) => {
    input.addEventListener("input", calcularTotales);
  });

  const enviarVotosBtn = document.getElementById("enviar_votos_btn");
  if (enviarVotosBtn) {
    enviarVotosBtn.addEventListener("click", enviarVotos);
  }

  calcularTotales();
});

function calcularTotales() {
  const columnas = [...document.querySelectorAll('th[data-cargo]')];
  const totalesAgrupaciones = {};
  const totalesCompletos = {};
  const totalVotantes = parseInt(document.getElementById('total_votantes')?.value) || 0;

  columnas.forEach(th => {
    const cargoId = th.dataset.cargo;
    totalesAgrupaciones[cargoId] = 0;
    totalesCompletos[cargoId] = 0;
  });

  document.querySelectorAll('.voto_input').forEach(input => {
    const cargoId = input.dataset.cargo;
    const valor = parseInt(input.value) || 0;
    totalesAgrupaciones[cargoId] += valor;
    totalesCompletos[cargoId] += valor;
  });

  document.querySelectorAll('.voto_input_adicional').forEach(input => {
    const inputCargoId = input.name.split('_').pop();
    const valor = parseInt(input.value) || 0;
    totalesCompletos[inputCargoId] += valor;
  });

  let mensaje = "";

  for (const [cargoId, totalAgrupaciones] of Object.entries(totalesAgrupaciones)) {
    const totalFinal = totalesCompletos[cargoId];

    const inputAgrupaciones = document.getElementById('total_' + cargoId);
    const inputTotal = document.getElementById('total_agrupaciones_' + cargoId);
    
    inputAgrupaciones.value = totalAgrupaciones;
    inputTotal.value = totalFinal;

    if (totalVotantes > 0 && totalFinal > totalVotantes) {
      inputTotal.classList.add('input-error');
      mensaje += `⚠️ El total de votos para el cargo ID ${cargoId} (${totalFinal}) supera el total de votantes (${totalVotantes}).\n`;
    } else {
      inputTotal.classList.remove('input-error');
    }
  }

  const diferenciaCampo = document.getElementById('diferencia_sobres');
  const diferencia = parseInt(diferenciaCampo?.value) || 0;

  // Validar manualmente si la diferencia es distinta de cero
  if (diferencia !== 0) {
    diferenciaCampo.classList.add('input-error');
    mensaje += `⚠️ La diferencia ingresada entre votantes y sobres no es cero. Diferencia: ${diferencia}.\n`;
  } else {
    diferenciaCampo.classList.remove('input-error');
  }

  // Remarcar la diferencia en rojo si no es igual a 0
  if (diferencia !== 0) {
    diferenciaCampo.classList.add('input-error');
    mensaje += `⚠️ La diferencia entre votantes y sobres no es cero. Diferencia: ${diferencia}.\n`;
  } else {
    diferenciaCampo.classList.remove('input-error');
  }

  const mensajeDiv = document.getElementById('mensaje_validacion');
  if (mensaje) {
    mensajeDiv.textContent = mensaje;
    mensajeDiv.style.color = "red";
    mensajeDiv.style.display = "block";
  } else {
    mensajeDiv.textContent = "";
    mensajeDiv.style.display = "none";
  }
}

function enviarVotos() {
  const mesaId = document.getElementById("mesa_id");

  if (!mesaId || !mesaId.value) {
    alert("Mesa no seleccionada");
    return;
  }

  // Validación del checkbox de confirmación
  const checkboxEscrutada = document.getElementById("escrutada");
  if (!checkboxEscrutada || !checkboxEscrutada.checked) {
    alert("Debés confirmar que la mesa está escrutada marcando la casilla.");
    return;
  }

  const votosCargo = [];
  const votosEspeciales = [];

  document.querySelectorAll(".voto_input").forEach(input => {
    const partidoId = input.dataset.partido;
    const cargoId = input.dataset.cargo;
    const cantidad = parseInt(input.value) || 0;

    votosCargo.push({
      partido_postulacion_id: partidoId,
      cargo_id: cargoId,
      votos: cantidad,
    });
  });

  document.querySelectorAll(".voto_especial_input").forEach(input => {
    const tipoVoto = input.dataset.tipo;
    const cantidad = parseInt(input.value) || 0;

    votosEspeciales.push({
      tipo: tipoVoto,
      votos: cantidad,
    });
  });
  console.log("Votos especiales enviados:", votosEspeciales);


  const resumenMesa = {
    electores_votaron: parseInt(document.getElementById("electores_votaron").value) || 0,
    sobres_encontrados: parseInt(document.getElementById("sobres_encontrados").value) || 0,
    diferencia: parseInt(document.getElementById("diferencia_sobres").value) || 0,
    escrutada: checkboxEscrutada.checked,
  };

  const payload = {
    mesa_id: mesaId.value,
    votos_cargo: votosCargo,
    votos_especiales: votosEspeciales,
    resumen_mesa: resumenMesa,
  };

  fetch("/operador/guardar-votos/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie('csrftoken'),
    },
    body: JSON.stringify(payload),
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === "ok") {
        alert("✅ Votos guardados correctamente");
      } else {
        alert("❌ Error al guardar votos: " + data.message);
      }
    })
    .catch(err => {
      console.error("Error al enviar votos:", err);
      alert("❌ Error de red o servidor");
    });
}
