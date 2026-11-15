/**
 * Prescriptions Feature Module
 * Multimodal camera capture, OCR Schedule H/H1/X compliance, and doctor registry verification.
 */

export interface PrescriptionScanResult {
  scanId: string;
  prescriberName: string;
  doctorRegistration: string;
  patientName: string;
  schedule: string;
  isCompliant: boolean;
}

