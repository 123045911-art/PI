import { StaticObject, TrackPoint, Zone } from './types';

// Jornada simulada de 08:00 a 16:00. Las coordenadas conservan el mismo
// contrato que la base: tracker, instante, x, y y area asociada.
export const FLOOR = { width: 100, height: 68, duration: 8 * 3600 };
export const SAMPLE_SECONDS = 4;
export const SIMULATED_TRACKS = 900;

export const ZONES: Zone[] = [
  { id: 'access', name: 'Acceso visible', x: 2, y: 22, width: 16, height: 29, kind: 'access' },
  { id: 'launch', name: 'Rack denim', x: 18, y: 7, width: 29, height: 23, kind: 'interaction' },
  { id: 'central', name: 'Mesa temporada', x: 36, y: 28, width: 31, height: 27, kind: 'interaction' },
  { id: 'premium', name: 'Rack vestidos', x: 58, y: 6, width: 24, height: 22, kind: 'interaction' },
  { id: 'service', name: 'Caja visible', x: 78, y: 30, width: 20, height: 32, kind: 'service' },
  { id: 'north', name: 'Paso probadores', x: 17, y: 51, width: 42, height: 14, kind: 'transit' },
];

export const STATIC_OBJECTS: StaticObject[] = [
  // CAM-03 observa solo esta fracción de la tienda, no la planta completa.
  { id: 'wall-n', label: 'Muro de exhibición', x: 0, y: 0, width: 100, height: 1.2, elevation: 4.5, kind: 'wall' },
  { id: 'wall-w', label: 'Límite del local', x: 0, y: 0, width: 1.2, height: 53, elevation: 5.5, kind: 'wall' },
  { id: 'rack-denim', label: 'Rack denim', x: 25, y: 13, width: 16, height: 4, elevation: 4.2, kind: 'display' },
  { id: 'rack-dresses', label: 'Rack vestidos', x: 62, y: 12, width: 15, height: 4, elevation: 4.6, kind: 'display' },
  { id: 'table-season', label: 'Mesa temporada', x: 44, y: 35, width: 14, height: 8, elevation: 2.1, kind: 'display' },
  { id: 'rack-accessories', label: 'Accesorios', x: 21, y: 38, width: 5, height: 12, elevation: 3.1, kind: 'display' },
  { id: 'mannequin-1', label: 'Maniquí', x: 47, y: 18, width: 2.5, height: 2.5, elevation: 5.2, kind: 'display' },
  { id: 'mannequin-2', label: 'Maniquí', x: 53, y: 18, width: 2.5, height: 2.5, elevation: 4.8, kind: 'display' },
  { id: 'fitting-wall', label: 'Probadores', x: 70, y: 43, width: 3, height: 19, elevation: 6.2, kind: 'wall' },
  { id: 'fitting-bench', label: 'Banca', x: 76, y: 51, width: 11, height: 4, elevation: 1.4, kind: 'display' },
  { id: 'checkout-edge', label: 'Caja parcial', x: 88, y: 33, width: 12, height: 9, elevation: 3, kind: 'service' },
];

const SIMULATED_FLOOR = { ...FLOOR };
const SIMULATED_ZONES = ZONES.map((zone) => ({ ...zone }));
const SIMULATED_STATIC_OBJECTS = STATIC_OBJECTS.map((object) => ({ ...object }));

/** Switches the map renderer between independently calibrated sites. */
export function activateMapScene(
  floor: { width: number; height: number; duration?: number },
  zones: Zone[],
  objects: StaticObject[],
) {
  FLOOR.width = floor.width;
  FLOOR.height = floor.height;
  FLOOR.duration = floor.duration ?? 3600;
  ZONES.splice(0, ZONES.length, ...zones.map((zone) => ({ ...zone })));
  STATIC_OBJECTS.splice(0, STATIC_OBJECTS.length, ...objects.map((object) => ({ ...object })));
}

export function restoreSimulatedMapScene() {
  activateMapScene(SIMULATED_FLOOR, SIMULATED_ZONES, SIMULATED_STATIC_OBJECTS);
}

const anchors: Record<string, [number, number]> = {
  access: [8, 35],
  launch: [34, 24],
  central: [52, 48],
  premium: [70, 23],
  service: [82, 45],
  north: [36, 59],
  exit: [98, 63],
};

