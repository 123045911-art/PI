import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Insight } from '../types';

const tones = {
  attention: { accent: '#ff6334', soft: '#3b211d', code: '01' },
  pattern: { accent: '#56bfd2', soft: '#13333b', code: '02' },
  movement: { accent: '#28b85a', soft: '#123523', code: '03' },
};

export function InsightCard({ insight, onPress }: { insight: Insight; onPress: () => void }) {
  const tone = tones[insight.tone];
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.topRow}>
        <View style={[styles.code, { backgroundColor: tone.soft }]}>
          <Text style={[styles.codeText, { color: tone.accent }]}>{tone.code}</Text>
        </View>
        <Text style={[styles.eyebrow, { color: tone.accent }]}>{insight.eyebrow.toUpperCase()}</Text>
      </View>
      <Text style={styles.title}>{insight.title}</Text>
      <Text style={styles.detail}>{insight.detail}</Text>
      <View style={styles.evidence}>
        <Text style={styles.evidenceLabel}>{insight.evidenceLabel}</Text>
        <Text style={[styles.evidenceValue, { color: tone.accent }]}>{insight.evidenceValue}</Text>
      </View>
      <View style={styles.actionRow}>
        <Text style={styles.action}>{insight.action}</Text>
        <Text style={[styles.arrow, { color: tone.accent }]}>→</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { padding: 14, borderRadius: 17, borderWidth: 1, borderColor: '#1b343c', backgroundColor: '#0d2027' },
  pressed: { transform: [{ scale: 0.99 }], opacity: 0.88 },
  topRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  code: { width: 27, height: 27, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  codeText: { fontWeight: '900', fontSize: 9 },
  eyebrow: { fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },
  title: { marginTop: 10, color: '#f7fbfc', fontSize: 14, lineHeight: 19, fontWeight: '900', letterSpacing: -0.2 },
  detail: { marginTop: 5, color: '#99adb4', fontSize: 10, lineHeight: 15 },
  evidence: { marginTop: 11, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 10, backgroundColor: '#08171c', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  evidenceLabel: { flex: 1, color: '#7f969e', fontSize: 8, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.45 },
  evidenceValue: { fontSize: 13, fontWeight: '900' },
  actionRow: { marginTop: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  action: { flex: 1, color: '#c8d5d9', fontSize: 9, lineHeight: 13, fontWeight: '700' },
  arrow: { fontSize: 18, fontWeight: '500' },
});
