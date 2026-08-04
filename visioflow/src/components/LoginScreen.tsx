import React, { useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { DEMO_LOGIN, LocalSession } from '../localStore';
import { loginApi } from '../liveApi';

export function LoginScreen({ onAuthenticated }: { onAuthenticated: (session: LocalSession) => void }) {
  const [username, setUsername] = useState<string>(DEMO_LOGIN.username);
  const [password, setPassword] = useState<string>(DEMO_LOGIN.password);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!username.trim() || !password) {
      setError('Escribe el usuario y la contraseña.');
      return;
    }
    setBusy(true);
    try {
      const session = await loginApi(username, password);
      setError('');
      onAuthenticated(session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No fue posible conectar con la API.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.card}>
        <Image source={require('../../assets/visioflow-logo.jpg')} style={styles.mark} />
        <Text style={styles.eyebrow}>ACCESO OPERATIVO</Text>
        <Text style={styles.title}>Bienvenido a VisioFlow</Text>
        <Text style={styles.subtitle}>Consulta movimiento y registra alertas del área observada.</Text>

        <Text style={styles.label}>USUARIO</Text>
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          onChangeText={setUsername}
          placeholder="Usuario"
          placeholderTextColor="#6f8389"
          style={styles.input}
          value={username}
        />
        <Text style={styles.label}>CONTRASEÑA</Text>
        <TextInput
          onChangeText={setPassword}
          onSubmitEditing={submit}
          placeholder="Contraseña"
          placeholderTextColor="#6f8389"
          secureTextEntry
          style={styles.input}
          value={password}
        />
        {!!error && <Text style={styles.error}>{error}</Text>}
        <Pressable disabled={busy} onPress={submit} style={[styles.button, busy && styles.buttonDisabled]}>
          <Text style={styles.buttonText}>{busy ? 'Validando…' : 'Entrar'}</Text>
        </Pressable>

        <View style={styles.demoCard}>
          <Text style={styles.demoTitle}>ACCESO DE PRESENTACIÓN</Text>
          <Text style={styles.demoText}>Usuario: {DEMO_LOGIN.username} · Contraseña: {DEMO_LOGIN.password}</Text>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20, backgroundColor: '#07171c' },
  card: { width: '100%', maxWidth: 430, padding: 24, borderRadius: 26, borderWidth: 1, borderColor: '#1c343c', backgroundColor: '#0d2027' },
  mark: { width: 58, height: 58, borderRadius: 29, backgroundColor: '#000000' },
  eyebrow: { marginTop: 22, color: '#63bfd0', fontSize: 8, fontWeight: '900', letterSpacing: 1 },
  title: { marginTop: 5, color: '#ffffff', fontSize: 25, fontWeight: '900', letterSpacing: -0.7 },
  subtitle: { marginTop: 6, marginBottom: 20, color: '#91a4aa', fontSize: 10, lineHeight: 15 },
  label: { marginTop: 11, marginBottom: 6, color: '#9fb0b5', fontSize: 8, fontWeight: '900', letterSpacing: 0.7 },
  input: { minHeight: 46, paddingHorizontal: 13, borderRadius: 12, borderWidth: 1, borderColor: '#29434b', backgroundColor: '#132a31', color: '#ffffff', fontSize: 13, fontWeight: '700' },
  error: { marginTop: 10, color: '#ff8b69', fontSize: 9, fontWeight: '700' },
  button: { minHeight: 48, marginTop: 18, alignItems: 'center', justifyContent: 'center', borderRadius: 13, backgroundColor: '#ff5a2a' },
  buttonDisabled: { opacity: 0.55 },
  buttonText: { color: '#ffffff', fontSize: 11, fontWeight: '900' },
  demoCard: { marginTop: 17, padding: 12, borderRadius: 13, backgroundColor: '#10262d', borderWidth: 1, borderColor: '#1f3941' },
  demoTitle: { color: '#f0b09b', fontSize: 7.5, fontWeight: '900', letterSpacing: 0.65 },
  demoText: { marginTop: 5, color: '#e5edef', fontSize: 9, fontWeight: '800' },
  demoWarning: { marginTop: 5, color: '#7f969c', fontSize: 8, lineHeight: 12 },
});
