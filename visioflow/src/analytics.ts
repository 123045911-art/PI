import { FLOOR, SAMPLE_SECONDS, ZONES } from './data';
import { AnalyticsSummary, Insight, IntervalStat, TrackPoint, ZoneStats } from './types';

function median(values: number[]) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2);
}

function groupByTrack(points: TrackPoint[]) {
  const tracks = new Map<number, TrackPoint[]>();
  points.forEach((point) => {
    const list = tracks.get(point.trackId) ?? [];
    list.push(point);
    tracks.set(point.trackId, list);
  });
  tracks.forEach((list) => list.sort((a, b) => a.timestamp - b.timestamp));
  return tracks;
}

function visitDurations(points: TrackPoint[]) {
  const visits = new Map<string, number[]>();
  const tracks = groupByTrack(points);

  tracks.forEach((track) => {
    let start = track[0];
    let previous = track[0];
    for (let index = 1; index <= track.length; index += 1) {
      const point = track[index];
      const continues = point && point.zoneId === previous.zoneId && point.timestamp - previous.timestamp <= SAMPLE_SECONDS * 3;
      if (continues) {
        previous = point;
        continue;
      }
      if (start.zoneId) {
        const duration = Math.max(SAMPLE_SECONDS, previous.timestamp - start.timestamp + SAMPLE_SECONDS);
        const values = visits.get(start.zoneId) ?? [];
        values.push(duration);
        visits.set(start.zoneId, values);
      }
      if (point) {
        start = point;
        previous = point;
      }
    }
  });
  return visits;
}

export const STOP_MAX_STEP = 1.35;
export const STOP_MAX_RADIUS = 1.8;
export const STOP_MIN_SECONDS = 12;

function metricDistance(a: TrackPoint, b: TrackPoint) {
  return Math.hypot(
    (a.worldX ?? a.x) - (b.worldX ?? b.x),
    (a.worldY ?? a.y) - (b.worldY ?? b.y),
  );
}

// Un tracker se considera detenido solo si permanece en la misma zona y sus
// desplazamientos consecutivos se mantienen dentro del margen de ruido. Se
// exigen al menos 12 s para evitar convertir una sola lectura estable en una
// permanencia real.
export function detectStoppedPoints(points: TrackPoint[]) {
  const stopped: TrackPoint[] = [];
  groupByTrack(points).forEach((track) => {
    let runStart = 0;
    const flush = (endIndex: number) => {
      if (endIndex < runStart) return;
      const duration = track[endIndex].timestamp - track[runStart].timestamp + SAMPLE_SECONDS;
      if (duration >= STOP_MIN_SECONDS) stopped.push(...track.slice(runStart, endIndex + 1));
    };

    for (let index = 1; index < track.length; index += 1) {
      const previous = track[index - 1];
      const point = track[index];
      const continuous = Boolean(
        point.zoneId &&
        point.zoneId === previous.zoneId &&
        point.timestamp - previous.timestamp <= SAMPLE_SECONDS * 3 &&
        metricDistance(point, previous) <= STOP_MAX_STEP &&
        metricDistance(point, track[runStart]) <= STOP_MAX_RADIUS,
      );
      if (!continuous) {
        flush(index - 1);
        runStart = index;
      }
    }
    flush(track.length - 1);
  });
  return stopped;
}

function stoppedDurations(points: TrackPoint[]) {
  return visitDurations(detectStoppedPoints(points));
}

function concurrentByZone(points: TrackPoint[], bucketSeconds = 20) {
  const buckets = new Map<number, Map<string, Set<number>>>();
  points.forEach((point) => {
    const bucket = Math.floor(point.timestamp / bucketSeconds);
    const zoneMap = buckets.get(bucket) ?? new Map<string, Set<number>>();
    const zoneId = point.zoneId ?? '__unassigned__';
    const tracks = zoneMap.get(zoneId) ?? new Set<number>();
    tracks.add(point.trackId);
    zoneMap.set(zoneId, tracks);
    buckets.set(bucket, zoneMap);
  });

  const peaks = new Map<string, number>();
  let overallPeak = 0;
  buckets.forEach((zoneMap) => {
    const allTracks = new Set<number>();
    zoneMap.forEach((tracks, zoneId) => {
      if (zoneId !== '__unassigned__') peaks.set(zoneId, Math.max(peaks.get(zoneId) ?? 0, tracks.size));
      tracks.forEach((trackId) => allTracks.add(trackId));
    });
    overallPeak = Math.max(overallPeak, allTracks.size);
  });
  return { peaks, overallPeak };
}

