import React, { useMemo } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import Svg, {
  Circle,
  Defs,
  Ellipse,
  G,
  LinearGradient,
  Path,
  Polygon,
  RadialGradient,
  Rect,
  Stop,
} from 'react-native-svg';
import { detectStoppedPoints } from '../analytics';
import { FLOOR, isBlocked, SAMPLE_SECONDS, STATIC_OBJECTS, ZONES } from '../data';
import { HeatScaleMode, MapPerspective, Metric, StaticObject, TrackPoint, ViewMode, Zone } from '../types';

type Props = {
  points: TrackPoint[];
  currentTime: number;
  metric: Metric;
  mode: ViewMode;
  scaleMode: HeatScaleMode;
  scopeSeconds: number;
  selectedZone: string | null;
  onSelectZone: (zoneId: string | null) => void;
  zoom: number;
  perspective: MapPerspective;
  showObjects: boolean;
  showTrackers: boolean;
  showTrails: boolean;
  zones?: Zone[];
  objects?: StaticObject[];
  comparison?: {
    baselinePoints: TrackPoint[];
    comparisonPoints: TrackPoint[];
    baselineLabel: string;
    comparisonLabel: string;
  } | null;
};

function activationProps(handler: (event: any) => void, label?: string) {
  return Platform.OS === 'web'
    ? { onClick: handler, 'aria-label': label, 'data-zone-selector': label }
    : { onPress: handler, ...(label ? { accessible: true, accessibilityRole: 'button', accessibilityLabel: label } : {}) };
}

type WeightedSample = { x: number; y: number; weight: number };
type SurfaceNode = {
  x: number;
  y: number;
  value: number;
  ratio: number;
  heightRatio: number;
  densityRatio: number;
  evidenceRatio: number;
  signedRatio: number;
  z: number;
};

const GRID_STEP = 3;
const TIME_BUCKET = 20;
const CONTOUR_LEVELS = [0.14, 0.28, 0.44, 0.62, 0.8];

const metricLabels: Record<Metric, string> = {
  flow: 'PERSONAS',
  dwell: 'TIEMPO DE PRESENCIA',
  stopped: 'TIEMPO DETENIDO',
  density: 'CONCURRENCIA MEDIA',
};

const FIXED_MAX: Record<Metric, Record<ViewMode, number>> = {
  flow: { moving: 55, accumulated: 320, average: 58 },
  dwell: { moving: 2400, accumulated: 16000, average: 280 },
  stopped: { moving: 1500, accumulated: 9000, average: 190 },
  density: { moving: 12, accumulated: 10, average: 10 },
};

function binKey(x: number, y: number) {
  return `${Math.round(x / 3) * 3}:${Math.round(y / 3) * 3}`;
}

function weightedSamples(points: TrackPoint[], metric: Metric, mode: ViewMode, scopeSeconds: number): WeightedSample[] {
  const bins = new Map<string, WeightedSample>();
  const add = (point: TrackPoint, weight: number) => {
    const key = binKey(point.x, point.y);
    const current = bins.get(key) ?? {
      x: Math.round(point.x / 3) * 3,
      y: Math.round(point.y / 3) * 3,
      weight: 0,
    };
    current.weight += weight;
    bins.set(key, current);
  };

  if (metric === 'flow') {
    const seen = new Set<string>();
    const hours = Math.max(1, scopeSeconds / 3600);
    points.forEach((point) => {
      const hourKey = mode === 'average' ? `${Math.floor(point.timestamp / 3600)}:` : '';
      const spatialKey = `${hourKey}${point.trackId}:${binKey(point.x, point.y)}`;
      if (seen.has(spatialKey)) return;
      seen.add(spatialKey);
      add(point, mode === 'average' ? 1 / hours : 1);
    });
  } else if (metric === 'dwell' || metric === 'stopped') {
    const source = metric === 'stopped' ? detectStoppedPoints(points) : points;
    if (mode === 'average') {
      const perTrackBin = new Map<string, WeightedSample>();
      source.forEach((point) => {
        const key = `${point.trackId}:${binKey(point.x, point.y)}`;
        const current = perTrackBin.get(key) ?? {
          x: Math.round(point.x / 3) * 3,
          y: Math.round(point.y / 3) * 3,
          weight: 0,
        };
        current.weight += SAMPLE_SECONDS;
        perTrackBin.set(key, current);
      });
      const totals = new Map<string, { sample: WeightedSample; tracks: number }>();
      perTrackBin.forEach((sample) => {
        const key = binKey(sample.x, sample.y);
        const current = totals.get(key) ?? { sample: { ...sample, weight: 0 }, tracks: 0 };
        current.sample.weight += sample.weight;
        current.tracks += 1;
        totals.set(key, current);
      });
      totals.forEach(({ sample, tracks }) => {
        sample.weight /= Math.max(1, tracks);
        bins.set(binKey(sample.x, sample.y), sample);
      });
    } else {
      source.forEach((point) => add(point, SAMPLE_SECONDS));
    }
  } else {
    const temporal = new Map<number, Map<number, TrackPoint>>();
    points.forEach((point) => {
      const bucket = Math.floor(point.timestamp / TIME_BUCKET);
      const tracks = temporal.get(bucket) ?? new Map<number, TrackPoint>();
      const previous = tracks.get(point.trackId);
      if (!previous || previous.timestamp < point.timestamp) tracks.set(point.trackId, point);
      temporal.set(bucket, tracks);
    });
    const divisor = Math.max(1, Math.ceil(scopeSeconds / TIME_BUCKET));
    temporal.forEach((tracks) => tracks.forEach((point) => add(point, 1 / divisor)));
  }
  return [...bins.values()];
}

