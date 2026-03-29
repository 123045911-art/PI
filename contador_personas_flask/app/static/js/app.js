const areaForm = document.getElementById("area-form");
const formMessage = document.getElementById("form-message");
const statsContainer = document.getElementById("stats-container");
const videoImg = document.getElementById("video-stream");
const videoWrapper = document.getElementById("video-wrapper");
const drawCanvas = document.getElementById("draw-overlay");
const drawHint = document.getElementById("draw-hint");
const btnDraw = document.getElementById("btn-draw");
const btnCancelDraw = document.getElementById("btn-cancel-draw");
const btnSave = document.getElementById("btn-save");

const inputs = {
  x1: document.getElementById("x1"),
  y1: document.getElementById("y1"),
  x2: document.getElementById("x2"),
  y2: document.getElementById("y2"),
};

let drawingMode = false;
let dragActive = false;
let startDisp = { x: 0, y: 0 };
let ctx = null;

function setFormMessage(message, type = "success") {
  formMessage.textContent = message;
  formMessage.classList.remove("success", "error");
  formMessage.classList.add(type);
}

function syncOverlaySize() {
  if (!videoImg || !drawCanvas || !videoWrapper) return;
  const w = videoImg.clientWidth;
  const h = videoImg.clientHeight;
  if (w < 2 || h < 2) return;
  drawCanvas.width = w;
  drawCanvas.height = h;
  drawCanvas.style.width = `${w}px`;
  drawCanvas.style.height = `${h}px`;
  ctx = drawCanvas.getContext("2d");
}

/** Coordenadas del ratón relativas al borde superior izquierdo de la imagen (espacio mostrado). */
function displayCoordsFromEvent(ev) {
  const rect = videoImg.getBoundingClientRect();
  let x = ev.clientX - rect.left;
  let y = ev.clientY - rect.top;
  const maxX = Math.max(0, rect.width - 1e-6);
  const maxY = Math.max(0, rect.height - 1e-6);
  x = Math.max(0, Math.min(x, maxX));
  y = Math.max(0, Math.min(y, maxY));
  return { x, y };
}

/** Convierte coordenadas en pantalla a píxeles del frame (naturalWidth / naturalHeight). */
function toNatural(dispX, dispY) {
  const nw = videoImg.naturalWidth || videoImg.width;
  const nh = videoImg.naturalHeight || videoImg.height;
  const rw = videoImg.clientWidth;
  const rh = videoImg.clientHeight;
  if (!rw || !rh || !nw || !nh) return { x: 0, y: 0 };
  return {
    x: Math.round((dispX * nw) / rw),
    y: Math.round((dispY * nh) / rh),
  };
}

function clearOverlay() {
  if (!ctx) return;
  ctx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
}

function drawPreview(x0, y0, x1, y1) {
  if (!ctx) return;
  clearOverlay();
  ctx.strokeStyle = "rgba(56, 189, 248, 0.95)";
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  const left = Math.min(x0, x1);
  const top = Math.min(y0, y1);
  const w = Math.abs(x1 - x0);
  const h = Math.abs(y1 - y0);
  ctx.strokeRect(left, top, w, h);
  ctx.setLineDash([]);
}

function enterDrawingMode() {
  const name = (document.getElementById("name").value || "").trim();
  if (!name) {
    setFormMessage("Escribe primero el nombre del area.", "error");
    return;
  }
  if (!videoImg.naturalWidth || !videoImg.naturalHeight) {
    setFormMessage(
      "Espera un momento a que el video muestre un frame y vuelve a intentar.",
      "error",
    );
    return;
  }
  drawingMode = true;
  dragActive = false;
  drawCanvas.classList.add("active");
  btnDraw.disabled = true;
  btnCancelDraw.classList.remove("hidden");
  drawHint.textContent =
    "Mantén pulsado el ratón y arrastra para marcar el rectángulo. Suelta para confirmar.";
  setFormMessage("", "success");
  syncOverlaySize();
  clearOverlay();
}

function exitDrawingMode() {
  drawingMode = false;
  dragActive = false;
  drawCanvas.classList.remove("active");
  btnDraw.disabled = false;
  btnCancelDraw.classList.add("hidden");
  drawHint.textContent = "";
  clearOverlay();
}

