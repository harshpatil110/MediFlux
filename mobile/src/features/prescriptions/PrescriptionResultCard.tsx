import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ShieldCheck,
  UserCheck,
  UserX,
  Clock,
  ArrowRight,
  FileCheck2,
  Lock,
} from 'lucide-react-native';
import { PrescriptionRecord } from './types';

interface PrescriptionResultCardProps {
  prescription: PrescriptionRecord;
  showAttachButton?: boolean;
  onAttachToSale?: (prescription: PrescriptionRecord) => void;
  compact?: boolean;
}

export const PrescriptionResultCard: React.FC<PrescriptionResultCardProps> = ({
  prescription,
  showAttachButton = true,
  onAttachToSale,
  compact = false,
}) => {
  const router = useRouter();

  const isApproved = prescription.status === 'approved' || prescription.decision === 'approve_dispense';
  const isFlagged = prescription.status === 'flagged' || prescription.decision === 'flag';
  const isRejected = prescription.status === 'rejected' || prescription.decision === 'reject';

  const handleOpenApprovals = () => {
    if (prescription.hitl_task_id) {
      router.push({
        pathname: '/approvals/[id]',
        params: { id: prescription.hitl_task_id },
      } as any);
    } else {
      router.push('/(tabs)/approvals' as any);
    }
  };

  const handleAttachToSale = () => {
    if (onAttachToSale) {
      onAttachToSale(prescription);
      return;
    }

    const firstDrug = prescription.drugs?.[0];
    router.push({
      pathname: '/(tabs)/sell',
      params: {
        prescription_id: prescription.prescription_id || prescription.id,
        product_sku: firstDrug?.sku || '',
        patient_initials: prescription.patient_initials || 'ANON',
      },
    } as any);
  };

  return (
    <View style={styles.cardContainer}>
      {/* 1. Decision Status Banner */}
      {isApproved && (
        <View style={[styles.banner, styles.bannerApproved]}>
          <CheckCircle2 size={20} color="#10B981" />
          <View style={styles.bannerTextCol}>
            <Text style={styles.bannerTitleApproved}>✓ APPROVED FOR DISPENSING</Text>
            <Text style={styles.bannerSubApproved}>
              Valid verified physician & CDSCO schedule compliant.
            </Text>
          </View>
        </View>
      )}

      {isFlagged && (
        <View style={[styles.banner, styles.bannerFlagged]}>
          <AlertTriangle size={20} color="#D97706" />
          <View style={styles.bannerTextCol}>
            <Text style={styles.bannerTitleFlagged}>⏸ SENT FOR HUMAN APPROVAL (HITL)</Text>
            <Text style={styles.bannerSubFlagged}>
              Physician unverified or unlisted formulation. Hold active.
            </Text>
            <TouchableOpacity
              style={styles.approvalsCtaBtn}
              onPress={handleOpenApprovals}
              activeOpacity={0.8}
            >
              <Text style={styles.approvalsCtaText}>Open in Approvals (M5) →</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {isRejected && (
        <View style={[styles.banner, styles.bannerRejected]}>
          <XCircle size={20} color="#EF4444" />
          <View style={styles.bannerTextCol}>
            <Text style={styles.bannerTitleRejected}>✕ DISPENSE REJECTED</Text>
            <Text style={styles.bannerSubRejected}>
              Missing mandatory statutory credentials (e.g. Doctor Reg No).
            </Text>
          </View>
        </View>
      )}

      {/* 2. Privacy Minimized Header: Initials & Doctor Info */}
      <View style={styles.section}>
        <View style={styles.rowBetween}>
          <View style={styles.fieldBlock}>
            <Text style={styles.fieldLabel}>PATIENT INITIALS</Text>
            <View style={styles.initialsBadge}>
              <Text style={styles.initialsText}>{prescription.patient_initials || 'ANON'}</Text>
            </View>
          </View>

          <View style={[styles.fieldBlock, { alignItems: 'flex-end' }]}>
            <Text style={styles.fieldLabel}>PRESCRIPTION ID</Text>
            <Text style={styles.monoId}>
              {(prescription.prescription_id || prescription.id || '').substring(0, 16)}...
            </Text>
          </View>
        </View>

        <View style={styles.doctorBlock}>
          <Text style={styles.fieldLabel}>PRESCRIBING PHYSICIAN</Text>
          <View style={styles.doctorDetailsRow}>
            <Text style={styles.doctorName}>
              {prescription.doctor_name || 'Dr. Unknown Physician'}
            </Text>
            <Text style={styles.doctorRegNo}>
              Reg No:{' '}
              <Text style={styles.monoText}>
                {prescription.doctor_registration_no || 'MISSING / UNKNOWN'}
              </Text>
            </Text>
          </View>

          <View style={styles.doctorStatusRow}>
            {prescription.doctor_verified ? (
              <View style={styles.docBadgeVerified}>
                <UserCheck size={14} color="#059669" />
                <Text style={styles.docBadgeTextVerified}>VERIFIED IN CDSCO REGISTRY</Text>
              </View>
            ) : (
              <View style={styles.docBadgeUnverified}>
                <UserX size={14} color="#D97706" />
                <Text style={styles.docBadgeTextUnverified}>
                  {prescription.doctor_verification_reason === 'missing_registration_number'
                    ? 'MISSING CREDENTIALS'
                    : 'UNVERIFIED PHYSICIAN'}
                </Text>
              </View>
            )}
          </View>
        </View>
      </View>

      {/* 3. CDSCO Drug Schedule Class List */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          PRESCRIBED FORMULATIONS ({prescription.drugs?.length || 0})
        </Text>

        {(prescription.drugs || []).map((drug, idx) => {
          const isOtc = drug.schedule_class === 'OTC';
          const isSchedH =
            drug.schedule_class === 'H' ||
            drug.schedule_class === 'H1' ||
            drug.schedule_class === 'X';
          const isUnknown = drug.schedule_class === 'unknown';

          return (
            <View key={`drug-${idx}`} style={styles.drugItemCard}>
              <View style={styles.drugHeaderRow}>
                <Text style={styles.drugName}>{drug.name}</Text>
                {isOtc && (
                  <View style={[styles.schedBadge, styles.schedBadgeOtc]}>
                    <Text style={styles.schedTextOtc}>OTC (SCHEDULE 0)</Text>
                  </View>
                )}
                {isSchedH && (
                  <View style={[styles.schedBadge, styles.schedBadgeH]}>
                    <Text style={styles.schedTextH}>SCHEDULE {drug.schedule_class}</Text>
                  </View>
                )}
                {isUnknown && (
                  <View style={[styles.schedBadge, styles.schedBadgeUnknown]}>
                    <Text style={styles.schedTextUnknown}>UNKNOWN SCHEDULE (NOT GUESSED)</Text>
                  </View>
                )}
              </View>

              <View style={styles.drugMetaRow}>
                {drug.dose ? <Text style={styles.drugMetaText}>Dose: {drug.dose}</Text> : null}
                {drug.quantity ? (
                  <Text style={styles.drugMetaText}>Qty: {drug.quantity} units</Text>
                ) : null}
                {drug.frequency ? (
                  <Text style={styles.drugMetaText}>Sig: {drug.frequency}</Text>
                ) : null}
              </View>
            </View>
          );
        })}
      </View>

      {/* 4. 4-Stage Workflow Steps (if present and not compact) */}
      {!compact && prescription.steps && prescription.steps.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>SOVEREIGN 4-STAGE PIPELINE TRACE</Text>
          <View style={styles.stepsContainer}>
            {prescription.steps.map((st, i) => {
              const isDone = st.status === 'done';
              const isStepFlagged = st.status === 'flagged';
              return (
                <View key={`step-${i}`} style={styles.stepRow}>
                  <View style={styles.stepIndexCol}>
                    <View
                      style={[
                        styles.stepDot,
                        isDone
                          ? styles.stepDotDone
                          : isStepFlagged
                            ? styles.stepDotFlagged
                            : styles.stepDotFail,
                      ]}
                    >
                      <Text style={styles.stepNum}>{i + 1}</Text>
                    </View>
                    {i < (prescription.steps?.length || 0) - 1 && <View style={styles.stepLine} />}
                  </View>
                  <View style={styles.stepContentCol}>
                    <Text style={styles.stepStageName}>{st.stage.replace('_', ' ').toUpperCase()}</Text>
                    <Text style={styles.stepSummary}>{st.summary}</Text>
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      )}

      {/* 5. Monospace Compliance Log Reference */}
      <View style={styles.complianceRow}>
        <FileCheck2 size={15} color="#5C584E" />
        <Text style={styles.complianceText}>
          Compliance Log ID:{' '}
          <Text style={styles.monoText}>
            {prescription.compliance_log_id || 'COMP-AUDIT-ACTIVE'}
          </Text>
        </Text>
      </View>

      {/* 6. Prominent Sovereign Privacy Notice Banner */}
      <View style={styles.privacyCard}>
        <Lock size={15} color="#00AEBB" />
        <Text style={styles.privacyNoticeText}>
          {prescription.privacy_notice ||
            '🔒 Sovereign Local Processing (sensitivity="sensitive"): Scans parsed strictly by local on-premise models. Patient names redacted to initials; cached image files purged.'}
        </Text>
      </View>

      {/* 7. Primary Action Button: Attach to Sale in POS (M4) */}
      {showAttachButton && isApproved && (
        <TouchableOpacity
          style={styles.attachBtn}
          onPress={handleAttachToSale}
          activeOpacity={0.85}
        >
          <Text style={styles.attachBtnText}>💊 Attach to Sale in POS (M4)</Text>
          <ArrowRight size={18} color="#031211" />
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  cardContainer: {
    backgroundColor: '#F7F5F0',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#D8D3C3',
    padding: 16,
    marginVertical: 8,
  },
  banner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 12,
    borderRadius: 6,
    borderWidth: 1,
    marginBottom: 14,
  },
  bannerApproved: {
    backgroundColor: '#ECFDF5',
    borderColor: '#A7F3D0',
  },
  bannerFlagged: {
    backgroundColor: '#FFFBEB',
    borderColor: '#FDE68A',
  },
  bannerRejected: {
    backgroundColor: '#FEF2F2',
    borderColor: '#FECACA',
  },
  bannerTextCol: {
    marginLeft: 10,
    flex: 1,
  },
  bannerTitleApproved: {
    fontSize: 13,
    fontWeight: '800',
    color: '#065F46',
    letterSpacing: 0.5,
  },
  bannerSubApproved: {
    fontSize: 12,
    color: '#047857',
    marginTop: 2,
  },
  bannerTitleFlagged: {
    fontSize: 13,
    fontWeight: '800',
    color: '#92400E',
    letterSpacing: 0.5,
  },
  bannerSubFlagged: {
    fontSize: 12,
    color: '#B45309',
    marginTop: 2,
  },
  bannerTitleRejected: {
    fontSize: 13,
    fontWeight: '800',
    color: '#991B1B',
    letterSpacing: 0.5,
  },
  bannerSubRejected: {
    fontSize: 12,
    color: '#B91C1C',
    marginTop: 2,
  },
  approvalsCtaBtn: {
    backgroundColor: '#D97706',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 4,
    alignSelf: 'flex-start',
    marginTop: 8,
  },
  approvalsCtaText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  section: {
    marginBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E0D0',
    paddingBottom: 12,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
    color: '#5C584E',
    marginBottom: 8,
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  fieldBlock: {
    flex: 1,
  },
  fieldLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#78716C',
    letterSpacing: 0.6,
    marginBottom: 3,
  },
  initialsBadge: {
    backgroundColor: '#031211',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    alignSelf: 'flex-start',
  },
  initialsText: {
    fontFamily: 'Courier',
    fontSize: 14,
    fontWeight: '900',
    color: '#00AEBB',
  },
  monoId: {
    fontFamily: 'Courier',
    fontSize: 11,
    color: '#5C584E',
  },
  doctorBlock: {
    marginTop: 6,
  },
  doctorDetailsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  doctorName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#031211',
  },
  doctorRegNo: {
    fontSize: 12,
    color: '#5C584E',
  },
  monoText: {
    fontFamily: 'Courier',
    fontWeight: '700',
    color: '#031211',
  },
  doctorStatusRow: {
    marginTop: 6,
  },
  docBadgeVerified: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ECFDF5',
    borderWidth: 1,
    borderColor: '#A7F3D0',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    alignSelf: 'flex-start',
    gap: 4,
  },
  docBadgeTextVerified: {
    fontSize: 10,
    fontWeight: '800',
    color: '#065F46',
    letterSpacing: 0.4,
  },
  docBadgeUnverified: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFBEB',
    borderWidth: 1,
    borderColor: '#FDE68A',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    alignSelf: 'flex-start',
    gap: 4,
  },
  docBadgeTextUnverified: {
    fontSize: 10,
    fontWeight: '800',
    color: '#B45309',
    letterSpacing: 0.4,
  },
  drugItemCard: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5E0D0',
    borderRadius: 6,
    padding: 10,
    marginBottom: 6,
  },
  drugHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  drugName: {
    fontSize: 14,
    fontWeight: '700',
    color: '#031211',
    flex: 1,
  },
  schedBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    marginLeft: 6,
  },
  schedBadgeOtc: {
    backgroundColor: '#ECFDF5',
    borderWidth: 1,
    borderColor: '#10B981',
  },
  schedTextOtc: {
    fontSize: 9,
    fontWeight: '800',
    color: '#065F46',
  },
  schedBadgeH: {
    backgroundColor: '#FFFBEB',
    borderWidth: 1,
    borderColor: '#F59E0B',
  },
  schedTextH: {
    fontSize: 9,
    fontWeight: '800',
    color: '#92400E',
  },
  schedBadgeUnknown: {
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#EF4444',
  },
  schedTextUnknown: {
    fontSize: 9,
    fontWeight: '900',
    color: '#991B1B',
  },
  drugMetaRow: {
    flexDirection: 'row',
    gap: 12,
  },
  drugMetaText: {
    fontSize: 11,
    color: '#5C584E',
  },
  stepsContainer: {
    marginTop: 4,
  },
  stepRow: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  stepIndexCol: {
    alignItems: 'center',
    width: 26,
    marginRight: 8,
  },
  stepDot: {
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepDotDone: {
    backgroundColor: '#00AEBB',
  },
  stepDotFlagged: {
    backgroundColor: '#F59E0B',
  },
  stepDotFail: {
    backgroundColor: '#EF4444',
  },
  stepNum: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
  },
  stepLine: {
    width: 1,
    flex: 1,
    backgroundColor: '#D8D3C3',
    marginVertical: 2,
  },
  stepContentCol: {
    flex: 1,
    paddingBottom: 4,
  },
  stepStageName: {
    fontSize: 11,
    fontWeight: '800',
    color: '#031211',
  },
  stepSummary: {
    fontSize: 11,
    color: '#5C584E',
    marginTop: 1,
  },
  complianceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  complianceText: {
    fontSize: 11,
    color: '#5C584E',
  },
  privacyCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E6F7F8',
    borderWidth: 1,
    borderColor: '#B2EBF0',
    borderRadius: 6,
    padding: 10,
    gap: 8,
    marginBottom: 12,
  },
  privacyNoticeText: {
    fontSize: 11,
    color: '#031211',
    flex: 1,
    lineHeight: 15,
  },
  attachBtn: {
    backgroundColor: '#00AEBB',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 6,
    gap: 8,
  },
  attachBtnText: {
    fontSize: 14,
    fontWeight: '800',
    color: '#031211',
    letterSpacing: 0.3,
  },
});