function randomFactory(seed: number) {
  return () => {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function isBlocked(x: number, y: number, padding = 0.8) {
  return STATIC_OBJECTS.some((object) =>
    x >= object.x - padding &&
    x <= object.x + object.width + padding &&
    y >= object.y - padding &&
    y <= object.y + object.height + padding,
  );
}

// La zona se deriva exclusivamente de la coordenada observada. Cuando dos
// poligonos se superponen, gana el de menor superficie por ser el mas
// especifico. Un punto de pasillo puede no pertenecer a ninguna zona.
export function zoneAtPoint(x: number, y: number) {
  return [...ZONES]
    .filter((zone) =>
      x >= zone.x && x <= zone.x + zone.width &&
      y >= zone.y && y <= zone.y + zone.height,
    )
    .sort((a, b) => a.width * a.height - b.width * b.height)[0]?.id ?? null;
}

function keepWalkable(x: number, y: number): [number, number] {
  const safeX = Math.max(1.8, Math.min(FLOOR.width - 1.8, x));
  const safeY = Math.max(2, Math.min(FLOOR.height - 2, y));
  if (!isBlocked(safeX, safeY, 1.05)) return [safeX, safeY];

  for (let distance = 2; distance <= 9; distance += 1.5) {
    const candidates: [number, number][] = [
      [safeX + distance, safeY], [safeX - distance, safeY],
      [safeX, safeY + distance], [safeX, safeY - distance],
    ];
    const available = candidates.find(([candidateX, candidateY]) =>
      candidateX > 1.5 && candidateX < FLOOR.width - 1.5 &&
      candidateY > 1.5 && candidateY < FLOOR.height - 1.5 &&
      !isBlocked(candidateX, candidateY, 1.05),
    );
    if (available) return available;
  }
  return [safeX, safeY];
}

export function segmentCrossesStructure(a: [number, number], b: [number, number], padding = 1.05) {
  const distance = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const samples = Math.max(2, Math.ceil(distance / 0.55));
  for (let index = 0; index <= samples; index += 1) {
    const ratio = index / samples;
    if (isBlocked(a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio, padding)) return true;
  }
  return false;
}

const PATH_STEP = 2;
const pathCache = new Map<string, [number, number][]>();

function routeAroundStructures(from: [number, number], to: [number, number]) {
  const safeFrom = keepWalkable(from[0], from[1]);
  const safeTo = keepWalkable(to[0], to[1]);
  const cacheKey = `${safeFrom.map(Math.round).join(',')}>${safeTo.map(Math.round).join(',')}`;
  const cached = pathCache.get(cacheKey);
  if (cached) return cached;
  if (!segmentCrossesStructure(safeFrom, safeTo)) {
    const direct = [safeFrom, safeTo] as [number, number][];
    pathCache.set(cacheKey, direct);
    return direct;
  }

  const snap = ([x, y]: [number, number]) => [Math.round(x / PATH_STEP) * PATH_STEP, Math.round(y / PATH_STEP) * PATH_STEP] as [number, number];
  const nearestWalkable = (point: [number, number]) => {
    const origin = snap(point);
    for (let ring = 0; ring <= 7; ring += 1) {
      for (let dx = -ring; dx <= ring; dx += 1) {
        for (let dy = -ring; dy <= ring; dy += 1) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== ring) continue;
          const candidate: [number, number] = [origin[0] + dx * PATH_STEP, origin[1] + dy * PATH_STEP];
          if (candidate[0] >= 2.2 && candidate[0] <= FLOOR.width - 2.2 && candidate[1] >= 2.2 && candidate[1] <= FLOOR.height - 2.2 && !isBlocked(candidate[0], candidate[1], 1.05)) return candidate;
        }
      }
    }
    return keepWalkable(point[0], point[1]);
  };
  const start = nearestWalkable(safeFrom);
  const goal = nearestWalkable(safeTo);
  const key = ([x, y]: [number, number]) => `${x},${y}`;
  const parse = (value: string) => value.split(',').map(Number) as [number, number];
  const open = new Set([key(start)]);
  const cameFrom = new Map<string, string>();
  const gScore = new Map<string, number>([[key(start), 0]]);
  const fScore = new Map<string, number>([[key(start), Math.hypot(goal[0] - start[0], goal[1] - start[1])]]);
  const directions: [number, number][] = [
    [1, 0], [-1, 0], [0, 1], [0, -1],
    [1, 1], [1, -1], [-1, 1], [-1, -1],
  ];
  let result: [number, number][] | null = null;

  while (open.size) {
    let currentKey = [...open].reduce((best, candidate) => (fScore.get(candidate) ?? Infinity) < (fScore.get(best) ?? Infinity) ? candidate : best);
    const current = parse(currentKey);
    if (currentKey === key(goal)) {
      const reversed = [current];
      while (cameFrom.has(currentKey)) {
        currentKey = cameFrom.get(currentKey)!;
        reversed.push(parse(currentKey));
      }
      result = reversed.reverse();
      break;
    }
    open.delete(currentKey);
    directions.forEach(([dx, dy]) => {
      const neighbor: [number, number] = [current[0] + dx * PATH_STEP, current[1] + dy * PATH_STEP];
      if (neighbor[0] < 2.2 || neighbor[0] > FLOOR.width - 2.2 || neighbor[1] < 2.2 || neighbor[1] > FLOOR.height - 2.2) return;
      if (isBlocked(neighbor[0], neighbor[1], 1.05) || segmentCrossesStructure(current, neighbor)) return;
      const neighborKey = key(neighbor);
      const tentative = (gScore.get(currentKey) ?? Infinity) + Math.hypot(dx, dy) * PATH_STEP;
      if (tentative >= (gScore.get(neighborKey) ?? Infinity)) return;
      cameFrom.set(neighborKey, currentKey);
      gScore.set(neighborKey, tentative);
      fScore.set(neighborKey, tentative + Math.hypot(goal[0] - neighbor[0], goal[1] - neighbor[1]));
      open.add(neighborKey);
    });
  }

  const gridPath = result ?? [start, goal];
  const complete = [safeFrom, ...gridPath, safeTo];
  const simplified: [number, number][] = [complete[0]];
  let cursor = 0;
  while (cursor < complete.length - 1) {
    let next = complete.length - 1;
    while (next > cursor + 1 && segmentCrossesStructure(complete[cursor], complete[next])) next -= 1;
    simplified.push(complete[next]);
    cursor = next;
  }
  pathCache.set(cacheKey, simplified);
  return simplified;
}