function cancelDrawing() {
  exitDrawingMode();
  inputs.x1.value = "";
  inputs.y1.value = "";
  inputs.x2.value = "";
  inputs.y2.value = "";
  btnSave.disabled = true;
}

function onOverlayMouseDown(ev) {
  if (!drawingMode) return;
  ev.preventDefault();
  dragActive = true;
  startDisp = displayCoordsFromEvent(ev);
  drawPreview(startDisp.x, startDisp.y, startDisp.x, startDisp.y);
}

function onOverlayMouseMove(ev) {
  if (!drawingMode || !dragActive) return;
  const p = displayCoordsFromEvent(ev);
  drawPreview(startDisp.x, startDisp.y, p.x, p.y);
}

function onOverlayMouseUp(ev) {
  if (!drawingMode || !dragActive) return;
  ev.preventDefault();
  dragActive = false;
  const endDisp = displayCoordsFromEvent(ev);

  const w = Math.abs(endDisp.x - startDisp.x);
  const h = Math.abs(endDisp.y - startDisp.y);
  if (w < 4 || h < 4) {
    setFormMessage("Rectangulo demasiado pequeño. Intenta de nuevo.", "error");
    clearOverlay();
    return;
  }

  const n0 = toNatural(startDisp.x, startDisp.y);
  const n1 = toNatural(endDisp.x, endDisp.y);
  const x1 = Math.min(n0.x, n1.x);
  const y1 = Math.min(n0.y, n1.y);
  const x2 = Math.max(n0.x, n1.x);
  const y2 = Math.max(n0.y, n1.y);

  inputs.x1.value = String(x1);
  inputs.y1.value = String(y1);
  inputs.x2.value = String(x2);
  inputs.y2.value = String(y2);

  exitDrawingMode();
  btnSave.disabled = false;
  setFormMessage(
    "Rectangulo listo. Pulsa «Guardar area» para enviarlo al servidor.",
    "success",
  );
  drawPreview(
    Math.min(startDisp.x, endDisp.x),
    Math.min(startDisp.y, endDisp.y),
    Math.max(startDisp.x, endDisp.x),
    Math.max(startDisp.y, endDisp.y),
  );
  drawCanvas.classList.add("preview-locked");
}

btnDraw.addEventListener("click", () => {
  drawCanvas.classList.remove("preview-locked");
  enterDrawingMode();
});

btnCancelDraw.addEventListener("click", () => {
  drawCanvas.classList.remove("preview-locked");
  cancelDrawing();
});

window.addEventListener("resize", () => {
  syncOverlaySize();
});

videoImg.addEventListener("load", () => {
  syncOverlaySize();
});

if (typeof ResizeObserver !== "undefined" && videoWrapper) {
  const ro = new ResizeObserver(() => syncOverlaySize());
  ro.observe(videoImg);
}

drawCanvas.addEventListener("mousedown", onOverlayMouseDown);
window.addEventListener("mousemove", onOverlayMouseMove);
window.addEventListener("mouseup", onOverlayMouseUp);

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && drawingMode) {
    drawCanvas.classList.remove("preview-locked");
    cancelDrawing();
  }
});

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

  if (
    [payload.x1, payload.y1, payload.x2, payload.y2].some(
      (n) => Number.isNaN(n) || n === undefined,
    )
  ) {
    setFormMessage("Dibuja el area en el video antes de guardar.", "error");
    return;
  }

  try {
    const result = await addArea(payload);
    if (!result.ok) {
      setFormMessage(result.error || "No se pudo guardar el area.", "error");
      return;
    }

    setFormMessage(`Area "${result.area.name}" creada correctamente.`, "success");
    areaForm.reset();
    inputs.x1.value = "";
    inputs.y1.value = "";
    inputs.x2.value = "";
    inputs.y2.value = "";
    btnSave.disabled = true;
    drawCanvas.classList.remove("preview-locked");
    clearOverlay();
    fetchStats();
  } catch (err) {
    setFormMessage("Error de red al guardar el area.", "error");
    console.error(err);
  }
});

fetchStats();
setInterval(fetchStats, 2000);

requestAnimationFrame(() => syncOverlaySize());