function percentile95(values: number[]) {
  const nonZero = values.filter((value) => value > 0).sort((a, b) => a - b);
  if (!nonZero.length) return 1;
  return nonZero[Math.min(nonZero.length - 1, Math.floor(nonZero.length * 0.95))];
}

function buildSurface(points: TrackPoint[], metric: Metric, mode: ViewMode, scaleMode: HeatScaleMode, scopeSeconds: number) {
  const primary = weightedSamples(points, metric, mode, scopeSeconds);
  const presence = metric === 'dwell' ? primary : weightedSamples(points, 'dwell', mode, scopeSeconds);
  const density = metric === 'density' ? primary : weightedSamples(points, 'density', mode, scopeSeconds);
  const evidence = metric === 'flow' ? primary : weightedSamples(points, 'flow', mode, scopeSeconds);
  const baseBandwidth = metric === 'density' ? 6.8 : metric === 'dwell' || metric === 'stopped' ? 8.2 : 7.5;
  const bandwidth = baseBandwidth + (mode === 'average' ? 5.2 : mode === 'accumulated' ? 3.8 : 0);
  const denominator = 2 * bandwidth * bandwidth;
  const rows: SurfaceNode[][] = [];

  const evaluate = (samples: WeightedSample[], x: number, y: number) => samples.reduce((sum, sample) => {
    const distanceSquared = (x - sample.x) ** 2 + (y - sample.y) ** 2;
    if (distanceSquared > bandwidth * bandwidth * 9) return sum;
    return sum + Math.exp(-distanceSquared / denominator) * sample.weight;
  }, 0);

  for (let y = 0; y <= FLOOR.height; y += GRID_STEP) {
    const row: SurfaceNode[] = [];
    for (let x = 0; x <= FLOOR.width; x += GRID_STEP) {
      let value = 0;
      let presenceValue = 0;
      let densityValue = 0;
      let evidenceValue = 0;
      if (!isBlocked(x, y, 0.25)) {
        value = evaluate(primary, x, y);
        presenceValue = evaluate(presence, x, y);
        densityValue = evaluate(density, x, y);
        evidenceValue = evaluate(evidence, x, y);
      }
      row.push({
        x, y, value, ratio: 0, signedRatio: 0, z: 0,
        heightRatio: presenceValue,
        densityRatio: densityValue,
        evidenceRatio: evidenceValue,
      });
    }
    rows.push(row);
  }

  const nodes = rows.flat();
  const primaryMax = scaleMode === 'fixed' ? FIXED_MAX[metric][mode] : percentile95(nodes.map((node) => node.value));
  const presenceMax = scaleMode === 'fixed' ? FIXED_MAX.dwell[mode] : percentile95(nodes.map((node) => node.heightRatio));
  const densityMax = scaleMode === 'fixed' ? FIXED_MAX.density[mode] : percentile95(nodes.map((node) => node.densityRatio));
  const evidenceMax = scaleMode === 'fixed' ? FIXED_MAX.flow[mode] : percentile95(nodes.map((node) => node.evidenceRatio));

  rows.forEach((row) => row.forEach((node) => {
    const normalized = Math.min(1, node.value / Math.max(0.01, primaryMax));
    node.ratio = Math.pow(normalized, mode === 'moving' ? 0.84 : 0.58);
    node.signedRatio = node.ratio;
    node.heightRatio = Math.pow(Math.min(1, node.heightRatio / Math.max(0.01, presenceMax)), 0.72);
    node.densityRatio = Math.pow(Math.min(1, node.densityRatio / Math.max(0.01, densityMax)), 0.78);
    node.evidenceRatio = Math.pow(Math.min(1, node.evidenceRatio / Math.max(0.01, evidenceMax)), 0.72);
    const height = mode === 'moving' ? 11.5 : mode === 'accumulated' ? 9.4 : 8.6;
    node.z = node.heightRatio * height;
  }));
  return rows;
}

