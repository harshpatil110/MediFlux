/**
 * In-App Interactive Push Alert Banner (Task M7).
 * Provides visual banner feedback for web, emulator, and active foreground sessions.
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { AlertCircle, ShieldAlert, X } from 'lucide-react-native';
import { handleNotificationTapPayload, NotificationPayloadData } from './notificationService';

export interface BannerMessage {
  id: string;
  title: string;
  body: string;
  type: 'hitl' | 'coldchain' | 'generic';
  data?: NotificationPayloadData;
}

interface Props {
  banner: BannerMessage | null;
  onDismiss: () => void;
}

export const NotificationBanner: React.FC<Props> = ({ banner, onDismiss }) => {
  const router = useRouter();
  const slideAnim = useRef(new Animated.Value(-120)).current;

  useEffect(() => {
    if (banner) {
      Animated.spring(slideAnim, {
        toValue: 0,
        useNativeDriver: Platform.OS !== 'web',
        tension: 60,
        friction: 9,
      }).start();

      const timer = setTimeout(() => {
        handleDismiss();
      }, 6000);

      return () => clearTimeout(timer);
    } else {
      Animated.timing(slideAnim, {
        toValue: -120,
        duration: 250,
        useNativeDriver: Platform.OS !== 'web',
      }).start();
    }
  }, [banner]);

  const handleDismiss = () => {
    Animated.timing(slideAnim, {
      toValue: -120,
      duration: 200,
      useNativeDriver: Platform.OS !== 'web',
    }).start(() => {
      onDismiss();
    });
  };

  const handlePress = () => {
    if (!banner) return;
    const handled = handleNotificationTapPayload(banner.data, router);
    handleDismiss();
  };

  if (!banner) return null;

  const isColdChain = banner.type === 'coldchain';
  const borderColor = isColdChain ? '#EF4444' : '#00AEBB';

  return (
    <Animated.View style={[styles.container, { transform: [{ translateY: slideAnim }] }]}>
      <TouchableOpacity
        style={[styles.card, { borderColor }]}
        activeOpacity={0.9}
        onPress={handlePress}
      >
        <View style={styles.iconContainer}>
          {isColdChain ? (
            <AlertCircle size={22} color="#EF4444" />
          ) : (
            <ShieldAlert size={22} color="#00AEBB" />
          )}
        </View>

        <View style={styles.content}>
          <Text style={styles.title} numberOfLines={1}>
            {banner.title}
          </Text>
          <Text style={styles.body} numberOfLines={2}>
            {banner.body}
          </Text>
          <Text style={styles.tapPrompt}>Tap to inspect →</Text>
        </View>

        <TouchableOpacity style={styles.closeBtn} onPress={handleDismiss} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <X size={16} color="#A8A29E" />
        </TouchableOpacity>
      </TouchableOpacity>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 50 : 20,
    left: 16,
    right: 16,
    zIndex: 9999,
  },
  card: {
    backgroundColor: '#031211',
    borderRadius: 8,
    borderWidth: 1.5,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  iconContainer: {
    marginRight: 12,
    alignSelf: 'flex-start',
    marginTop: 2,
  },
  content: {
    flex: 1,
  },
  title: {
    fontSize: 14,
    fontWeight: '700',
    color: '#F7F5F0',
    marginBottom: 2,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  body: {
    fontSize: 12,
    color: '#D8D3C3',
    lineHeight: 16,
  },
  tapPrompt: {
    fontSize: 11,
    fontWeight: '600',
    color: '#00AEBB',
    marginTop: 4,
  },
  closeBtn: {
    marginLeft: 8,
    padding: 4,
    alignSelf: 'flex-start',
  },
});