function interpolate(a: [number, number], b: [number, number], count: number, jitter: number, random: () => number) {
  const route = routeAroundStructures(a, b);
  const segments = route.slice(1).map((point, index) => ({
    from: route[index],
    to: point,
    length: Math.hypot(point[0] - route[index][0], point[1] - route[index][1]),
  }));
  const totalLength = segments.reduce((sum, segment) => sum + segment.length, 0);
  const sampleCount = Math.max(count, Math.round(totalLength / 1.75));
  let previous = route[0];
  return Array.from({ length: sampleCount }, (_, index) => {
    let targetDistance = (index / Math.max(1, sampleCount - 1)) * totalLength;
    const segment = segments.find((item) => {
      if (targetDistance <= item.length) return true;
      targetDistance -= item.length;
      return false;
    }) ?? segments[segments.length - 1];
    const ratio = Math.min(1, targetDistance / Math.max(0.001, segment.length));
    const base: [number, number] = [
      segment.from[0] + (segment.to[0] - segment.from[0]) * ratio,
      segment.from[1] + (segment.to[1] - segment.from[1]) * ratio,
    ];
    const candidate = keepWalkable(
      base[0] + (random() - 0.5) * Math.min(jitter, 0.8),
      base[1] + (random() - 0.5) * Math.min(jitter, 0.8),
    );
    const point = segmentCrossesStructure(previous, candidate) ? base : candidate;
    previous = point;
    return point;
  });
}

