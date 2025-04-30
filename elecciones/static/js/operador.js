document.addEventListener("DOMContentLoaded", function () {
  const inputMesa = document.getElementById("mesa_input");
  const inputCircuito = document.getElementById("circuito_input");
  const inputEscuela = document.getElementById("escuela_input");
  const mensajeError = document.getElementById("mensaje_error_mesa");  // Este es el mensaje que mostrarás al usuario si hay error o problema
  const buscarMesaBtn = document.getElementById("buscar_mesa_btn"); // El botón para buscar mesa

  // Función que maneja la búsqueda de datos de mesa
  function buscarMesa() {
    const numeroMesa = inputMesa.value;

    // Limpiar los campos si no hay número de mesa
    if (numeroMesa.length < 1) {
      inputEscuela.value = "";
      inputCircuito.value = "";
      mensajeError.textContent = "";  // Limpiar mensaje de error
      return;  // No hacer nada más si el campo de mesa está vacío
    }

    // Verificación básica del número de mesa (ejemplo: que tenga al menos 4 caracteres)
    if (numeroMesa.length < 3) {
      mensajeError.textContent = "⚠️ El número de mesa debe tener al menos 3 dígitos.";
      return;  // Salir si el número de mesa no es válido
    }

    // Mostrar mensaje de carga mientras buscamos
    mensajeError.textContent = "Buscando mesa...";

    const token = localStorage.getItem("jwt_token");
    if (!token) {
      inputEscuela.value = "Token no encontrado";
      inputCircuito.value = "";
      mensajeError.textContent = "⚠️ No estás autenticado. Por favor, inicia sesión.";
      return;
    }

    // Realizar la búsqueda de datos de la mesa
    fetch(`/api/obtener_datos_mesa/?numero_mesa=${numeroMesa}`, {
      headers: {
        "Authorization": `Bearer ${token}`,
      },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.error) {
          // Si hay un error, mostrar un mensaje claro
          inputEscuela.value = "Mesa no encontrada";
          inputCircuito.value = "";
          mensajeError.textContent = "⚠️ Mesa no encontrada. Verifica el número de mesa.";
        } else {
          // Si los datos son correctos, llenar los campos correspondientes
          inputEscuela.value = data.escuela;
          inputCircuito.value = data.circuito;
          mensajeError.textContent = "";  // Limpiar el mensaje de error
        }
      })
      .catch((err) => {
        console.error("Error al obtener los datos de la mesa:", err);
        inputEscuela.value = "Error al obtener datos";
        inputCircuito.value = "";
        mensajeError.textContent = "⚠️ Hubo un error al obtener los datos de la mesa. Intenta nuevamente.";
      });
  }

  // Asociar la función de búsqueda al evento del botón "Buscar"
  buscarMesaBtn.addEventListener("click", buscarMesa);

  // También puedes seguir manejando la entrada de texto en el campo de mesa si lo deseas
  inputMesa.addEventListener("input", function () {
    // Limpiar mensaje de error y campos cuando el usuario está escribiendo
    inputEscuela.value = "";
    inputCircuito.value = "";
    mensajeError.textContent = "";
  });

  // Evento para recalcular totales en cada cambio de input
  document.querySelectorAll("input").forEach((input) => {
    input.addEventListener("input", calcularTotales);
  });

  // Ejecutar el cálculo de totales al cargar la página por primera vez
  calcularTotales();
});

// Función para calcular los totales de votos
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

  // Calcular diferencia entre votantes y sobres
  const sobres = parseInt(document.getElementById('sobres_utilizados')?.value) || 0;
  const diferencia = totalVotantes - sobres;
  document.getElementById('diferencia_sobres').value = diferencia;

  // Remarcar la diferencia en rojo si no es igual a 0
  const diferenciaCampo = document.getElementById('diferencia_sobres');
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
