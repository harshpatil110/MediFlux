/**
 * Cold Chain Feature Module
 * Biologics IoT sensor telemetry, MKT calculation, and autonomous quarantine alerts.
 */

export interface ColdChainAlert {
  batchId: string;
  sensorId: string;
  temperatureC: number;
  thresholdC: number;
  severity: 'warning' | 'critical';
  timestamp: string;
}
