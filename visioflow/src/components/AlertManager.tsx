import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, PanResponder, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import Slider from '@react-native-community/slider';
import { AppModal } from './AppModal';
import { DAY_NAMES } from '../history';
import { AlertScheduleMode, deleteLocalAlert, getAlertScheduleLabel, getAlertStatusLabel, getAlertTypeLabel, LocalAlert, LocalSession } from '../localStore';

type AreaOption = { id: string; name: string; peopleCount: number };

const TODAY_DAY_INDEX = (new Date().getDay() + 6) % 7;

function SwipeAlertRow({ alert, onDelete, onEdit }: { alert: LocalAlert; onDelete: () => void; onEdit: () => void }) {
  const translateX = useRef(new Animated.Value(0)).current;
  const responder = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: (_, gesture) => Math.abs(gesture.dx) > 8 && Math.abs(gesture.dx) > Math.abs(gesture.dy),
    onPanResponderMove: (_, gesture) => translateX.setValue(Math.max(-150, Math.min(0, gesture.dx))),
    onPanResponderRelease: (_, gesture) => {
      if (gesture.dx < -125) {
        Animated.timing(translateX, { toValue: -180, duration: 140, useNativeDriver: true }).start(onDelete);
        return;
      }
      Animated.spring(translateX, { toValue: gesture.dx < -42 ? -86 : 0, useNativeDriver: true }).start();
    },
  }), [onDelete, translateX]);
  return (
    <View style={styles.swipeRow}>
      <Pressable accessibilityLabel={`Eliminar ${alert.areaName}`} onPress={onDelete} style={styles.deleteAction}>
        <Text style={styles.deleteActionText}>Eliminar</Text>
      </Pressable>
      <Animated.View style={{ transform: [{ translateX }] }} {...responder.panHandlers}>
        <Pressable onPress={onEdit} style={styles.alertRow}>
          <View style={styles.alertDot} />
          <View style={{ flex: 1 }}>
            <Text style={styles.alertTitle}>{getAlertTypeLabel(alert.type)} · {alert.areaName}</Text>
            <Text style={styles.alertReason}>{alert.reason}</Text>
            <Text style={styles.alertMeta}>{getAlertScheduleLabel(alert)} · {new Date(alert.createdAt).toLocaleString('es-MX')} · {alert.peopleCountSnapshot} personas</Text>
          </View>
          <Text style={[styles.status, alert.status === 'triggered' && styles.statusTriggered, alert.status === 'resolved' && styles.statusResolved]}>{getAlertStatusLabel(alert.status)}</Text>
        </Pressable>
      </Animated.View>
    </View>
  );
}

