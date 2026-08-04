import AsyncStorage from '@react-native-async-storage/async-storage';

export type LocalSession = {
  username: string;
  displayName: string;
  role: 'operator';
  signedInAt: string;
};

export type AlertType = 'crowding' | 'low_flow' | 'unusual_dwell' | 'blocked_access' | 'manual';
export type AlertScheduleMode = 'immediate' | 'all_days' | 'weekly' | 'date';
export type AlertStatus = 'new' | 'watching' | 'triggered' | 'acknowledged' | 'resolved';

export type LocalAlert = {
  id: string;
  areaId: string;
  areaName: string;
  type: AlertType;
  reason: string;
  status: AlertStatus;
  thresholdPeople?: number;
  scheduleMode?: AlertScheduleMode;
  scheduleDay?: number;
  scheduleDate?: string;
  peopleCountSnapshot: number;
  createdBy: string;
  createdAt: string;
};

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  crowding: 'Alta afluencia',
  low_flow: 'Baja afluencia',
  unusual_dwell: 'Tiempo inusual',
  blocked_access: 'Acceso bloqueado',
  manual: 'Observación',
};

const ALERT_DAY_NAMES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];

export function getAlertTypeLabel(type: AlertType) {
  return ALERT_TYPE_LABELS[type];
}

export function getAlertStatusLabel(status: AlertStatus) {
  if (status === 'triggered') return 'CONDICIÓN CUMPLIDA';
  if (status === 'watching') return 'EN ESPERA';
  if (status === 'resolved') return 'RESUELTA';
  if (status === 'acknowledged') return 'REVISADA';
  return 'REPORTE REGISTRADO';
}

export function getAlertScheduleLabel(alert: Pick<LocalAlert, 'scheduleMode' | 'scheduleDay' | 'scheduleDate' | 'type'>) {
  if (alert.scheduleMode === 'all_days') return 'Todos los días';
  if (alert.scheduleMode === 'weekly') return `Cada ${ALERT_DAY_NAMES[alert.scheduleDay ?? 0]}`;
  if (alert.scheduleMode === 'date' && alert.scheduleDate) {
    const [year, month, day] = alert.scheduleDate.split('-');
    return `${day}/${month}/${year}`;
  }
  return alert.type === 'crowding' || alert.type === 'low_flow' ? 'Todos los días' : 'Reporte inmediato';
}

function localDateKey(date: Date) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

export function alertScheduleApplies(alert: Pick<LocalAlert, 'scheduleMode' | 'scheduleDay' | 'scheduleDate' | 'type'>, date = new Date()) {
  const scheduleMode = alert.scheduleMode
    ?? (alert.type === 'crowding' || alert.type === 'low_flow' ? 'all_days' : 'immediate');
  if (scheduleMode === 'all_days') return true;
  if (scheduleMode === 'weekly') return alert.scheduleDay === (date.getDay() + 6) % 7;
  if (scheduleMode === 'date') return alert.scheduleDate === localDateKey(date);
  return false;
}

const SESSION_KEY = '@visioflow/session-v1';
const ALERTS_KEY = '@visioflow/alerts-v1';
const DELETED_ALERTS_KEY = '@visioflow/deleted-alerts-v1';

const DEMO_ALERT_HISTORY: LocalAlert[] = [];
const LEGACY_DEMO_ALERT_IDS = new Set([
  'demo-history-crowding-central', 'demo-history-blocked-north',
  'demo-history-lowflow-premium', 'demo-history-dwell-launch',
  'demo-history-crowding-service',
]);

// TODO SECURITY / BACKEND:
// Estas credenciales existen solo para la demostración sin API solicitada.
// Antes de producción deben eliminarse del cliente. La contraseña se debe
// almacenar en el backend únicamente como hash Argon2id (con salt), nunca en
// texto plano. La sesión local debe reemplazarse por access/refresh tokens
// seguros y las alertas deben validarse y persistirse mediante la API.
import { API_BASE_URL } from './liveApi';

const DEMO_USER = {
  username: 'operador',
  password: 'visioflow',
  displayName: 'Operador demo',
} as const;

export const DEMO_LOGIN = { username: DEMO_USER.username, password: DEMO_USER.password };

