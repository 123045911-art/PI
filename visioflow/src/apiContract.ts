import { TrackPoint, Zone } from './types';
import type { AlertScheduleMode, AlertStatus, AlertType, LocalAlert } from './localStore';

/** Wire-level types defined by docs/openapi.yaml. */
export type ExternalId = string;

export type ApiCamera = {
  siteId: ExternalId;
  cameraId: ExternalId;
  name: string;
  sensorMode: 'rgbd' | 'stereo' | 'monocular';
  active: boolean;
};

export type ApiArea = {
  areaId: ExternalId;
  name: string;
  kind: Zone['kind'];
  polygon: [number, number][];
  bounds: { x: number; y: number; width: number; height: number };
};

export type ApiStaticObject = {
  objectId: string;
  name: string;
  type: 'wall' | 'table' | 'shelf' | 'rack' | 'display' | 'checkout' | 'bench' | 'column' | 'other';
  footprint: [number, number][];
  center?: { x: number; y: number; z: number };
  widthMeters?: number;
  depthMeters?: number;
  heightMeters?: number;
  depthMethod: 'rgbd' | 'stereo' | 'ground_plane' | 'manual';
  approximate: boolean;
  confidence?: number;
  metadata?: Record<string, unknown>;
};

export type ApiScene = {
  cameraId: ExternalId;
  coordinateSystem: {
    name: 'world_ground';
    unit: 'meter';
    origin: string;
    xAxis: 'right';
    yAxis: 'forward';
    zAxis: 'up';
  };
  calibrationVersion: number;
  fieldOfViewPolygon: [number, number][];
  operationalAreas: ApiArea[];
  objects: ApiStaticObject[];
  fixedPointMatrixResolutionMeters?: number;
  createdAt: string;
  version: number;
};

export type ApiBootstrap = {
  siteId: ExternalId;
  name: string;
  timezone: string;
  cameras: ApiCamera[];
  areas: ApiArea[];
  scenes: ApiScene[];
};

export type ApiTrackPoint = {
  cameraId: ExternalId;
  sessionId: string;
  frameId: number;
  trackerId: `trk-${number}`;
  capturedAt: string;
  imagePoint?: { u: number; v: number } | null;
  x: number;
  y: number;
  z: number;
  areaId: ExternalId | null;
  confidence: number;
};

export type ApiAreaState = {
  cameraId: ExternalId;
  areaId: ExternalId;
  peopleCount: number;
  observedAt: string;
};

export type ApiAreaEvent = {
  eventId: string;
  cameraId: ExternalId;
  sessionId: string;
  trackerId: `trk-${number}`;
  areaId: ExternalId;
  eventType: 'enter' | 'exit';
  capturedAt: string;
  dwellSeconds: number;
};

export type ApiAreaHourMetric = {
  areaId: ExternalId;
  bucketStart: string;
  uniqueTracks: number;
  visits: number;
  medianDwellSeconds: number;
  stoppedVisits: number;
  medianStoppedSeconds: number;
  peakConcurrent: number;
};

/**
 * The alert returned by the API is deliberately the exact LocalAlert shape.
 * Keeping this alias prevents alertType/type, alertId/id, or scheduleDay naming drift.
 */
export type ApiAlert = LocalAlert;

export type ApiAlertCreate = {
  areaId: ExternalId;
  type: AlertType;
  reason: string;
  thresholdPeople?: number;
  scheduleMode: AlertScheduleMode;
  scheduleDay?: number;
  scheduleDate?: string;
};

export type ApiAlertUpdate = {
  status: AlertStatus;
};

export type ApiAlertSummary = {
  total: number;
  byType: Record<AlertType, number>;
  byStatus: Record<AlertStatus, number>;
};

export type ApiAlertListResponse = {
  items: ApiAlert[];
  summary: ApiAlertSummary;
  nextCursor: string | null;
};

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};

export type WorldBounds = {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
};

export type WorldProjection = {
  bounds: WorldBounds;
  scale: number;
  offsetX: number;
  offsetY: number;
  toDisplay: (x: number, y: number) => { x: number; y: number };
};

