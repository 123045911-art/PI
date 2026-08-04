import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { AppModal } from './AppModal';

export function HeatmapHelp({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  return (
    <AppModal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <View style={styles.card}>
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.eyebrow}>GUÍA DEL MAPA</Text>
              <Text style={styles.title}>¿Qué estoy viendo?</Text>
            </View>
            <Pressable accessibilityLabel="Cerrar guía" onPress={onClose} style={styles.close}><Text style={styles.closeText}>×</Text></Pressable>
          </View>
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
            <Text style={styles.intro}>El mapa resume dónde estuvieron las personas dentro del área que observa el sensor.</Text>

            <View style={styles.legendCard}>
              <View style={styles.gradient}>
                {['#fff8e8', '#ffd875', '#ff9a3d', '#ff5a2a', '#cf2718'].map((color) => <View key={color} style={[styles.gradientPart, { backgroundColor: color }]} />)}
              </View>
              <Text style={styles.legendTitle}>De menor a mayor actividad</Text>
              <Text style={styles.legendText}>Naranja claro significa poca actividad; naranja intenso y rojo señalan mayor concentración o tiempo.</Text>
            </View>

            <View style={styles.item}><Text style={styles.itemTitle}>Personas que pasaron</Text><Text style={styles.itemText}>Cantidad de recorridos diferentes observados en cada punto.</Text></View>
            <View style={styles.item}><Text style={styles.itemTitle}>Tiempo dentro de la zona</Text><Text style={styles.itemText}>Cuánto tiempo permanecieron las personas, aunque continuaran caminando.</Text></View>
            <View style={styles.item}><Text style={styles.itemTitle}>Movimiento mínimo</Text><Text style={styles.itemText}>Personas que se movieron muy poco durante al menos 12 segundos, tolerando el ruido del sensor.</Text></View>
            <View style={styles.item}><Text style={styles.itemTitle}>Concentración</Text><Text style={styles.itemText}>Promedio de personas presentes al mismo tiempo.</Text></View>

            <View style={styles.structureCard}>
              <Text style={styles.structureTitle}>ESTRUCTURAS DEL ÁREA</Text>
              <Text style={styles.structureText}>Las figuras blancas son muros, racks, mesas y módulos no transitables. Ocultarlas solo cambia la vista: siguen bloqueando recorridos y calor.</Text>
            </View>

            <View style={styles.compareCard}>
              <View style={styles.compareGradient}>
                {['#1759d1', '#82adeb', '#f5f2eb', '#ff9a54', '#e93e1e'].map((color) => <View key={color} style={[styles.gradientPart, { backgroundColor: color }]} />)}
              </View>
              <Text style={styles.legendTitle}>Cuando comparas dos horas</Text>
              <Text style={styles.legendText}>Azul: disminuyó la actividad. Blanco: casi no cambió. Naranja: aumentó la actividad.</Text>
            </View>
          </ScrollView>
        </View>
      </View>
    </AppModal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'center', padding: 16, backgroundColor: 'rgba(2,10,14,0.65)' },
  card: { width: '100%', maxWidth: 520, maxHeight: '88%', alignSelf: 'center', overflow: 'hidden', borderRadius: 25, borderWidth: 1, borderColor: '#24414a', backgroundColor: '#0b1d23' },
  header: { minHeight: 78, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 18, borderBottomWidth: 1, borderBottomColor: '#1b343c' },
  eyebrow: { color: '#63bfd0', fontSize: 8, fontWeight: '900', letterSpacing: 0.9 },
  title: { marginTop: 4, color: '#ffffff', fontSize: 21, fontWeight: '900' },
  close: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center', borderRadius: 18, backgroundColor: '#142c33' },
  closeText: { color: '#ffffff', fontSize: 23, lineHeight: 24 },
  content: { padding: 18, paddingBottom: 28, gap: 10 },
  intro: { marginBottom: 2, color: '#a7b7bb', fontSize: 10, lineHeight: 15 },
  legendCard: { padding: 13, borderRadius: 16, backgroundColor: '#ffffff' },
  gradient: { height: 11, flexDirection: 'row', overflow: 'hidden', borderRadius: 6 },
  gradientPart: { flex: 1 },
  legendTitle: { marginTop: 9, color: '#102329', fontSize: 11, fontWeight: '900' },
  legendText: { marginTop: 3, color: '#687c82', fontSize: 9, lineHeight: 13 },
  item: { padding: 12, borderRadius: 14, borderWidth: 1, borderColor: '#1c363e', backgroundColor: '#10262d' },
  itemTitle: { color: '#f2f7f8', fontSize: 10, fontWeight: '900' },
  itemText: { marginTop: 3, color: '#8fa3a9', fontSize: 8.5, lineHeight: 13 },
  structureCard: { padding: 13, borderRadius: 15, borderWidth: 1, borderColor: '#37515a', backgroundColor: '#f5f2eb' },
  structureTitle: { color: '#20363c', fontSize: 8, fontWeight: '900', letterSpacing: 0.7 },
  structureText: { marginTop: 5, color: '#586b70', fontSize: 9, lineHeight: 14 },
  compareCard: { padding: 13, borderRadius: 16, backgroundColor: '#ffffff' },
  compareGradient: { height: 11, flexDirection: 'row', overflow: 'hidden', borderRadius: 6 },
});
