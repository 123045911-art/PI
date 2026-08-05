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
let editingAreaId = null;

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
  videoImg.classList.remove("stream-reconnecting");
});

let streamRetryTimer = null;
videoImg.addEventListener("error", () => {
  videoImg.classList.add("stream-reconnecting");
  videoImg.alt = "Streaming de video limitado a uno por usuario";
  if (streamRetryTimer) clearTimeout(streamRetryTimer);
  streamRetryTimer = setTimeout(() => {
    videoImg.src = `/video_feed?retry=${Date.now()}`;
  }, 1500);
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

async function mutateArea(areaId, method, payload) {
  const response = await fetch(`/areas/${areaId}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  return response.json();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[char]);
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
        <p class="stat-title">${escapeHtml(area.name)}</p>
        <p class="stat-line">Actuales: ${area.current_count}</p>
        <p class="stat-line">Entradas: ${area.total_entries}</p>
        <p class="stat-line">Salidas: ${area.total_exits}</p>
        <p class="stat-line">Permanencia total: ${area.total_dwell_seconds.toFixed(2)} s</p>
        <p class="stat-line">Permanencia promedio: ${area.avg_dwell_seconds.toFixed(2)} s</p>
        <p class="stat-line">Rect: [${area.rect.join(", ")}]</p>
        <div class="form-actions">
          <button type="button" class="btn-secondary area-edit" data-area-id="${area.id}">Editar</button>
          <button type="button" class="btn-ghost area-delete" data-area-id="${area.id}">Eliminar</button>
        </div>
      </article>
    `
    )
    .join("");
}

statsContainer.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-area-id]");
  if (!button) return;
  const areaId = Number(button.dataset.areaId);
  const response = await fetch("/stats");
  const data = await response.json();
  const area = (data.areas || []).find((item) => item.id === areaId);
  if (!area) return;
  if (button.classList.contains("area-delete")) {
    if (!window.confirm(`¿Eliminar el área "${area.name}"?`)) return;
    const result = await mutateArea(areaId, "DELETE");
    if (!result.ok) window.alert(result.error || "No se pudo eliminar el área.");
    if (editingAreaId === areaId) {
      editingAreaId = null;
      areaForm.reset();
      btnSave.textContent = "Guardar area";
      btnSave.disabled = true;
    }
    await fetchStats();
    return;
  }
  const [x1, y1, x2, y2] = area.rect;
  editingAreaId = areaId;
  document.getElementById("name").value = area.name;
  inputs.x1.value = String(x1); inputs.y1.value = String(y1);
  inputs.x2.value = String(x2); inputs.y2.value = String(y2);
  btnSave.disabled = false;
  btnSave.textContent = "Guardar cambios";
  setFormMessage("Edita el nombre o vuelve a dibujar el rectángulo y guarda los cambios.", "success");
  areaForm.scrollIntoView({ behavior: "smooth", block: "start" });
});

