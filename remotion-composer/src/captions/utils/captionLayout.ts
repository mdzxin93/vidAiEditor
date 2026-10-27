import { CaptionStylePreset, KineticCue } from '../types/caption.types';

export const clamp = (v: number, min: number, max: number): number =>
  Math.max(min, Math.min(max, v));

export function computeCueLayout(
  cue: KineticCue,
  preset: CaptionStylePreset,
  width: number,
  height: number
): {
  x: number;
  y: number;
  fontSize: number;
  isEmphasis: boolean;
  maxWidth: number;
} {
  const isEmphasis = cue.mode === 'emphasis' || cue.mode === 'stack';
  const customScale = cue.sizeScale || 1.0;

  const rendering = preset.rendering || {
    normal_size_pct_of_width: 0.072,
    emphasis_size_pct_of_width: 0.125,
    support_size_pct_of_width: 0.055,
  };
  const layout = preset.layout || {
    horizontal_alignment: 'center',
    vertical_position: 0.65,
    top_emphasis_vertical_position: 0.65,
    safe_margin_percent: 8,
    max_width_percent: 92,
  };

  // Responsive font size relative to width, maintaining visual impact across resolutions
  const baseSizePct = isEmphasis
    ? (rendering.emphasis_size_pct_of_width || 0.125)
    : (rendering.normal_size_pct_of_width || 0.072);

  const fontSize = Math.round(width * baseSizePct * customScale);

  // Layout X coordinate (default center 50%)
  const rawX = cue.x !== undefined ? cue.x : (layout.horizontal_alignment === 'left' ? 0.2 : 0.5);
  const x = clamp(rawX, 0.08, 0.92) * width;

  // Layout Y coordinate
  let defaultY = layout.vertical_position || 0.65;
  if (isEmphasis && layout.top_emphasis_vertical_position !== undefined) {
    defaultY = layout.top_emphasis_vertical_position;
  }
  const rawY = cue.y !== undefined ? cue.y : defaultY;
  const y = clamp(rawY, 0.08, 0.92) * height;

  const safeMarginPct = (layout.safe_margin_percent || 8) / 100;
  const maxAllowedWidth = width * (1.0 - 2 * safeMarginPct);
  const maxWidth = Math.min(width * ((layout.max_width_percent || 92) / 100), maxAllowedWidth);

  return {
    x,
    y,
    fontSize,
    isEmphasis,
    maxWidth,
  };
}
