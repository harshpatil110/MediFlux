import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ArrowLeft, FileText, AlertCircle } from 'lucide-react-native';
import { apiClient } from '../../src/api/client';
import {
  PrescriptionRecord,
  PrescriptionResultCard,
} from '../../src/features/prescriptions';

export default function PrescriptionDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [prescription, setPrescription] = useState<PrescriptionRecord | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchPrescription() {
      if (!id) return;
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const data = await apiClient.get<PrescriptionRecord>(`/api/v1/prescriptions/${id}`);
        if (isMounted) {
          setPrescription(data);
        }
      } catch (err: any) {
        if (isMounted) {
          setErrorMsg(err.message || `Prescription '${id}' not found or access restricted.`);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }
    void fetchPrescription();
    return () => {
      isMounted = false;
    };
  }, [id]);

  return (
    <View style={styles.container}>
      {/* Top Header Bar */}
      <View style={styles.topBar}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
        >
          <ArrowLeft size={18} color="#031211" />
          <Text style={styles.backButtonText}>Prescriptions</Text>
        </TouchableOpacity>

        <Text style={styles.headerTitle} numberOfLines={1}>
          Rx {id?.substring(0, 8)}
        </Text>
      </View>

      <ScrollView contentContainerStyle={styles.contentContainer}>
        {isLoading ? (
          <View style={styles.centerContainer}>
            <ActivityIndicator size="large" color="#00AEBB" />
            <Text style={styles.loadingText}>Retrieving statutory prescription record...</Text>
          </View>
        ) : errorMsg || !prescription ? (
          <View style={styles.errorCard}>
            <AlertCircle size={32} color="#EF4444" />
            <Text style={styles.errorTitle}>Prescription Lookup Error</Text>
            <Text style={styles.errorSubtitle}>
              {errorMsg || 'Record could not be retrieved. Please check node permissions.'}
            </Text>
            <TouchableOpacity
              style={styles.errorBackBtn}
              onPress={() => router.back()}
              activeOpacity={0.8}
            >
              <Text style={styles.errorBackBtnText}>← Return to Scans</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View>
            <View style={styles.metaHeader}>
              <View style={styles.docIconBox}>
                <FileText size={20} color="#00AEBB" />
              </View>
              <View style={styles.metaCol}>
                <Text style={styles.rxNumberText}>
                  {prescription.rx_number || `RX-${(prescription.id || '').substring(0, 8).toUpperCase()}`}
                </Text>
                <Text style={styles.rxSubText}>
                  Recorded on {prescription.created_at ? new Date(prescription.created_at).toLocaleString() : 'N/A'}
                </Text>
              </View>
            </View>

            <PrescriptionResultCard
              prescription={prescription}
              showAttachButton={true}
              compact={false}
            />
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#E8E4D3',
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 12,
    backgroundColor: '#DFDBCA',
    borderBottomWidth: 1,
    borderBottomColor: '#D8D3C3',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  backButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#031211',
  },
  headerTitle: {
    fontSize: 14,
    fontFamily: 'Courier',
    fontWeight: '800',
    color: '#5C584E',
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 40,
  },
  centerContainer: {
    paddingVertical: 60,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 13,
    color: '#5C584E',
  },
  errorCard: {
    backgroundColor: '#F7F5F0',
    borderWidth: 1,
    borderColor: '#FECACA',
    borderRadius: 8,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    gap: 10,
  },
  errorTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#991B1B',
  },
  errorSubtitle: {
    fontSize: 13,
    color: '#78716C',
    textAlign: 'center',
    lineHeight: 18,
  },
  errorBackBtn: {
    backgroundColor: '#031211',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 6,
    marginTop: 8,
  },
  errorBackBtnText: {
    color: '#00AEBB',
    fontSize: 13,
    fontWeight: '800',
  },
  metaHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F7F5F0',
    borderWidth: 1,
    borderColor: '#D8D3C3',
    borderRadius: 8,
    padding: 12,
    marginBottom: 10,
    gap: 12,
  },
  docIconBox: {
    width: 38,
    height: 38,
    borderRadius: 6,
    backgroundColor: '#031211',
    alignItems: 'center',
    justifyContent: 'center',
  },
  metaCol: {
    flex: 1,
  },
  rxNumberText: {
    fontSize: 15,
    fontFamily: 'Courier',
    fontWeight: '800',
    color: '#031211',
  },
  rxSubText: {
    fontSize: 11,
    color: '#5C584E',
    marginTop: 2,
  },
});