async function fetchStats() {
  try {
    const response = await fetch("/stats");
    const data = await response.json();
    renderStats(data.areas || []);
    refreshAlertAreaOptions(data.areas || []);
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
    const result = editingAreaId
      ? await mutateArea(editingAreaId, "PATCH", payload)
      : await addArea(payload);
    if (!result.ok) {
      setFormMessage(result.error || "No se pudo guardar el area.", "error");
      return;
    }

    setFormMessage(`Area "${result.area.name}" ${editingAreaId ? "actualizada" : "creada"} correctamente.`, "success");
    editingAreaId = null;
    areaForm.reset();
    inputs.x1.value = "";
    inputs.y1.value = "";
    inputs.x2.value = "";
    inputs.y2.value = "";
    btnSave.disabled = true;
    btnSave.textContent = "Guardar area";
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

const alertForm = document.getElementById("alert-form");
const alertArea = document.getElementById("alert-area");
const alertType = document.getElementById("alert-type");
const alertThreshold = document.getElementById("alert-threshold");
const alertMessage = document.getElementById("alert-message");
const alertSave = document.getElementById("alert-save");
const alertCancel = document.getElementById("alert-cancel");
const alertsContainer = document.getElementById("alerts-container");
let editingAlertId = null;
let latestAlerts = [];

function refreshAlertAreaOptions(areas) {
  const selected = alertArea.value;
  alertArea.innerHTML = areas.map((area) =>
    `<option value="${escapeHtml(area.external_id || `area-local-${area.id}`)}">${escapeHtml(area.name)}</option>`
  ).join("");
  if ([...alertArea.options].some((option) => option.value === selected)) alertArea.value = selected;
}

function renderAlerts(alerts) {
  latestAlerts = alerts;
  if (!alerts.length) {
    alertsContainer.innerHTML = '<p class="empty">No hay alertas configuradas.</p>';
    return;
  }
  alertsContainer.innerHTML = alerts.map((alert) => `
    <article class="stat-card">
      <p class="stat-title">${escapeHtml(alert.type === "crowding" ? "Alta afluencia" : "Baja afluencia")} · ${escapeHtml(alert.areaName)}</p>
      <p class="stat-line">${escapeHtml(alert.reason)}</p>
      <p class="stat-line">Conteo actual: ${Number(alert.peopleCountSnapshot || 0)}</p>
      <p class="stat-line">Estado: <strong>${alert.status === "triggered" ? "ACTIVA" : "EN ESPERA"}</strong></p>
      <div class="form-actions">
        <button type="button" class="btn-secondary alert-edit" data-alert-id="${escapeHtml(alert.id)}">Editar</button>
        <button type="button" class="btn-ghost alert-delete" data-alert-id="${escapeHtml(alert.id)}">Eliminar</button>
      </div>
    </article>`).join("");
}

async function fetchAlerts() {
  try {
    const response = await fetch("/api/v1/sites/pasillo-real/alerts");
    const data = await response.json();
    renderAlerts(data.items || []);
  } catch (error) {
    alertMessage.textContent = "No se pudieron actualizar las alertas.";
  }
}

function resetAlertForm() {
  editingAlertId = null;
  alertForm.reset();
  alertThreshold.value = "1";
  alertSave.textContent = "Crear alerta";
  alertCancel.classList.add("hidden");
}

alertForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const areaName = alertArea.options[alertArea.selectedIndex]?.text || "Area";
  const thresholdPeople = Number(alertThreshold.value);
  const payload = {
    areaId: alertArea.value, areaName, type: alertType.value,
    thresholdPeople, scheduleMode: "all_days", createdBy: "flask",
    reason: alertType.value === "crowding"
      ? `Avisar cuando haya ${thresholdPeople} personas o mas.`
      : `Avisar cuando haya ${thresholdPeople} personas o menos.`,
  };
  const path = editingAlertId
    ? `/api/v1/sites/pasillo-real/alerts/${encodeURIComponent(editingAlertId)}`
    : "/api/v1/sites/pasillo-real/alerts";
  const response = await fetch(path, {
    method: editingAlertId ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  const data = await response.json();
  alertMessage.textContent = response.ok ? "Alerta guardada correctamente." : (data.error || "No se pudo guardar.");
  if (response.ok) { resetAlertForm(); await fetchAlerts(); }
});

alertsContainer.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-alert-id]");
  if (!button) return;
  const alert = latestAlerts.find((item) => item.id === button.dataset.alertId);
  if (!alert) return;
  if (button.classList.contains("alert-delete")) {
    if (!window.confirm(`¿Eliminar la alerta de "${alert.areaName}"?`)) return;
    await fetch(`/api/v1/sites/pasillo-real/alerts/${encodeURIComponent(alert.id)}`, { method: "DELETE" });
    await fetchAlerts();
    return;
  }
  editingAlertId = alert.id;
  alertArea.value = alert.areaId;
  alertType.value = alert.type;
  alertThreshold.value = String(alert.thresholdPeople);
  alertSave.textContent = "Guardar cambios";
  alertCancel.classList.remove("hidden");
  alertForm.scrollIntoView({ behavior: "smooth", block: "center" });
});

