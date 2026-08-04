const video = document.getElementById("config-video");
const wrapper = document.getElementById("config-video-wrapper");
const canvas = document.getElementById("scene-overlay");
const ctx = canvas.getContext("2d");

let calibration = null;
let scene = null;
let scanStatus = null;
let drawing = false;
let draftImagePoints = [];
let dragging = null;
let moveTimer = null;

function message(id, text, error = false) {
  const element = document.getElementById(id);
  element.textContent = text;
  element.className = `form-message ${error ? "error" : "success"}`;
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function syncCanvas() {
  const width = video.clientWidth;
  const height = video.clientHeight;
  if (!width || !height) return;
  canvas.width = width;
  canvas.height = height;
  renderOverlay();
}

function naturalFromEvent(event) {
  const rect = video.getBoundingClientRect();
  const naturalWidth = video.naturalWidth || 1280;
  const naturalHeight = video.naturalHeight || 720;
  return {
    u: ((event.clientX - rect.left) * naturalWidth) / rect.width,
    v: ((event.clientY - rect.top) * naturalHeight) / rect.height,
  };
}

function displayPoint(point) {
  const naturalWidth = video.naturalWidth || 1280;
  const naturalHeight = video.naturalHeight || 720;
  return {
    x: (point.u * canvas.width) / naturalWidth,
    y: (point.v * canvas.height) / naturalHeight,
  };
}

function projectGround(point) {
  const h = calibration?.world?.groundToImageHomography;
  if (!h) return null;
  const x = Number(point[0]);
  const y = Number(point[1]);
  const px = h[0][0] * x + h[0][1] * y + h[0][2];
  const py = h[1][0] * x + h[1][1] * y + h[1][2];
  const w = h[2][0] * x + h[2][1] * y + h[2][2];
  if (Math.abs(w) < 1e-8) return null;
  return displayPoint({ u: px / w, v: py / w });
}

function strokePolygon(points, color, width = 2, close = true) {
  const valid = points.filter(Boolean);
  if (valid.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(valid[0].x, valid[0].y);
  valid.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  if (close) ctx.closePath();
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.stroke();
}

function renderGrid() {
  const fov = scene?.fieldOfViewPolygon || [];
  if (fov.length < 3 || !calibration?.world) return;
  const xs = fov.map((point) => point[0]);
  const ys = fov.map((point) => point[1]);
  const minX = Math.floor(Math.min(...xs));
  const maxX = Math.ceil(Math.max(...xs));
  const minY = Math.floor(Math.min(...ys));
  const maxY = Math.ceil(Math.max(...ys));
  for (let x = minX; x <= maxX; x += 1) {
    strokePolygon([projectGround([x, minY]), projectGround([x, maxY])], "rgba(34,197,94,.4)", 1, false);
  }
  for (let y = minY; y <= maxY; y += 1) {
    strokePolygon([projectGround([minX, y]), projectGround([maxX, y])], "rgba(34,197,94,.4)", 1, false);
  }
}

function renderOverlay() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  renderGrid();
  const fov = (scene?.fieldOfViewPolygon || []).map(projectGround);
  strokePolygon(fov, "rgba(56,189,248,.95)", 2);
  (scene?.objects || []).forEach((object) => {
    const points = (object.footprint || []).map(projectGround);
    strokePolygon(points, "rgba(249,115,22,.95)", 3);
    points.forEach((point) => {
      if (!point) return;
      ctx.beginPath();
      ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = "#fb923c";
      ctx.fill();
    });
  });
  const draft = draftImagePoints.map(displayPoint);
  strokePolygon(draft, "#facc15", 2, false);
  draft.forEach((point) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#facc15";
    ctx.fill();
  });
}

async function refreshStatus() {
  calibration = await api("/api/calibration/status");
  const status = document.getElementById("calibration-status");
  status.innerHTML = `
    <div><span>Intrinsecos</span><strong>${calibration.intrinsics ? `v${calibration.intrinsics.version} · ${calibration.intrinsics.reprojectionErrorPx.toFixed(3)}px` : "pendiente"}</strong></div>
    <div><span>Mundo</span><strong>${calibration.world ? `v${calibration.world.version} · ${calibration.world.validationErrorMeters.toFixed(3)}m` : "pendiente"}</strong></div>
    <div><span>Profundidad</span><strong>${calibration.depth.method || calibration.depth.mode}</strong></div>
    <div><span>Escaneo</span><strong>${calibration.scanReady ? "listo" : calibration.blockers.join(", ")}</strong></div>`;
  renderOverlay();
}