function localDateInputValue() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function validDateInput(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T12:00:00`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function AlertManager({
  visible,
  onClose,
  areas,
  initialAreaId,
  session,
  alerts,
  onCreated,
  onUpdated,
  onDeleted,
}: {
  visible: boolean;
  onClose: () => void;
  areas: AreaOption[];
  initialAreaId: string | null;
  session: LocalSession;
  alerts: LocalAlert[];
  onCreated: (alert: LocalAlert) => void | Promise<void>;
  onUpdated: (alert: LocalAlert) => void | Promise<void>;
  onDeleted: (alertId: string) => void | Promise<void>;
}) {
  const [areaId, setAreaId] = useState(initialAreaId ?? areas[0]?.id ?? '');
  const [flowRule, setFlowRule] = useState<'crowding' | 'low_flow'>('crowding');
  const [thresholdPeople, setThresholdPeople] = useState(20);
  const [scheduleMode, setScheduleMode] = useState<Exclude<AlertScheduleMode, 'immediate'>>('all_days');
  const [scheduleDay, setScheduleDay] = useState(TODAY_DAY_INDEX);
  const [scheduleDate, setScheduleDate] = useState(localDateInputValue());
  const [editingAlertId, setEditingAlertId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const area = useMemo(() => areas.find((item) => item.id === areaId), [areaId, areas]);

  useEffect(() => {
    if (visible && initialAreaId) setAreaId(initialAreaId);
  }, [initialAreaId, visible]);

  const saveRule = async () => {
    if (!area) {
      setError('Selecciona un área antes de crear la alerta.');
      return;
    }
    if (scheduleMode === 'date' && !validDateInput(scheduleDate)) {
      setError('Escribe una fecha válida con el formato AAAA-MM-DD.');
      return;
    }
    if (scheduleMode === 'date' && scheduleDate < localDateInputValue()) {
      setError('La fecha específica debe ser hoy o un día futuro.');
      return;
    }
    const conditionMet = flowRule === 'crowding'
      ? area.peopleCount >= thresholdPeople
      : area.peopleCount <= thresholdPeople;
    const scheduleAppliesToday = scheduleMode === 'all_days'
      || (scheduleMode === 'weekly' && scheduleDay === TODAY_DAY_INDEX)
      || (scheduleMode === 'date' && scheduleDate === localDateInputValue());
    setSaving(true);
    const values = {
      areaId: area.id,
      areaName: area.name,
      type: flowRule,
      reason: flowRule === 'crowding'
        ? `Avisar cuando haya ${thresholdPeople} personas o más.`
        : `Avisar cuando haya ${thresholdPeople} personas o menos.`,
      status: conditionMet && scheduleAppliesToday ? 'triggered' : 'watching',
      thresholdPeople,
      scheduleMode,
      scheduleDay: scheduleMode === 'weekly' ? scheduleDay : undefined,
      scheduleDate: scheduleMode === 'date' ? scheduleDate : undefined,
      peopleCountSnapshot: area.peopleCount,
      createdBy: session.username,
    } as const;
    try {
      const existing = alerts.find((alert) => alert.id === editingAlertId);
      if (existing) {
        const updated = { ...existing, ...values } as LocalAlert;
        await onUpdated(updated);
      } else {
        const created: LocalAlert = {
          ...values,
          id: `alert-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          createdAt: new Date().toISOString(),
        };
        await onCreated(created);
      }
      setError('');
      setEditingAlertId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No fue posible guardar la alerta.');
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (alert: LocalAlert) => {
    if (alert.type !== 'crowding' && alert.type !== 'low_flow') return;
    setEditingAlertId(alert.id);
    setAreaId(alert.areaId);
    setFlowRule(alert.type);
    setThresholdPeople(alert.thresholdPeople ?? 20);
    setScheduleMode(alert.scheduleMode === 'weekly' || alert.scheduleMode === 'date' ? alert.scheduleMode : 'all_days');
    setScheduleDay(alert.scheduleDay ?? TODAY_DAY_INDEX);
    setScheduleDate(alert.scheduleDate ?? localDateInputValue());
  };

  const removeAlert = async (alertId: string) => {
    try {
      await onDeleted(alertId);
      await deleteLocalAlert(alertId);
      if (editingAlertId === alertId) setEditingAlertId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No fue posible eliminar la alerta.');
    }
  };

  return (
    <AppModal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.eyebrow}>GESTOR DE ALERTAS</Text>
              <Text style={styles.title}>Crear y editar alertas</Text>
              <Text style={styles.subtitle}>Reglas automáticas por área.</Text>
            </View>
            <Pressable accessibilityLabel="Cerrar alertas" onPress={onClose} style={styles.close}><Text style={styles.closeText}>×</Text></Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
            <View style={styles.statusGuide}>
              <Text style={styles.statusGuideTitle}>ESTADOS DE UNA REGLA</Text>
              <Text style={styles.statusGuideText}><Text style={styles.statusGuideStrong}>En espera:</Text> está guardada y el conteo todavía no cumple el umbral.</Text>
              <Text style={styles.statusGuideText}><Text style={styles.statusGuideStrong}>Condición cumplida:</Text> el último registro ya cumple la regla y se mostró el aviso.</Text>
            </View>
            <Text style={styles.sectionLabel}>1 · ELIGE EL ÁREA ESPECÍFICA</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
              {areas.map((item) => (
                <Pressable key={item.id} onPress={() => setAreaId(item.id)} style={[styles.chip, areaId === item.id && styles.chipActive]}>
                  <Text style={[styles.chipText, areaId === item.id && styles.chipTextActive]}>{item.name}</Text>
                </Pressable>
              ))}
            </ScrollView>
            <View style={styles.selectedAreaCard}>
              <View style={{ flex: 1 }}>
                <Text style={styles.selectedAreaLabel}>LA REGLA SE APLICARÁ ÚNICAMENTE EN</Text>
                <Text style={styles.selectedAreaName}>{area?.name ?? 'Selecciona un área'}</Text>
              </View>
              <View style={styles.selectedAreaCount}>
                <Text style={styles.selectedAreaCountValue}>{area?.peopleCount ?? 0}</Text>
                <Text style={styles.selectedAreaCountLabel}>AHORA</Text>
              </View>
            </View>

            <Text style={styles.sectionLabel}>2 · DEFINE UN UMBRAL DE PERSONAS</Text>
            <View style={styles.ruleCard}>
              <View style={styles.ruleToggle}>
                <Pressable onPress={() => setFlowRule('crowding')} style={[styles.ruleToggleButton, flowRule === 'crowding' && styles.ruleToggleActive]}>
                  <Text style={[styles.ruleToggleText, flowRule === 'crowding' && styles.ruleToggleTextActive]}>Alta afluencia</Text>
                </Pressable>
                <Pressable onPress={() => setFlowRule('low_flow')} style={[styles.ruleToggleButton, flowRule === 'low_flow' && styles.ruleToggleActive]}>
                  <Text style={[styles.ruleToggleText, flowRule === 'low_flow' && styles.ruleToggleTextActive]}>Baja afluencia</Text>
                </Pressable>
              </View>
              <View style={styles.thresholdHeader}>
                <View>
                  <Text style={styles.thresholdLabel}>{flowRule === 'crowding' ? 'AVISAR AL LLEGAR A' : 'AVISAR AL BAJAR A'}</Text>
                  <Text style={styles.thresholdValue}>{thresholdPeople} <Text style={styles.thresholdUnit}>personas</Text></Text>
                </View>
                <View style={styles.currentCountBadge}>
                  <Text style={styles.currentCountLabel}>ÚLTIMO REGISTRO</Text>
                  <Text style={styles.currentCountValue}>{area?.peopleCount ?? 0}</Text>
                </View>
              </View>
              <Slider
                accessibilityLabel="Umbral de personas"
                minimumValue={1}
                maximumValue={120}
                step={1}
                value={thresholdPeople}
                onValueChange={(value) => setThresholdPeople(Math.round(value))}
                minimumTrackTintColor="#ff5a2a"
                maximumTrackTintColor="#2a4249"
                thumbTintColor="#ff6b3d"
                style={styles.slider}
              />
              <View style={styles.sliderScale}><Text style={styles.sliderScaleText}>1</Text><Text style={styles.sliderScaleText}>120 personas</Text></View>
              <Text style={styles.ruleExplanation}>
                {flowRule === 'crowding'
                  ? `La alerta se activa cuando ${area?.name ?? 'el área'} tenga ${thresholdPeople} personas o más.`
                  : `La alerta se activa cuando ${area?.name ?? 'el área'} tenga ${thresholdPeople} personas o menos.`}
              </Text>
              <Text style={styles.scheduleTitle}>CUÁNDO SE EVALÚA ESTA REGLA</Text>
              <View style={styles.scheduleModes}>
                {([['all_days', 'Todos los días'], ['weekly', 'Semanal'], ['date', 'Fecha exacta']] as const).map(([id, label]) => (
                  <Pressable key={id} onPress={() => setScheduleMode(id)} style={[styles.scheduleModeButton, scheduleMode === id && styles.scheduleModeActive]}>
                    <Text style={[styles.scheduleModeText, scheduleMode === id && styles.scheduleModeTextActive]}>{label}</Text>
                  </Pressable>
                ))}
              </View>
              {scheduleMode === 'weekly' && (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.weekDays}>
                  {DAY_NAMES.map((day, index) => (
                    <Pressable key={day} onPress={() => setScheduleDay(index)} style={[styles.weekDay, scheduleDay === index && styles.weekDayActive]}>
                      <Text style={[styles.weekDayText, scheduleDay === index && styles.weekDayTextActive]}>{day}</Text>
                    </Pressable>
                  ))}
                </ScrollView>
              )}
              {scheduleMode === 'date' && (
                <TextInput
                  accessibilityLabel="Fecha específica de la alerta"
                  maxLength={10}
                  onChangeText={setScheduleDate}
                  placeholder="AAAA-MM-DD"
                  placeholderTextColor="#6f858c"
                  style={styles.dateInput}
                  value={scheduleDate}
                />
              )}
              <Text style={styles.scheduleExplanation}>
                {scheduleMode === 'all_days'
                  ? 'El umbral se revisará todos los días cuando lleguen nuevos registros.'
                  : scheduleMode === 'weekly'
                    ? `El umbral se revisará cada ${DAY_NAMES[scheduleDay]}.`
                    : `El umbral solo se revisará el ${scheduleDate || 'día indicado'}.`}
              </Text>
              <Pressable disabled={saving} onPress={saveRule} style={[styles.ruleSaveButton, saving && styles.disabled]}>
                <Text style={styles.ruleSaveText}>{editingAlertId ? 'Guardar cambios' : 'Guardar regla de afluencia'}</Text>
              </Pressable>
            </View>
            {!!error && <Text style={styles.error}>{error}</Text>}

            <View style={styles.historyHeader}>
              <Text style={styles.sectionLabel}>ALERTAS RECIENTES</Text>
              <Text style={styles.historyCount}>{alerts.length}</Text>
            </View>
            {alerts.length === 0 ? (
              <View style={styles.empty}><Text style={styles.emptyTitle}>Aún no hay alertas</Text><Text style={styles.emptyText}>Las alertas creadas en este dispositivo aparecerán aquí.</Text></View>
            ) : alerts.slice(0, 20).map((alert) => (
              <SwipeAlertRow key={alert.id} alert={alert} onDelete={() => void removeAlert(alert.id)} onEdit={() => startEdit(alert)} />
            ))}
          </ScrollView>
        </View>
      </View>
    </AppModal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(2,10,14,0.55)' },
  sheet: { width: '100%', maxHeight: '92%', borderTopLeftRadius: 28, borderTopRightRadius: 28, borderWidth: 1, borderColor: '#1d3941', backgroundColor: '#081a20', overflow: 'hidden' },
  grabber: { width: 46, height: 5, marginTop: 9, alignSelf: 'center', borderRadius: 3, backgroundColor: '#60777d' },
  header: { minHeight: 82, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 18, borderBottomWidth: 1, borderBottomColor: '#1a343c' },
  eyebrow: { color: '#ff7851', fontSize: 8, fontWeight: '900', letterSpacing: 0.9 },
  title: { marginTop: 4, color: '#ffffff', fontSize: 20, fontWeight: '900' },
  subtitle: { marginTop: 3, color: '#81969c', fontSize: 8.5 },
  close: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center', borderRadius: 18, backgroundColor: '#142c33' },
  closeText: { color: '#ffffff', fontSize: 23, lineHeight: 24 },
  content: { padding: 17, paddingBottom: 38 },
  localBadge: { alignSelf: 'flex-start', paddingHorizontal: 9, paddingVertical: 6, borderRadius: 8, backgroundColor: '#17323a' },
  localBadgeText: { color: '#64becd', fontSize: 7, fontWeight: '900', letterSpacing: 0.55 },
  statusGuide: { marginTop: 12, padding: 11, borderRadius: 13, borderWidth: 1, borderColor: '#244149', backgroundColor: '#10262d' },
  statusGuideTitle: { color: '#ff8b63', fontSize: 7, fontWeight: '900', letterSpacing: 0.55 },
  statusGuideText: { marginTop: 5, color: '#8fa4aa', fontSize: 8.2, lineHeight: 12.5 },
  statusGuideStrong: { color: '#eef4f5', fontWeight: '900' },
  sectionLabel: { marginTop: 17, marginBottom: 8, color: '#9aadb2', fontSize: 8, fontWeight: '900', letterSpacing: 0.7 },
  chips: { gap: 6 },
  chip: { minHeight: 34, justifyContent: 'center', paddingHorizontal: 11, borderRadius: 10, borderWidth: 1, borderColor: '#244149', backgroundColor: '#10262d' },
  chipActive: { borderColor: '#ff7851', backgroundColor: '#ff5a2a' },
  chipText: { color: '#9db0b5', fontSize: 8.5, fontWeight: '800' },
  chipTextActive: { color: '#ffffff' },
  selectedAreaCard: { marginTop: 8, minHeight: 57, flexDirection: 'row', alignItems: 'center', gap: 10, padding: 11, borderRadius: 13, borderWidth: 1, borderColor: '#34515a', backgroundColor: '#0c2027' },
  selectedAreaLabel: { color: '#71888f', fontSize: 6.5, fontWeight: '900', letterSpacing: 0.45 },
  selectedAreaName: { marginTop: 3, color: '#ffffff', fontSize: 11, fontWeight: '900' },
  selectedAreaCount: { minWidth: 53, alignItems: 'center', paddingVertical: 6, borderRadius: 10, backgroundColor: '#17323a' },
  selectedAreaCountValue: { color: '#69c3d0', fontSize: 15, fontWeight: '900' },
  selectedAreaCountLabel: { color: '#71888f', fontSize: 5.5, fontWeight: '900' },
  ruleCard: { padding: 13, borderRadius: 17, borderWidth: 1, borderColor: '#244149', backgroundColor: '#10262d' },
  ruleToggle: { flexDirection: 'row', padding: 3, borderRadius: 11, backgroundColor: '#081a20' },
  ruleToggleButton: { flex: 1, minHeight: 34, alignItems: 'center', justifyContent: 'center', borderRadius: 9 },
  ruleToggleActive: { backgroundColor: '#ff5a2a' },
  ruleToggleText: { color: '#839aa0', fontSize: 8.5, fontWeight: '900' },
  ruleToggleTextActive: { color: '#ffffff' },
  thresholdHeader: { marginTop: 15, flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 10 },
  thresholdLabel: { color: '#899da3', fontSize: 7, fontWeight: '900', letterSpacing: 0.55 },
  thresholdValue: { marginTop: 3, color: '#ffffff', fontSize: 27, fontWeight: '900' },
  thresholdUnit: { color: '#a9b9bd', fontSize: 10, fontWeight: '800' },
  currentCountBadge: { minWidth: 82, paddingHorizontal: 10, paddingVertical: 8, alignItems: 'flex-end', borderRadius: 11, backgroundColor: '#17323a' },
  currentCountLabel: { color: '#789097', fontSize: 6.5, fontWeight: '900', letterSpacing: 0.45 },
  currentCountValue: { marginTop: 2, color: '#69c3d0', fontSize: 17, fontWeight: '900' },
  slider: { width: '100%', height: 40, marginTop: 8 },
  sliderScale: { marginTop: -5, flexDirection: 'row', justifyContent: 'space-between' },
  sliderScaleText: { color: '#71878d', fontSize: 7 },
  ruleExplanation: { marginTop: 10, color: '#b2c0c3', fontSize: 8.5, lineHeight: 13 },
  scheduleTitle: { marginTop: 15, color: '#ff8b63', fontSize: 7, fontWeight: '900', letterSpacing: 0.55 },
  scheduleModes: { marginTop: 7, flexDirection: 'row', padding: 3, gap: 3, borderRadius: 11, backgroundColor: '#081a20' },
  scheduleModeButton: { flex: 1, minHeight: 33, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5, borderRadius: 9 },
  scheduleModeActive: { backgroundColor: '#f4f7f7' },
  scheduleModeText: { color: '#82989e', fontSize: 7.5, fontWeight: '900', textAlign: 'center' },
  scheduleModeTextActive: { color: '#13282e' },
  weekDays: { marginTop: 8, gap: 5, paddingRight: 8 },
  weekDay: { minWidth: 39, minHeight: 31, alignItems: 'center', justifyContent: 'center', borderRadius: 9, borderWidth: 1, borderColor: '#2a444c', backgroundColor: '#132b32' },
  weekDayActive: { borderColor: '#ff7851', backgroundColor: '#ff5a2a' },
  weekDayText: { color: '#879da3', fontSize: 7.5, fontWeight: '900' },
  weekDayTextActive: { color: '#ffffff' },
  dateInput: { minHeight: 40, marginTop: 8, paddingHorizontal: 12, borderRadius: 11, borderWidth: 1, borderColor: '#38535b', backgroundColor: '#081a20', color: '#ffffff', fontSize: 10, fontWeight: '800' },
  scheduleExplanation: { marginTop: 7, color: '#81979d', fontSize: 7.8, lineHeight: 12 },
  ruleSaveButton: { minHeight: 43, marginTop: 12, alignItems: 'center', justifyContent: 'center', borderRadius: 12, backgroundColor: '#ff5a2a' },
  ruleSaveText: { color: '#ffffff', fontSize: 9.5, fontWeight: '900' },
  manualExplanation: { padding: 11, borderRadius: 13, borderWidth: 1, borderColor: '#244149', backgroundColor: '#10262d' },
  manualExplanationTitle: { color: '#ffffff', fontSize: 9, fontWeight: '900' },
  manualExplanationText: { marginTop: 4, color: '#8fa4aa', fontSize: 8.2, lineHeight: 12.5 },
  typeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  typeButton: { minHeight: 34, justifyContent: 'center', paddingHorizontal: 10, borderRadius: 10, backgroundColor: '#11272e', borderWidth: 1, borderColor: '#244149' },
  typeButtonActive: { backgroundColor: '#f4f7f7', borderColor: '#f4f7f7' },
  typeText: { color: '#8ea3a9', fontSize: 8, fontWeight: '800' },
  typeTextActive: { color: '#14282e' },
  reasonInput: { minHeight: 88, marginTop: 9, padding: 12, borderRadius: 14, borderWidth: 1, borderColor: '#29464e', backgroundColor: '#10262d', color: '#ffffff', fontSize: 10, textAlignVertical: 'top' },
  counter: { marginTop: 4, color: '#71868c', fontSize: 7.5, textAlign: 'right' },
  error: { marginTop: 6, color: '#ff8b69', fontSize: 8.5, fontWeight: '700' },
  saveButton: { minHeight: 45, marginTop: 10, alignItems: 'center', justifyContent: 'center', borderRadius: 12, backgroundColor: '#ffffff' },
  saveText: { color: '#102329', fontSize: 10, fontWeight: '900' },
  disabled: { opacity: 0.55 },
  historyHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  historyCount: { marginTop: 10, color: '#ff7851', fontSize: 10, fontWeight: '900' },
  empty: { padding: 17, borderRadius: 15, backgroundColor: '#10262d' },
  emptyTitle: { color: '#edf4f5', fontSize: 10, fontWeight: '900' },
  emptyText: { marginTop: 3, color: '#7f959b', fontSize: 8.5 },
  swipeRow: { marginBottom: 7, borderRadius: 14, overflow: 'hidden', backgroundColor: '#d92d20' },
  deleteAction: { position: 'absolute', top: 0, right: 0, bottom: 0, width: 86, alignItems: 'center', justifyContent: 'center', backgroundColor: '#d92d20' },
  deleteActionText: { color: '#ffffff', fontSize: 9, fontWeight: '900' },
  alertRow: { padding: 12, flexDirection: 'row', alignItems: 'flex-start', gap: 9, borderRadius: 14, borderWidth: 1, borderColor: '#1d3941', backgroundColor: '#10262d' },
  alertDot: { width: 7, height: 7, marginTop: 4, borderRadius: 4, backgroundColor: '#ff5a2a' },
  alertTitle: { color: '#f2f7f8', fontSize: 9.5, fontWeight: '900' },
  alertReason: { marginTop: 3, color: '#a2b2b6', fontSize: 8.5, lineHeight: 12 },
  alertMeta: { marginTop: 5, color: '#70878d', fontSize: 7 },
  status: { maxWidth: 86, color: '#ffb04d', fontSize: 6.5, fontWeight: '900', textAlign: 'right' },
  statusTriggered: { color: '#ff5a2a' },
  statusResolved: { color: '#72b9c5' },
});