const DISPLAY_FLOOR = { width: 100, height: 68 };

export function createWorldProjection(fieldOfViewPolygon: [number, number][]): WorldProjection {
  if (fieldOfViewPolygon.length < 3) throw new Error('A field-of-view polygon needs at least three points');
  const xs = fieldOfViewPolygon.map(([x]) => x);
  const ys = fieldOfViewPolygon.map(([, y]) => y);
  const bounds = {
    minX: Math.min(...xs), minY: Math.min(...ys),
    maxX: Math.max(...xs), maxY: Math.max(...ys),
  };
  const worldWidth = bounds.maxX - bounds.minX;
  const worldHeight = bounds.maxY - bounds.minY;
  if (!(worldWidth > 0) || !(worldHeight > 0)) throw new Error('Field-of-view bounds must have positive dimensions');
  const scale = Math.min(DISPLAY_FLOOR.width / worldWidth, DISPLAY_FLOOR.height / worldHeight);
  const offsetX = (DISPLAY_FLOOR.width - worldWidth * scale) / 2;
  const offsetY = (DISPLAY_FLOOR.height - worldHeight * scale) / 2;
  return {
    bounds, scale, offsetX, offsetY,
    toDisplay: (x, y) => ({
      x: offsetX + (x - bounds.minX) * scale,
      y: offsetY + (y - bounds.minY) * scale,
    }),
  };
}

export function apiAreaToZone(area: ApiArea, projection?: WorldProjection): Zone {
  const topLeft = projection?.toDisplay(area.bounds.x, area.bounds.y)
    ?? { x: area.bounds.x, y: area.bounds.y };
  const bottomRight = projection?.toDisplay(
    area.bounds.x + area.bounds.width,
    area.bounds.y + area.bounds.height,
  ) ?? { x: area.bounds.x + area.bounds.width, y: area.bounds.y + area.bounds.height };
  return {
    id: area.areaId,
    name: area.name,
    kind: area.kind,
    x: topLeft.x,
    y: topLeft.y,
    width: bottomRight.x - topLeft.x,
    height: bottomRight.y - topLeft.y,
  };
}

/**
 * The visualizer still uses numeric IDs and seconds relative to a visible
 * period. The API uses the collision-safe camera/session/tracker tuple and UTC.
 * Keep one adapter instance for the complete paginated period.
 */
export function createTrackPointAdapter(periodStart: string | Date, projection?: WorldProjection) {
  const startMs = new Date(periodStart).getTime();
  if (!Number.isFinite(startMs)) throw new Error('periodStart must be a valid ISO date');

  const numericIds = new Map<string, number>();
  let nextId = 1;

  return (point: ApiTrackPoint): TrackPoint => {
    const capturedMs = Date.parse(point.capturedAt);
    if (!Number.isFinite(capturedMs)) throw new Error(`Invalid capturedAt: ${point.capturedAt}`);
    const identity = `${point.cameraId}:${point.sessionId}:${point.trackerId}`;
    let trackId = numericIds.get(identity);
    if (trackId === undefined) {
      trackId = nextId;
      nextId += 1;
      numericIds.set(identity, trackId);
    }
    const display = projection?.toDisplay(point.x, point.y) ?? { x: point.x, y: point.y };
    return {
      trackId,
      timestamp: Math.max(0, (capturedMs - startMs) / 1000),
      x: display.x,
      y: display.y,
      zoneId: point.areaId,
      worldX: point.x,
      worldY: point.y,
      worldZ: point.z,
      imageU: point.imagePoint?.u,
      imageV: point.imagePoint?.v,
      capturedAt: point.capturedAt,
      cameraId: point.cameraId,
      sessionId: point.sessionId,
      trackerId: point.trackerId,
    };
  };
}

export function mapApiTrackPoints(points: ApiTrackPoint[], periodStart: string | Date, projection?: WorldProjection) {
  const adapt = createTrackPointAdapter(periodStart, projection);
  return points.map(adapt);
}
