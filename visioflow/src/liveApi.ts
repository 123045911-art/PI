import { Platform } from 'react-native';
import type { ApiAreaState, ApiBootstrap, ApiTrackPoint } from './apiContract';
import { loadLocalSession, saveLocalSession, type LocalAlert, type LocalSession } from './localStore';

export type ApiSiteOption = {
  siteId: string;
  name: string;
  mode: 'live' | 'simulated';
};

const defaultBaseUrl = Platform.OS === 'android'
  ? 'http://10.0.2.2:8000'
  : 'http://127.0.0.1:8000';

export const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL || defaultBaseUrl).replace(/\/$/, '');

async function apiError(response: Response, fallback: string) {
  try {
    const payload = await response.json() as { detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>; error?: string };
    if (payload.error) return payload.error;
    if (typeof payload.detail === 'string') return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => {
        const field = item.loc?.at(-1);
        const message = (item.msg || 'Dato inválido').replace(/^Value error,\s*/i, '');
        return field && field !== 'body' ? `${String(field)}: ${message}` : message;
      }).join('\n');
    }
  } catch { /* la respuesta no era JSON */ }
  return fallback;
}

async function getJson<T>(path: string): Promise<T> {
  const session = await loadLocalSession();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: 'application/json',
      ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}),
    },
  });
  if (!response.ok) throw new Error(await apiError(response, `API ${response.status}: ${path}`));
  return response.json() as Promise<T>;
}

async function sendJson<T>(path: string, method: 'POST' | 'PATCH' | 'DELETE', body?: unknown): Promise<T> {
  const session = await loadLocalSession();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await apiError(response, `API ${response.status}: ${path}`));
  return response.json() as Promise<T>;
}

type LoginResponse = {
  access_token: string;
  token_type: string;
  user: { id: number; username: string; is_admin: boolean };
};

export async function loginApi(username: string, password: string): Promise<LocalSession> {
  const form = new URLSearchParams({ username: username.trim(), password });
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  if (!response.ok) {
    throw new Error(response.status === 401
      ? 'Credenciales incorrectas.'
      : await apiError(response, `API ${response.status}`));
  }
  const data = await response.json() as LoginResponse;
  return saveLocalSession({
    username: data.user.username,
    displayName: data.user.username,
    role: data.user.is_admin ? 'admin' : 'operator',
    accessToken: data.access_token,
    userId: data.user.id,
    isAdmin: data.user.is_admin,
    signedInAt: new Date().toISOString(),
  });
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
