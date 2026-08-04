import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { buildHistoricalPatterns, computeTimeZoneLeaders, DAY_NAMES, HISTORICAL_ZONE_HOURS, HISTORY_WEEKS } from '../history';
import { Insight } from '../types';
import { InsightCard } from './InsightCard';

type Props = {
  insights: Insight[];
  onSelectZone: (zoneId: string | null) => void;
  selectedDay: number;
  onSelectDay: (dayIndex: number) => void;
  comparison: { baselineHour: number; comparisonHour: number } | null;
  onApplyComparison: (baselineHour: number, comparisonHour: number) => void;
  onClearComparison: () => void;
  wide?: boolean;
};

const ORANGE = '#ff5a2a';
const DARK = '#07171c';

export function AnalysisPanel({ insights, onSelectZone, selectedDay, onSelectDay, comparison, onApplyComparison, onClearComparison, wide = false }: Props) {
  const [tab, setTab] = useState<'compare' | 'hours' | 'patterns'>('compare');
  const [grouping, setGrouping] = useState<'hour' | 'range'>('hour');
  const [baselineHour, setBaselineHour] = useState(comparison?.baselineHour ?? 9);
  const [comparisonHour, setComparisonHour] = useState(comparison?.comparisonHour ?? 13);
  const leaders = useMemo(
    () => computeTimeZoneLeaders(HISTORICAL_ZONE_HOURS, selectedDay, grouping),
    [grouping, selectedDay],
  );
  const historicalPatterns = useMemo(() => buildHistoricalPatterns(HISTORICAL_ZONE_HOURS), []);
  const maxLeader = Math.max(1, ...leaders.map((leader) => leader.averageTracks));

  return (
    <View style={[styles.panel, wide && styles.panelWide]}>
      <View style={styles.headingRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.eyebrow}>ANÁLISIS</Text>
          <Text style={styles.heading}>Patrones de movimiento</Text>
          <Text style={styles.subheading}>Resumen de {DAY_NAMES[selectedDay]}.</Text>
        </View>
        <View style={styles.badge}><Text style={styles.badgeText}>{HISTORY_WEEKS} SEM</Text></View>
      </View>

      <View style={styles.tabs}>
        {([
          ['compare', 'Comparar'],
          ['hours', 'Horarios'],
          ['patterns', 'Patrones'],
        ] as const).map(([id, label]) => (
          <Pressable key={id} onPress={() => setTab(id)} style={[styles.tab, tab === id && styles.tabActive]}>
            <Text style={[styles.tabText, tab === id && styles.tabTextActive]}>{label}</Text>
          </Pressable>
        ))}
      </View>

      {tab === 'compare' && (
        <View style={styles.compareCard}>
          <Text style={styles.cardEyebrow}>COMPARACIÓN ESPACIAL</Text>
          <Text style={styles.compareTitle}>Contrasta dos mapas por hora</Text>
          <Text style={styles.compareDescription}>
            El mapa calcula B − A en cada punto después de ponderar cada hora por su total. Azul indica menor participación espacial del flujo; naranja, mayor.
          </Text>

          <Text style={styles.hourSelectorLabel}>A · HORA DE REFERENCIA</Text>
          <ScrollView horizontal nestedScrollEnabled showsHorizontalScrollIndicator contentContainerStyle={styles.hourChips}>
            {Array.from({ length: 8 }, (_, index) => index + 8).map((hour) => (
              <Pressable key={`a-${hour}`} onPress={() => setBaselineHour(hour)} style={[styles.hourChip, baselineHour === hour && styles.hourChipBlue]}>
                <Text style={[styles.hourChipText, baselineHour === hour && styles.hourChipTextActive]}>{String(hour).padStart(2, '0')}:00</Text>
              </Pressable>
            ))}
          </ScrollView>

          <Text style={styles.hourSelectorLabel}>B · HORA A COMPARAR</Text>
          <ScrollView horizontal nestedScrollEnabled showsHorizontalScrollIndicator contentContainerStyle={styles.hourChips}>
            {Array.from({ length: 8 }, (_, index) => index + 8).map((hour) => (
              <Pressable key={`b-${hour}`} onPress={() => setComparisonHour(hour)} style={[styles.hourChip, comparisonHour === hour && styles.hourChipOrange]}>
                <Text style={[styles.hourChipText, comparisonHour === hour && styles.hourChipTextActive]}>{String(hour).padStart(2, '0')}:00</Text>
              </Pressable>
            ))}
          </ScrollView>

          <View style={styles.divergingLegend}>
            <Text style={styles.legendSide}>− participación</Text>
            <View style={styles.legendColors}>
              {['#1759d1', '#82adeb', '#f5f2eb', '#ff9a54', '#e93e1e'].map((color) => <View key={color} style={[styles.legendBlock, { backgroundColor: color }]} />)}
            </View>
            <Text style={styles.legendSide}>+ participación</Text>
          </View>

          <Pressable
            disabled={baselineHour === comparisonHour}
            onPress={() => onApplyComparison(baselineHour, comparisonHour)}
            style={[styles.applyButton, baselineHour === comparisonHour && styles.applyButtonDisabled]}
          >
            <Text style={styles.applyButtonText}>Mostrar diferencia en el mapa</Text>
          </Pressable>
          {comparison && (
            <View style={styles.activeComparison}>
              <Text style={styles.activeComparisonText}>Activo: {comparison.comparisonHour}:00 vs {comparison.baselineHour}:00</Text>
              <Pressable onPress={onClearComparison}><Text style={styles.clearText}>Quitar</Text></Pressable>
            </View>
          )}

          <View style={styles.methodCard}>
            <Text style={styles.methodTitle}>Lectura correcta</Text>
            <Text style={styles.methodText}>La intensidad representa la diferencia de distribución por cada 100 recorridos. Los indicadores superiores conservan los conteos absolutos. Blanco significa cambio pequeño o nulo.</Text>
          </View>
        </View>
      )}

      {tab === 'hours' && (
        <View style={styles.timeCard}>
          <View style={styles.cardTitleRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardEyebrow}>PROMEDIO ZONA–HORA</Text>
              <Text style={styles.cardTitle}>Zona con mayor afluencia</Text>
            </View>
            <View style={styles.groupToggle}>
              <Pressable onPress={() => setGrouping('hour')} style={[styles.toggleButton, grouping === 'hour' && styles.toggleActive]}>
                <Text style={[styles.toggleText, grouping === 'hour' && styles.toggleTextActive]}>Cada hora</Text>
              </Pressable>
              <Pressable onPress={() => setGrouping('range')} style={[styles.toggleButton, grouping === 'range' && styles.toggleActive]}>
                <Text style={[styles.toggleText, grouping === 'range' && styles.toggleTextActive]}>Rangos 2 h</Text>
              </Pressable>
            </View>
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.dayFilters}>
            {DAY_NAMES.map((day, index) => (
              <Pressable key={day} onPress={() => onSelectDay(index)} style={[styles.dayChip, selectedDay === index && styles.dayChipActive]}>
                <Text style={[styles.dayText, selectedDay === index && styles.dayTextActive]}>{day}</Text>
              </Pressable>
            ))}
          </ScrollView>
          <Text style={styles.cardNote}>Ranking de zonas interiores; el acceso se analiza por separado porque forma parte de casi todas las rutas.</Text>

          <View style={styles.leaderList}>
            {leaders.map((leader) => (
              <Pressable key={leader.label} onPress={() => onSelectZone(leader.zoneId)} style={styles.leaderRow}>
                <Text style={styles.timeLabel}>{leader.label}</Text>
                <View style={styles.leaderMain}>
                  <View style={styles.leaderCopy}>
                    <Text style={styles.zoneName} numberOfLines={1}>{leader.zoneName}</Text>
                    <Text style={styles.trackAverage}>{leader.averageTracks} personas promedio</Text>
                  </View>
                  <View style={styles.barTrack}>
                    <View style={[styles.barFill, { width: `${Math.max(8, (leader.averageTracks / maxLeader) * 100)}%` }]} />
                  </View>
                </View>
              </Pressable>
            ))}
          </View>
        </View>
      )}

      {tab === 'patterns' && (
        <>
          <Text style={styles.sectionLabel}>PERIODO SELECCIONADO</Text>
          <View style={styles.insightList}>
            {insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} onPress={() => onSelectZone(insight.zoneId ?? null)} />
            ))}
          </View>

          <Text style={styles.sectionLabel}>PATRONES ENTRE DÍAS Y SEMANAS</Text>
          <View style={styles.historyList}>
            {historicalPatterns.map((pattern) => (
              <Pressable key={pattern.id} onPress={() => onSelectZone(pattern.zoneId ?? null)} style={styles.historyCard}>
                <View style={[styles.directionDot, pattern.direction === 'down' ? styles.down : pattern.direction === 'up' ? styles.up : styles.stable]} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.historyTitle}>{pattern.title}</Text>
                  <Text style={styles.historyDetail}>{pattern.detail}</Text>
                </View>
                <Text style={[styles.evidence, pattern.direction === 'down' && styles.evidenceDown]}>{pattern.evidence}</Text>
              </Pressable>
            ))}
          </View>

          <View style={styles.truthCard}>
            <Text style={styles.truthTitle}>Cómo se calcula</Text>
            <Text style={styles.truthText}>Cada valor cuenta personas diferentes por zona y hora mediante su identificador temporal. No utiliza ventas, identidad, ingresos ni conversión.</Text>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { padding: 15, paddingBottom: 32, borderRadius: 23, backgroundColor: DARK, borderWidth: 1, borderColor: '#10282f' },
  panelWide: { width: 390 },
  headingRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 },
  eyebrow: { color: '#ff875f', fontSize: 8, fontWeight: '900', letterSpacing: 1 },
  heading: { marginTop: 4, color: '#ffffff', fontSize: 20, fontWeight: '900', letterSpacing: -0.55 },
  subheading: { marginTop: 3, color: '#879da4', fontSize: 8 },
  badge: { paddingHorizontal: 8, paddingVertical: 6, borderRadius: 9, backgroundColor: '#2e211d' },
  badgeText: { color: '#ff8b63', fontSize: 7, fontWeight: '900' },
  tabs: { marginTop: 14, marginBottom: 12, padding: 3, flexDirection: 'row', borderRadius: 11, backgroundColor: '#10262d' },
  tab: { flex: 1, minHeight: 34, alignItems: 'center', justifyContent: 'center', borderRadius: 8 },
  tabActive: { backgroundColor: '#ffffff' },
  tabText: { color: '#81969d', fontSize: 8, fontWeight: '900' },
  tabTextActive: { color: '#17282e' },
  compareCard: { padding: 14, borderRadius: 17, backgroundColor: '#0d2027', borderWidth: 1, borderColor: '#1b343c' },
  compareTitle: { marginTop: 4, color: '#ffffff', fontSize: 17, fontWeight: '900' },
  compareDescription: { marginTop: 5, color: '#8ca0a6', fontSize: 8, lineHeight: 12 },
  hourSelectorLabel: { marginTop: 15, marginBottom: 7, color: '#7e939a', fontSize: 7, fontWeight: '900', letterSpacing: 0.75 },
  hourChips: { gap: 5 },
  hourChip: { minWidth: 48, paddingHorizontal: 8, paddingVertical: 8, alignItems: 'center', borderRadius: 9, backgroundColor: '#172d34', borderWidth: 1, borderColor: '#243d45' },
  hourChipBlue: { backgroundColor: '#275daf', borderColor: '#82adeb' },
  hourChipOrange: { backgroundColor: '#d94b21', borderColor: '#ff9a54' },
  hourChipText: { color: '#82969d', fontSize: 8, fontWeight: '900' },
  hourChipTextActive: { color: '#ffffff' },
  divergingLegend: { marginTop: 16, flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendSide: { color: '#82969d', fontSize: 7, fontWeight: '800' },
  legendColors: { flex: 1, height: 8, flexDirection: 'row', overflow: 'hidden', borderRadius: 5 },
  legendBlock: { flex: 1 },
  applyButton: { marginTop: 15, minHeight: 43, alignItems: 'center', justifyContent: 'center', borderRadius: 12, backgroundColor: ORANGE },
  applyButtonDisabled: { opacity: 0.35 },
  applyButtonText: { color: '#ffffff', fontSize: 9, fontWeight: '900' },
  activeComparison: { marginTop: 9, paddingHorizontal: 10, minHeight: 34, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderRadius: 9, backgroundColor: '#152a31' },
  activeComparisonText: { color: '#dce8ea', fontSize: 8, fontWeight: '800' },
  clearText: { color: '#ff8159', fontSize: 8, fontWeight: '900' },
  methodCard: { marginTop: 12, padding: 11, borderRadius: 11, backgroundColor: '#101a1e' },
  methodTitle: { color: '#f0f6f7', fontSize: 8, fontWeight: '900' },
  methodText: { marginTop: 4, color: '#7c9097', fontSize: 7.5, lineHeight: 11 },
  sectionLabel: { marginTop: 16, marginBottom: 8, color: '#718991', fontSize: 8, fontWeight: '900', letterSpacing: 0.9 },
  insightList: { gap: 9 },
  timeCard: { padding: 13, borderRadius: 17, backgroundColor: '#0d2027', borderWidth: 1, borderColor: '#1b343c' },
  cardTitleRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  cardEyebrow: { color: '#ff8b63', fontSize: 7, fontWeight: '900', letterSpacing: 0.8 },
  cardTitle: { marginTop: 3, color: '#f2f7f8', fontSize: 13, fontWeight: '900' },
  groupToggle: { flexDirection: 'row', padding: 2, borderRadius: 8, backgroundColor: '#162d35' },
  toggleButton: { paddingHorizontal: 7, paddingVertical: 6, borderRadius: 6 },
  toggleActive: { backgroundColor: '#ffffff' },
  toggleText: { color: '#8ca0a7', fontSize: 7, fontWeight: '800' },
  toggleTextActive: { color: '#1b2b31' },
  dayFilters: { gap: 5, paddingVertical: 11 },
  dayChip: { minWidth: 36, paddingHorizontal: 8, paddingVertical: 7, alignItems: 'center', borderRadius: 8, backgroundColor: '#142930' },
  dayChipActive: { backgroundColor: ORANGE },
  dayText: { color: '#8ea1a7', fontSize: 7, fontWeight: '900' },
  dayTextActive: { color: '#ffffff' },
  cardNote: { marginBottom: 7, color: '#6f858c', fontSize: 7, lineHeight: 10 },
  leaderList: { gap: 4 },
  leaderRow: { minHeight: 42, flexDirection: 'row', alignItems: 'center', gap: 9, paddingVertical: 5, borderTopWidth: 1, borderTopColor: '#183039' },
  timeLabel: { width: 43, color: '#ff8b63', fontSize: 8, fontWeight: '900' },
  leaderMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 },
  leaderCopy: { width: 105 },
  zoneName: { color: '#edf5f6', fontSize: 8, fontWeight: '900' },
  trackAverage: { marginTop: 2, color: '#748b92', fontSize: 6.5 },
  barTrack: { flex: 1, height: 5, borderRadius: 3, backgroundColor: '#233b43', overflow: 'hidden' },
  barFill: { height: 5, borderRadius: 3, backgroundColor: ORANGE },
  historyList: { gap: 7 },
  historyCard: { minHeight: 70, padding: 11, flexDirection: 'row', alignItems: 'flex-start', gap: 9, borderRadius: 13, backgroundColor: '#0d2027', borderWidth: 1, borderColor: '#1b343c' },
  directionDot: { width: 8, height: 8, marginTop: 3, borderRadius: 4 },
  down: { backgroundColor: '#ff5a2a' },
  up: { backgroundColor: '#31b968' },
  stable: { backgroundColor: '#e7b33e' },
  historyTitle: { color: '#f0f6f7', fontSize: 9, lineHeight: 13, fontWeight: '900' },
  historyDetail: { marginTop: 4, color: '#7f949b', fontSize: 7.5, lineHeight: 11 },
  evidence: { color: '#55c879', fontSize: 13, fontWeight: '900' },
  evidenceDown: { color: '#ff6a3c' },
  truthCard: { marginTop: 14, padding: 12, borderRadius: 14, backgroundColor: '#0b1d23', borderWidth: 1, borderColor: '#1b343c' },
  truthTitle: { color: '#eef6f7', fontSize: 9, fontWeight: '900' },
  truthText: { marginTop: 4, color: '#82969d', fontSize: 8, lineHeight: 12 },
  truthFoot: { marginTop: 8, color: '#ff8b63', fontSize: 7, fontWeight: '800' },
});
