const areaForm = document.getElementById("area-form");
const formMessage = document.getElementById("form-message");
const statsContainer = document.getElementById("stats-container");

function setFormMessage(message, type = "success") {
  formMessage.textContent = message;
  formMessage.classList.remove("success", "error");
  formMessage.classList.add(type);
}

async function addArea(payload) {
  const response = await fetch("/add_area", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return response.json();
}

function renderStats(areas) {
  if (!areas.length) {
    statsContainer.innerHTML = `<p class="empty">No hay areas creadas todavia.</p>`;
    return;
  }

  statsContainer.innerHTML = areas
    .map(
      (area) => `
      <article class="stat-card">
        <p class="stat-title">${area.name}</p>
        <p class="stat-line">Actuales: ${area.current_count}</p>
        <p class="stat-line">Entradas: ${area.total_entries}</p>
        <p class="stat-line">Salidas: ${area.total_exits}</p>
        <p class="stat-line">Permanencia total: ${area.total_dwell_seconds.toFixed(2)} s</p>
        <p class="stat-line">Permanencia promedio: ${area.avg_dwell_seconds.toFixed(2)} s</p>
        <p class="stat-line">Rect: [${area.rect.join(", ")}]</p>
      </article>
    `
    )
    .join("");
}

async function fetchStats() {
  try {
    const response = await fetch("/stats");
    const data = await response.json();
    renderStats(data.areas || []);
  } catch (err) {
    console.error("Error al obtener stats:", err);
  }
}

areaForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(areaForm);
  const payload = {
    name: formData.get("name"),
    x1: Number(formData.get("x1")),
    y1: Number(formData.get("y1")),
    x2: Number(formData.get("x2")),
    y2: Number(formData.get("y2")),
  };

  try {
    const result = await addArea(payload);
    if (!result.ok) {
      setFormMessage(result.error || "No se pudo guardar el area.", "error");
      return;
    }

    setFormMessage(`Area "${result.area.name}" creada correctamente.`, "success");
    areaForm.reset();
    fetchStats();
  } catch (err) {
    setFormMessage("Error de red al guardar el area.", "error");
    console.error(err);
  }
});

fetchStats();
setInterval(fetchStats, 2000);