function buildDifferenceSurface(baselinePoints: TrackPoint[], comparisonPoints: TrackPoint[], scaleMode: HeatScaleMode) {
  const baselineTotal = Math.max(1, new Set(baselinePoints.map((point) => point.trackId)).size);
  const comparisonTotal = Math.max(1, new Set(comparisonPoints.map((point) => point.trackId)).size);
  const baseline = weightedSamples(baselinePoints, 'flow', 'moving', 3600).map((sample) => ({ ...sample, weight: (sample.weight / baselineTotal) * 100 }));
  const comparison = weightedSamples(comparisonPoints, 'flow', 'moving', 3600).map((sample) => ({ ...sample, weight: (sample.weight / comparisonTotal) * 100 }));
  const bandwidth = 9.5;
  const denominator = 2 * bandwidth * bandwidth;
  const rows: SurfaceNode[][] = [];
  let maxAbsolute = 0;

  const evaluate = (samples: WeightedSample[], x: number, y: number) => samples.reduce((sum, sample) => {
    const distanceSquared = (x - sample.x) ** 2 + (y - sample.y) ** 2;
    if (distanceSquared > bandwidth * bandwidth * 9) return sum;
    return sum + Math.exp(-distanceSquared / denominator) * sample.weight;
  }, 0);

  for (let y = 0; y <= FLOOR.height; y += GRID_STEP) {
    const row: SurfaceNode[] = [];
    for (let x = 0; x <= FLOOR.width; x += GRID_STEP) {
      const value = isBlocked(x, y, 0.25) ? 0 : evaluate(comparison, x, y) - evaluate(baseline, x, y);
      maxAbsolute = Math.max(maxAbsolute, Math.abs(value));
      row.push({ x, y, value, ratio: 0, heightRatio: 0, densityRatio: 0, evidenceRatio: 0, signedRatio: 0, z: 0 });
    }
    rows.push(row);
  }

  const adaptiveMax = percentile95(rows.flat().map((node) => Math.abs(node.value)));
  const scaleMax = scaleMode === 'fixed' ? 22 : Math.max(0.01, adaptiveMax || maxAbsolute);
  rows.forEach((row) => row.forEach((node) => {
    const signed = Math.max(-1, Math.min(1, node.value / scaleMax));
    node.ratio = Math.pow(Math.abs(signed), 0.68);
    node.signedRatio = Math.sign(signed) * node.ratio;
    node.heightRatio = node.ratio;
    node.densityRatio = node.ratio;
    node.evidenceRatio = node.ratio;
    node.z = Math.pow(node.ratio, 0.76) * 9.8;
  }));
  return rows;
}

function createProject(perspective: MapPerspective) {
  if (perspective === 'top') {
    return (x: number, y: number, z = 0) => ({ x: 6 + x * 0.9, y: 7 + y * 0.68 - z * 0.78 });
  }
  return (x: number, y: number, z = 0) => ({ x: 4 + x * 0.72 + y * 0.22, y: 18 + y * 0.45 - z * 1.08 });
}

function pointsString(points: { x: number; y: number }[]) {
  return points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');
}

function heatColor(ratio: number) {
  if (ratio > 0.92) return '#cf2718';
  if (ratio > 0.82) return '#e83a1d';
  if (ratio > 0.72) return '#f65021';
  if (ratio > 0.61) return '#ff6924';
  if (ratio > 0.5) return '#ff8429';
  if (ratio > 0.39) return '#ffa237';
  if (ratio > 0.28) return '#ffc04a';
  if (ratio > 0.18) return '#ffd875';
  if (ratio > 0.09) return '#ffedb2';
  return '#fff8e8';
}

