/**
 * POS (Point of Sale) Feature Module
 * Retail pharmacy barcode scanning, atomic strip sales, and local inventory cache.
 */

export interface PosScanItem {
  id: string;
  sku: string;
  name: string;
  batchNumber: string;
  units: number;
  unitPrice: number;
  schedule: string;
}