async function refreshScene() {
  scene = await api("/api/scene");
  const list = document.getElementById("object-list");
  list.innerHTML = (scene.objects || []).map((object) => `
    <div class="object-row"><span><strong>${object.name}</strong><small>${object.type} · ${object.depthMethod}${object.approximate ? " · aprox." : ""}</small></span>
    <span class="inline-actions"><button data-edit="${object.id}" class="action-link button-link">Editar</button><button data-delete="${object.id}" class="action-btn-danger">Eliminar</button></span></div>`).join("") || "<p class='empty'>Sin objetos guardados.</p>";
  list.querySelectorAll("[data-delete]").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/scene/objects/${encodeURIComponent(button.dataset.delete)}`, { method: "DELETE" });
    await refreshScene();
  }));
  list.querySelectorAll("[data-edit]").forEach((button) => button.addEventListener("click", async () => {
    const item = (scene.objects || []).find((object) => object.id === button.dataset.edit);
    if (!item) return;
    const newName = window.prompt("Nombre del objeto", item.name);
    if (newName === null || !newName.trim()) return;
    const newType = window.prompt("Clase del objeto", item.type);
    if (newType === null || !newType.trim()) return;
    await api(`/api/scene/objects/${encodeURIComponent(item.id)}`, {
      method: "PATCH",
      body: JSON.stringify({ name: newName.trim(), type: newType.trim() }),
    });
    await refreshScene();
  }));
  renderOverlay();
}

async function imagePointsToWorld(points) {
  return Promise.all(points.map(async (point) => {
    const data = await api(`/api/coordinates/image-to-ground?u=${point.u}&v=${point.v}`);
    return [data.worldPoint.x, data.worldPoint.y];
  }));
}

canvas.addEventListener("mousedown", (event) => {
  if (drawing) return;
  const click = { x: event.offsetX, y: event.offsetY };
  for (const object of scene?.objects || []) {
    const projected = (object.footprint || []).map(projectGround);
    const index = projected.findIndex((point) => point && Math.hypot(point.x - click.x, point.y - click.y) < 10);
    if (index >= 0) {
      dragging = { object, index };
      return;
    }
  }
});

canvas.addEventListener("mousemove", (event) => {
  const point = naturalFromEvent(event);
  document.getElementById("image-coordinate").textContent = `u=${point.u.toFixed(1)}, v=${point.v.toFixed(1)}`;
  if (dragging) {
    const world = calibration?.world?.imageToGroundHomography;
    if (world) {
      const p = world;
      const w = p[2][0] * point.u + p[2][1] * point.v + p[2][2];
      dragging.object.footprint[dragging.index] = [
        (p[0][0] * point.u + p[0][1] * point.v + p[0][2]) / w,
        (p[1][0] * point.u + p[1][1] * point.v + p[1][2]) / w,
      ];
      renderOverlay();
    }
  }
  clearTimeout(moveTimer);
  moveTimer = setTimeout(async () => {
    try {
      const data = await api(`/api/coordinates/image-to-ground?u=${point.u}&v=${point.v}`);
      document.getElementById("world-coordinate").textContent = `X=${data.worldPoint.x.toFixed(2)}m, Y=${data.worldPoint.y.toFixed(2)}m`;
    } catch (_) {
      document.getElementById("world-coordinate").textContent = "calibracion pendiente";
    }
  }, 100);
});

canvas.addEventListener("mouseup", async () => {
  if (!dragging) return;
  const item = dragging.object;
  dragging = null;
  try {
    await api(`/api/scene/objects/${encodeURIComponent(item.id)}`, {
      method: "PATCH",
      body: JSON.stringify({ footprint: item.footprint }),
    });
    await refreshScene();
  } catch (error) {
    message("object-message", error.message, true);
  }
});

canvas.addEventListener("click", (event) => {
  if (!drawing || dragging) return;
  draftImagePoints.push(naturalFromEvent(event));
  document.getElementById("save-object").disabled = draftImagePoints.length < 3;
  renderOverlay();
});

document.getElementById("begin-polygon").addEventListener("click", () => {
  drawing = true;
  draftImagePoints = [];
  document.getElementById("save-object").disabled = true;
  message("object-message", "Pulsa al menos tres vertices sobre el suelo.");
  renderOverlay();
});

document.getElementById("undo-vertex").addEventListener("click", () => {
  draftImagePoints.pop();
  document.getElementById("save-object").disabled = draftImagePoints.length < 3;
  renderOverlay();
});

document.getElementById("save-object").addEventListener("click", async () => {
  try {
    const footprint = await imagePointsToWorld(draftImagePoints);
    const heightRaw = document.getElementById("object-height").value;
    await api("/api/scene/objects", {
      method: "POST",
      body: JSON.stringify({
        name: document.getElementById("object-name").value,
        type: document.getElementById("object-type").value,
        footprint,
        heightMeters: heightRaw === "" ? null : Number(heightRaw),
        depthMethod: heightRaw === "" ? "ground_plane" : "manual",
        approximate: true,
        confidence: 1,
      }),
    });
    drawing = false;
    draftImagePoints = [];
    document.getElementById("save-object").disabled = true;
    message("object-message", "Objeto guardado en una nueva version de escena.");
    await refreshScene();
  } catch (error) {
    message("object-message", error.message, true);
  }
});

document.getElementById("capture-charuco").addEventListener("click", async () => {
  try {
    const data = await api("/api/calibration/intrinsics/capture", { method: "POST", body: "{}" });
    message("charuco-message", data.accepted ? `Vista ${data.captureCount} aceptada (${data.cornerCount} esquinas).` : data.warning, !data.accepted);
    await refreshStatus();
  } catch (error) { message("charuco-message", error.message, true); }
});

document.getElementById("solve-charuco").addEventListener("click", async () => {
  try {
    const data = await api("/api/calibration/intrinsics/solve", { method: "POST", body: "{}" });
    message("charuco-message", `Calibracion v${data.version}, RMS ${data.reprojectionErrorPx.toFixed(3)}px.`);
    await refreshStatus();
  } catch (error) { message("charuco-message", error.message, true); }
});

document.getElementById("solve-world").addEventListener("click", async () => {
  try {
    const payload = JSON.parse(document.getElementById("world-payload").value);
    const data = await api("/api/calibration/world/solve", { method: "POST", body: JSON.stringify(payload) });
    message("world-message", `Mundo v${data.version}, error ${data.validationErrorMeters.toFixed(3)}m.`);
    await Promise.all([refreshStatus(), refreshScene()]);
  } catch (error) { message("world-message", error.message, true); }
});

async function pollScan() {
  scanStatus = await api("/api/scene/scan/status");
  document.getElementById("scan-state").textContent = scanStatus.state;
  document.getElementById("scan-details").textContent = JSON.stringify({
    frames: `${scanStatus.framesCaptured || 0}/${scanStatus.framesTarget || 0}`,
    detections: scanStatus.detectionsObserved || 0,
    proposals: (scanStatus.proposals || []).map((item) => ({ id: item.id, type: item.type, confidence: item.confidence })),
    warnings: scanStatus.warnings || [],
    error: scanStatus.error || null,
  }, null, 2);
  document.getElementById("proposal-list").innerHTML = (scanStatus.proposals || []).map((item, index) => `
    <label class="proposal-row"><input type="checkbox" data-proposal="${index}" checked />
      <span>${item.name || item.type}<small>${item.type} · confianza ${Number(item.confidence || 0).toFixed(2)}</small></span>
    </label>`).join("");
}

document.getElementById("start-scan").addEventListener("click", async () => {
  try { await api("/api/scene/scan/start", { method: "POST", body: "{}" }); await pollScan(); }
  catch (error) { document.getElementById("scan-details").textContent = error.message; }
});
document.getElementById("stop-scan").addEventListener("click", async () => {
  await api("/api/scene/scan/stop", { method: "POST", body: "{}" }); await pollScan();
});
document.getElementById("accept-proposals").addEventListener("click", async () => {
  const current = await api("/api/scene");
  const selected = [...document.querySelectorAll("[data-proposal]:checked")]
    .map((checkbox) => (scanStatus.proposals || [])[Number(checkbox.dataset.proposal)])
    .filter(Boolean);
  await api("/api/scene", { method: "PUT", body: JSON.stringify({ ...current, objects: [...(current.objects || []), ...selected] }) });
  await refreshScene();
});
document.getElementById("refresh-status").addEventListener("click", refreshStatus);

video.addEventListener("load", syncCanvas);
window.addEventListener("resize", syncCanvas);
if (typeof ResizeObserver !== "undefined") new ResizeObserver(syncCanvas).observe(wrapper);
Promise.all([refreshStatus(), refreshScene(), pollScan()]).then(syncCanvas);
setInterval(pollScan, 1500);