function differenceColor(signedRatio: number) {
  if (signedRatio < -0.72) return '#1759d1';
  if (signedRatio < -0.45) return '#3f7fe2';
  if (signedRatio < -0.2) return '#82adeb';
  if (signedRatio < -0.06) return '#c6d9ef';
  if (signedRatio < 0.06) return '#f5f2eb';
  if (signedRatio < 0.22) return '#ffd6b8';
  if (signedRatio < 0.48) return '#ff9a54';
  if (signedRatio < 0.74) return '#ff662d';
  return '#e93e1e';
}

function findHeatSpots(surface: SurfaceNode[][]) {
  const candidates: SurfaceNode[] = [];
  for (let row = 1; row < surface.length - 1; row += 1) {
    for (let column = 1; column < surface[row].length - 1; column += 1) {
      const node = surface[row][column];
      if (node.ratio < 0.3 || isBlocked(node.x, node.y, 0.3)) continue;
      const neighbors = [
        surface[row - 1][column], surface[row + 1][column],
        surface[row][column - 1], surface[row][column + 1],
      ];
      if (neighbors.every((neighbor) => node.ratio >= neighbor.ratio)) candidates.push(node);
    }
  }

  const selected: SurfaceNode[] = [];
  candidates.sort((a, b) => b.ratio - a.ratio).forEach((candidate) => {
    if (selected.length >= 10) return;
    const separated = selected.every((item) => Math.hypot(item.x - candidate.x, item.y - candidate.y) > 10);
    if (separated) selected.push(candidate);
  });
  return selected;
}

function animatedHeight(node: SurfaceNode, currentTime: number, mode: ViewMode) {
  if (mode !== 'moving' || node.heightRatio < 0.03) return node.z;
  const phase = currentTime / 280 + node.x * 0.19 + node.y * 0.14;
  const wave = (Math.sin(phase) + Math.sin(phase * 0.56 + node.x * 0.12) * 0.55)
    * Math.pow(node.heightRatio, 0.55) * 0.95;
  return Math.max(0, node.z + wave);
}

function contourIntersection(a: SurfaceNode, b: SurfaceNode, level: number) {
  const aSide = a.ratio >= level;
  const bSide = b.ratio >= level;
  if (aSide === bSide) return null;
  const span = b.ratio - a.ratio;
  const amount = span === 0 ? 0.5 : (level - a.ratio) / span;
  return {
    x: a.x + (b.x - a.x) * amount,
    y: a.y + (b.y - a.y) * amount,
    z: a.z + (b.z - a.z) * amount + 0.16,
  };
}

function currentTrackers(points: TrackPoint[], time: number) {
  const latest = new Map<number, TrackPoint>();
  points.forEach((point) => {
    if (point.timestamp > time || point.timestamp < time - SAMPLE_SECONDS * 4) return;
    const previous = latest.get(point.trackId);
    if (!previous || previous.timestamp < point.timestamp) latest.set(point.trackId, point);
  });
  return [...latest.values()].slice(0, 140);
}

function recentTrails(points: TrackPoint[], time: number) {
  const trails = new Map<number, TrackPoint[]>();
  points.forEach((point) => {
    if (point.timestamp > time || point.timestamp < time - 160) return;
    const trail = trails.get(point.trackId) ?? [];
    trail.push(point);
    trails.set(point.trackId, trail);
  });
  return [...trails.entries()]
    .map(([trackId, trail]) => ({ trackId, trail: trail.sort((a, b) => a.timestamp - b.timestamp) }))
    .filter(({ trail }) => trail.length >= 4)
    .sort((a, b) => b.trail.at(-1)!.timestamp - a.trail.at(-1)!.timestamp)
    .slice(0, 18);
}

