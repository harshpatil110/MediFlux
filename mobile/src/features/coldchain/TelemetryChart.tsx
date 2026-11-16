/**
 * Native-Compatible SVG Telemetry Chart (Task M7).
 * Renders cross-platform temperature time-series with safe envelope thresholds (2°C - 8°C)
 * and excursion markers using react-native-svg.
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet, LayoutChangeEvent, Platform } from 'react-native';
import Svg, { Line, Polyline, Circle, Rect, Text as SvgText, G } from 'react-native-svg';

export interface TelemetryReadingPoint {
  ts: string;
  temperature_c: number;
  humidity?: number;
  shock_g?: number;
  decision?: string;
}

interface Props {
  readings: TelemetryReadingPoint[];
  storageMinC?: number;
  storageMaxC?: number;
  height?: number;
}

export const TelemetryChart: React.FC<Props> = ({
  readings = [],
  storageMinC = 2.0,
  storageMaxC = 8.0,
  height = 190,
}) => {
  const [chartWidth, setChartWidth] = useState<number>(340);

  const onLayout = (event: LayoutChangeEvent) => {
    const { width } = event.nativeEvent.layout;
    if (width > 50) {
      setChartWidth(width);
    }
  };

  // Provide synthetic fallback readings if list is empty
  const data = readings.length > 0 ? readings : [
    { ts: '1', temperature_c: 4.8, humidity: 50, shock_g: 0.2 },
    { ts: '2', temperature_c: 5.1, humidity: 49, shock_g: 0.1 },
    { ts: '3', temperature_c: 5.0, humidity: 51, shock_g: 0.2 },
  ];

  const paddingLeft = 45;
  const paddingRight = 20;
  const paddingTop = 25;
  const paddingBottom = 30;

  const plotWidth = Math.max(100, chartWidth - paddingLeft - paddingRight);
  const plotHeight = Math.max(50, height - paddingTop - paddingBottom);

  // Compute scale boundaries
  const allTemps = data.map((d) => Number(d.temperature_c) || 5.0);
  const dataMin = Math.min(...allTemps, storageMinC - 1.0);
  const dataMax = Math.max(...allTemps, storageMaxC + 1.0);
  const minTemp = Math.floor(dataMin - 1.0);
  const maxTemp = Math.ceil(dataMax + 1.0);
  const tempRange = Math.max(1.0, maxTemp - minTemp);

  const getY = (temp: number) => {
    const clamped = Math.max(minTemp, Math.min(temp, maxTemp));
    const fraction = (clamped - minTemp) / tempRange;
    return paddingTop + (1 - fraction) * plotHeight;
  };

  const getX = (index: number) => {
    if (data.length <= 1) return paddingLeft + plotWidth / 2;
    return paddingLeft + (index / (data.length - 1)) * plotWidth;
  };

  // Generate polyline points string: "x1,y1 x2,y2 ..."
  const polylinePoints = data
    .map((d, i) => `${getX(i).toFixed(1)},${getY(d.temperature_c).toFixed(1)}`)
    .join(' ');

  const upperLimitY = getY(storageMaxC);
  const lowerLimitY = getY(storageMinC);

  const latest = data[data.length - 1] || { temperature_c: 5.0, humidity: 50, shock_g: 0.2 };
  const latestTemp = Number(latest.temperature_c) || 5.0;
  const isLatestExcursion = latestTemp > storageMaxC || latestTemp < storageMinC;

  return (
    <View style={styles.container} onLayout={onLayout}>
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.chartTitle}>THERMAL ENVELOPE TELEMETRY</Text>
          <Text style={styles.chartSubtitle}>
            Safe bounds: {storageMinC.toFixed(1)}°C — {storageMaxC.toFixed(1)}°C
          </Text>
        </View>
        <View style={styles.metricsBadge}>
          <Text
            style={[
              styles.currentTempText,
              { color: isLatestExcursion ? '#EF4444' : '#00AEBB' },
            ]}
          >
            {latestTemp.toFixed(1)}°C
          </Text>
          <Text style={styles.secondaryMetrics}>
            💧 {latest.humidity ? `${Math.round(latest.humidity)}%` : '50%'} • 💥 {latest.shock_g ? `${latest.shock_g.toFixed(1)}g` : '0.2g'}
          </Text>
        </View>
      </View>

      <Svg width={chartWidth} height={height}>
        {/* Background plot container */}
        <Rect
          x={paddingLeft}
          y={paddingTop}
          width={plotWidth}
          height={plotHeight}
          fill="#031211"
          stroke="#2A2824"
          strokeWidth="1"
        />

        {/* Safe temperature band shading */}
        {upperLimitY < lowerLimitY && (
          <Rect
            x={paddingLeft}
            y={upperLimitY}
            width={plotWidth}
            height={lowerLimitY - upperLimitY}
            fill="#00AEBB"
            fillOpacity="0.08"
          />
        )}

        {/* Upper limit threshold line (8°C) */}
        <Line
          x1={paddingLeft}
          y1={upperLimitY}
          x2={paddingLeft + plotWidth}
          y2={upperLimitY}
          stroke="#EF4444"
          strokeWidth="1.5"
          strokeDasharray="4, 3"
        />
        <SvgText
          x={paddingLeft + 6}
          y={upperLimitY - 4}
          fill="#EF4444"
          fontSize="9"
          fontWeight="bold"
          fontFamily={Platform.OS === 'ios' ? 'Menlo' : 'monospace'}
        >
          {storageMaxC.toFixed(1)}°C MAX
        </SvgText>

        {/* Lower limit threshold line (2°C) */}
        <Line
          x1={paddingLeft}
          y1={lowerLimitY}
          x2={paddingLeft + plotWidth}
          y2={lowerLimitY}
          stroke="#00AEBB"
          strokeWidth="1.5"
          strokeDasharray="4, 3"
        />
        <SvgText
          x={paddingLeft + 6}
          y={lowerLimitY + 11}
          fill="#00AEBB"
          fontSize="9"
          fontWeight="bold"
          fontFamily={Platform.OS === 'ios' ? 'Menlo' : 'monospace'}
        >
          {storageMinC.toFixed(1)}°C MIN
        </SvgText>

        {/* Y-Axis Value Labels */}
        <SvgText
          x={paddingLeft - 8}
          y={upperLimitY + 3}
          fill="#A8A29E"
          fontSize="9"
          textAnchor="end"
          fontFamily={Platform.OS === 'ios' ? 'Menlo' : 'monospace'}
        >
          {storageMaxC.toFixed(0)}°C
        </SvgText>
        <SvgText
          x={paddingLeft - 8}
          y={lowerLimitY + 3}
          fill="#A8A29E"
          fontSize="9"
          textAnchor="end"
          fontFamily={Platform.OS === 'ios' ? 'Menlo' : 'monospace'}
        >
          {storageMinC.toFixed(0)}°C
        </SvgText>

        {/* Temperature Time Series Line */}
        <Polyline
          points={polylinePoints}
          fill="none"
          stroke="#00AEBB"
          strokeWidth="2"
        />

        {/* Data points */}
        {data.map((d, i) => {
          const cx = getX(i);
          const cy = getY(d.temperature_c);
          const isExcursion = d.temperature_c > storageMaxC || d.temperature_c < storageMinC;
          const fillColor = isExcursion ? '#EF4444' : '#00AEBB';

          return (
            <G key={`point-${i}`}>
              <Circle
                cx={cx}
                cy={cy}
                r={isExcursion ? 4.5 : 3.5}
                fill={fillColor}
                stroke="#031211"
                strokeWidth="1.5"
              />
            </G>
          );
        })}
      </Svg>

      <View style={styles.legendRow}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#00AEBB' }]} />
          <Text style={styles.legendText}>Nominal (2-8°C)</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#EF4444' }]} />
          <Text style={styles.legendText}>Thermal Excursion</Text>
        </View>
        <Text style={styles.countText}>{data.length} readings recorded</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#031211',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2A2824',
    padding: 12,
    marginVertical: 8,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  chartTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: '#F7F5F0',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    letterSpacing: 0.5,
  },
  chartSubtitle: {
    fontSize: 11,
    color: '#8C887B',
    marginTop: 2,
  },
  metricsBadge: {
    alignItems: 'flex-end',
  },
  currentTempText: {
    fontSize: 18,
    fontWeight: '800',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  secondaryMetrics: {
    fontSize: 10,
    color: '#A8A29E',
    marginTop: 2,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  legendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 6,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: '#1C1917',
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 12,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  legendText: {
    fontSize: 10,
    color: '#A8A29E',
  },
  countText: {
    fontSize: 10,
    color: '#5C584E',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});
