import assert from 'node:assert/strict';
import { computeAnalytics, detectStoppedPoints } from '../src/analytics';
import {
  ApiAlertListResponse,
  ApiTrackPoint,
  createTrackPointAdapter,
  createWorldProjection,
} from '../src/apiContract';

const periodStart = '2026-08-02T18:30:00.000Z';
const projection = createWorldProjection([[0, 0], [10, 0], [10, 6.8], [0, 6.8]]);
const adapt = createTrackPointAdapter(periodStart, projection);

const source = (sessionId: string, frameId: number, seconds: number, x: number): ApiTrackPoint => ({
  cameraId: 'cam-03',
  sessionId,
  frameId,
  trackerId: 'trk-184',
  capturedAt: new Date(Date.parse(periodStart) + seconds * 1000).toISOString(),
  imagePoint: { u: 824 + frameId, v: 591 },
  x,
  y: 4.72,
  z: 0,
  areaId: 'central',
  confidence: 0.93,
});

const firstTrack = [
  adapt(source('90c347ab-c49e-44e4-bc9f-c6aec038749d', 1, 0, 2.0)),
  adapt(source('90c347ab-c49e-44e4-bc9f-c6aec038749d', 2, 4, 2.2)),
  adapt(source('90c347ab-c49e-44e4-bc9f-c6aec038749d', 3, 8, 2.4)),
];
const restartedTrack = adapt(source('bfc0e321-461e-4efc-8713-7a179cebdd0a', 1, 4, 5.0));
const points = [...firstTrack, restartedTrack];

assert.equal(firstTrack[0].worldX, 2.0, 'metric X must be preserved');
assert.equal(firstTrack[0].worldY, 4.72, 'metric Y must be preserved');
assert.equal(firstTrack[0].imageU, 825, 'image U must be preserved');
assert.equal(firstTrack[0].imageV, 591, 'image V must be preserved');
assert.equal(firstTrack[0].x, 20, 'metric X must project to the display canvas');
assert.ok(Math.abs(firstTrack[0].y - 47.2) < 1e-9, 'metric Y must project to the display canvas');
assert.notEqual(firstTrack[0].trackId, restartedTrack.trackId, 'restarted trackers must not collide');
assert.equal(detectStoppedPoints(firstTrack).length, 3, 'stopped detection must use metric coordinates');

const summary = computeAnalytics(points, 8);
assert.equal(summary.uniqueTracks, 2);
assert.equal(summary.zoneStats.find((zone) => zone.id === 'central')?.visitors, 2);
assert.equal(summary.peakConcurrent, 2);

const alerts: ApiAlertListResponse = {
  items: [{
    id: '47920d3a-33a7-419e-a7d5-a9d30b9de93d',
    areaId: 'central',
    areaName: 'Mesa temporada',
    type: 'crowding',
    reason: 'Avisar cuando haya 20 personas o más.',
    status: 'watching',
    thresholdPeople: 20,
    scheduleMode: 'weekly',
    scheduleDay: 3,
    peopleCountSnapshot: 14,
    createdBy: 'operador',
    createdAt: '2026-08-02T18:30:14.125Z',
  }],
  summary: {
    total: 1,
    byType: { crowding: 1, low_flow: 0, unusual_dwell: 0, blocked_access: 0, manual: 0 },
    byStatus: { new: 0, watching: 1, triggered: 0, acknowledged: 0, resolved: 0 },
  },
  nextCursor: null,
};
assert.equal(alerts.items[0].type, 'crowding', 'API alert must use LocalAlert.type');
assert.equal(alerts.items[0].scheduleDay, 3, 'API alert must use LocalAlert.scheduleDay');
assert.deepEqual(Object.keys(alerts.summary.byType), [
  'crowding', 'low_flow', 'unusual_dwell', 'blocked_access', 'manual',
]);

console.log(JSON.stringify({
  coordinatePreservation: 'ok',
  displayProjection: 'ok',
  trackerSessionIsolation: 'ok',
  heatmapInput: 'ok',
  alertContract: 'ok',
  analytics: {
    uniqueTracks: summary.uniqueTracks,
    centralVisitors: summary.zoneStats.find((zone) => zone.id === 'central')?.visitors,
    peakConcurrent: summary.peakConcurrent,
  },
}, null, 2));
