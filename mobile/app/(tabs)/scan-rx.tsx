import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import {
  FileText,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Calendar,
  User,
  ArrowRight,
  Shield,
  Layers,
} from 'lucide-react-native';
import { useAuth } from '../../src/features/auth/AuthContext';
import { isTabVisibleForRole } from '../../src/features/auth/roleMap';
import { apiClient } from '../../src/api/client';
import {
  PrescriptionRecord,
  PrescriptionCaptureCard,
  PrescriptionResultCard,
  cleanupAllTempPrescriptionImages,
} from '../../src/features/prescriptions';

export default function ScanRxScreen() {
  const router = useRouter();
  const { user } = useAuth();

  // Role guard: redirect if role has no access to scan-rx
  useEffect(() => {
    if (user && !isTabVisibleForRole(user.role, 'scan-rx')) {
      router.replace('/(tabs)');
    }
  }, [user, router]);

  // Clean ephemeral cached prescription images on screen exit
  useEffect(() => {
    return () => {
      void cleanupAllTempPrescriptionImages();
    };
  }, []);

  const [activeTab, setActiveTab] = useState<'scan' | 'history'>('scan');
  const [latestVerifiedRx, setLatestVerifiedRx] = useState<PrescriptionRecord | null>(null);

  // History state
  const [historyList, setHistoryList] = useState<PrescriptionRecord[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchHistory = useCallback(async () => {
    setIsLoadingHistory(true);
    try {
      const resp = await apiClient.get<{ prescriptions: PrescriptionRecord[]; total: number }>(
        '/api/v1/prescriptions?limit=50'
      );
      if (resp && resp.prescriptions) {
        setHistoryList(resp.prescriptions);
      }
    } catch (err) {
      console.error('Failed to fetch prescription history:', err);
    } finally {
      setIsLoadingHistory(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'history') {
      void fetchHistory();
    }
  }, [activeTab, fetchHistory]);

  const onRefresh = () => {
    setIsRefreshing(true);
    void fetchHistory();
  };

  const handlePrescriptionVerified = (record: PrescriptionRecord) => {
    setLatestVerifiedRx(record);
    // Refresh history in background
    void fetchHistory();
  };

  const handleScanAnother = async () => {
    await cleanupAllTempPrescriptionImages();
    setLatestVerifiedRx(null);
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      refreshControl={
        activeTab === 'history' ? (
          <RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} tintColor="#00AEBB" />
        ) : undefined
      }
    >
      {/* Editorial Header */}
      <View style={styles.header}>
        <View style={styles.badgeRow}>
          <View style={styles.sovereignBadge}>
            <Shield size={12} color="#00AEBB" />
            <Text style={styles.sovereignBadgeText}>LOCAL SOVEREIGN PIPELINE</Text>
          </View>
          <Text style={styles.roleHeaderBadge}>
            {user?.role?.toUpperCase() || 'PHARMACY'} NODE
          </Text>
        </View>

        <Text style={styles.title}>Prescription Scanner</Text>
        <Text style={styles.subtitle}>
          Multimodal optical character extraction, CDSCO Schedule H/H1/X compliance validation, and
          national physician registry verification.
        </Text>
      </View>

      {/* Segmented Control: [ Scan Rx | History (N) ] */}
      <View style={styles.segmentedContainer}>
        <TouchableOpacity
          style={[styles.segmentBtn, activeTab === 'scan' && styles.segmentBtnActive]}
          onPress={() => setActiveTab('scan')}
          activeOpacity={0.8}
        >
          <Text style={[styles.segmentText, activeTab === 'scan' && styles.segmentTextActive]}>
            📷 Scan Rx
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.segmentBtn, activeTab === 'history' && styles.segmentBtnActive]}
          onPress={() => setActiveTab('history')}
          activeOpacity={0.8}
        >
          <Text style={[styles.segmentText, activeTab === 'history' && styles.segmentTextActive]}>
            📋 History ({historyList.length > 0 ? historyList.length : '—'})
          </Text>
        </TouchableOpacity>
      </View>

      {/* TAB 1: SCAN RX */}
      {activeTab === 'scan' && (
        <View style={styles.tabContent}>
          {!latestVerifiedRx ? (
            <PrescriptionCaptureCard
              onPrescriptionVerified={handlePrescriptionVerified}
              nodeId={user?.node_id || undefined}
            />
          ) : (
            <View style={styles.resultContainer}>
              <View style={styles.resultHeaderRow}>
                <Text style={styles.resultHeaderTitle}>COMPLIANCE EVALUATION RESULT</Text>
                <TouchableOpacity
                  style={styles.scanAnotherBtn}
                  onPress={() => void handleScanAnother()}
                  activeOpacity={0.7}
                >
                  <RotateCcw size={14} color="#031211" />
                  <Text style={styles.scanAnotherText}>Scan Another Rx</Text>
                </TouchableOpacity>
              </View>

              <PrescriptionResultCard
                prescription={latestVerifiedRx}
                showAttachButton={true}
              />
            </View>
          )}
        </View>
      )}

      {/* TAB 2: RLS-SCOPED PRESCRIPTION HISTORY */}
      {activeTab === 'history' && (
        <View style={styles.tabContent}>
          {isLoadingHistory && historyList.length === 0 ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#00AEBB" />
              <Text style={styles.loadingText}>Fetching RLS-scoped pharmacy prescriptions...</Text>
            </View>
          ) : historyList.length === 0 ? (
            <View style={styles.emptyContainer}>
              <FileText size={40} color="#A8A29E" />
              <Text style={styles.emptyTitle}>No Prescriptions Recorded</Text>
              <Text style={styles.emptySubtitle}>
                Scanned prescriptions for this pharmacy node will appear here with full CDSCO
                compliance audit trails.
              </Text>
              <TouchableOpacity
                style={styles.emptyScanBtn}
                onPress={() => setActiveTab('scan')}
                activeOpacity={0.8}
              >
                <Text style={styles.emptyScanBtnText}>Scan First Prescription →</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.historyListContainer}>
              {historyList.map((item, idx) => {
                const isItemApproved = item.status === 'approved' || item.decision === 'approve_dispense';
                const isItemFlagged = item.status === 'flagged' || item.decision === 'flag';
                const isItemRejected = item.status === 'rejected' || item.decision === 'reject';

                return (
                  <TouchableOpacity
                    key={`hist-${item.id || idx}`}
                    style={styles.historyCard}
                    onPress={() => {
                      router.push({
                        pathname: '/prescriptions/[id]',
                        params: { id: item.id || item.prescription_id },
                      } as any);
                    }}
                    activeOpacity={0.8}
                  >
                    <View style={styles.histHeaderRow}>
                      <View style={styles.patientBadge}>
                        <User size={12} color="#00AEBB" />
                        <Text style={styles.patientInitialsText}>
                          {item.patient_initials || 'ANON'}
                        </Text>
                      </View>

                      {isItemApproved && (
                        <View style={[styles.statusBadge, styles.badgeApproved]}>
                          <CheckCircle size={12} color="#059669" />
                          <Text style={styles.statusTextApproved}>APPROVED</Text>
                        </View>
                      )}
                      {isItemFlagged && (
                        <View style={[styles.statusBadge, styles.badgeFlagged]}>
                          <AlertTriangle size={12} color="#D97706" />
                          <Text style={styles.statusTextFlagged}>FLAGGED HITL</Text>
                        </View>
                      )}
                      {isItemRejected && (
                        <View style={[styles.statusBadge, styles.badgeRejected]}>
                          <XCircle size={12} color="#DC2626" />
                          <Text style={styles.statusTextRejected}>REJECTED</Text>
                        </View>
                      )}
                    </View>

                    <Text style={styles.histDoctorText}>
                      {item.doctor_name || 'Dr. Physician'} •{' '}
                      <Text style={styles.monoSmall}>
                        Reg: {item.doctor_registration_no || 'MISSING'}
                      </Text>
                    </Text>

                    <View style={styles.histDrugsRow}>
                      <Layers size={13} color="#5C584E" />
                      <Text style={styles.histDrugsText} numberOfLines={1}>
                        {(item.drugs || []).map((d) => d.name).join(', ') || '1 formulation'}
                      </Text>
                    </View>

                    <View style={styles.histFooterRow}>
                      <View style={styles.dateCol}>
                        <Calendar size={12} color="#78716C" />
                        <Text style={styles.dateText}>
                          {item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Today'}
                        </Text>
                      </View>

                      <View style={styles.viewDetailCol}>
                        <Text style={styles.viewDetailText}>View Details</Text>
                        <ArrowRight size={13} color="#00AEBB" />
                      </View>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#E8E4D3',
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 40,
  },
  header: {
    marginBottom: 16,
  },
  badgeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  sovereignBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#031211',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    gap: 5,
  },
  sovereignBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#00AEBB',
    letterSpacing: 0.5,
  },
  roleHeaderBadge: {
    fontSize: 10,
    fontWeight: '800',
    color: '#5C584E',
    letterSpacing: 0.5,
  },
  title: {
    fontSize: 24,
    fontWeight: '900',
    color: '#031211',
    letterSpacing: -0.4,
  },
  subtitle: {
    fontSize: 13,
    color: '#5C584E',
    marginTop: 4,
    lineHeight: 18,
  },
  segmentedContainer: {
    flexDirection: 'row',
    backgroundColor: '#DFDBCA',
    borderRadius: 6,
    padding: 3,
    borderWidth: 1,
    borderColor: '#D8D3C3',
    marginBottom: 14,
  },
  segmentBtn: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 4,
  },
  segmentBtnActive: {
    backgroundColor: '#031211',
  },
  segmentText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#5C584E',
  },
  segmentTextActive: {
    color: '#00AEBB',
  },
  tabContent: {
    minHeight: 250,
  },
  resultContainer: {
    marginTop: 4,
  },
  resultHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  resultHeaderTitle: {
    fontSize: 11,
    fontWeight: '800',
    color: '#5C584E',
    letterSpacing: 0.6,
  },
  scanAnotherBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#DFDBCA',
    borderWidth: 1,
    borderColor: '#D8D3C3',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 4,
    gap: 5,
  },
  scanAnotherText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#031211',
  },
  loadingContainer: {
    paddingVertical: 50,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 13,
    color: '#5C584E',
  },
  emptyContainer: {
    backgroundColor: '#F7F5F0',
    borderWidth: 1,
    borderColor: '#D8D3C3',
    borderRadius: 8,
    padding: 30,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#031211',
    marginTop: 12,
  },
  emptySubtitle: {
    fontSize: 12,
    color: '#78716C',
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 18,
    maxWidth: 280,
  },
  emptyScanBtn: {
    backgroundColor: '#00AEBB',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 6,
    marginTop: 16,
  },
  emptyScanBtnText: {
    fontSize: 13,
    fontWeight: '800',
    color: '#031211',
  },
  historyListContainer: {
    gap: 8,
  },
  historyCard: {
    backgroundColor: '#F7F5F0',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#D8D3C3',
    padding: 14,
  },
  histHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  patientBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#031211',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    gap: 5,
  },
  patientInitialsText: {
    fontSize: 12,
    fontFamily: 'Courier',
    fontWeight: '900',
    color: '#00AEBB',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    borderWidth: 1,
    gap: 4,
  },
  badgeApproved: {
    backgroundColor: '#ECFDF5',
    borderColor: '#A7F3D0',
  },
  statusTextApproved: {
    fontSize: 10,
    fontWeight: '800',
    color: '#065F46',
  },
  badgeFlagged: {
    backgroundColor: '#FFFBEB',
    borderColor: '#FDE68A',
  },
  statusTextFlagged: {
    fontSize: 10,
    fontWeight: '800',
    color: '#B45309',
  },
  badgeRejected: {
    backgroundColor: '#FEF2F2',
    borderColor: '#FECACA',
  },
  statusTextRejected: {
    fontSize: 10,
    fontWeight: '800',
    color: '#B91C1C',
  },
  histDoctorText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#031211',
    marginBottom: 6,
  },
  monoSmall: {
    fontFamily: 'Courier',
    fontSize: 11,
    color: '#5C584E',
  },
  histDrugsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  histDrugsText: {
    fontSize: 12,
    color: '#5C584E',
    flex: 1,
  },
  histFooterRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#E5E0D0',
    paddingTop: 8,
  },
  dateCol: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  dateText: {
    fontSize: 11,
    color: '#78716C',
  },
  viewDetailCol: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  viewDetailText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#00AEBB',
  },
});
