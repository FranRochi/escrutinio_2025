document.addEventListener("DOMContentLoaded", () => {
    if (typeof votosData === "undefined") return;
  
    const ctx = document.getElementById("graficoVotos").getContext("2d");
  
    const cargos = Object.keys(votosData);
    const partidosSet = new Set();
  
    cargos.forEach(cargo => {
      Object.keys(votosData[cargo]).forEach(p => partidosSet.add(p));
    });
  
    const partidos = Array.from(partidosSet);
    const colores = [
      "#3e95cd", "#8e5ea2", "#3cba9f", "#e8c3b9",
      "#c45850", "#f1c40f", "#2ecc71", "#3498db"
    ];
  
    const datasets = partidos.map((partido, i) => ({
      label: partido,
      data: cargos.map(cargo => votosData[cargo][partido] || 0),
      backgroundColor: colores[i % colores.length]
    }));
  
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: cargos,
        datasets: datasets
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: 'Distribución de votos por cargo y partido'
          },
          tooltip: {
            mode: 'index',
            intersect: false
          }
        },
        interaction: {
          mode: 'nearest',
          axis: 'x',
          intersect: false
        },
        scales: {
          x: {
            stacked: true
          },
          y: {
            stacked: true,
            beginAtZero: true
          }
        }
      }
    });
  });
  
  const contenedorGraficos = document.getElementById('graficos-por-cargo');

  Object.entries(votosData).forEach(([cargo, partidos], index) => {
    // Crear canvas
    const canvas = document.createElement('canvas');
    canvas.id = `grafico-cargo-${index}`;
    canvas.width = 600;
    canvas.height = 300;
    contenedorGraficos.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    const labels = Object.keys(partidos);
    const data = Object.values(partidos);

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: `${cargo}`,
          data: data,
          backgroundColor: 'rgba(54, 162, 235, 0.7)',
          borderColor: 'rgba(54, 162, 235, 1)',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: cargo,
            font: {
              size: 18
            }
          },
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              precision: 0
            }
          }
        }
      }
    });
  });