function findTopTransition(points: TrackPoint[]) {
  const counts = new Map<string, number>();
  groupByTrack(points).forEach((track) => {
    const sequence = track.reduce<string[]>((zones, point) => {
      if (point.zoneId && zones.at(-1) !== point.zoneId) zones.push(point.zoneId);
      return zones;
    }, []);
    for (let index = 1; index < sequence.length; index += 1) {
      const key = `${sequence[index - 1]}::${sequence[index]}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  });
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
  if (!top) return null;
  const [fromId, toId] = top[0].split('::');
  return {
    from: ZONES.find((zone) => zone.id === fromId)?.name ?? fromId,
    to: ZONES.find((zone) => zone.id === toId)?.name ?? toId,
    count: top[1],
  };
}

export function computeAnalytics(points: TrackPoint[], currentTime: number): AnalyticsSummary {
  const uniqueTracks = new Set(points.map((point) => point.trackId));
  const activeNow = new Set(
    points
      .filter((point) => point.timestamp <= currentTime && point.timestamp >= currentTime - SAMPLE_SECONDS * 4)
      .map((point) => point.trackId),
  ).size;
  const visits = visitDurations(points);
  const stopped = stoppedDurations(points);
  const { peaks, overallPeak } = concurrentByZone(points);
  const zoneStats: ZoneStats[] = ZONES.map((zone) => {
    const zonePoints = points.filter((point) => point.zoneId === zone.id);
    const durations = visits.get(zone.id) ?? [];
    const stoppedValues = stopped.get(zone.id) ?? [];
    return {
      ...zone,
      visitors: new Set(zonePoints.map((point) => point.trackId)).size,
      visits: durations.length,
      medianDwellSeconds: median(durations),
      totalDwellSeconds: durations.reduce((sum, value) => sum + value, 0),
      stoppedVisits: stoppedValues.length,
      medianStoppedSeconds: median(stoppedValues),
      totalStoppedSeconds: stoppedValues.reduce((sum, value) => sum + value, 0),
      peakConcurrent: peaks.get(zone.id) ?? 0,
    };
  });
  const allDurations = [...visits.values()].flat();
  const allStoppedDurations = [...stopped.values()].flat();
  return {
    uniqueTracks: uniqueTracks.size,
    activeNow,
    medianDwellSeconds: median(allDurations),
    medianStoppedSeconds: median(allStoppedDurations),
    peakConcurrent: overallPeak,
    zoneStats,
    topTransition: findTopTransition(points),
  };
}

export function computeIntervals(points: TrackPoint[], intervalSeconds = 900): IntervalStat[] {
  const intervals: IntervalStat[] = [];
  for (let start = 0; start < FLOOR.duration; start += intervalSeconds) {
    const end = Math.min(FLOOR.duration, start + intervalSeconds);
    const intervalPoints = points.filter((point) => point.timestamp >= start && point.timestamp < end);
    intervals.push({
      start,
      end,
      visitors: new Set(intervalPoints.map((point) => point.trackId)).size,
      peakConcurrent: concurrentByZone(intervalPoints).overallPeak,
    });
  }
  return intervals;
}

export function buildInsights(summary: AnalyticsSummary): Insight[] {
  const populated = summary.zoneStats.filter((zone) => zone.visitors > 0);
  const busiest = [...populated].sort((a, b) => b.visitors - a.visitors)[0];
  const longest = [...populated].sort((a, b) => b.medianDwellSeconds - a.medianDwellSeconds)[0];
  const mostConcurrent = [...populated].sort((a, b) => b.peakConcurrent - a.peakConcurrent)[0];
  const visitorShare = busiest && summary.uniqueTracks
    ? Math.round((busiest.visitors / summary.uniqueTracks) * 100)
    : 0;

  const insights: Insight[] = [];
  if (busiest) {
    insights.push({
      id: 'busiest', tone: 'attention', eyebrow: 'Mayor afluencia',
      title: `${busiest.name} recibió ${busiest.visitors} tracks únicos.`,
      detail: `${visitorShare}% de las personas observadas pasó por esta área durante el periodo visible.`,
      evidenceLabel: 'Participación del flujo', evidenceValue: `${visitorShare}%`,
      action: 'Revisar la distribución espacial dentro y alrededor del área.', zoneId: busiest.id,
    });
  }
  if (longest) {
    insights.push({
      id: 'dwell', tone: 'pattern', eyebrow: 'Mayor permanencia',
      title: `${longest.name} registró una mediana de ${longest.medianDwellSeconds} s.`,
      detail: `Se calcularon ${longest.visits} visitas continuas mediante cambios de área y tiempo entre puntos.`,
      evidenceLabel: 'Permanencia mediana', evidenceValue: `${longest.medianDwellSeconds} s`,
      action: 'Determinar operativamente si representa interacción o espera.', zoneId: longest.id,
    });
  }
  if (summary.topTransition) {
    insights.push({
      id: 'transition', tone: 'movement', eyebrow: 'Ruta dominante',
      title: `${summary.topTransition.from} → ${summary.topTransition.to}`,
      detail: `${summary.topTransition.count} tracks realizaron esta transición entre áreas en el periodo visible.`,
      evidenceLabel: 'Transiciones observadas', evidenceValue: String(summary.topTransition.count),
      action: 'Verificar que la ruta permanezca libre de obstáculos y contraflujos.', zoneId: mostConcurrent?.id,
    });
  }
  return insights;
}
