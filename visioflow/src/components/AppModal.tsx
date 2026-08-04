import React from 'react';
import { Modal, Platform, StyleSheet, View } from 'react-native';

type Props = {
  visible: boolean;
  children?: React.ReactNode;
  transparent?: boolean;
  animationType?: 'none' | 'slide' | 'fade';
  onRequestClose?: () => void;
};

// React Native Web 0.21 todavía propaga handlers de responder obsoletos desde
// Modal con React 19. En web usamos una capa fija; Expo Go conserva Modal y sus
// animaciones nativas.
export function AppModal({ visible, children, ...nativeProps }: Props) {
  if (Platform.OS === 'web') {
    if (!visible) return null;
    return <View style={styles.webRoot}>{children}</View>;
  }
  return <Modal visible={visible} {...nativeProps}>{children}</Modal>;
}

const styles = StyleSheet.create({
  webRoot: {
    position: 'fixed' as any,
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    zIndex: 1000,
  },
});