export function FlowMap({
  points,
  currentTime,
  metric,
  mode,
  scaleMode,
  scopeSeconds,
  selectedZone,
  onSelectZone,
  zoom,
  perspective,
  showObjects,
  showTrackers,
  showTrails,
  zones,
  objects,
  comparison,
}: Props) {
  const activeZones = zones ?? ZONES;
  const activeObjects = showObjects ? (objects ?? STATIC_OBJECTS) : [];
  const surface = useMemo(
    () => comparison
      ? buildDifferenceSurface(comparison.baselinePoints, comparison.comparisonPoints, scaleMode)
      : buildSurface(points, metric, mode, scaleMode, scopeSeconds),
    [comparison, points, metric, mode, scaleMode, scopeSeconds],
  );
  const heatSpots = useMemo(() => findHeatSpots(surface), [surface]);
  const trackers = useMemo(() => currentTrackers(points, currentTime), [points, currentTime]);
  const trails = useMemo(() => recentTrails(points, currentTime), [points, currentTime]);
  const project = useMemo(() => createProject(perspective), [perspective]);
  const viewWidth = 105 / zoom;
  const viewHeight = 54 / zoom;
  const viewX = (105 - viewWidth) / 2;
  const viewY = 4 + (54 - viewHeight) / 2;

  const floor = [project(0, 0), project(FLOOR.width, 0), project(FLOOR.width, FLOOR.height), project(0, FLOOR.height)];
  const surfaceCells: { key: string; ratio: number; evidenceRatio: number; signedRatio: number; depth: number; polygon: string }[] = [];
  const contourSegments: { key: string; path: string; level: number }[] = [];
  for (let rowIndex = 0; rowIndex < surface.length - 1; rowIndex += 1) {
    for (let columnIndex = 0; columnIndex < surface[rowIndex].length - 1; columnIndex += 1) {
      const nodes = [
        surface[rowIndex][columnIndex],
        surface[rowIndex][columnIndex + 1],
        surface[rowIndex + 1][columnIndex + 1],
        surface[rowIndex + 1][columnIndex],
      ].map((node) => ({ ...node, z: comparison ? node.z : animatedHeight(node, currentTime, mode) }));
      const centerX = nodes.reduce((sum, node) => sum + node.x, 0) / 4;
      const centerY = nodes.reduce((sum, node) => sum + node.y, 0) / 4;
      const ratio = nodes.reduce((sum, node) => sum + node.ratio, 0) / 4;
      const evidenceRatio = nodes.reduce((sum, node) => sum + node.evidenceRatio, 0) / 4;
      const signedRatio = nodes.reduce((sum, node) => sum + node.signedRatio, 0) / 4;
      if (ratio < 0.018 || isBlocked(centerX, centerY, 0.4)) continue;
      surfaceCells.push({
        key: `${rowIndex}-${columnIndex}`,
        ratio,
        evidenceRatio,
        signedRatio,
        depth: centerY,
        polygon: pointsString(nodes.map((node) => project(node.x, node.y, node.z))),
      });

      const densityNodes = nodes.map((node) => ({ ...node, ratio: node.densityRatio, z: node.z + 0.12 }));
      CONTOUR_LEVELS.forEach((level) => {
        const intersections = [
          contourIntersection(densityNodes[0], densityNodes[1], level),
          contourIntersection(densityNodes[1], densityNodes[2], level),
          contourIntersection(densityNodes[2], densityNodes[3], level),
          contourIntersection(densityNodes[3], densityNodes[0], level),
        ].filter((point): point is { x: number; y: number; z: number } => point !== null);
        for (let index = 0; index + 1 < intersections.length; index += 2) {
          const start = project(intersections[index].x, intersections[index].y, intersections[index].z);
          const end = project(intersections[index + 1].x, intersections[index + 1].y, intersections[index + 1].z);
          contourSegments.push({
            key: `contour-${rowIndex}-${columnIndex}-${level}-${index}`,
            level,
            path: `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} L ${end.x.toFixed(2)} ${end.y.toFixed(2)}`,
          });
        }
      });
    }
  }
  surfaceCells.sort((a, b) => a.depth - b.depth);

  return (
    <View style={styles.shell}>
      <View style={styles.captionRow}>
        <View style={styles.liveGroup}>
          <View style={styles.liveDot} />
          <Text style={styles.caption}>
            {comparison
              ? `DISTRIBUCIÓN · ${comparison.comparisonLabel} VS ${comparison.baselineLabel}`
              : mode === 'moving'
                ? 'VENTANA MÓVIL'
                : mode === 'accumulated' && metric === 'density'
                  ? 'MEDIA HASTA AHORA'
                  : mode === 'accumulated'
                    ? 'ACUMULADO HASTA AHORA'
                    : 'PROMEDIO GENERAL'}
          </Text>
        </View>
        <Text style={styles.coordinate}>ZONA DE EXHIBICIÓN · {metricLabels[metric]}</Text>
      </View>

      <Svg
        width="100%"
        height="100%"
        viewBox={`${viewX} ${viewY} ${viewWidth} ${viewHeight}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <Defs>
          <LinearGradient id="floor" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor="#ffffff" />
            <Stop offset="1" stopColor="#f1f2ef" />
          </LinearGradient>
          <LinearGradient id="objectTop" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#ffffff" />
            <Stop offset="1" stopColor="#ecece8" />
          </LinearGradient>
          <RadialGradient id="heatGlow" cx="50%" cy="50%" rx="50%" ry="50%">
            <Stop offset="0%" stopColor="#cf2718" stopOpacity="0.99" />
            <Stop offset="24%" stopColor="#f65021" stopOpacity="0.96" />
            <Stop offset="52%" stopColor="#ff8429" stopOpacity="0.82" />
            <Stop offset="76%" stopColor="#ffc04a" stopOpacity="0.5" />
            <Stop offset="100%" stopColor="#fff0b8" stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="warmGlow" cx="50%" cy="50%" rx="50%" ry="50%">
            <Stop offset="0%" stopColor="#ff6a24" stopOpacity="0.9" />
            <Stop offset="38%" stopColor="#ff9e32" stopOpacity="0.78" />
            <Stop offset="72%" stopColor="#ffd75d" stopOpacity="0.42" />
            <Stop offset="100%" stopColor="#fff3c9" stopOpacity="0" />
          </RadialGradient>
          <RadialGradient id="negativeGlow" cx="50%" cy="50%" rx="50%" ry="50%">
            <Stop offset="0%" stopColor="#1759d1" stopOpacity="0.92" />
            <Stop offset="45%" stopColor="#4f8be1" stopOpacity="0.74" />
            <Stop offset="78%" stopColor="#a8c5eb" stopOpacity="0.36" />
            <Stop offset="100%" stopColor="#dce8f5" stopOpacity="0" />
          </RadialGradient>
        </Defs>

        <Polygon points={pointsString(floor)} fill="url(#floor)" stroke="#c8cbc7" strokeWidth="0.46" />

        {Array.from({ length: 11 }, (_, index) => {
          const start = project(index * 10, 0);
          const end = project(index * 10, FLOOR.height);
          return <Path key={`grid-x-${index}`} d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`} stroke="#aeb4af" strokeOpacity="0.2" strokeWidth="0.16" />;
        })}
        {Array.from({ length: 8 }, (_, index) => {
          const start = project(0, index * 10);
          const end = project(FLOOR.width, index * 10);
          return <Path key={`grid-y-${index}`} d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`} stroke="#aeb4af" strokeOpacity="0.2" strokeWidth="0.16" />;
        })}

        {activeZones.map((zone) => {
          const corners = [
            project(zone.x, zone.y),
            project(zone.x + zone.width, zone.y),
            project(zone.x + zone.width, zone.y + zone.height),
            project(zone.x, zone.y + zone.height),
          ];
          const selected = zone.id === selectedZone;
          return (
            <G key={zone.id} {...activationProps((event) => { onSelectZone(zone.id); event.stopPropagation?.(); }) as any}>
              <Polygon
                points={pointsString(corners)}
                fill={selected ? '#e9f7ed' : '#ffffff'}
                fillOpacity={selected ? 0.34 : 0.03}
                stroke={selected ? '#20a755' : '#9da7a0'}
                strokeOpacity={selected ? 1 : 0.66}
                strokeWidth={selected ? 0.72 : 0.3}
                strokeDasharray={selected ? undefined : '1.1 0.85'}
              />
            </G>
          );
        })}

        <G opacity={mode === 'moving' ? 0.86 : 0.78}>
          {heatSpots.map((spot, index) => {
            const center = project(spot.x, spot.y, 0.18);
            const radius = 7.5 + spot.ratio * (mode === 'moving' ? 6 : 9);
            return (
              <Ellipse
                key={`glow-${index}`}
                cx={center.x}
                cy={center.y}
                rx={radius}
                ry={radius * (perspective === 'isometric' ? 0.48 : 0.7)}
                fill={comparison && spot.signedRatio < 0 ? 'url(#negativeGlow)' : spot.ratio > 0.63 ? 'url(#heatGlow)' : 'url(#warmGlow)'}
              />
            );
          })}
        </G>

        <G opacity={mode === 'moving' ? 0.78 : 0.62}>
          {surfaceCells.map((cell) => (
            <Polygon
              key={cell.key}
              points={cell.polygon}
              fill={comparison ? differenceColor(cell.signedRatio) : heatColor(cell.ratio)}
              fillOpacity={0.14 + cell.evidenceRatio * 0.22 + cell.ratio * 0.34}
              stroke="transparent"
            />
          ))}
        </G>

        <G opacity="0.78">
          {contourSegments.map((segment) => (
            <Path
              key={segment.key}
              d={segment.path}
              fill="none"
              stroke="#ffffff"
              strokeOpacity={0.5 + segment.level * 0.45}
              strokeWidth={segment.level > 0.7 ? 0.34 : 0.24}
            />
          ))}
        </G>

        {!comparison && showTrails && mode === 'moving' && trails.map(({ trackId, trail }) => {
          const d = trail.map((point, index) => {
            const projected = project(point.x, point.y, 0.7);
            return `${index === 0 ? 'M' : 'L'} ${projected.x.toFixed(2)} ${projected.y.toFixed(2)}`;
          }).join(' ');
          return <Path key={`trail-${trackId}`} d={d} fill="none" stroke="#ffcc45" strokeOpacity="0.68" strokeWidth="0.42" />;
        })}

        {activeObjects.map((object) => {
          const base = [
            project(object.x, object.y),
            project(object.x + object.width, object.y),
            project(object.x + object.width, object.y + object.height),
            project(object.x, object.y + object.height),
          ];
          const top = [
            project(object.x, object.y, object.elevation),
            project(object.x + object.width, object.y, object.elevation),
            project(object.x + object.width, object.y + object.height, object.elevation),
            project(object.x, object.y + object.height, object.elevation),
          ];
          const isWall = object.kind === 'wall';
          const shadow = base.map((point) => ({ x: point.x + 0.9, y: point.y + 1.1 }));
          const railStart = project(object.x + Math.min(1, object.width / 4), object.y + object.height / 2, object.elevation + 0.25);
          const railEnd = project(object.x + object.width - Math.min(1, object.width / 4), object.y + object.height / 2, object.elevation + 0.25);
          return (
            <G key={object.id}>
              <Polygon points={pointsString(shadow)} fill="#2d3431" fillOpacity="0.16" />
              <Polygon points={pointsString([base[1], base[2], top[2], top[1]])} fill={isWall ? '#c8cbc7' : '#d7d9d5'} stroke="#8d938e" strokeWidth="0.3" />
              <Polygon points={pointsString([base[2], base[3], top[3], top[2]])} fill={isWall ? '#dcdfda' : '#e5e6e2'} stroke="#929793" strokeWidth="0.3" />
              <Polygon points={pointsString(top)} fill="url(#objectTop)" stroke="#737a75" strokeWidth="0.38" />
              {!isWall && <Path d={`M ${railStart.x} ${railStart.y} L ${railEnd.x} ${railEnd.y}`} stroke="#777d78" strokeWidth="0.32" />}
            </G>
          );
        })}

        {!comparison && showTrackers && mode === 'moving' && trackers.map((point) => {
          const projected = project(point.x, point.y, 0.9);
          return (
            <G key={point.trackId}>
              <Circle cx={projected.x} cy={projected.y} r="1.05" fill="#ffffff" fillOpacity="0.92" />
              <Circle cx={projected.x} cy={projected.y} r="0.58" fill="#ff5526" />
            </G>
          );
        })}

        {activeZones.map((zone) => {
          const corners = [
            project(zone.x, zone.y, 0.25),
            project(zone.x + zone.width, zone.y, 0.25),
            project(zone.x + zone.width, zone.y + zone.height, 0.25),
            project(zone.x, zone.y + zone.height, 0.25),
          ];
          const selected = zone.id === selectedZone;
          return (
            <Polygon
              key={`zone-outline-${zone.id}`}
              points={pointsString(corners)}
              fill="transparent"
              stroke={selected ? '#187f43' : '#68716b'}
              strokeOpacity={selected ? 1 : 0.68}
              strokeWidth={selected ? 0.72 : 0.3}
              strokeDasharray={selected ? undefined : '1.1 0.85'}
              {...activationProps((event) => { onSelectZone(zone.id); event.stopPropagation?.(); }, `Ver datos de ${zone.name}`) as any}
            />
          );
        })}

      </Svg>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.zoneSelector}
        contentContainerStyle={styles.zoneSelectorContent}
      >
        {activeZones.map((zone) => {
          const selected = zone.id === selectedZone;
          return (
            <Pressable
              accessibilityLabel={`Seleccionar ${zone.name}`}
              key={`zone-selector-${zone.id}`}
              onPress={() => onSelectZone(zone.id)}
              style={[styles.zoneSelectorButton, selected && styles.zoneSelectorButtonActive]}
            >
              <Text style={[styles.zoneSelectorText, selected && styles.zoneSelectorTextActive]}>{zone.name}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <View style={styles.layerLegend}>
        <View style={styles.legendItem}><View style={[styles.legendSymbol, styles.areaSymbol]} /><Text style={styles.legendText}>Área</Text></View>
        <View style={styles.legendItem}><View style={[styles.legendSymbol, styles.objectSymbol]} /><Text style={styles.legendText}>Estructura fija</Text></View>
        <View style={styles.legendItem}><View style={[styles.legendSymbol, styles.personSymbol]} /><Text style={styles.legendText}>Persona</Text></View>
      </View>

      <View style={styles.heatLegend}>
        <Text style={styles.scaleModeText}>{scaleMode === 'fixed' ? 'FIJA' : 'P95'}</Text>
        <Text style={styles.legendText}>{comparison ? 'Menos' : 'Baja'}</Text>
        <View style={styles.legendBar}>
          {(comparison
            ? ['#1759d1', '#4f8be1', '#a8c5eb', '#f5f2eb', '#ffd6b8', '#ff9a54', '#ff662d', '#e93e1e']
            : ['#fff8e8', '#ffedb2', '#ffd875', '#ffc04a', '#ffa237', '#ff8429', '#f65021', '#cf2718']
          ).map((color) => <View key={color} style={[styles.segment, { backgroundColor: color }]} />)}
        </View>
        <Text style={styles.legendText}>{comparison ? 'Más' : 'Alta'}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: { flex: 1, minHeight: 330, backgroundColor: '#fafdfe', borderRadius: 22, overflow: 'hidden' },
  captionRow: { position: 'absolute', top: 12, left: 14, right: 14, zIndex: 4, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  liveGroup: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'rgba(255,255,255,0.9)', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 6 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#ff5526' },
  caption: { color: '#53666b', fontSize: 9, fontWeight: '900', letterSpacing: 0.65 },
  coordinate: { color: '#52676c', fontSize: 8, fontWeight: '800', backgroundColor: 'rgba(255,255,255,0.9)', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 5 },
  zoneSelector: { position: 'absolute', top: 48, left: 12, right: 12, zIndex: 5, maxHeight: 32 },
  zoneSelectorContent: { gap: 5, paddingRight: 10 },
  zoneSelectorButton: { minHeight: 27, justifyContent: 'center', paddingHorizontal: 8, borderRadius: 9, borderWidth: 1, borderColor: '#d6e2e4', backgroundColor: 'rgba(255,255,255,0.94)' },
  zoneSelectorButtonActive: { borderColor: '#ff5a2a', backgroundColor: '#ff5a2a' },
  zoneSelectorText: { color: '#51676c', fontSize: 7.5, fontWeight: '900' },
  zoneSelectorTextActive: { color: '#ffffff' },
  layerLegend: { position: 'absolute', left: 12, bottom: 11, flexDirection: 'row', gap: 9, backgroundColor: 'rgba(255,255,255,0.94)', borderColor: '#dfe7e9', borderWidth: 1, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 6 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendSymbol: { width: 8, height: 8 },
  areaSymbol: { borderWidth: 1, borderStyle: 'dashed', borderColor: '#4d9da7', backgroundColor: '#d9f2f1' },
  objectSymbol: { backgroundColor: '#d2dade', borderWidth: 1, borderColor: '#aeb9bd' },
  personSymbol: { borderRadius: 4, backgroundColor: '#ff5526' },
  heatLegend: { position: 'absolute', right: 12, bottom: 11, flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: 'rgba(255,255,255,0.94)', borderColor: '#dfe7e9', borderWidth: 1, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 6 },
  legendText: { color: '#68777b', fontSize: 8, fontWeight: '700' },
  scaleModeText: { color: '#26383d', fontSize: 6.5, fontWeight: '900', letterSpacing: 0.35 },
  legendBar: { width: 68, height: 7, borderRadius: 6, overflow: 'hidden', flexDirection: 'row' },
  segment: { flex: 1 },
});