alertCancel.addEventListener("click", resetAlertForm);
fetchAlerts();
setInterval(fetchAlerts, 2000);

// --- Cámara del propio navegador: el visitante comparte su cámara y el
// backend la usa como fuente de video para el conteo de personas. ---
const ownCameraPreview = document.getElementById("own-camera-preview");
const ownCameraCanvas = document.getElementById("own-camera-canvas");
const btnShareCamera = document.getElementById("btn-share-camera");
const ownCameraStatus = document.getElementById("own-camera-status");

const OWN_CAMERA_PUSH_INTERVAL_MS = 333; // ~3 fps, de sobra para conteo
let ownCameraStream = null;
let ownCameraPushTimer = null;

function setOwnCameraStatus(message, type = "success") {
  ownCameraStatus.textContent = message;
  ownCameraStatus.style.color = type === "error" ? "var(--danger, #f87171)" : "var(--accent)";
}

async function pushOwnCameraFrame() {
  if (!ownCameraPreview.videoWidth || !ownCameraPreview.videoHeight) return;
  ownCameraCanvas.width = ownCameraPreview.videoWidth;
  ownCameraCanvas.height = ownCameraPreview.videoHeight;
  const ctx2d = ownCameraCanvas.getContext("2d");
  ctx2d.drawImage(ownCameraPreview, 0, 0, ownCameraCanvas.width, ownCameraCanvas.height);
  const imageBase64 = ownCameraCanvas.toDataURL("image/jpeg", 0.7);
  try {
    const response = await fetch("/api/live/push-frame", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ imageBase64 }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      setOwnCameraStatus(payload.error || `El servidor respondió ${response.status}`, "error");
      return;
    }
    setOwnCameraStatus("Compartiendo tu cámara con el sistema...");
  } catch {
    setOwnCameraStatus("No fue posible conectar con el servidor.", "error");
  }
}

async function startSharingOwnCamera() {
  try {
    // Limitamos la resolucion a propósito: YOLO reescala internamente a
    // 320px, así que pedir mas (algunos celulares capturan en 1080p+ por
    // defecto) solo agrega peso a cada envio sin mejorar la deteccion, y
    // hace que todo el pipeline se sienta mas lento/trabado.
    ownCameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "environment",
        width: { ideal: 640, max: 640 },
        height: { ideal: 480, max: 480 },
      },
      audio: false,
    });
  } catch {
    setOwnCameraStatus("No se pudo acceder a la cámara (permiso denegado o no disponible).", "error");
    return;
  }
  ownCameraPreview.srcObject = ownCameraStream;
  btnShareCamera.textContent = "Detener mi cámara";
  setOwnCameraStatus("Cámara activada, iniciando envío...");
  if (ownCameraPushTimer) clearInterval(ownCameraPushTimer);
  ownCameraPushTimer = setInterval(pushOwnCameraFrame, OWN_CAMERA_PUSH_INTERVAL_MS);
}

function stopSharingOwnCamera() {
  if (ownCameraPushTimer) {
    clearInterval(ownCameraPushTimer);
    ownCameraPushTimer = null;
  }
  if (ownCameraStream) {
    ownCameraStream.getTracks().forEach((track) => track.stop());
    ownCameraStream = null;
  }
  ownCameraPreview.srcObject = null;
  btnShareCamera.textContent = "Activar mi cámara";
  setOwnCameraStatus("Dejaste de compartir tu cámara.");
}

btnShareCamera.addEventListener("click", () => {
  if (ownCameraStream) {
    stopSharingOwnCamera();
  } else {
    startSharingOwnCamera();
  }
});