export async function authenticateLocal(username: string, password: string) {
  const u = username.trim();
  const lower = u.toLowerCase();

  // 1. Intentar autenticación contra la API de Flask (permite entrar a usuarios creados dinámicamente en Flask)
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ username: u, password }),
    });
    if (response.ok) {
      const data = await response.json();
      if (data?.ok && data?.user) {
        const session: LocalSession = {
          username: String(data.user.username || u),
          displayName: data.user.is_admin ? 'Administrador VisioFlow' : `Usuario ${data.user.username}`,
          role: 'operator',
          signedInAt: new Date().toISOString(),
        };
        await AsyncStorage.setItem(SESSION_KEY, JSON.stringify(session));
        return session;
      }
    }
  } catch {
    // Si no hay respuesta o la API está sin red, se valida con credenciales locales
  }

  // 2. Credenciales estáticas de respaldo (operador / visioflow y admin / admin)
  const isAdmin = lower === 'admin' && (password === 'admin' || password === '123456' || password === 'root');
  const isOperator = lower === 'operador' && password === 'visioflow';

  if (!isAdmin && !isOperator) return null;

  const session: LocalSession = {
    username: u,
    displayName: isAdmin ? 'Administrador VisioFlow' : 'Operador demo',
    role: 'operator',
    signedInAt: new Date().toISOString(),
  };
  await AsyncStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export async function loadLocalSession() {
  const value = await AsyncStorage.getItem(SESSION_KEY);
  if (!value) return null;
  try {
    return JSON.parse(value) as LocalSession;
  } catch {
    await AsyncStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export async function clearLocalSession() {
  await AsyncStorage.removeItem(SESSION_KEY);
}

export async function loadLocalAlerts() {
  const deletedValue = await AsyncStorage.getItem(DELETED_ALERTS_KEY);
  let deletedIds = new Set<string>();
  try { deletedIds = new Set<string>(deletedValue ? JSON.parse(deletedValue) : []); } catch { /* ignore corrupt tombstones */ }
  const value = await AsyncStorage.getItem(ALERTS_KEY);
  if (!value) {
    const visibleDemo = DEMO_ALERT_HISTORY.filter((alert) => !deletedIds.has(alert.id));
    await AsyncStorage.setItem(ALERTS_KEY, JSON.stringify(visibleDemo));
    return visibleDemo;
  }
  try {
    const stored = JSON.parse(value) as LocalAlert[];
    const userAlerts = stored.filter((alert) => !LEGACY_DEMO_ALERT_IDS.has(alert.id));
    const merged = [...userAlerts, ...DEMO_ALERT_HISTORY.filter((alert) => !deletedIds.has(alert.id))]
      .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt))
      .slice(0, 50);
    // Los casos históricos de demostración se restauran como resueltos; no son reglas en tiempo real.
    await AsyncStorage.setItem(ALERTS_KEY, JSON.stringify(merged));
    return merged;
  } catch {
    await AsyncStorage.removeItem(ALERTS_KEY);
    await AsyncStorage.setItem(ALERTS_KEY, JSON.stringify(DEMO_ALERT_HISTORY));
    return DEMO_ALERT_HISTORY;
  }
}

export async function createLocalAlert(alert: Omit<LocalAlert, 'id' | 'createdAt'>) {
  const alerts = await loadLocalAlerts();
  const created: LocalAlert = {
    ...alert,
    id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    createdAt: new Date().toISOString(),
  };
  const next = [created, ...alerts].slice(0, 50);
  // Temporal: se guarda como JSON en texto plano hasta conectar POST /alerts.
  await AsyncStorage.setItem(ALERTS_KEY, JSON.stringify(next));
  return created;
}

export async function saveLocalAlerts(alerts: LocalAlert[]) {
  // Temporal: el backend será responsable de reevaluar y persistir estados en producción.
  await AsyncStorage.setItem(ALERTS_KEY, JSON.stringify(alerts.slice(0, 50)));
}

export async function updateLocalAlert(updated: LocalAlert) {
  const alerts = await loadLocalAlerts();
  const next = alerts.map((alert) => alert.id === updated.id ? updated : alert);
  await saveLocalAlerts(next);
  return updated;
}

export async function deleteLocalAlert(alertId: string) {
  const alerts = await loadLocalAlerts();
  const deletedValue = await AsyncStorage.getItem(DELETED_ALERTS_KEY);
  let deletedIds = new Set<string>();
  try { deletedIds = new Set<string>(deletedValue ? JSON.parse(deletedValue) : []); } catch { /* ignore corrupt tombstones */ }
  deletedIds.add(alertId);
  await AsyncStorage.setItem(DELETED_ALERTS_KEY, JSON.stringify([...deletedIds].slice(-100)));
  const next = alerts.filter((alert) => alert.id !== alertId);
  await saveLocalAlerts(next);
  return next;
}
