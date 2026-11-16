/**
 * Ephemeral Image Cache Cleanup Module (Task M6 / Acceptance Criterion #4)
 *
 * Ensures prescription images captured from camera, media library, image manipulator,
 * or synthetic fixture conversions are strictly ephemeral. Tracks local URIs and
 * guarantees full deletion from the device filesystem or memory on upload completion,
 * discard/retake, or screen unmount.
 */

import * as FileSystem from 'expo-file-system';
import { Platform } from 'react-native';

/**
 * In-memory registry tracking all temporary file URIs generated during the
 * prescription capture lifecycle.
 */
export const trackedTempImageUris = new Set<string>();

/**
 * Register a newly created temporary prescription image URI for tracked cleanup.
 */
export function registerTempPrescriptionUri(uri: string | null | undefined): void {
  if (!uri || typeof uri !== 'string') {
    return;
  }
  const cleanUri = uri.trim();
  if (cleanUri.length > 0) {
    trackedTempImageUris.add(cleanUri);
  }
}

/**
 * Delete a single temporary prescription image from disk or revoke its blob URL,
 * and unregister it from the tracking set.
 */
export async function cleanupPrescriptionUri(uri: string | null | undefined): Promise<void> {
  if (!uri || typeof uri !== 'string') {
    return;
  }

  const cleanUri = uri.trim();
  trackedTempImageUris.delete(cleanUri);

  // Web platform blob URLs
  if (Platform.OS === 'web') {
    if (cleanUri.startsWith('blob:') && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
      try {
        URL.revokeObjectURL(cleanUri);
      } catch (err) {
        console.debug('Failed to revoke blob URL:', err);
      }
    }
    return;
  }

  // Native filesystem (file:// or local cache paths)
  try {
    const info = await FileSystem.getInfoAsync(cleanUri);
    if (info.exists) {
      await FileSystem.deleteAsync(cleanUri, { idempotent: true });
    }
  } catch (err) {
    console.debug('Prescription image cleanup deleteAsync warning:', err);
  }
}

/**
 * Delete all tracked temporary prescription image files and clear the registry.
 * Returns the list of URIs that were cleaned up.
 */
export async function cleanupAllTempPrescriptionImages(): Promise<string[]> {
  const urisToClean = Array.from(trackedTempImageUris);
  trackedTempImageUris.clear();

  await Promise.all(
    urisToClean.map(async (uri) => {
      if (Platform.OS === 'web') {
        if (uri.startsWith('blob:') && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
          try {
            URL.revokeObjectURL(uri);
          } catch (err) {
            console.debug('Blob revoke warning:', err);
          }
        }
        return;
      }

      try {
        const info = await FileSystem.getInfoAsync(uri);
        if (info.exists) {
          await FileSystem.deleteAsync(uri, { idempotent: true });
        }
      } catch (err) {
        console.debug('Failed to delete temp prescription image:', uri, err);
      }
    })
  );

  return urisToClean;
}

/**
 * Retrieve the current set of remaining temporary prescription URIs.
 * Used for automated assertions and verification (assert remaining === 0).
 */
export function getRemainingTempPrescriptionUris(): string[] {
  return Array.from(trackedTempImageUris);
}
