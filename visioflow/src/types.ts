export type Metric = 'flow' | 'dwell' | 'stopped' | 'density';
export type ViewMode = 'moving' | 'accumulated' | 'average';
export type MapPerspective = 'isometric' | 'top';
export type HeatScaleMode = 'fixed' | 'adaptive';

export type Zone = {
  id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  kind: 'access' | 'interaction' | 'transit' | 'service';
};

export type StaticObject = {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  elevation: number;
  kind: 'wall' | 'display' | 'service';
};

export type TrackPoint = {
  trackId: number;
  timestamp: number;
  /** Display coordinates in the current 100 x 68 map canvas. */
  x: number;
  y: number;
  zoneId: string | null;
  /** Preserved source coordinates; production observations use meters. */
  worldX?: number;
  worldY?: number;
  worldZ?: number;
  /** Preserved image coordinates for frame overlays and diagnostics. */
  imageU?: number;
  imageV?: number;
  capturedAt?: string;
  cameraId?: string;
  sessionId?: string;
  trackerId?: string;
};

export type ZoneStats = Zone & {
  visitors: number;
  visits: number;
  medianDwellSeconds: number;
  totalDwellSeconds: number;
  stoppedVisits: number;
  medianStoppedSeconds: number;
  totalStoppedSeconds: number;
  peakConcurrent: number;
};

export type IntervalStat = {
  start: number;
  end: number;
  visitors: number;
  peakConcurrent: number;
};

export type AnalyticsSummary = {
  uniqueTracks: number;
  activeNow: number;
  medianDwellSeconds: number;
  medianStoppedSeconds: number;
  peakConcurrent: number;
  zoneStats: ZoneStats[];
  topTransition: { from: string; to: string; count: number } | null;
};

export type Insight = {
  id: string;
  tone: 'attention' | 'pattern' | 'movement';
  eyebrow: string;
  title: string;
  detail: string;
  evidenceLabel: string;
  evidenceValue: string;
  action: string;
  zoneId?: string;
};

export type HistoricalZoneHour = {
  week: number;
  dayIndex: number;
  dayName: string;
  hour: number;
  zoneId: string;
  uniqueTracks: number;
};

export type TimeZoneLeader = {
  label: string;
  zoneId: string;
  zoneName: string;
  averageTracks: number;
};

export type HistoricalPattern = {
  id: string;
  title: string;
  detail: string;
  evidence: string;
  zoneId?: string;
  direction: 'down' | 'up' | 'stable';
};
