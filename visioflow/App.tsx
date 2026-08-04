import { StatusBar } from 'expo-status-bar';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  Image,
  PanResponder,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { computeAnalytics, buildInsights } from './src/analytics';
import { AnalysisPanel } from './src/components/AnalysisPanel';
import { AlertManager } from './src/components/AlertManager';
import { AppModal } from './src/components/AppModal';
import { FlowMap } from './src/components/FlowMap';
import { HeatmapHelp } from './src/components/HeatmapHelp';
import { LoginScreen } from './src/components/LoginScreen';
import { apiAreaToZone, ApiAreaState, ApiBootstrap, ApiTrackPoint, createTrackPointAdapter, createWorldProjection } from './src/apiContract';
import { activateMapScene, FLOOR, restoreSimulatedMapScene, SIMULATED_TRACKS, trackPointsForDay } from './src/data';
import { DAY_NAMES, getZoneDayProfile } from './src/history';
import { API_BASE_URL, ApiSiteOption, createAlert, deleteAlert, getVideoFeedUrl, listSites, loadAlerts, loadAreaState, loadBootstrap, loadTrackPoints, updateAlert } from './src/liveApi';
import { alertScheduleApplies, clearLocalSession, getAlertScheduleLabel, getAlertStatusLabel, getAlertTypeLabel, loadLocalAlerts, loadLocalSession, LocalAlert, LocalSession, saveLocalAlerts } from './src/localStore';
import { HeatScaleMode, MapPerspective, Metric, StaticObject, TrackPoint, ViewMode } from './src/types';

const ORANGE = '#ff5a2a';
const TEAL = '#3ba5bb';
const GREEN = '#20ad50';
const DARK = '#07171c';

const PERIODS = [
  { label: '15 min', seconds: 900 },
  { label: '30 min', seconds: 1800 },
  { label: '1 h', seconds: 3600 },
  { label: '2 h', seconds: 7200 },
];

const PLAYBACK_SPEEDS = [
  { value: 60, label: '+1 m' },
  { value: 300, label: '+5 m' },
  { value: 900, label: '+15 m' },
];

const METRICS: { id: Metric; label: string; description: string }[] = [
  { id: 'flow', label: 'Personas', description: 'Personas diferentes que recorrieron cada punto del espacio.' },
  { id: 'dwell', label: 'Tiempo en zona', description: 'Tiempo dentro del área, incluso cuando la persona continúa caminando.' },
  { id: 'stopped', label: 'Movimiento mínimo', description: 'Tiempo con movimiento muy pequeño durante al menos 12 s; tolera ruido del sensor.' },
  { id: 'density', label: 'Concentración', description: 'Promedio de personas presentes al mismo tiempo en intervalos de 20 segundos.' },
];

const MODE_OPTIONS: Record<Metric, { id: ViewMode; label: string; description: string }[]> = {
  flow: [
    { id: 'moving', label: 'Ventana móvil', description: 'Personas diferentes de la ventana seleccionada.' },
    { id: 'accumulated', label: 'Acumulado', description: 'Personas diferentes desde el inicio hasta la hora visible.' },
    { id: 'average', label: 'Promedio general', description: 'Promedio de personas diferentes por hora en la jornada.' },
  ],
  dwell: [
    { id: 'moving', label: 'Ventana móvil', description: 'Segundos de presencia dentro de la ventana.' },
    { id: 'accumulated', label: 'Acumulado', description: 'Segundos de presencia desde el inicio.' },
    { id: 'average', label: 'Promedio general', description: 'Presencia media por persona y punto espacial.' },
  ],
  stopped: [
    { id: 'moving', label: 'Ventana móvil', description: 'Tiempo detenido detectado en la ventana.' },
    { id: 'accumulated', label: 'Acumulado', description: 'Tiempo detenido acumulado hasta ahora.' },
    { id: 'average', label: 'Promedio general', description: 'Tiempo con movimiento mínimo por persona y punto espacial.' },
  ],
  density: [
    { id: 'moving', label: 'Ventana móvil', description: 'Concurrencia media de la ventana.' },
    { id: 'accumulated', label: 'Media hasta ahora', description: 'Concurrencia media desde el inicio, incluyendo intervalos vacíos.' },
    { id: 'average', label: 'Promedio general', description: 'Concurrencia media de toda la jornada, incluyendo intervalos vacíos.' },
  ],
};

const LIVE_WINDOW_SECONDS = 300;
const TODAY_DAY_INDEX = (new Date().getDay() + 6) % 7;

function objectsForSite(bootstrap: ApiBootstrap, projection: ReturnType<typeof createWorldProjection>): StaticObject[] {
  return (bootstrap.scenes[0]?.objects ?? []).map((object) => {
    const footprint = object.footprint.length ? object.footprint : [[0, 0] as [number, number]];
    const xs = footprint.map(([x]) => x);
    const ys = footprint.map(([, y]) => y);
    const start = projection.toDisplay(Math.min(...xs), Math.min(...ys));
    const end = projection.toDisplay(Math.max(...xs), Math.max(...ys));
    return {
      id: object.objectId,
      label: object.name,
      x: Math.min(start.x, end.x),
      y: Math.min(start.y, end.y),
      width: Math.max(1, Math.abs(end.x - start.x)),
      height: Math.max(1, Math.abs(end.y - start.y)),
      elevation: Math.max(2, Math.min(10, (object.heightMeters ?? 1.8) * projection.scale)),
      kind: object.type === 'wall' ? 'wall' : object.type === 'checkout' ? 'service' : 'display',
    };
  });
}

function formatClock(seconds: number) {
  const minutes = 8 * 60 + Math.round(seconds / 60);
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

function Pill({ active, label, onPress }: { active: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.pill, active && styles.pillActive]}>
      <Text style={[styles.pillText, active && styles.pillTextActive]}>{label}</Text>
    </Pressable>
  );
}

function LayerButton({ active, label, onPress }: { active?: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.layerButton, active && styles.layerButtonActive]}>
      <Text style={[styles.layerButtonText, active && styles.layerButtonTextActive]}>{label}</Text>
    </Pressable>
  );
}

function KpiCard({ label, value, detail, color, dark = false }: { label: string; value: string; detail: string; color: string; dark?: boolean }) {
  return (
    <View style={[styles.kpiCard, dark && styles.kpiCardDark]}>
      <View style={[styles.kpiLine, { backgroundColor: color }]} />
      <Text style={[styles.kpiLabel, dark && styles.kpiLabelDark]}>{label.toUpperCase()}</Text>
      <Text style={[styles.kpiValue, dark && styles.kpiValueDark]}>{value}</Text>
      <Text style={[styles.kpiDetail, dark && styles.kpiDetailDark]}>{detail}</Text>
    </View>
  );
}