export function generateTrackPoints(): TrackPoint[] {
  const random = randomFactory(2026);
  const points: TrackPoint[] = [];
  const routes = [
    ['access', 'launch', 'central', 'premium', 'service'],
    ['access', 'central', 'service'],
    ['access', 'launch', 'premium', 'service'],
    ['access', 'central', 'north', 'service'],
    ['access', 'launch', 'central', 'north'],
    ['access', 'premium', 'central', 'service'],
    ['access', 'north', 'central', 'launch', 'service'],
    ['access', 'central', 'premium', 'central', 'service'],
  ];

  const pushPoint = (point: Omit<TrackPoint, 'zoneId'>) => {
    if (point.timestamp <= FLOOR.duration) {
      const previous = points[points.length - 1];
      const crossesStructure = previous?.trackId === point.trackId && segmentCrossesStructure([previous.x, previous.y], [point.x, point.y]);
      const x = crossesStructure ? previous.x : point.x;
      const y = crossesStructure ? previous.y : point.y;
      points.push({ ...point, x, y, zoneId: zoneAtPoint(x, y) });
    }
  };

  for (let trackId = 1; trackId <= SIMULATED_TRACKS; trackId += 1) {
    // Tres olas de afluencia producen una jornada legible sin inventar
    // variables comerciales: solo cambia cuándo aparece cada trayectoria.
    const cluster = random();
    const center = cluster < 0.3 ? 1.5 * 3600 : cluster < 0.72 ? 4.25 * 3600 : 6.45 * 3600;
    const spread = (random() + random() + random() - 1.5) * 3900;
    const start = Math.floor(Math.max(0, Math.min(FLOOR.duration - 1200, center + spread)));
    const route = routes[Math.floor(random() * routes.length)];
    let timestamp = start;

    route.forEach((zoneId, routeIndex) => {
      const from = routeIndex === 0 ? [1.8, 35] as [number, number] : anchors[route[routeIndex - 1]];
      const to = anchors[zoneId];
      const distance = Math.hypot(to[0] - from[0], to[1] - from[1]);
      const movementSamples = Math.max(9, Math.round(distance / 1.75));
      interpolate(from, to, movementSamples, 1.55, random).forEach(([x, y]) => {
        pushPoint({ trackId, timestamp, x, y });
        timestamp += SAMPLE_SECONDS;
      });

      const dwellBase = zoneId === 'premium' ? 15 : zoneId === 'central' ? 12 : zoneId === 'north' ? 4 : 8;
      const dwellCount = dwellBase + Math.floor(random() * (zoneId === 'north' ? 5 : 14));
      const stoppedSegment = zoneId !== 'north' && random() < 0.72;
      for (let dwellIndex = 0; dwellIndex < dwellCount; dwellIndex += 1) {
        const [x, y] = keepWalkable(
          to[0] + (random() - 0.5) * (stoppedSegment ? 0.82 : 5.2),
          to[1] + (random() - 0.5) * (stoppedSegment ? 0.82 : 4.1),
        );
        pushPoint({ trackId, timestamp, x, y });
        timestamp += SAMPLE_SECONDS;
      }
    });

    const lastAnchor = anchors[route[route.length - 1]];
    const exitSamples = Math.max(10, Math.round(Math.hypot(anchors.exit[0] - lastAnchor[0], anchors.exit[1] - lastAnchor[1]) / 1.8));
    interpolate(lastAnchor, anchors.exit, exitSamples, 1.2, random).forEach(([x, y]) => {
      pushPoint({ trackId, timestamp, x, y });
      timestamp += SAMPLE_SECONDS;
    });
  }
  return points;
}

export const TRACK_POINTS = generateTrackPoints();

const DAY_RETENTION = [0.76, 0.82, 0.88, 0.92, 0.96, 1, 0.7];
const dayPointCache = new Map<number, TrackPoint[]>();

// Proyección determinística para explorar una semana sin multiplicar por siete
// el costo de memoria móvil. Conserva trayectorias completas y solo cambia la
// muestra de personas incluida en cada día. El backend reemplazará esta capa
// con registros reales filtrados por fecha.
export function trackPointsForDay(dayIndex: number) {
  const normalizedDay = Math.max(0, Math.min(6, Math.round(dayIndex)));
  const cached = dayPointCache.get(normalizedDay);
  if (cached) return cached;
  const retention = DAY_RETENTION[normalizedDay];
  const selected = TRACK_POINTS.filter((point) => {
    const deterministic = ((point.trackId * 97 + normalizedDay * 193) % 1000) / 1000;
    return deterministic <= retention;
  });
  dayPointCache.set(normalizedDay, selected);
  return selected;
}
