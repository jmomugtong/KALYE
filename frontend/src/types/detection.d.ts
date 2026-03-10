export enum DetectionType {
  POTHOLE = 'pothole',
  OBSTRUCTION = 'obstruction',
  MISSING_SIGN = 'missing_sign',
  CURB_RAMP = 'curb_ramp',
  DAMAGED_SIDEWALK = 'damaged_sidewalk',
  MISSING_RAMP = 'missing_ramp',
  BLOCKED_PATH = 'blocked_path',
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DetectionResult {
  id: string;
  type: DetectionType;
  confidence: number;
  boundingBox: BoundingBox;
  label: string;
  description?: string;
}

export interface SegmentationResult {
  id: string;
  imageId: string;
  maskUrl: string;
  classes: SegmentationClass[];
  sidewalkCoveragePercent: number;
  roadCoveragePercent: number;
  curbCoveragePercent: number;
}

export interface SegmentationClass {
  label: string;
  pixelCount: number;
  percentage: number;
  color: string;
}

export interface DetectionSummary {
  totalDetections: number;
  byType: Record<DetectionType, number>;
  averageConfidence: number;
  highConfidenceCount: number;
  lowConfidenceCount: number;
}
