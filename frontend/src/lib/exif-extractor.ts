/**
 * EXIF GPS extraction utilities.
 *
 * Reads raw EXIF data from JPEG/PNG files using DataView on the file's
 * ArrayBuffer and converts DMS (degrees-minutes-seconds) coordinates to
 * decimal degrees.
 */

export interface GPSCoordinates {
  lat: number;
  lng: number;
}

export interface ImageMetadata {
  gps: GPSCoordinates | null;
  camera: string | null;
  timestamp: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Convert degrees/minutes/seconds + compass reference to a signed decimal
 * degree value.
 */
export function parseDMS(
  degrees: number,
  minutes: number,
  seconds: number,
  ref: string,
): number {
  let decimal = degrees + minutes / 60 + seconds / 3600;
  if (ref === 'S' || ref === 'W') {
    decimal = -decimal;
  }
  return decimal;
}

// ---------------------------------------------------------------------------
// Low-level EXIF reader
// ---------------------------------------------------------------------------

interface IFDEntry {
  tag: number;
  type: number;
  count: number;
  valueOffset: number;
}

function readUint16(view: DataView, offset: number, littleEndian: boolean): number {
  return view.getUint16(offset, littleEndian);
}

function readUint32(view: DataView, offset: number, littleEndian: boolean): number {
  return view.getUint32(offset, littleEndian);
}

function readRational(view: DataView, offset: number, littleEndian: boolean): number {
  const numerator = readUint32(view, offset, littleEndian);
  const denominator = readUint32(view, offset + 4, littleEndian);
  return denominator === 0 ? 0 : numerator / denominator;
}

function readIFDEntry(view: DataView, offset: number, littleEndian: boolean): IFDEntry {
  return {
    tag: readUint16(view, offset, littleEndian),
    type: readUint16(view, offset + 2, littleEndian),
    count: readUint32(view, offset + 4, littleEndian),
    valueOffset: readUint32(view, offset + 8, littleEndian),
  };
}

function readString(view: DataView, offset: number, length: number): string {
  let str = '';
  for (let i = 0; i < length; i++) {
    const code = view.getUint8(offset + i);
    if (code === 0) break;
    str += String.fromCharCode(code);
  }
  return str;
}

function getStringValue(
  view: DataView,
  entry: IFDEntry,
  tiffStart: number,
  littleEndian: boolean,
): string {
  if (entry.count <= 4) {
    // Value stored inline in the valueOffset field
    const inlineOffset = tiffStart + entry.valueOffset;
    // Re-read from the raw 4-byte slot at the entry's value position
    // For short strings (<= 4 bytes) they are packed directly.
    return readString(view, inlineOffset, entry.count);
  }
  return readString(view, tiffStart + entry.valueOffset, entry.count);
}

function readDMSRationals(
  view: DataView,
  offset: number,
  littleEndian: boolean,
): [number, number, number] {
  const degrees = readRational(view, offset, littleEndian);
  const minutes = readRational(view, offset + 8, littleEndian);
  const seconds = readRational(view, offset + 16, littleEndian);
  return [degrees, minutes, seconds];
}

// EXIF tag constants
const TAG_GPS_IFD_POINTER = 0x8825;
const TAG_EXIF_IFD_POINTER = 0x8769;
const TAG_GPS_LATITUDE_REF = 0x0001;
const TAG_GPS_LATITUDE = 0x0002;
const TAG_GPS_LONGITUDE_REF = 0x0003;
const TAG_GPS_LONGITUDE = 0x0004;
const TAG_MAKE = 0x010f;
const TAG_MODEL = 0x0110;
const TAG_DATE_TIME_ORIGINAL = 0x9003;
const TAG_DATE_TIME = 0x0132;

interface ParsedExif {
  gpsLatRef: string | null;
  gpsLat: [number, number, number] | null;
  gpsLngRef: string | null;
  gpsLng: [number, number, number] | null;
  make: string | null;
  model: string | null;
  dateTime: string | null;
}

function parseIFD(
  view: DataView,
  tiffStart: number,
  ifdOffset: number,
  littleEndian: boolean,
  result: ParsedExif,
  depth: number,
): void {
  if (depth > 4) return; // prevent infinite recursion

  const abs = tiffStart + ifdOffset;
  if (abs + 2 > view.byteLength) return;

  const entryCount = readUint16(view, abs, littleEndian);

  for (let i = 0; i < entryCount; i++) {
    const entryOffset = abs + 2 + i * 12;
    if (entryOffset + 12 > view.byteLength) break;

    const entry = readIFDEntry(view, entryOffset, littleEndian);

    switch (entry.tag) {
      case TAG_GPS_IFD_POINTER:
        parseGPSIFD(view, tiffStart, entry.valueOffset, littleEndian, result);
        break;
      case TAG_EXIF_IFD_POINTER:
        parseIFD(view, tiffStart, entry.valueOffset, littleEndian, result, depth + 1);
        break;
      case TAG_MAKE:
        result.make = getStringValue(view, entry, tiffStart, littleEndian).trim();
        break;
      case TAG_MODEL:
        result.model = getStringValue(view, entry, tiffStart, littleEndian).trim();
        break;
      case TAG_DATE_TIME_ORIGINAL:
      case TAG_DATE_TIME:
        if (!result.dateTime) {
          result.dateTime = getStringValue(view, entry, tiffStart, littleEndian).trim();
        }
        break;
    }
  }
}

function parseGPSIFD(
  view: DataView,
  tiffStart: number,
  ifdOffset: number,
  littleEndian: boolean,
  result: ParsedExif,
): void {
  const abs = tiffStart + ifdOffset;
  if (abs + 2 > view.byteLength) return;

  const entryCount = readUint16(view, abs, littleEndian);

  for (let i = 0; i < entryCount; i++) {
    const entryOffset = abs + 2 + i * 12;
    if (entryOffset + 12 > view.byteLength) break;

    const entry = readIFDEntry(view, entryOffset, littleEndian);

    switch (entry.tag) {
      case TAG_GPS_LATITUDE_REF:
        result.gpsLatRef = String.fromCharCode(view.getUint8(entryOffset + 8));
        break;
      case TAG_GPS_LATITUDE:
        result.gpsLat = readDMSRationals(
          view,
          tiffStart + entry.valueOffset,
          littleEndian,
        );
        break;
      case TAG_GPS_LONGITUDE_REF:
        result.gpsLngRef = String.fromCharCode(view.getUint8(entryOffset + 8));
        break;
      case TAG_GPS_LONGITUDE:
        result.gpsLng = readDMSRationals(
          view,
          tiffStart + entry.valueOffset,
          littleEndian,
        );
        break;
    }
  }
}

function parseExifFromBuffer(buffer: ArrayBuffer): ParsedExif {
  const view = new DataView(buffer);
  const result: ParsedExif = {
    gpsLatRef: null,
    gpsLat: null,
    gpsLngRef: null,
    gpsLng: null,
    make: null,
    model: null,
    dateTime: null,
  };

  // Find JPEG SOI marker
  if (view.getUint8(0) !== 0xff || view.getUint8(1) !== 0xd8) {
    return result; // Not a JPEG
  }

  let offset = 2;

  while (offset < view.byteLength - 1) {
    if (view.getUint8(offset) !== 0xff) {
      offset++;
      continue;
    }

    const marker = view.getUint8(offset + 1);

    // APP1 marker (EXIF)
    if (marker === 0xe1) {
      const length = view.getUint16(offset + 2);

      // Check "Exif\0\0" header
      const exifHeader =
        view.getUint8(offset + 4) === 0x45 && // E
        view.getUint8(offset + 5) === 0x78 && // x
        view.getUint8(offset + 6) === 0x69 && // i
        view.getUint8(offset + 7) === 0x66 && // f
        view.getUint8(offset + 8) === 0x00 &&
        view.getUint8(offset + 9) === 0x00;

      if (!exifHeader) {
        offset += 2 + length;
        continue;
      }

      const tiffStart = offset + 10;

      // Determine byte order
      const byteOrder = view.getUint16(tiffStart);
      const littleEndian = byteOrder === 0x4949; // "II"

      // Verify TIFF magic number
      if (readUint16(view, tiffStart + 2, littleEndian) !== 0x002a) {
        return result;
      }

      // Read first IFD offset
      const firstIFDOffset = readUint32(view, tiffStart + 4, littleEndian);

      parseIFD(view, tiffStart, firstIFDOffset, littleEndian, result, 0);

      return result;
    }

    // Skip non-APP1 markers
    if (marker >= 0xe0 && marker <= 0xef) {
      const length = view.getUint16(offset + 2);
      offset += 2 + length;
    } else if (marker === 0xda) {
      // Start of scan — no more metadata
      break;
    } else {
      offset++;
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Extract GPS coordinates from a file's EXIF data.
 * Returns null if GPS data is not available.
 */
export async function extractGPS(file: File): Promise<GPSCoordinates | null> {
  try {
    const buffer = await file.arrayBuffer();
    const exif = parseExifFromBuffer(buffer);

    if (!exif.gpsLat || !exif.gpsLng || !exif.gpsLatRef || !exif.gpsLngRef) {
      return null;
    }

    const lat = parseDMS(exif.gpsLat[0], exif.gpsLat[1], exif.gpsLat[2], exif.gpsLatRef);
    const lng = parseDMS(exif.gpsLng[0], exif.gpsLng[1], exif.gpsLng[2], exif.gpsLngRef);

    if (isNaN(lat) || isNaN(lng)) return null;

    return { lat, lng };
  } catch {
    return null;
  }
}

/**
 * Extract full metadata (GPS, camera model, timestamp) from a file's EXIF
 * data. Any field may be null if the data is not present.
 */
export async function extractMetadata(file: File): Promise<ImageMetadata> {
  try {
    const buffer = await file.arrayBuffer();
    const exif = parseExifFromBuffer(buffer);

    let gps: GPSCoordinates | null = null;
    if (exif.gpsLat && exif.gpsLng && exif.gpsLatRef && exif.gpsLngRef) {
      const lat = parseDMS(exif.gpsLat[0], exif.gpsLat[1], exif.gpsLat[2], exif.gpsLatRef);
      const lng = parseDMS(exif.gpsLng[0], exif.gpsLng[1], exif.gpsLng[2], exif.gpsLngRef);
      if (!isNaN(lat) && !isNaN(lng)) {
        gps = { lat, lng };
      }
    }

    const cameraParts = [exif.make, exif.model].filter(Boolean);
    const camera = cameraParts.length > 0 ? cameraParts.join(' ') : null;

    return {
      gps,
      camera,
      timestamp: exif.dateTime,
    };
  } catch {
    return { gps: null, camera: null, timestamp: null };
  }
}