function ComparisonKpiTable({
  baselineLabel,
  comparisonLabel,
  rows,
  dark = false,
}: {
  baselineLabel: string;
  comparisonLabel: string;
  rows: { label: string; baseline: number; comparison: number; suffix?: string }[];
  dark?: boolean;
}) {
  return (
    <View style={[styles.comparisonKpiTable, dark && styles.comparisonKpiTableDark]}>
      <View style={[styles.comparisonKpiRow, styles.comparisonKpiHeader, dark && styles.comparisonKpiHeaderDark]}>
        <Text style={[styles.comparisonKpiCell, styles.comparisonKpiMetric, dark && styles.comparisonKpiCellDark]}>MÉTRICA</Text>
        <Text style={[styles.comparisonKpiCell, dark && styles.comparisonKpiCellDark]}>A · {baselineLabel}</Text>
        <Text style={[styles.comparisonKpiCell, dark && styles.comparisonKpiCellDark]}>B · {comparisonLabel}</Text>
        <Text style={[styles.comparisonKpiCell, dark && styles.comparisonKpiCellDark]}>CAMBIO</Text>
      </View>
      {rows.map((row) => {
        const delta = row.comparison - row.baseline;
        return (
          <View key={row.label} style={[styles.comparisonKpiRow, dark && styles.comparisonKpiRowDark]}>
            <Text style={[styles.comparisonKpiCell, styles.comparisonKpiMetric, dark && styles.comparisonKpiCellDark]}>{row.label}</Text>
            <Text style={[styles.comparisonKpiValue, dark && styles.comparisonKpiValueDark]}>{row.baseline}{row.suffix ?? ''}</Text>
            <Text style={[styles.comparisonKpiValue, dark && styles.comparisonKpiValueDark]}>{row.comparison}{row.suffix ?? ''}</Text>
            <Text style={[styles.comparisonKpiDelta, delta < 0 && styles.comparisonKpiDeltaNegative]}>
              {delta > 0 ? '+' : ''}{delta}{row.suffix ?? ''}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

export default function App() {
  const { width, height } = useWindowDimensions();
  const isWide = width >= 1040;
  const compact = width < 520;
  const [metric, setMetric] = useState<Metric>('density');
  const [mode, setMode] = useState<ViewMode>('moving');
  const [scaleMode, setScaleMode] = useState<HeatScaleMode>('adaptive');
  const [period, setPeriod] = useState(3600);
  const [currentTime, setCurrentTime] = useState(4.5 * 3600);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(300);
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [perspective, setPerspective] = useState<MapPerspective>('isometric');
  const [showObjects, setShowObjects] = useState(true);
  const [showTrackers, setShowTrackers] = useState(true);
  const [showTrails, setShowTrails] = useState(true);
  const [timelineWidth, setTimelineWidth] = useState(1);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [kpiScope, setKpiScope] = useState<'general' | 'live' | 'period'>('general');
  const [comparisonHours, setComparisonHours] = useState<{ baselineHour: number; comparisonHour: number } | null>(null);
  const [selectedDay, setSelectedDay] = useState(TODAY_DAY_INDEX);
  const [session, setSession] = useState<LocalSession | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [alerts, setAlerts] = useState<LocalAlert[]>([]);
  const [alertManagerOpen, setAlertManagerOpen] = useState(false);
  const [alertAreaFilter, setAlertAreaFilter] = useState('all');
  const [alertToast, setAlertToast] = useState<LocalAlert | null>(null);
  const [heatmapHelpOpen, setHeatmapHelpOpen] = useState(false);
  const [activeSiteId, setActiveSiteId] = useState('sitio-simulado');
  const activeSite = activeSiteId === 'sitio-simulado' ? 'simulated' : 'corridor';
  const [cameraSelectorOpen, setCameraSelectorOpen] = useState(false);
  const [videoStreamOpen, setVideoStreamOpen] = useState(false);
  const [siteOptions, setSiteOptions] = useState<ApiSiteOption[]>([
    { siteId: 'sitio-simulado', name: 'Cámara simulada', mode: 'simulated' },
    { siteId: 'pasillo-real', name: 'Dell Webcam WB7022', mode: 'live' },
  ]);
  const [liveBootstrap, setLiveBootstrap] = useState<ApiBootstrap | null>(null);
  const [realSitePoints, setRealSitePoints] = useState<TrackPoint[]>([]);
  const [liveAreaState, setLiveAreaState] = useState<ApiAreaState[]>([]);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [liveUpdatedAt, setLiveUpdatedAt] = useState('NA');
  const liveCursorRef = useRef<string | null>(null);
  const liveWirePointsRef = useRef<ApiTrackPoint[]>([]);
  const pulse = useRef(new Animated.Value(0)).current;
  const alertToastProgress = useRef(new Animated.Value(0)).current;
  const alertToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const analysisTranslateY = useRef(new Animated.Value(1000)).current;
  const analysisBackdropOpacity = useRef(new Animated.Value(0)).current;
  const sheetDragStart = useRef(0);
  const analysisSheetHeight = Math.min(height * 0.84, 760);

  useEffect(() => {
    let mounted = true;
    Promise.all([loadLocalSession(), loadLocalAlerts()])
      .then(([storedSession, storedAlerts]) => {
        if (!mounted) return;
        setSession(storedSession);
        setAlerts(storedAlerts);
      })
      .finally(() => {
        if (mounted) setSessionReady(true);
      });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!sessionReady || activeSite !== 'corridor') return;
    let mounted = true;
    const refreshAlerts = () => loadAlerts(activeSiteId)
      .then((items) => { if (mounted) setAlerts(items); })
      .catch(() => undefined);
    void refreshAlerts();
    const timer = setInterval(refreshAlerts, 2000);
    return () => { mounted = false; clearInterval(timer); };
  }, [activeSite, activeSiteId, sessionReady]);

  const showAlertToast = useCallback((alert: LocalAlert) => {
    if (alertToastTimer.current) clearTimeout(alertToastTimer.current);
    setAlertToast(alert);
    alertToastProgress.setValue(0);
    Animated.spring(alertToastProgress, {
      toValue: 1,
      damping: 18,
      stiffness: 220,
      mass: 0.8,
      useNativeDriver: Platform.OS !== 'web',
    }).start();
    alertToastTimer.current = setTimeout(() => {
      Animated.timing(alertToastProgress, {
        toValue: 0,
        duration: 180,
        useNativeDriver: Platform.OS !== 'web',
      }).start(({ finished }) => {
        if (finished) setAlertToast(null);
      });
    }, 5000);
  }, [alertToastProgress]);

  useEffect(() => () => {
    if (alertToastTimer.current) clearTimeout(alertToastTimer.current);
  }, []);

  useEffect(() => {
    if (!playing || mode !== 'moving') return;
    const timer = setInterval(() => {
      setCurrentTime((time) => time + speed >= FLOOR.duration ? 0 : time + speed);
    }, 180);
    return () => clearInterval(timer);
  }, [playing, speed, mode]);

  useEffect(() => {
    const animation = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 1, duration: 850, useNativeDriver: Platform.OS !== 'web' }),
      Animated.timing(pulse, { toValue: 0, duration: 850, useNativeDriver: Platform.OS !== 'web' }),
    ]));
    animation.start();
    return () => animation.stop();
  }, [pulse]);

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    document.documentElement.lang = 'es-MX';
    document.documentElement.setAttribute('translate', 'no');
    document.documentElement.classList.add('notranslate');
    let translationMeta = document.querySelector('meta[name="google"]');
    if (!translationMeta) {
      translationMeta = document.createElement('meta');
      translationMeta.setAttribute('name', 'google');
      document.head.appendChild(translationMeta);
    }
    translationMeta.setAttribute('content', 'notranslate');
  }, []);

  const liveProjection = useMemo(() => {
    const polygon = liveBootstrap?.scenes[0]?.fieldOfViewPolygon;
    return polygon?.length ? createWorldProjection(polygon) : null;
  }, [liveBootstrap]);
  const liveZones = useMemo(
    () => liveBootstrap && liveProjection
      ? liveBootstrap.areas.map((area) => apiAreaToZone(area, liveProjection))
      : [],
    [liveBootstrap, liveProjection],
  );
  const liveObjects = useMemo(
    () => liveBootstrap && liveProjection ? objectsForSite(liveBootstrap, liveProjection) : [],
    [liveBootstrap, liveProjection],
  );
  const siteCopy = activeSite === 'corridor'
    ? {
        sourceTitle: 'MI PASILLO · CÁMARA DELL',
        sourceText: `${liveBootstrap?.cameras[0]?.name ?? 'Dell Webcam WB7022'} · ${liveError ? 'sin conexión' : 'en vivo'} · actualización ${liveUpdatedAt}`,
        eyebrow: 'MI PASILLO · ÁREA OBSERVADA',
        title: 'Pasillo en vivo',
        subtitle: 'Tres áreas calibradas: cercana, media y lejana. Los datos históricos no disponibles se muestran como NA.',
        contract: 'persona · hora del registro · coordenadas de imagen y mundo · área calculada',
      }
    : {
        sourceTitle: 'TIENDA CENTRO · ZONA DE EXHIBICIÓN',
        sourceText: `Sensor 03 · cobertura parcial · ${SIMULATED_TRACKS} personas simuladas`,
        eyebrow: 'TIENDA CENTRO · ÁREA OBSERVADA',
        title: 'Exhibición y circulación',
        subtitle: 'Área observada: exhibición, caja y paso a probadores. No representa toda la tienda.',
        contract: 'persona · hora del registro · coordenadas · área calculada en móvil',
      };

  useEffect(() => {
    const refreshSites = () => listSites().then(setSiteOptions).catch(() => undefined);
    void refreshSites();
    const timer = setInterval(refreshSites, 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (activeSite !== 'corridor') return;
    let active = true;
    const refreshBootstrap = () => loadBootstrap(activeSiteId)
      .then((bootstrap) => { if (active) setLiveBootstrap(bootstrap); })
      .catch((reason) => { if (active) setLiveError(`API no disponible: ${String(reason)}`); });
    void refreshBootstrap();
    const timer = setInterval(refreshBootstrap, 2000);
    return () => { active = false; clearInterval(timer); };
  }, [activeSite, activeSiteId]);

  const selectSite = (option: ApiSiteOption) => {
    const nextSite = option.mode === 'simulated' ? 'simulated' : 'corridor';
    setActiveSiteId(option.siteId);
    setCameraSelectorOpen(false);
    setSelectedZone(null);
    setComparisonHours(null);
    setPlaying(false);
    if (nextSite === 'simulated') {
      restoreSimulatedMapScene();
      setCurrentTime(trackPointsForDay(selectedDay).at(-1)?.timestamp ?? 0);
    } else {
      liveCursorRef.current = null;
      liveWirePointsRef.current = [];
      setRealSitePoints([]);
      setLiveError(null);
    }
  };

  useEffect(() => {
    if (activeSite !== 'corridor') return;
    activateMapScene({ width: 100, height: 68, duration: 3600 }, liveZones, liveObjects);
    setSelectedZone(null);
    setComparisonHours(null);
    return restoreSimulatedMapScene;
  }, [activeSite, liveObjects, liveZones]);

  useEffect(() => {
    if (activeSite !== 'corridor' || !liveProjection) return;
    let active = true;
    let refreshing = false;
    const refresh = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        const [page, states] = await Promise.all([
          loadTrackPoints(activeSiteId, liveCursorRef.current),
          loadAreaState(activeSiteId),
        ]);
        if (!active) return;
        if (page.items.length) {
          liveWirePointsRef.current = [...liveWirePointsRef.current, ...page.items].slice(-4000);
          liveCursorRef.current = page.nextCursor;
        }
        const wirePoints = liveWirePointsRef.current;
        const periodStart = wirePoints[0]?.capturedAt ?? new Date().toISOString();
        const adapt = createTrackPointAdapter(periodStart, liveProjection);
        const mapped = wirePoints.map(adapt);
        setRealSitePoints(mapped);
        setLiveAreaState(states);
        setLiveUpdatedAt(new Date().toLocaleTimeString('es-MX'));
        setLiveError(null);
        setCurrentTime(mapped.at(-1)?.timestamp ?? 0);
      } catch (reason) {
        if (active) setLiveError(`Sin conexión con ${API_BASE_URL}: ${String(reason)}`);
      } finally {
        refreshing = false;
      }
    };
    void refresh();
    const timer = setInterval(refresh, 500);
    return () => { active = false; clearInterval(timer); };
  }, [activeSite, activeSiteId, liveProjection]);

  const dayPoints = useMemo(
    () => activeSite === 'corridor' ? realSitePoints : trackPointsForDay(selectedDay),
    [activeSite, realSitePoints, selectedDay],
  );
  const todayPoints = useMemo(
    () => activeSite === 'corridor' ? realSitePoints : trackPointsForDay(TODAY_DAY_INDEX),
    [activeSite, realSitePoints],
  );
  const todayLatestRecordTime = useMemo(
    () => todayPoints.reduce((latest, point) => Math.max(latest, point.timestamp), 0),
    [todayPoints],
  );
  const selectedLatestRecordTime = useMemo(
    () => dayPoints.reduce((latest, point) => Math.max(latest, point.timestamp), 0),
    [dayPoints],
  );
  const visiblePoints = useMemo(() => {
    if (mode === 'average') return dayPoints;
    if (mode === 'accumulated') return dayPoints.filter((point) => point.timestamp <= currentTime);
    const start = Math.max(0, currentTime - period);
    return dayPoints.filter((point) => point.timestamp >= start && point.timestamp <= currentTime);
  }, [currentTime, dayPoints, mode, period]);
  const scopeSeconds = mode === 'moving'
    ? Math.max(20, Math.min(period, currentTime || period))
    : mode === 'accumulated'
      ? Math.max(20, currentTime)
      : FLOOR.duration;

  const summary = useMemo(() => computeAnalytics(visiblePoints, currentTime), [activeSite, currentTime, liveZones, visiblePoints]);
  const generalSummary = useMemo(() => computeAnalytics(dayPoints, FLOOR.duration), [activeSite, dayPoints, liveZones]);
  const livePoints = useMemo(
    () => dayPoints.filter((point) => point.timestamp >= Math.max(0, selectedLatestRecordTime - LIVE_WINDOW_SECONDS) && point.timestamp <= selectedLatestRecordTime),
    [dayPoints, selectedLatestRecordTime],
  );
  const previousLivePoints = useMemo(
    () => dayPoints.filter((point) => point.timestamp >= Math.max(0, selectedLatestRecordTime - LIVE_WINDOW_SECONDS * 2) && point.timestamp < selectedLatestRecordTime - LIVE_WINDOW_SECONDS),
    [dayPoints, selectedLatestRecordTime],
  );
  const liveSummary = useMemo(() => computeAnalytics(livePoints, selectedLatestRecordTime), [activeSite, livePoints, liveZones, selectedLatestRecordTime]);
  const liveTrend = useMemo(() => {
    const currentTracks = new Set(livePoints.map((point) => point.trackId)).size;
    const previousTracks = new Set(previousLivePoints.map((point) => point.trackId)).size;
    return previousTracks ? Math.round(((currentTracks - previousTracks) / previousTracks) * 100) : 0;
  }, [livePoints, previousLivePoints]);
  const comparisonData = useMemo(() => {
    if (!comparisonHours) return null;
    const baselineStart = (comparisonHours.baselineHour - 8) * 3600;
    const comparisonStart = (comparisonHours.comparisonHour - 8) * 3600;
    return {
      baselinePoints: dayPoints.filter((point) => point.timestamp >= baselineStart && point.timestamp < baselineStart + 3600),
      comparisonPoints: dayPoints.filter((point) => point.timestamp >= comparisonStart && point.timestamp < comparisonStart + 3600),
      baselineLabel: `${String(comparisonHours.baselineHour).padStart(2, '0')}:00`,
      comparisonLabel: `${String(comparisonHours.comparisonHour).padStart(2, '0')}:00`,
      baselineEnd: baselineStart + 3600,
      comparisonEnd: comparisonStart + 3600,
    };
  }, [comparisonHours, dayPoints]);
  const baselineComparisonSummary = useMemo(
    () => comparisonData ? computeAnalytics(comparisonData.baselinePoints, comparisonData.baselineEnd) : null,
    [activeSite, comparisonData, liveZones],
  );
  const comparisonSummary = useMemo(
    () => comparisonData ? computeAnalytics(comparisonData.comparisonPoints, comparisonData.comparisonEnd) : null,
    [activeSite, comparisonData, liveZones],
  );
  const selectedPeriodSummary = useMemo(
    () => comparisonSummary ?? summary,
    [comparisonSummary, summary],
  );
  const liveInsights = useMemo(() => buildInsights(selectedPeriodSummary), [selectedPeriodSummary]);
  const [frozenInsights, setFrozenInsights] = useState(liveInsights);
  useEffect(() => {
    if (!playing) setFrozenInsights(liveInsights);
  }, [liveInsights, playing]);
  const insights = frozenInsights.length ? frozenInsights : liveInsights;
  const selectedStats = selectedPeriodSummary.zoneStats.find((zone) => zone.id === selectedZone);
  const selectedZoneDayProfile = useMemo(
    () => selectedZone && activeSite === 'simulated' ? getZoneDayProfile(selectedZone, selectedDay) : null,
    [activeSite, selectedDay, selectedZone],
  );
  const selectedZoneMaxHour = Math.max(1, ...(selectedZoneDayProfile?.hours.map((row) => row.people) ?? [1]));
  const alertAreaCounts = useMemo(() => {
    const byArea = new Map<string, Set<number>>();
    todayPoints
      .filter((point) => point.timestamp >= todayLatestRecordTime - LIVE_WINDOW_SECONDS && point.timestamp <= todayLatestRecordTime && point.zoneId)
      .forEach((point) => {
        const people = byArea.get(point.zoneId!) ?? new Set<number>();
        people.add(point.trackId);
        byArea.set(point.zoneId!, people);
      });
    return byArea;
  }, [todayLatestRecordTime, todayPoints]);
  const liveAlertAreaCounts = useMemo(
    () => new Map(liveAreaState.map((area) => [area.areaId, area.peopleCount])),
    [liveAreaState],
  );
  const alertAreas = useMemo(() => generalSummary.zoneStats.map((zone) => ({
    id: zone.id,
    name: zone.name,
    peopleCount: activeSite === 'corridor'
      ? liveAlertAreaCounts.get(zone.id) ?? 0
      : alertAreaCounts.get(zone.id)?.size ?? 0,
  })), [activeSite, alertAreaCounts, generalSummary.zoneStats, liveAlertAreaCounts]);

  useEffect(() => {
    if (!sessionReady || alerts.length === 0) return;
    const peopleByArea = new Map(alertAreas.map((area) => [area.id, area.peopleCount]));
    let changed = false;
    let newlyTriggered: LocalAlert | null = null;
    const now = new Date();
    const nextAlerts = alerts.map((alert) => {
      if ((alert.status !== 'watching' && alert.status !== 'triggered') || (alert.type !== 'crowding' && alert.type !== 'low_flow') || alert.thresholdPeople == null) return alert;
      const peopleCount = peopleByArea.get(alert.areaId) ?? 0;
      const conditionMet = alert.type === 'crowding'
        ? peopleCount >= alert.thresholdPeople
        : peopleCount <= alert.thresholdPeople;
      const nextStatus: LocalAlert['status'] = alertScheduleApplies(alert, now) && conditionMet ? 'triggered' : 'watching';
      if (nextStatus === alert.status) return alert;
      changed = true;
      const updated = { ...alert, status: nextStatus, peopleCountSnapshot: peopleCount };
      if (nextStatus === 'triggered') newlyTriggered = updated;
      return updated;
    });
    if (!changed) return;
    setAlerts(nextAlerts);
    void saveLocalAlerts(nextAlerts);
    if (newlyTriggered) showAlertToast(newlyTriggered);
  }, [alertAreas, alerts, sessionReady, showAlertToast]);

  const handleAlertCreated = useCallback((created: LocalAlert) => {
    setAlerts((current) => [created, ...current]);
    if (activeSite === 'corridor') void createAlert(activeSiteId, created);
    if (created.status === 'triggered') showAlertToast(created);
  }, [activeSite, activeSiteId, showAlertToast]);
  const handleAlertUpdated = useCallback((updated: LocalAlert) => {
    setAlerts((current) => current.map((alert) => alert.id === updated.id ? updated : alert));
    if (activeSite === 'corridor') void updateAlert(activeSiteId, updated);
  }, [activeSite, activeSiteId]);
  const handleAlertDeleted = useCallback((alertId: string) => {
    setAlerts((current) => current.filter((alert) => alert.id !== alertId));
    setAlertToast((current) => current?.id === alertId ? null : current);
    if (activeSite === 'corridor') void deleteAlert(activeSiteId, alertId);
  }, [activeSite, activeSiteId]);
  const filteredAlerts = useMemo(
    () => alertAreaFilter === 'all' ? alerts : alerts.filter((alert) => alert.areaId === alertAreaFilter),
    [alertAreaFilter, alerts],
  );
  const alertOverview = useMemo(() => ({
    conditionMet: filteredAlerts.filter((alert) => alert.status === 'triggered').length,
    waiting: filteredAlerts.filter((alert) => alert.status === 'watching').length,
    recent: filteredAlerts.slice(0, compact ? 2 : 3),
  }), [compact, filteredAlerts]);
  const selectedMetric = METRICS.find((item) => item.id === metric)!;
  const selectedMode = MODE_OPTIONS[metric].find((item) => item.id === mode)!;
  const mapHeight = isWide ? Math.max(650, height - 160) : compact ? 670 : 710;
  const kpis = useMemo(() => {
    const scoped = kpiScope === 'general' ? generalSummary : kpiScope === 'live' ? liveSummary : selectedPeriodSummary;
    const visits = scoped.zoneStats.reduce((sum, zone) => sum + zone.visits, 0);
    if (kpiScope === 'live') {
      return [
        { label: 'Personas activas', value: String(scoped.activeNow), detail: `Último registro ${formatClock(selectedLatestRecordTime)} · tolerancia 16 s`, color: ORANGE },
        { label: 'Personas en 5 min', value: String(scoped.uniqueTracks), detail: 'Ventana anclada al último registro', color: TEAL },
        { label: 'Presencia mediana', value: `${scoped.medianDwellSeconds} s`, detail: 'Presencia continua durante los últimos 5 min', color: GREEN },
        { label: 'Tendencia 5 min', value: `${liveTrend > 0 ? '+' : ''}${liveTrend}%`, detail: 'Contra los 5 min inmediatamente anteriores', color: liveTrend < 0 ? '#3976c5' : ORANGE },
      ];
    }
    return [
      { label: 'Personas detectadas', value: String(scoped.uniqueTracks), detail: kpiScope === 'general' ? 'Jornada completa de 8 horas' : 'Hora o ventana seleccionada', color: TEAL },
      { label: 'Entradas a zonas', value: String(visits), detail: 'Ingresos continuos a las áreas', color: ORANGE },
      { label: 'Presencia mediana', value: `${scoped.medianDwellSeconds} s`, detail: 'Estadística estable del alcance', color: GREEN },
      { label: 'Concurrencia pico', value: String(scoped.peakConcurrent), detail: 'Máximo simultáneo en 20 s', color: '#6676c7' },
    ];
  }, [generalSummary, kpiScope, liveSummary, liveTrend, selectedLatestRecordTime, selectedPeriodSummary]);

  const comparisonKpiRows = useMemo(() => {
    if (!baselineComparisonSummary || !comparisonSummary) return [];
    return [
      { label: 'Personas detectadas', baseline: baselineComparisonSummary.uniqueTracks, comparison: comparisonSummary.uniqueTracks },
      { label: 'Presencia mediana', baseline: baselineComparisonSummary.medianDwellSeconds, comparison: comparisonSummary.medianDwellSeconds, suffix: ' s' },
      { label: 'Detenido mediano', baseline: baselineComparisonSummary.medianStoppedSeconds, comparison: comparisonSummary.medianStoppedSeconds, suffix: ' s' },
      { label: 'Concurrencia pico', baseline: baselineComparisonSummary.peakConcurrent, comparison: comparisonSummary.peakConcurrent },
    ];
  }, [baselineComparisonSummary, comparisonSummary]);

  const setAnalysisSheet = (open: boolean) => {
    const useNativeDriver = Platform.OS !== 'web';
    if (open) {
      setPlaying(false);
      analysisTranslateY.setValue(analysisSheetHeight + 36);
      analysisBackdropOpacity.setValue(0);
      setAnalysisOpen(true);
      requestAnimationFrame(() => {
        Animated.parallel([
          Animated.spring(analysisTranslateY, {
            toValue: 0,
            useNativeDriver,
            damping: 27,
            stiffness: 250,
            mass: 0.9,
          }),
          Animated.timing(analysisBackdropOpacity, {
            toValue: 1,
            duration: 240,
            useNativeDriver,
          }),
        ]).start();
      });
      return;
    }
    Animated.parallel([
      Animated.timing(analysisTranslateY, {
        toValue: analysisSheetHeight + 36,
        duration: 280,
        useNativeDriver,
      }),
      Animated.timing(analysisBackdropOpacity, {
        toValue: 0,
        duration: 220,
        useNativeDriver,
      }),
    ]).start(({ finished }) => {
      if (finished) setAnalysisOpen(false);
    });
  };

  useEffect(() => {
    if (isWide) return;
    analysisTranslateY.setValue(0);
    analysisBackdropOpacity.setValue(0);
    setAnalysisOpen(false);
  }, [analysisBackdropOpacity, analysisTranslateY, isWide]);

  const analysisPanResponder = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: (_, gesture) => !isWide && Math.abs(gesture.dy) > 6 && Math.abs(gesture.dy) > Math.abs(gesture.dx),
    onPanResponderGrant: () => {
      analysisTranslateY.stopAnimation((value) => { sheetDragStart.current = value; });
    },
    onPanResponderMove: (_, gesture) => {
      if (analysisOpen) analysisTranslateY.setValue(Math.max(0, sheetDragStart.current + gesture.dy));
    },
    onPanResponderRelease: (_, gesture) => {
      if (!analysisOpen) {
        if (gesture.dy < -20 || gesture.vy < -0.35) setAnalysisSheet(true);
        return;
      }
      const shouldClose = gesture.dy > 70 || gesture.vy > 0.5;
      if (shouldClose) {
        setAnalysisSheet(false);
        return;
      }
      Animated.spring(analysisTranslateY, {
        toValue: 0,
        useNativeDriver: Platform.OS !== 'web',
        damping: 24,
        stiffness: 230,
        mass: 0.85,
      }).start();
    },
  }), [analysisBackdropOpacity, analysisOpen, analysisSheetHeight, analysisTranslateY, isWide]);

  const handleTimelinePress = (event: any) => {
    const { locationX } = event.nativeEvent;
    setCurrentTime(Math.max(0, Math.min(FLOOR.duration, (locationX / timelineWidth) * FLOOR.duration)));
  };

  const applyComparison = (baselineHour: number, comparisonHour: number) => {
    setComparisonHours({ baselineHour, comparisonHour });
    setMetric('flow');
    setPlaying(false);
    setKpiScope('period');
    if (!isWide) setAnalysisSheet(false);
  };

  const handleSelectZone = (zoneId: string | null) => {
    setSelectedZone(zoneId);
    if (zoneId) setPlaying(false);
  };

  const handleSelectDay = (dayIndex: number) => {
    setPlaying(false);
    setSelectedDay(dayIndex);
    setComparisonHours(null);
  };

  const signOut = async () => {
    await clearLocalSession();
    setSession(null);
    setAlertManagerOpen(false);
    setHeatmapHelpOpen(false);
  };

  if (!sessionReady) {
    return <View style={styles.loadingRoot}><StatusBar style="light" /><Text style={styles.loadingText}>Preparando VisioFlow…</Text></View>;
  }

  if (!session) return <LoginScreen onAuthenticated={setSession} />;

  return (
    <View style={[styles.root, darkMode && styles.rootDark]}>
      <StatusBar style={darkMode ? 'light' : 'dark'} />
      {alertToast && (
        <Animated.View
          accessibilityLiveRegion="assertive"
          pointerEvents="box-none"
          style={[
            styles.alertToastWrapper,
            {
              opacity: alertToastProgress,
              transform: [{
                translateY: alertToastProgress.interpolate({ inputRange: [0, 1], outputRange: [-24, 0] }),
              }],
            },
          ]}
        >
          <Pressable onPress={() => setAlertManagerOpen(true)} style={styles.alertToast}>
            <View style={styles.alertToastIcon}><Text style={styles.alertToastIconText}>!</Text></View>
            <View style={styles.alertToastContent}>
              <Text style={styles.alertToastEyebrow}>CONDICIÓN CUMPLIDA</Text>
              <Text style={styles.alertToastTitle}>{getAlertTypeLabel(alertToast.type)} · {alertToast.areaName}</Text>
              <Text style={styles.alertToastDetail}>{alertToast.peopleCountSnapshot} personas en el último registro · toca para ver</Text>
            </View>
          </Pressable>
        </Animated.View>
      )}
      <ScrollView
        contentContainerStyle={[styles.page, darkMode && styles.pageDark, isWide && styles.pageWide]}
        showsVerticalScrollIndicator={false}
        stickyHeaderIndices={[]}
      >
        <View style={[styles.header, darkMode && styles.headerDark]}>
          <View style={styles.brandRow}>
            <Image source={require('./assets/visioflow-logo.jpg')} style={styles.logo} />
            <View>
              <Text style={[styles.brandName, darkMode && styles.brandNameDark]}>VisioFlow</Text>
              <Text style={[styles.brandTag, darkMode && styles.brandTagDark]}>ANALÍTICA ESPACIAL DE PERSONAS</Text>
            </View>
          </View>
          <View style={styles.headerActions}>
            {!compact && (
              <View style={styles.sourceMeta}>
                <Text style={[styles.sourceTitle, darkMode && styles.sourceTitleDark]}>{siteCopy.sourceTitle}</Text>
                <View style={styles.liveBadge}>
                  <Animated.View style={[styles.liveDot, { opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35, 1] }) }]} />
                  <Text style={[styles.sourceText, darkMode && styles.sourceTextDark]}>{siteCopy.sourceText}</Text>
                </View>
              </View>
            )}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={darkMode ? 'Activar modo claro' : 'Activar modo oscuro'}
              onPress={() => setDarkMode((value) => !value)}
              style={[styles.themeButton, darkMode && styles.themeButtonDark]}
            >
              <Text style={[styles.themeButtonText, darkMode && styles.themeButtonTextDark]}>{darkMode ? '☀ Claro' : '☾ Oscuro'}</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.titleSection}>
          <View style={{ flex: 1 }}>
            <Text style={styles.sectionEyebrow}>{siteCopy.eyebrow}</Text>
            <Text style={[styles.pageTitle, darkMode && styles.pageTitleDark]}>{siteCopy.title}</Text>
            <Text style={[styles.pageSubtitle, darkMode && styles.pageSubtitleDark]}>{siteCopy.subtitle}</Text>
          </View>
          {!compact && (
            <View style={[styles.dataContract, darkMode && styles.dataContractDark]}>
              <Text style={styles.dataContractLabel}>DATOS UTILIZADOS</Text>
              <Text style={[styles.dataContractValue, darkMode && styles.dataContractValueDark]}>{siteCopy.contract}</Text>
            </View>
          )}
        </View>

        <View style={styles.contextActions}>
          <Pressable onPress={() => setCameraSelectorOpen(true)} style={styles.alertButton}>
            <Text style={styles.alertButtonText}>Cámaras disponibles · {siteOptions.length}</Text>
          </Pressable>
          {activeSite === 'corridor' && (
            <Pressable onPress={() => setVideoStreamOpen(true)} style={[styles.contextButton, darkMode && styles.contextButtonDark]}>
              <Text style={[styles.contextButtonText, darkMode && styles.contextButtonTextDark]}>📹 Ver Streaming</Text>
            </Pressable>
          )}
          <Pressable onPress={() => setHeatmapHelpOpen(true)} style={[styles.contextButton, darkMode && styles.contextButtonDark]}>
            <Text style={[styles.contextButtonText, darkMode && styles.contextButtonTextDark]}>¿Cómo leer el mapa?</Text>
          </Pressable>
          <Pressable onPress={() => setAlertManagerOpen(true)} style={styles.alertButton}>
            <Text style={styles.alertButtonText}>Alertas{alerts.length ? ` · ${alerts.length}` : ''}</Text>
          </Pressable>
          <View style={styles.sessionInfo}>
            {!compact && <Text style={[styles.sessionName, darkMode && styles.sessionNameDark]}>{session.displayName}</Text>}
            <Pressable accessibilityRole="button" onPress={signOut}><Text style={styles.signOutText}>Salir</Text></Pressable>
          </View>
        </View>

        <View style={[styles.alertOverview, darkMode && styles.alertOverviewDark]}>
          <View style={styles.alertOverviewHeader}>
            <View style={{ flex: 1 }}>
              <Text style={styles.alertOverviewEyebrow}>CENTRO DE ALERTAS</Text>
              <Text style={[styles.alertOverviewTitle, darkMode && styles.alertOverviewTitleDark]}>Alertas y reglas por área</Text>
            </View>
            <View style={styles.alertOverviewCounts}>
              <View style={styles.alertOverviewCount}><Text style={styles.alertOverviewCountValue}>{alertOverview.conditionMet}</Text><Text style={styles.alertOverviewCountLabel}>CUMPLEN AHORA</Text></View>
              <View style={styles.alertOverviewCount}><Text style={styles.alertOverviewCountValue}>{alertOverview.waiting}</Text><Text style={styles.alertOverviewCountLabel}>EN ESPERA</Text></View>
            </View>
            <Pressable onPress={() => setAlertManagerOpen(true)} style={styles.alertOverviewOpen}>
              <Text style={styles.alertOverviewOpenText}>Nueva alerta</Text>
            </Pressable>
          </View>
          <Text style={[styles.alertAreaFilterLabel, darkMode && styles.alertOverviewReasonDark]}>FILTRAR HISTORIAL Y CREAR PARA UN ÁREA ESPECÍFICA</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.alertAreaFilters}>
            <Pressable onPress={() => setAlertAreaFilter('all')} style={[styles.alertAreaFilter, darkMode && styles.alertAreaFilterDark, alertAreaFilter === 'all' && styles.alertAreaFilterActive]}>
              <Text style={[styles.alertAreaFilterText, alertAreaFilter === 'all' && styles.alertAreaFilterTextActive]}>Todas · {alerts.length}</Text>
            </Pressable>
            {alertAreas.map((area) => {
              const count = alerts.filter((alert) => alert.areaId === area.id).length;
              return (
                <Pressable key={area.id} onPress={() => setAlertAreaFilter(area.id)} style={[styles.alertAreaFilter, darkMode && styles.alertAreaFilterDark, alertAreaFilter === area.id && styles.alertAreaFilterActive]}>
                  <Text style={[styles.alertAreaFilterText, alertAreaFilter === area.id && styles.alertAreaFilterTextActive]}>{area.name} · {count}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          {alertOverview.recent.length ? (
            <View style={styles.alertOverviewList}>
              {alertOverview.recent.map((alert) => (
                <Pressable key={alert.id} onPress={() => setAlertManagerOpen(true)} style={[styles.alertOverviewItem, darkMode && styles.alertOverviewItemDark]}>
                  <View style={styles.alertOverviewItemTop}>
                    <Text style={[styles.alertOverviewItemTitle, darkMode && styles.alertOverviewItemTitleDark]} numberOfLines={1}>{getAlertTypeLabel(alert.type)} · {alert.areaName}</Text>
                    <Text style={[styles.alertOverviewStatus, alert.status === 'triggered' && styles.alertOverviewStatusActive]}>{getAlertStatusLabel(alert.status)}</Text>
                  </View>
                  <Text style={[styles.alertOverviewReason, darkMode && styles.alertOverviewReasonDark]} numberOfLines={2}>{alert.reason}</Text>
                  <Text style={styles.alertOverviewSchedule}>{getAlertScheduleLabel(alert)}</Text>
                </Pressable>
              ))}
            </View>
          ) : (
            <Text style={[styles.alertOverviewEmpty, darkMode && styles.alertOverviewReasonDark]}>No hay alertas para esta área. Puedes crear una con el botón “Nueva alerta”.</Text>
          )}
        </View>

        <View style={styles.daySelectorRow}>
          <Text style={[styles.summaryScopeLabel, darkMode && styles.summaryScopeLabelDark]}>DÍA DEL MAPA</Text>
          {activeSite === 'simulated' ? (
            <ScrollView horizontal nestedScrollEnabled showsHorizontalScrollIndicator contentContainerStyle={styles.daySelectorButtons}>
              {DAY_NAMES.map((day, index) => (
                <Pill
                  key={day}
                  active={selectedDay === index}
                  label={index === TODAY_DAY_INDEX ? `${day} · Hoy` : day}
                  onPress={() => handleSelectDay(index)}
                />
              ))}
            </ScrollView>
          ) : <Pill active label="Ahora · historial NA" onPress={() => {}} />}
        </View>

        <View style={styles.summaryScopeRow}>
          <Text style={[styles.summaryScopeLabel, darkMode && styles.summaryScopeLabelDark]}>ESTADÍSTICAS</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.summaryScopeButtons}>
            {([
              ['general', 'Generales'],
              ['live', 'En vivo'],
              ['period', 'Periodo seleccionado'],
            ] as const).map(([id, label]) => (
              <Pill
                key={id}
                active={kpiScope === id}
                label={label}
                onPress={() => {
                  setKpiScope(id);
                  if (id === 'live') {
                    setCurrentTime(selectedLatestRecordTime);
                    setMode('moving');
                    setPlaying(false);
                    setComparisonHours(null);
                  }
                  if (id === 'period') setPlaying(false);
                }}
              />
            ))}
          </ScrollView>
        </View>

        {comparisonData && kpiScope === 'period' ? (
          <ComparisonKpiTable
            baselineLabel={comparisonData.baselineLabel}
            comparisonLabel={comparisonData.comparisonLabel}
            rows={comparisonKpiRows}
            dark={darkMode}
          />
        ) : (
          <View style={[styles.kpiRow, compact && styles.kpiRowCompact]}>
            {kpis.map((item) => <KpiCard key={item.label} {...item} dark={darkMode} />)}
          </View>
        )}

        <View style={[styles.workspace, isWide && styles.workspaceWide]}>
          <View style={[styles.mapPanel, darkMode && styles.mapPanelDark, { height: mapHeight }, isWide && styles.mapPanelWide]}>
            <View style={[styles.mapToolbar, darkMode && styles.mapToolbarDark, compact && styles.mapToolbarCompact]}>
              {comparisonHours ? (
                <View style={styles.relativeMetricBadge}>
                  <Text style={styles.relativeMetricLabel}>DISTRIBUCIÓN RELATIVA · B − A</Text>
                </View>
              ) : (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={compact && styles.toolbarScrollCompact} contentContainerStyle={styles.metricGroup}>
                  {METRICS.map((item) => <Pill key={item.id} active={metric === item.id} label={item.label} onPress={() => setMetric(item.id)} />)}
                </ScrollView>
              )}
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={compact && styles.toolbarScrollCompact} contentContainerStyle={styles.layerGroup}>
                <LayerButton active={showObjects} label="Estructuras" onPress={() => setShowObjects((value) => !value)} />
                {!comparisonHours && mode === 'moving' && <LayerButton active={showTrackers} label="Personas" onPress={() => setShowTrackers((value) => !value)} />}
                {!comparisonHours && mode === 'moving' && <LayerButton active={showTrails} label="Recorridos" onPress={() => setShowTrails((value) => !value)} />}
                <LayerButton active={perspective === 'isometric'} label={perspective === 'isometric' ? '2.5D' : 'Superior'} onPress={() => setPerspective((value) => value === 'isometric' ? 'top' : 'isometric')} />
                {zoom > 1 && <LayerButton label="−" onPress={() => setZoom((value) => Math.max(1, Number((value - 0.2).toFixed(1))))} />}
                {zoom < 1.8 && <LayerButton label="+" onPress={() => setZoom((value) => Math.min(1.8, Number((value + 0.2).toFixed(1))))} />}
              </ScrollView>
            </View>

            <View style={[styles.metricDefinition, darkMode && styles.metricDefinitionDark]}>
              <Text style={[styles.metricDefinitionTitle, darkMode && styles.metricDefinitionTitleDark]}>{comparisonHours ? 'Distribución relativa' : selectedMetric.label}</Text>
              <Text style={[styles.metricDefinitionText, darkMode && styles.metricDefinitionTextDark]}>
                {comparisonHours
                  ? 'Cambio de participación espacial por cada 100 recorridos; azul disminuye y naranja aumenta.'
                  : `${selectedMetric.description} ${selectedMode.description}`}
              </Text>
            </View>

            <View style={[styles.encodingRow, darkMode && styles.encodingRowDark, compact && styles.encodingRowCompact]}>
              <View style={styles.encodingCopy}>
                <Text style={[styles.encodingTitle, darkMode && styles.encodingTitleDark]}>CODIFICACIÓN MULTIVARIABLE</Text>
                <Text style={[styles.encodingText, darkMode && styles.encodingTextDark]}>
                  {comparisonHours
                    ? 'Color y altura: magnitud del cambio · blanco: cambio mínimo'
                    : `Color: ${selectedMetric.label.toLowerCase()} · altura: presencia · contornos: concentración · opacidad: cantidad de datos`}
                </Text>
              </View>
              <View style={styles.scaleSelector}>
                <Text style={[styles.scaleSelectorLabel, darkMode && styles.scaleSelectorLabelDark]}>ESCALA · {scaleMode === 'fixed' ? 'FIJA' : 'P95 LOCAL'}</Text>
                <Pill active={scaleMode === 'fixed'} label="Fija" onPress={() => setScaleMode('fixed')} />
                <Pill active={scaleMode === 'adaptive'} label="Adaptativa" onPress={() => setScaleMode('adaptive')} />
              </View>
            </View>

            <View style={[styles.modeRow, darkMode && styles.modeRowDark]}>
              {comparisonHours ? (
                <View style={styles.comparisonBanner}>
                  <View style={styles.comparisonScaleMini}>
                    <View style={[styles.comparisonScalePart, { backgroundColor: '#1759d1' }]} />
                    <View style={[styles.comparisonScalePart, { backgroundColor: '#f5f2eb' }]} />
                    <View style={[styles.comparisonScalePart, { backgroundColor: ORANGE }]} />
                  </View>
                  <Text style={styles.comparisonBannerText}>
                    {String(comparisonHours.comparisonHour).padStart(2, '0')}:00 vs {String(comparisonHours.baselineHour).padStart(2, '0')}:00
                  </Text>
                  <Pressable onPress={() => setComparisonHours(null)}><Text style={styles.comparisonClear}>Quitar</Text></Pressable>
                </View>
              ) : MODE_OPTIONS[metric].map((item) => (
                <Pill
                  key={item.id}
                  active={mode === item.id}
                  label={item.label}
                  onPress={() => {
                    setMode(item.id);
                    if (item.id !== 'moving') setPlaying(false);
                  }}
                />
              ))}
            </View>

            <View style={styles.mapWrap}>
              <FlowMap
                points={visiblePoints}
                currentTime={currentTime}
                metric={metric}
                mode={mode}
                scaleMode={scaleMode}
                scopeSeconds={scopeSeconds}
                selectedZone={selectedZone}
                onSelectZone={handleSelectZone}
                zoom={zoom}
                perspective={perspective}
                showObjects={showObjects}
                showTrackers={showTrackers}
                showTrails={showTrails}
                zones={activeSite !== 'simulated' ? liveZones : undefined}
                objects={activeSite !== 'simulated' ? liveObjects : undefined}
                comparison={comparisonData}
              />
              {selectedStats && (
                <ScrollView
                  nestedScrollEnabled
                  showsVerticalScrollIndicator={compact}
                  style={[styles.zonePopover, compact && styles.zonePopoverCompact]}
                >
                  <View style={styles.zonePopoverTop}>
                    <Text style={styles.zonePopoverEyebrow}>ÁREA SELECCIONADA</Text>
                    <Pressable onPress={() => handleSelectZone(null)}><Text style={styles.zoneClose}>×</Text></Pressable>
                  </View>
                  <Text style={styles.zonePopoverTitle}>{selectedStats.name}</Text>
                  <Text style={styles.zonePopoverDay}>{activeSite === 'simulated' ? `${DAY_NAMES[selectedDay]} · datos del mapa` : 'Ahora · datos en vivo'}</Text>
                  <View style={styles.zonePopoverStats}>
                    <View style={styles.zoneStat}><Text style={styles.zoneNumber}>{selectedZoneDayProfile?.total ?? selectedStats.visitors}</Text><Text style={styles.zoneStatLabel}>{activeSite === 'simulated' ? 'afluencia del día' : 'personas observadas'}</Text></View>
                    <View style={styles.zoneStat}><Text style={styles.zoneNumber}>{selectedZoneDayProfile?.peak.people ?? 'NA'}</Text><Text style={styles.zoneStatLabel}>{selectedZoneDayProfile ? `pico · ${selectedZoneDayProfile.peak.hour}:00` : 'pico histórico'}</Text></View>
                    <View style={styles.zoneStat}><Text style={[styles.zoneNumber, (selectedZoneDayProfile?.changeVsPreviousDay ?? 0) < 0 && styles.zoneNumberNegative]}>{selectedZoneDayProfile ? `${selectedZoneDayProfile.changeVsPreviousDay > 0 ? '+' : ''}${selectedZoneDayProfile.changeVsPreviousDay}%` : 'NA'}</Text><Text style={styles.zoneStatLabel}>vs. día anterior</Text></View>
                  </View>
                  <Text style={styles.zoneHourlyTitle}>PERSONAS ACUMULADAS POR HORA</Text>
                  <View style={styles.zoneHourlyList}>
                    {selectedZoneDayProfile ? selectedZoneDayProfile.hours.map((row) => (
                      <View key={row.hour} style={styles.zoneHourlyRow}>
                        <Text style={styles.zoneHourLabel}>{String(row.hour).padStart(2, '0')}:00</Text>
                        <View style={styles.zoneHourBar}><View style={[styles.zoneHourFill, { width: `${Math.max(5, (row.people / selectedZoneMaxHour) * 100)}%` }]} /></View>
                        <Text style={styles.zoneHourValue}>{row.people}</Text>
                        <Text style={styles.zoneCumulative}>acum. {row.cumulative}</Text>
                      </View>
                    )) : <Text style={styles.zoneMethodNote}>NA · todavía no existe historial horario para este sitio.</Text>}
                  </View>
                  <Text style={styles.zoneMethodNote}>El acumulado cuenta personas distintas observadas en cada hora.</Text>
                  <Pressable onPress={() => setAlertManagerOpen(true)} style={styles.zoneAlertButton}>
                    <Text style={styles.zoneAlertButtonText}>Crear alerta en esta área</Text>
                  </Pressable>
                </ScrollView>
              )}
            </View>

            {comparisonHours ? (
              <View style={[styles.comparisonFooter, darkMode && styles.comparisonFooterDark]}>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.comparisonFooterTitle, darkMode && styles.comparisonFooterTitleDark]}>Redistribución relativa por hora</Text>
                  <Text style={[styles.comparisonFooterText, darkMode && styles.comparisonFooterTextDark]}>Cada hora se pondera por 100 recorridos; la línea de tiempo no modifica este contraste.</Text>
                </View>
                {!isWide && (
                  <Pressable onPress={() => setAnalysisSheet(true)} style={styles.editComparisonButton}>
                    <Text style={styles.editComparisonText}>Editar</Text>
                  </Pressable>
                )}
              </View>
            ) : (
              <>
                <View style={[styles.timelinePanel, darkMode && styles.timelinePanelDark]}>
                  <Pressable onPress={() => { setMode('moving'); setPlaying((value) => !value); }} style={styles.playButton}>
                    <Text style={styles.playText}>{playing && mode === 'moving' ? 'Ⅱ' : '▶'}</Text>
                  </Pressable>
                  {!compact && <View style={styles.timeCopy}><Text style={[styles.timeNow, darkMode && styles.timeNowDark]}>{formatClock(currentTime)}</Text><Text style={styles.timeRange}>08:00—16:00</Text></View>}
                  <Pressable onLayout={(event) => setTimelineWidth(event.nativeEvent.layout.width)} onPress={handleTimelinePress} style={styles.timelineTrack}>
                    <View style={[styles.timelineFill, { width: `${(currentTime / FLOOR.duration) * 100}%` }]} />
                    <View style={[styles.timelineThumb, { left: `${(currentTime / FLOOR.duration) * 100}%` }]} />
                  </Pressable>
                  <View style={styles.speedGroup}>
                    {!compact && <Text style={styles.speedCaption}>PASO</Text>}
                    {PLAYBACK_SPEEDS.map((item) => (
                      <Pressable key={item.value} onPress={() => setSpeed(item.value)} style={[styles.speedButton, speed === item.value && styles.speedActive]}>
                        <Text style={[styles.speedText, speed === item.value && styles.speedTextActive]}>{item.label}</Text>
                      </Pressable>
                    ))}
                  </View>
                </View>

                <View style={[styles.periodRow, darkMode && styles.periodRowDark]}>
                  <Text style={[styles.periodLabel, darkMode && styles.periodLabelDark]}>Ventana</Text>
                  {PERIODS.map((item) => <Pill key={item.seconds} active={period === item.seconds} label={item.label} onPress={() => setPeriod(item.seconds)} />)}
                  <Text style={[styles.timestamp, darkMode && styles.timestampDark]}>{formatClock(currentTime)}</Text>
                </View>
              </>
            )}
          </View>

          {isWide && (
            <AnalysisPanel
              wide
              insights={insights}
              onSelectZone={handleSelectZone}
              selectedDay={selectedDay}
              onSelectDay={handleSelectDay}
              comparison={comparisonHours}
              onApplyComparison={applyComparison}
              onClearComparison={() => setComparisonHours(null)}
            />
          )}
        </View>
      </ScrollView>

      {!isWide && !analysisOpen && (
        <View style={styles.analysisLauncher} {...(Platform.OS === 'web' ? {} : analysisPanResponder.panHandlers)}>
          <View style={styles.analysisGrabber} />
          <Pressable onPress={() => setAnalysisSheet(true)} style={styles.analysisSheetTitleRow}>
            <View>
              <Text style={styles.analysisSheetTitle}>Análisis</Text>
              <Text style={styles.analysisSheetHint}>Toca o desliza hacia arriba para abrir</Text>
            </View>
            <Text style={styles.analysisChevron}>⌃</Text>
          </Pressable>
        </View>
      )}

      <AppModal visible={!isWide && analysisOpen} transparent animationType="none" onRequestClose={() => setAnalysisSheet(false)}>
        <View style={styles.analysisModalRoot}>
          <Animated.View style={[styles.analysisBackdropLayer, { opacity: analysisBackdropOpacity }]}>
            <Pressable style={styles.analysisBackdrop} onPress={() => setAnalysisSheet(false)} />
          </Animated.View>
          <Animated.View style={[styles.analysisSheet, { height: analysisSheetHeight, transform: [{ translateY: analysisTranslateY }] }]}>
          <View style={styles.analysisSheetHandle} {...(Platform.OS === 'web' ? {} : analysisPanResponder.panHandlers)}>
            <View style={styles.analysisGrabber} />
            <Pressable onPress={() => setAnalysisSheet(false)} style={styles.analysisSheetTitleRow}>
              <View>
                <Text style={styles.analysisSheetTitle}>Análisis</Text>
                <Text style={styles.analysisSheetHint}>Modal de trabajo · desliza hacia abajo para cerrar</Text>
              </View>
              <Text style={styles.analysisChevron}>⌄</Text>
            </Pressable>
          </View>
          <ScrollView style={styles.analysisSheetScroll} contentContainerStyle={styles.analysisSheetContent} showsVerticalScrollIndicator={false}>
            <AnalysisPanel
              insights={insights}
              onSelectZone={handleSelectZone}
              selectedDay={selectedDay}
              onSelectDay={handleSelectDay}
              comparison={comparisonHours}
              onApplyComparison={applyComparison}
              onClearComparison={() => setComparisonHours(null)}
            />
          </ScrollView>
        </Animated.View>
        </View>
      </AppModal>

      <HeatmapHelp visible={heatmapHelpOpen} onClose={() => setHeatmapHelpOpen(false)} />
      <AppModal visible={cameraSelectorOpen} transparent animationType="fade" onRequestClose={() => setCameraSelectorOpen(false)}>
        <View style={styles.cameraModalOverlay}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setCameraSelectorOpen(false)} />
          <View style={styles.cameraModalCard}>
            <View style={styles.cameraModalHeader}>
              <View style={{ flex: 1 }}><Text style={styles.cameraModalEyebrow}>FUENTE DE DATOS (API)</Text><Text style={styles.cameraModalTitle}>Cámaras disponibles</Text></View>
              <Pressable onPress={() => setCameraSelectorOpen(false)}><Text style={styles.cameraModalClose}>×</Text></Pressable>
            </View>
            {siteOptions.map((option) => {
              const simulated = option.mode === 'simulated';
              const selected = option.siteId === activeSiteId;
              const name = simulated ? 'Cámara simulada' : liveBootstrap?.cameras[0]?.name ?? option.name;
              return (
                <Pressable key={option.siteId} onPress={() => selectSite(option)} style={[styles.cameraOption, selected && styles.cameraOptionSelected]}>
                  <View style={[styles.cameraStatusDot, option.mode === 'live' && styles.cameraStatusLive]} />
                  <View style={{ flex: 1 }}><Text style={styles.cameraOptionName}>{name}</Text><Text style={styles.cameraOptionMeta}>{option.mode === 'live' ? 'En vivo · API' : 'Datos simulados'}</Text></View>
                  <Text style={styles.cameraOptionAction}>{selected ? 'ACTIVA' : 'ABRIR'}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      </AppModal>

      <AppModal visible={videoStreamOpen} transparent animationType="fade" onRequestClose={() => setVideoStreamOpen(false)}>
        <View style={styles.cameraModalOverlay}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setVideoStreamOpen(false)} />
          <View style={styles.cameraModalCard}>
            <View style={styles.cameraModalHeader}>
              <View style={{ flex: 1 }}>
                <Text style={styles.cameraModalEyebrow}>STREAMING CÁMARA EN VIVO (API)</Text>
                <Text style={styles.cameraModalTitle}>{liveBootstrap?.cameras[0]?.name ?? 'Dell Webcam WB7022'}</Text>
              </View>
              <Pressable onPress={() => setVideoStreamOpen(false)}>
                <Text style={styles.cameraModalClose}>×</Text>
              </Pressable>
            </View>
            <View style={styles.videoStreamContainer}>
              <Image
                source={{ uri: `${getVideoFeedUrl()}?t=${Date.now()}` }}
                style={styles.videoStreamImage}
                resizeMode="contain"
              />
            </View>
            <Text style={styles.videoStreamMeta}>
              Fuente API: {getVideoFeedUrl()} · {liveError ? 'Sin conexión' : 'Transmisión activa'}
            </Text>
          </View>
        </View>
      </AppModal>
      <AlertManager
        visible={alertManagerOpen}
        onClose={() => setAlertManagerOpen(false)}
        areas={alertAreas}
        initialAreaId={alertAreaFilter !== 'all' ? alertAreaFilter : selectedZone}
        session={session}
        alerts={alerts}
        onCreated={handleAlertCreated}
        onUpdated={handleAlertUpdated}
        onDeleted={handleAlertDeleted}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#eef3f4' },
  rootDark: { backgroundColor: '#081318' },
  alertToastWrapper: { position: 'absolute', top: Platform.OS === 'web' ? 16 : 48, left: 14, right: 14, zIndex: 1000, alignItems: 'center' },
  alertToast: { width: '100%', maxWidth: 520, minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: 11, paddingHorizontal: 13, paddingVertical: 11, borderRadius: 17, borderWidth: 1, borderColor: '#ff8a64', backgroundColor: '#10242a', shadowColor: '#07171c', shadowOpacity: 0.24, shadowRadius: 14, shadowOffset: { width: 0, height: 7 }, elevation: 12 },
  alertToastIcon: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center', borderRadius: 17, backgroundColor: ORANGE },
  alertToastIconText: { color: '#ffffff', fontSize: 17, fontWeight: '900' },
  alertToastContent: { flex: 1 },
  alertToastEyebrow: { color: '#ff8a64', fontSize: 7, fontWeight: '900', letterSpacing: 0.7 },
  alertToastTitle: { marginTop: 2, color: '#ffffff', fontSize: 11, fontWeight: '900' },
  alertToastDetail: { marginTop: 3, color: '#9fb0b5', fontSize: 7.5, lineHeight: 11 },
  cameraModalOverlay: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20, backgroundColor: 'rgba(2,10,14,0.62)' },
  cameraModalCard: { width: '100%', maxWidth: 430, padding: 17, borderRadius: 22, borderWidth: 1, borderColor: '#244149', backgroundColor: '#081a20' },
  cameraModalHeader: { marginBottom: 12, flexDirection: 'row', alignItems: 'center' },
  cameraModalEyebrow: { color: ORANGE, fontSize: 7, fontWeight: '900', letterSpacing: 0.7 },
  cameraModalTitle: { marginTop: 3, color: '#ffffff', fontSize: 19, fontWeight: '900' },
  cameraModalClose: { color: '#ffffff', fontSize: 25 },
  cameraOption: { minHeight: 62, marginTop: 7, paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 14, borderWidth: 1, borderColor: '#203b43', backgroundColor: '#10262d' },
  cameraOptionSelected: { borderColor: ORANGE },
  cameraStatusDot: { width: 9, height: 9, borderRadius: 5, backgroundColor: '#789097' },
  cameraStatusLive: { backgroundColor: '#35bd6f' },
  cameraOptionName: { color: '#f4f8f9', fontSize: 10, fontWeight: '900' },
  cameraOptionMeta: { marginTop: 3, color: '#82979d', fontSize: 7.5 },
  cameraOptionAction: { color: ORANGE, fontSize: 7, fontWeight: '900' },
  videoStreamContainer: { width: '100%', height: 260, backgroundColor: '#000000', borderRadius: 14, overflow: 'hidden', justifyContent: 'center', alignItems: 'center' },
  videoStreamImage: { width: '100%', height: '100%' },
  videoStreamMeta: { marginTop: 10, color: '#82979d', fontSize: 8, textAlign: 'center' },
  loadingRoot: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#07171c' },
  loadingText: { color: '#d6e2e5', fontSize: 11, fontWeight: '800' },
  page: { paddingTop: Platform.OS === 'android' ? 52 : 56, paddingHorizontal: 14, paddingBottom: 112, backgroundColor: '#eef3f4' },
  pageDark: { backgroundColor: '#081318' },
  pageWide: { paddingHorizontal: 24, paddingTop: Platform.OS === 'web' ? 20 : Platform.OS === 'android' ? 52 : 38, maxWidth: 1600, width: '100%', alignSelf: 'center' },
  header: { minHeight: 64, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#eef3f4', paddingBottom: 10, zIndex: 20 },
  headerDark: { backgroundColor: '#081318' },
  headerActions: { flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 12, flexShrink: 1 },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 11 },
  logo: { width: 46, height: 46, borderRadius: 23, backgroundColor: '#000000' },
  brandName: { color: DARK, fontSize: 20, fontWeight: '900', letterSpacing: -0.7 },
  brandNameDark: { color: '#f3f7f8' },
  brandTag: { marginTop: 2, color: '#60757b', fontSize: 8, fontWeight: '900', letterSpacing: 0.85 },
  brandTagDark: { color: '#85a0a7' },
  sourceMeta: { alignItems: 'flex-end', gap: 4, flexShrink: 1, maxWidth: '58%' },
  sourceTitle: { color: '#344a50', fontSize: 11, fontWeight: '800', textAlign: 'right' },
  sourceTitleDark: { color: '#d1dde0' },
  liveBadge: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: ORANGE },
  sourceText: { color: '#819095', fontSize: 8, fontWeight: '600' },
  sourceTextDark: { color: '#7f979e' },
  themeButton: { minHeight: 34, justifyContent: 'center', paddingHorizontal: 11, borderRadius: 17, borderWidth: 1, borderColor: '#d4dfe1', backgroundColor: '#ffffff' },
  themeButtonDark: { borderColor: '#2b4148', backgroundColor: '#12252c' },
  themeButtonText: { color: '#344a50', fontSize: 8.5, fontWeight: '900' },
  themeButtonTextDark: { color: '#f2f7f8' },
  titleSection: { minHeight: 82, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 10 },
  sectionEyebrow: { color: TEAL, fontSize: 9, fontWeight: '900', letterSpacing: 1 },
  pageTitle: { color: DARK, marginTop: 3, fontSize: 25, fontWeight: '900', letterSpacing: -0.8 },
  pageTitleDark: { color: '#f4f8f9' },
  pageSubtitle: { marginTop: 3, color: '#718287', fontSize: 10 },
  pageSubtitleDark: { color: '#8ca0a6' },
  dataContract: { maxWidth: 330, paddingHorizontal: 13, paddingVertical: 10, borderRadius: 13, borderWidth: 1, borderColor: '#d9e3e5', backgroundColor: '#f8fbfb' },
  dataContractDark: { borderColor: '#22373e', backgroundColor: '#102128' },
  dataContractLabel: { color: GREEN, fontSize: 8, fontWeight: '900', letterSpacing: 0.7 },
  dataContractValue: { marginTop: 4, color: '#42565c', fontSize: 9, fontWeight: '700' },
  dataContractValueDark: { color: '#b6c7cc' },
  contextActions: { minHeight: 38, marginBottom: 8, flexDirection: 'row', alignItems: 'center', gap: 7 },
  contextButton: { minHeight: 34, justifyContent: 'center', paddingHorizontal: 11, borderRadius: 10, borderWidth: 1, borderColor: '#d3dfe1', backgroundColor: '#ffffff' },
  contextButtonDark: { borderColor: '#294149', backgroundColor: '#10262d' },
  contextButtonText: { color: '#40565c', fontSize: 8.5, fontWeight: '900' },
  contextButtonTextDark: { color: '#eaf1f2' },
  alertButton: { minHeight: 34, justifyContent: 'center', paddingHorizontal: 12, borderRadius: 10, backgroundColor: ORANGE },
  alertButtonText: { color: '#ffffff', fontSize: 8.5, fontWeight: '900' },
  alertOverview: { marginBottom: 10, padding: 12, borderRadius: 17, borderWidth: 1, borderColor: '#d9e3e5', backgroundColor: '#ffffff' },
  alertOverviewDark: { borderColor: '#21363d', backgroundColor: '#102128' },
  alertOverviewHeader: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  alertOverviewEyebrow: { color: ORANGE, fontSize: 7, fontWeight: '900', letterSpacing: 0.7 },
  alertOverviewTitle: { marginTop: 2, color: DARK, fontSize: 13, fontWeight: '900' },
  alertOverviewTitleDark: { color: '#f2f7f8' },
  alertOverviewCounts: { flexDirection: 'row', gap: 5 },
  alertOverviewCount: { minWidth: 60, paddingHorizontal: 7, paddingVertical: 6, alignItems: 'center', borderRadius: 9, backgroundColor: '#f1f5f5' },
  alertOverviewCountValue: { color: ORANGE, fontSize: 13, fontWeight: '900' },
  alertOverviewCountLabel: { color: '#7c8d92', fontSize: 5.5, fontWeight: '900' },
  alertOverviewOpen: { minHeight: 32, justifyContent: 'center', paddingHorizontal: 10, borderRadius: 9, backgroundColor: DARK },
  alertOverviewOpenText: { color: '#ffffff', fontSize: 7.5, fontWeight: '900' },
  alertAreaFilterLabel: { marginTop: 10, color: '#718287', fontSize: 6.5, fontWeight: '900', letterSpacing: 0.45 },
  alertAreaFilters: { marginTop: 6, gap: 5, paddingRight: 8 },
  alertAreaFilter: { minHeight: 30, justifyContent: 'center', paddingHorizontal: 10, borderRadius: 9, borderWidth: 1, borderColor: '#d8e2e4', backgroundColor: '#f4f7f7' },
  alertAreaFilterDark: { borderColor: '#294149', backgroundColor: '#13282f' },
  alertAreaFilterActive: { borderColor: ORANGE, backgroundColor: ORANGE },
  alertAreaFilterText: { color: '#687b81', fontSize: 7.3, fontWeight: '900' },
  alertAreaFilterTextActive: { color: '#ffffff' },
  alertOverviewList: { marginTop: 9, flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  alertOverviewItem: { flex: 1, minWidth: 180, padding: 10, borderRadius: 12, borderWidth: 1, borderColor: '#e0e7e9', backgroundColor: '#f8fafa' },
  alertOverviewItemDark: { borderColor: '#294149', backgroundColor: '#13282f' },
  alertOverviewItemTop: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  alertOverviewItemTitle: { flex: 1, color: '#263b41', fontSize: 8.5, fontWeight: '900' },
  alertOverviewItemTitleDark: { color: '#edf4f5' },
  alertOverviewStatus: { maxWidth: 92, color: '#d08a20', fontSize: 6, fontWeight: '900', textAlign: 'right' },
  alertOverviewStatusActive: { color: ORANGE },
  alertOverviewReason: { marginTop: 4, color: '#708187', fontSize: 7.5, lineHeight: 11 },
  alertOverviewReasonDark: { color: '#8ea2a8' },
  alertOverviewSchedule: { marginTop: 5, color: TEAL, fontSize: 6.8, fontWeight: '900' },
  alertOverviewEmpty: { marginTop: 8, color: '#718287', fontSize: 8.5 },
  sessionInfo: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 8 },
  sessionName: { color: '#6f8288', fontSize: 8, fontWeight: '800' },
  sessionNameDark: { color: '#8da2a8' },
  signOutText: { color: ORANGE, fontSize: 8.5, fontWeight: '900' },
  daySelectorRow: { minHeight: 42, marginBottom: 5, flexDirection: 'row', alignItems: 'center', gap: 9 },
  daySelectorButtons: { gap: 5, alignItems: 'center', paddingRight: 8 },
  summaryScopeRow: { minHeight: 42, marginBottom: 8, flexDirection: 'row', alignItems: 'center', gap: 9 },
  summaryScopeLabel: { color: '#6f8288', fontSize: 8, fontWeight: '900', letterSpacing: 0.8 },
  summaryScopeLabelDark: { color: '#8ba0a6' },
  summaryScopeButtons: { gap: 5, alignItems: 'center' },
  kpiRow: { flexDirection: 'row', gap: 9, marginBottom: 11 },
  kpiRowCompact: { flexWrap: 'wrap' },
  kpiCard: { flex: 1, minWidth: 145, minHeight: 91, padding: 13, borderRadius: 17, backgroundColor: '#ffffff', borderWidth: 1, borderColor: '#dfe7e9', overflow: 'hidden' },
  kpiCardDark: { backgroundColor: '#102128', borderColor: '#21363d' },
  kpiLine: { position: 'absolute', top: 0, left: 0, right: 0, height: 3 },
  kpiLabel: { marginTop: 2, color: '#74858a', fontSize: 8, fontWeight: '900', letterSpacing: 0.7 },
  kpiLabelDark: { color: '#8ea2a8' },
  kpiValue: { marginTop: 7, color: DARK, fontSize: 23, fontWeight: '900', letterSpacing: -0.6 },
  kpiValueDark: { color: '#f4f8f9' },
  kpiDetail: { marginTop: 3, color: '#77898e', fontSize: 8, fontWeight: '600' },
  kpiDetailDark: { color: '#81969c' },
  comparisonKpiTable: { marginBottom: 11, borderRadius: 17, backgroundColor: '#ffffff', borderWidth: 1, borderColor: '#dfe7e9', overflow: 'hidden' },
  comparisonKpiTableDark: { backgroundColor: '#102128', borderColor: '#21363d' },
  comparisonKpiRow: { minHeight: 34, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 9, borderTopWidth: 1, borderTopColor: '#edf1f2' },
  comparisonKpiHeader: { minHeight: 31, backgroundColor: '#f4f7f7', borderTopWidth: 0 },
  comparisonKpiHeaderDark: { backgroundColor: '#152a31' },
  comparisonKpiRowDark: { borderTopColor: '#21363d' },
  comparisonKpiCell: { flex: 1, color: '#708187', fontSize: 7, fontWeight: '900', textAlign: 'right' },
  comparisonKpiCellDark: { color: '#91a5ab' },
  comparisonKpiMetric: { flex: 1.35, textAlign: 'left' },
  comparisonKpiValue: { flex: 1, color: DARK, fontSize: 10, fontWeight: '900', textAlign: 'right' },
  comparisonKpiValueDark: { color: '#f1f6f7' },
  comparisonKpiDelta: { flex: 1, color: ORANGE, fontSize: 10, fontWeight: '900', textAlign: 'right' },
  comparisonKpiDeltaNegative: { color: '#3976c5' },
  workspace: { gap: 11 },
  workspaceWide: { flexDirection: 'row', alignItems: 'stretch' },
  mapPanel: { borderRadius: 23, backgroundColor: '#ffffff', borderWidth: 1, borderColor: '#dce5e7', overflow: 'hidden' },
  mapPanelDark: { backgroundColor: '#102128', borderColor: '#21363d' },
  mapPanelWide: { flex: 1 },
  mapToolbar: { minHeight: 54, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 10, borderBottomWidth: 1, borderBottomColor: '#e8edef', gap: 8 },
  mapToolbarDark: { backgroundColor: '#102128', borderBottomColor: '#21363d' },
  mapToolbarCompact: { minHeight: 86, flexDirection: 'column', alignItems: 'stretch', justifyContent: 'center', paddingVertical: 6, gap: 5 },
  toolbarScrollCompact: { width: '100%', flexGrow: 0 },
  metricGroup: { gap: 4, alignItems: 'center' },
  layerGroup: { gap: 4, alignItems: 'center' },
  relativeMetricBadge: { minHeight: 31, justifyContent: 'center', paddingHorizontal: 11, borderRadius: 10, backgroundColor: '#eef2f4', borderWidth: 1, borderColor: '#d1dcdf' },
  relativeMetricLabel: { color: '#20363c', fontSize: 8, fontWeight: '900', letterSpacing: 0.35 },
  pill: { minHeight: 31, justifyContent: 'center', paddingHorizontal: 11, borderRadius: 10, backgroundColor: '#e9eef0' },
  pillActive: { backgroundColor: '#ffffff', borderColor: '#cfdadd', borderWidth: 1, shadowColor: DARK, shadowOpacity: 0.07, shadowRadius: 7, shadowOffset: { width: 0, height: 3 }, elevation: 1 },
  pillText: { color: '#687b80', fontSize: 9, fontWeight: '800' },
  pillTextActive: { color: DARK },
  layerButton: { minHeight: 29, justifyContent: 'center', paddingHorizontal: 8, borderRadius: 9, borderWidth: 1, borderColor: '#dce4e6', backgroundColor: '#ffffff' },
  layerButtonActive: { backgroundColor: '#e7f6f7', borderColor: '#9dcfd5' },
  layerButtonText: { color: '#819095', fontSize: 8, fontWeight: '800' },
  layerButtonTextActive: { color: '#176f7a' },
  metricDefinition: { minHeight: 42, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, backgroundColor: '#f8fafb', borderBottomWidth: 1, borderBottomColor: '#edf1f2' },
  metricDefinitionDark: { backgroundColor: '#0d1c22', borderBottomColor: '#21363d' },
  metricDefinitionTitle: { color: DARK, fontSize: 10, fontWeight: '900' },
  metricDefinitionTitleDark: { color: '#f2f7f8' },
  metricDefinitionText: { flex: 1, color: '#75868b', fontSize: 8, lineHeight: 12 },
  metricDefinitionTextDark: { color: '#8ea2a8' },
  encodingRow: { minHeight: 49, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: '#ffffff', borderBottomWidth: 1, borderBottomColor: '#edf1f2' },
  encodingRowDark: { backgroundColor: '#102128', borderBottomColor: '#21363d' },
  encodingRowCompact: { minHeight: 74, alignItems: 'stretch', flexDirection: 'column', gap: 5 },
  encodingCopy: { flex: 1 },
  encodingTitle: { color: '#53666b', fontSize: 7, fontWeight: '900', letterSpacing: 0.55 },
  encodingTitleDark: { color: '#9fb1b6' },
  encodingText: { marginTop: 2, color: '#7a8a8f', fontSize: 7.5, lineHeight: 11 },
  encodingTextDark: { color: '#82979d' },
  scaleSelector: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  scaleSelectorLabel: { color: '#6e8085', fontSize: 7, fontWeight: '900', marginRight: 2 },
  scaleSelectorLabelDark: { color: '#9aadb2' },
  modeRow: { paddingHorizontal: 10, paddingVertical: 7, flexDirection: 'row', gap: 5, backgroundColor: '#fbfcfc', borderBottomWidth: 1, borderBottomColor: '#edf1f2' },
  modeRowDark: { backgroundColor: '#0d1c22', borderBottomColor: '#21363d' },
  comparisonBanner: { flex: 1, minHeight: 32, paddingHorizontal: 9, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 10, backgroundColor: '#f2f4f5', borderWidth: 1, borderColor: '#d9e0e2' },
  comparisonScaleMini: { width: 42, height: 6, flexDirection: 'row', overflow: 'hidden', borderRadius: 4 },
  comparisonScalePart: { flex: 1 },
  comparisonBannerText: { flex: 1, color: DARK, fontSize: 9, fontWeight: '900' },
  comparisonClear: { color: ORANGE, fontSize: 8, fontWeight: '900' },
  comparisonFooter: { minHeight: 58, paddingHorizontal: 13, flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#f8faf9', borderTopWidth: 1, borderTopColor: '#e2e8e5' },
  comparisonFooterDark: { backgroundColor: '#0d1c22', borderTopColor: '#21363d' },
  comparisonFooterTitle: { color: DARK, fontSize: 9, fontWeight: '900' },
  comparisonFooterTitleDark: { color: '#f1f6f7' },
  comparisonFooterText: { marginTop: 3, color: '#7a8984', fontSize: 7.5 },
  comparisonFooterTextDark: { color: '#82979d' },
  editComparisonButton: { paddingHorizontal: 13, paddingVertical: 9, borderRadius: 9, backgroundColor: DARK },
  editComparisonText: { color: '#ffffff', fontSize: 8, fontWeight: '900' },
  mapWrap: { flex: 1, minHeight: 270, paddingHorizontal: 6, position: 'relative' },
  zonePopover: { position: 'absolute', top: 18, right: 15, width: 320, padding: 12, borderRadius: 15, backgroundColor: DARK, shadowColor: '#000', shadowOpacity: 0.22, shadowRadius: 14, shadowOffset: { width: 0, height: 6 }, elevation: 6 },
  zonePopoverCompact: { left: 7, right: 7, width: 'auto', maxHeight: 340 },
  zonePopoverTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  zonePopoverEyebrow: { color: '#79bdc9', fontSize: 8, fontWeight: '900', letterSpacing: 0.7 },
  zoneClose: { color: '#c4d1d5', fontSize: 20, lineHeight: 20 },
  zonePopoverTitle: { marginTop: 5, color: '#ffffff', fontSize: 16, fontWeight: '900' },
  zonePopoverDay: { marginTop: 2, color: '#7e969d', fontSize: 7.5, fontWeight: '800' },
  zonePopoverStats: { marginTop: 10, flexDirection: 'row', gap: 8 },
  zoneStat: { flex: 1, minWidth: 0 },
  zoneNumber: { color: '#ffffff', fontSize: 15, fontWeight: '900' },
  zoneNumberNegative: { color: '#6fa5ed' },
  zoneStatLabel: { color: '#91a6ad', fontSize: 6.5, lineHeight: 9, marginTop: 1 },
  zoneHourlyTitle: { marginTop: 11, color: '#ff8b63', fontSize: 7, fontWeight: '900', letterSpacing: 0.55 },
  zoneHourlyList: { marginTop: 6, gap: 3 },
  zoneHourlyRow: { minHeight: 16, flexDirection: 'row', alignItems: 'center', gap: 5 },
  zoneHourLabel: { width: 29, color: '#9eb0b5', fontSize: 6.5, fontWeight: '800' },
  zoneHourBar: { flex: 1, height: 5, overflow: 'hidden', borderRadius: 3, backgroundColor: '#263d44' },
  zoneHourFill: { height: 5, borderRadius: 3, backgroundColor: ORANGE },
  zoneHourValue: { width: 20, color: '#ffffff', fontSize: 7, fontWeight: '900', textAlign: 'right' },
  zoneCumulative: { width: 48, color: '#789096', fontSize: 6.2, textAlign: 'right' },
  zoneMethodNote: { marginTop: 7, color: '#70868c', fontSize: 6.5, lineHeight: 9 },
  zoneAlertButton: { minHeight: 33, marginTop: 11, alignItems: 'center', justifyContent: 'center', borderRadius: 9, backgroundColor: ORANGE },
  zoneAlertButtonText: { color: '#ffffff', fontSize: 8, fontWeight: '900' },
  timelinePanel: { height: 52, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 11, borderTopWidth: 1, borderTopColor: '#e7edef' },
  timelinePanelDark: { backgroundColor: '#102128', borderTopColor: '#21363d' },
  playButton: { width: 33, height: 33, borderRadius: 17, backgroundColor: ORANGE, alignItems: 'center', justifyContent: 'center', shadowColor: ORANGE, shadowOpacity: 0.24, shadowRadius: 7, shadowOffset: { width: 0, height: 3 }, elevation: 2 },
  playText: { color: '#ffffff', fontSize: 11, fontWeight: '900' },
  timeCopy: { width: 55 },
  timeNow: { color: DARK, fontSize: 12, fontWeight: '900' },
  timeNowDark: { color: '#f3f7f8' },
  timeRange: { marginTop: 1, color: '#98a5a9', fontSize: 7 },
  timelineTrack: { flex: 1, height: 24, justifyContent: 'center', backgroundColor: '#e6ecee', borderRadius: 3 },
  timelineFill: { height: 4, borderRadius: 3, backgroundColor: ORANGE },
  timelineThumb: { position: 'absolute', marginLeft: -5, width: 11, height: 11, borderRadius: 6, backgroundColor: '#ffffff', borderWidth: 3, borderColor: ORANGE },
  speedGroup: { flexDirection: 'row', padding: 3, borderRadius: 9, backgroundColor: '#edf1f2' },
  speedCaption: { alignSelf: 'center', marginHorizontal: 4, color: '#8a999d', fontSize: 6.5, fontWeight: '900' },
  speedButton: { paddingHorizontal: 7, height: 24, borderRadius: 7, justifyContent: 'center' },
  speedActive: { backgroundColor: '#ffffff' },
  speedText: { color: '#7d8d92', fontSize: 8, fontWeight: '800' },
  speedTextActive: { color: ORANGE },
  periodRow: { minHeight: 44, paddingHorizontal: 11, flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#f9fbfb', borderTopWidth: 1, borderTopColor: '#edf1f2' },
  periodRowDark: { backgroundColor: '#0d1c22', borderTopColor: '#21363d' },
  periodLabel: { color: '#74858a', fontSize: 9, fontWeight: '800', marginRight: 2 },
  periodLabelDark: { color: '#91a5ab' },
  timestamp: { marginLeft: 'auto', color: DARK, fontSize: 11, fontWeight: '900' },
  timestampDark: { color: '#f3f7f8' },
  swipeHint: { height: 53, alignItems: 'center', justifyContent: 'center', gap: 3 },
  swipeHandle: { width: 42, height: 4, borderRadius: 2, backgroundColor: '#bdc9cc' },
  swipeText: { color: '#829196', fontSize: 8, fontWeight: '900', letterSpacing: 0.75 },
  swipeArrow: { color: ORANGE, fontSize: 13, lineHeight: 13 },
  analysisLauncher: { position: Platform.OS === 'web' ? 'fixed' as any : 'absolute', left: 0, right: 0, bottom: 0, zIndex: 100, height: 76, paddingTop: 9, paddingHorizontal: 18, borderTopLeftRadius: 24, borderTopRightRadius: 24, backgroundColor: '#091c22', shadowColor: '#000000', shadowOpacity: 0.22, shadowRadius: 14, shadowOffset: { width: 0, height: -4 }, elevation: 18 },
  analysisModalRoot: { flex: 1, justifyContent: 'flex-end' },
  analysisBackdropLayer: { ...StyleSheet.absoluteFillObject },
  analysisBackdrop: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, backgroundColor: 'rgba(2,12,16,0.48)' },
  analysisSheet: { width: '100%', borderTopLeftRadius: 24, borderTopRightRadius: 24, backgroundColor: DARK, shadowColor: '#000000', shadowOpacity: 0.28, shadowRadius: 18, shadowOffset: { width: 0, height: -5 }, elevation: 20, overflow: 'hidden' },
  analysisSheetHandle: { height: 76, paddingTop: 9, paddingHorizontal: 18, backgroundColor: '#091c22', borderBottomWidth: 1, borderBottomColor: '#19323a' },
  analysisGrabber: { width: 44, height: 5, alignSelf: 'center', borderRadius: 3, backgroundColor: '#60747a' },
  analysisSheetTitleRow: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  analysisSheetTitle: { color: '#ffffff', fontSize: 17, fontWeight: '900' },
  analysisSheetHint: { marginTop: 2, color: '#7f949b', fontSize: 8 },
  analysisChevron: { color: ORANGE, fontSize: 24, fontWeight: '900' },
  analysisSheetScroll: { flex: 1, backgroundColor: DARK },
  analysisSheetContent: { paddingBottom: 32 },
  insightsPanel: { padding: 15, borderRadius: 23, backgroundColor: DARK, borderWidth: 1, borderColor: '#10282f' },
  insightsPanelWide: { width: 360 },
  insightHeadingRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 },
  insightEyebrow: { color: '#63bfd0', fontSize: 8, fontWeight: '900', letterSpacing: 1 },
  insightHeading: { marginTop: 4, color: '#ffffff', fontSize: 20, fontWeight: '900', letterSpacing: -0.55 },
  insightSubheading: { marginTop: 3, color: '#879da4', fontSize: 8 },
  derivedBadge: { paddingHorizontal: 8, paddingVertical: 6, borderRadius: 9, backgroundColor: '#153039' },
  derivedBadgeText: { color: '#55c1d3', fontSize: 7, fontWeight: '900' },
  insightList: { marginTop: 14, gap: 9 },
  intervalCard: { marginTop: 14, padding: 13, borderRadius: 17, backgroundColor: '#0d2027', borderWidth: 1, borderColor: '#1b343c' },
  intervalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  intervalTitle: { color: '#f0f6f8', fontSize: 10, fontWeight: '900' },
  intervalMeta: { color: '#6dbac8', fontSize: 7, fontWeight: '900' },
  barChart: { height: 125, marginTop: 11, flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-around', gap: 8 },
  barColumn: { flex: 1, alignItems: 'center', justifyContent: 'flex-end' },
  barValue: { marginBottom: 4, color: '#8fa4aa', fontSize: 8, fontWeight: '800' },
  bar: { width: '62%', maxWidth: 28, borderRadius: 6, backgroundColor: '#28414a' },
  barPeak: { backgroundColor: ORANGE },
  barLabel: { marginTop: 5, color: '#82969d', fontSize: 7 },
  intervalFooter: { marginTop: 10, paddingTop: 9, borderTopWidth: 1, borderTopColor: '#1c343c', flexDirection: 'row', justifyContent: 'space-between' },
  intervalFooterLabel: { color: '#81969d', fontSize: 8, fontWeight: '700' },
  intervalFooterValue: { color: ORANGE, fontSize: 9, fontWeight: '900' },
  truthCard: { marginTop: 13, padding: 11, borderRadius: 14, borderWidth: 1, borderColor: '#1b343c', flexDirection: 'row', gap: 9, backgroundColor: '#0b1d23' },
  truthIcon: { width: 28, height: 28, borderRadius: 9, alignItems: 'center', justifyContent: 'center', backgroundColor: '#123523' },
  truthIconText: { color: GREEN, fontSize: 13, fontWeight: '900' },
  truthTitle: { color: '#eff7f8', fontSize: 9, fontWeight: '900' },
  truthText: { marginTop: 3, color: '#81969d', fontSize: 8, lineHeight: 12 },
});
