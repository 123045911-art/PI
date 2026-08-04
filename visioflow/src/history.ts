import { trackPointsForDay, ZONES } from './data';
import { HistoricalPattern, HistoricalZoneHour, TimeZoneLeader } from './types';

export const HISTORY_WEEKS = 8;
export const DAY_NAMES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

const zoneBase: Record<string, number> = {
  access: 54,
  launch: 36,
  central: 44,
  premium: 34,
  service: 25,
  north: 21,
};

const hourCurve = [0.62, 0.78, 0.94, 1.1, 1.25, 1.18, 0.98, 0.76];
const dayCurve = [0.84, 0.9, 0.98, 1.03, 1.16, 1.3, 0.78];

function deterministicNoise(week: number, day: number, hour: number, zoneIndex: number) {
  const value = Math.sin((week + 1) * 17.13 + day * 9.71 + hour * 3.17 + zoneIndex * 5.41);
  return 1 + value * 0.075;
}

function zoneHourFactor(zoneId: string, hour: number) {
  if (zoneId === 'launch' && hour <= 10) return 1.48;
  if (zoneId === 'central' && hour >= 11 && hour <= 12) return 1.35;
  if (zoneId === 'premium' && hour >= 13 && hour <= 14) return 1.75;
  if (zoneId === 'service' && hour >= 14) return 2.1;
  if (zoneId === 'north' && hour >= 15) return 1.65;
  return 1;
}

export function generateHistoricalZoneHours(): HistoricalZoneHour[] {
  const rows: HistoricalZoneHour[] = [];
  for (let week = 0; week < HISTORY_WEEKS; week += 1) {
    for (let dayIndex = 0; dayIndex < DAY_NAMES.length; dayIndex += 1) {
      for (let hour = 8; hour < 16; hour += 1) {
        ZONES.forEach((zone, zoneIndex) => {
          let factor = dayCurve[dayIndex] * hourCurve[hour - 8] * zoneHourFactor(zone.id, hour);
          factor *= 0.95 + week * 0.014;

          // Anomalía deliberada y trazable: el rack de vestidos pierde afluencia
          // los jueves de las dos semanas más recientes.
          if (zone.id === 'premium' && dayIndex === 3 && week >= 6) {
            factor *= week === 6 ? 0.7 : 0.55;
          }

          // El área central de los sábados permanece deliberadamente estable.
          if (zone.id === 'central' && dayIndex === 5) {
            factor = 1.22 * hourCurve[hour - 8] * zoneHourFactor(zone.id, hour);
          }

          rows.push({
            week,
            dayIndex,
            dayName: DAY_NAMES[dayIndex],
            hour,
            zoneId: zone.id,
            uniqueTracks: Math.max(1, Math.round(zoneBase[zone.id] * factor * deterministicNoise(week, dayIndex, hour, zoneIndex))),
          });
        });
      }
    }
  }
  return rows;
}

export const HISTORICAL_ZONE_HOURS = generateHistoricalZoneHours();

function zoneHourCounts(zoneId: string, dayIndex: number) {
  const points = trackPointsForDay(dayIndex);
  return Array.from({ length: 8 }, (_, index) => {
    const start = index * 3600;
    const people = new Set(points
      .filter((point) => point.zoneId === zoneId && point.timestamp >= start && point.timestamp < start + 3600)
      .map((point) => point.trackId)).size;
    return { hour: index + 8, people };
  });
}

export function getZoneDayProfile(zoneId: string, dayIndex: number) {
  let cumulative = 0;
  const hours = zoneHourCounts(zoneId, dayIndex)
    .map((row) => {
      cumulative += row.people;
      return { ...row, cumulative };
    });
  const total = hours.reduce((sum, row) => sum + row.people, 0);
  const peak = [...hours].sort((a, b) => b.people - a.people)[0] ?? { hour: 8, people: 0, cumulative: 0 };
  const previousDayIndex = (dayIndex + 6) % 7;
  const previousTotal = zoneHourCounts(zoneId, previousDayIndex).reduce((sum, row) => sum + row.people, 0);
  const changeVsPreviousDay = previousTotal ? Math.round(((total - previousTotal) / previousTotal) * 100) : 0;
  return { hours, total, peak, changeVsPreviousDay };
}

