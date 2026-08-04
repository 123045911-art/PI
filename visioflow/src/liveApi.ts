import { Platform } from 'react-native';
import type { ApiAreaState, ApiBootstrap, ApiTrackPoint } from './apiContract';
import type { LocalAlert } from './localStore';

export type ApiSiteOption = {
  siteId: string;
  name: string;
  mode: 'live' | 'simulated';
};

const defaultBaseUrl = Platform.OS === 'android'
  ? 'http://10.0.2.2:5000'
  : 'http://127.0.0.1:5000';

export const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL || defaultBaseUrl).replace(/\/$/, '');

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}

async function sendJson<T>(path: string, method: 'POST' | 'PATCH' | 'DELETE', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return response.json() as Promise<T>;
}

export async function listSites() {
  const response = await getJson<{ items: ApiSiteOption[] }>('/api/v1/sites');
  return response.items;
}

export function loadBootstrap(siteId: string) {
  return getJson<ApiBootstrap>(`/api/v1/sites/${encodeURIComponent(siteId)}/bootstrap`);
}

export function loadTrackPoints(siteId: string, cursor?: string | null) {
  const query = new URLSearchParams({ limit: cursor ? '2000' : '4000' });
  if (cursor) query.set('cursor', cursor);
  return getJson<{ items: ApiTrackPoint[]; nextCursor: string | null }>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/track-points?${query.toString()}`,
  );
}

export async function loadAreaState(siteId: string) {
  const response = await getJson<{ items: ApiAreaState[] }>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/area-state`,
  );
  return response.items;
}

export async function loadAlerts(siteId: string) {
  const response = await getJson<{ items: LocalAlert[] }>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/alerts`,
  );
  return response.items;
}

export async function createAlert(siteId: string, alert: LocalAlert) {
  const response = await sendJson<{ item: LocalAlert }>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/alerts`, 'POST', alert,
  );
  return response.item;
}

export async function updateAlert(siteId: string, alert: LocalAlert) {
  const response = await sendJson<{ item: LocalAlert }>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/alerts/${encodeURIComponent(alert.id)}`,
    'PATCH', alert,
  );
  return response.item;
}

export function deleteAlert(siteId: string, alertId: string) {
  return sendJson<{ ok: boolean }>(
    `/api/v1/sites/${encodeURIComponent(siteId)}/alerts/${encodeURIComponent(alertId)}`,
    'DELETE',
  );
}

export function getVideoFeedUrl() {
  return `${API_BASE_URL}/video_feed`;
}