export function computeTimeZoneLeaders(
  rows: HistoricalZoneHour[],
  dayFilter: number | null,
  grouping: 'hour' | 'range',
): TimeZoneLeader[] {
  const filtered = dayFilter === null ? rows : rows.filter((row) => row.dayIndex === dayFilter);
  const dailyTotals = new Map<string, { zoneId: string; period: number; total: number }>();

  filtered.forEach((row) => {
    const period = grouping === 'hour' ? row.hour : Math.floor((row.hour - 8) / 2) * 2 + 8;
    const key = `${row.week}:${row.dayIndex}:${period}:${row.zoneId}`;
    const current = dailyTotals.get(key) ?? { zoneId: row.zoneId, period, total: 0 };
    current.total += row.uniqueTracks;
    dailyTotals.set(key, current);
  });

  const aggregates = new Map<string, { zoneId: string; period: number; sum: number; count: number }>();
  dailyTotals.forEach((item) => {
    const key = `${item.period}:${item.zoneId}`;
    const current = aggregates.get(key) ?? { zoneId: item.zoneId, period: item.period, sum: 0, count: 0 };
    current.sum += item.total;
    current.count += 1;
    aggregates.set(key, current);
  });

  const periods = grouping === 'hour' ? [8, 9, 10, 11, 12, 13, 14, 15] : [8, 10, 12, 14];
  return periods.map((period) => {
    const candidates = [...aggregates.values()]
      .filter((item) => item.period === period && item.zoneId !== 'access')
      .map((item) => ({ ...item, average: Math.round(item.sum / Math.max(1, item.count)) }))
      .sort((a, b) => b.average - a.average);
    const winner = candidates[0];
    return {
      label: grouping === 'hour' ? `${String(period).padStart(2, '0')}:00` : `${String(period).padStart(2, '0')}–${String(period + 2).padStart(2, '0')} h`,
      zoneId: winner?.zoneId ?? '',
      zoneName: ZONES.find((zone) => zone.id === winner?.zoneId)?.name ?? 'Sin datos',
      averageTracks: winner?.average ?? 0,
    };
  });
}

export function buildHistoricalPatterns(rows: HistoricalZoneHour[]): HistoricalPattern[] {
  const weekDayZone = new Map<string, number>();
  rows.forEach((row) => {
    const key = `${row.week}:${row.dayIndex}:${row.zoneId}`;
    weekDayZone.set(key, (weekDayZone.get(key) ?? 0) + row.uniqueTracks);
  });

  const comparisons: { zoneId: string; dayIndex: number; baseline: number; recent: number; delta: number }[] = [];
  ZONES.forEach((zone) => DAY_NAMES.forEach((_, dayIndex) => {
    const baselineValues = [0, 1, 2, 3, 4, 5].map((week) => weekDayZone.get(`${week}:${dayIndex}:${zone.id}`) ?? 0);
    const recentValues = [6, 7].map((week) => weekDayZone.get(`${week}:${dayIndex}:${zone.id}`) ?? 0);
    const baseline = baselineValues.reduce((sum, value) => sum + value, 0) / baselineValues.length;
    const recent = recentValues.reduce((sum, value) => sum + value, 0) / recentValues.length;
    comparisons.push({ zoneId: zone.id, dayIndex, baseline, recent, delta: baseline ? ((recent - baseline) / baseline) * 100 : 0 });
  }));

  const decline = [...comparisons].sort((a, b) => a.delta - b.delta)[0];
  const declineZone = ZONES.find((zone) => zone.id === decline.zoneId)!;

  const stability = comparisons
    .map((item) => {
      const values = Array.from({ length: HISTORY_WEEKS }, (_, week) => weekDayZone.get(`${week}:${item.dayIndex}:${item.zoneId}`) ?? 0);
      const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
      const deviation = Math.sqrt(values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length);
      return { ...item, variation: mean ? (deviation / mean) * 100 : 100 };
    })
    .sort((a, b) => a.variation - b.variation)[0];
  const stableZone = ZONES.find((zone) => zone.id === stability.zoneId)!;

  const weeklyTotals = Array.from({ length: HISTORY_WEEKS }, (_, week) => rows
    .filter((row) => row.week === week)
    .reduce((sum, row) => sum + row.uniqueTracks, 0));
  const earlyAverage = weeklyTotals.slice(0, 3).reduce((sum, value) => sum + value, 0) / 3;
  const latest = weeklyTotals.at(-1) ?? 0;
  const weekDelta = earlyAverage ? Math.round(((latest - earlyAverage) / earlyAverage) * 100) : 0;

  return [
    {
      id: 'historical-decline', direction: 'down', zoneId: decline.zoneId,
      title: `${DAY_NAMES[decline.dayIndex]}: bajó la afluencia en ${declineZone.name}.`,
      detail: `Las últimas 2 semanas se comparan contra el promedio de las 6 anteriores.`,
      evidence: `${Math.round(decline.delta)}%`,
    },
    {
      id: 'historical-stable', direction: 'stable', zoneId: stability.zoneId,
      title: `${stableZone.name} se mantiene estable los ${DAY_NAMES[stability.dayIndex]}.`,
      detail: `Es el patrón zona-día con menor variación entre las 8 semanas.`,
      evidence: `±${Math.round(stability.variation)}%`,
    },
    {
      id: 'historical-week', direction: weekDelta >= 0 ? 'up' : 'down',
      title: `La semana más reciente ${weekDelta >= 0 ? 'superó' : 'quedó debajo de'} la referencia inicial.`,
      detail: `Comparación contra el promedio de las primeras 3 semanas de la simulación.`,
      evidence: `${weekDelta >= 0 ? '+' : ''}${weekDelta}%`,
    },
  ];
}
