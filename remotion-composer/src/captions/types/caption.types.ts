export interface SupportWord {
  text: string;
  position?: 'top-left' | 'top-center' | 'top-right' | 'bottom-left' | 'bottom-center' | 'bottom-right';
  scale?: number; // relative font size scale (default 0.5)
}

export interface WordTimestamp {
  word: string;
  start: number; // in seconds
  end: number;   // in seconds
  probability?: number;
  isEmphasized?: boolean;
}

export interface StickerBadge {
  id?: string;
  src: string;
  label?: string;
  delayFrames?: number;
}

export interface KineticCue {
  id?: string;
  start: number; // in seconds
  end: number;   // in seconds
  text: string;
  topText?: string;
  bottomText?: string;
  bullets?: boolean;
  bulletColor?: string;
  mode?: 'normal' | 'emphasis' | 'stack' | 'editorial';
  serifFontFamily?: string;
  serifColor?: string;
  stickers?: StickerBadge[];
  x?: number; // normalized horizontal center (0.0 to 1.0, default 0.5)
  y?: number; // normalized vertical center (0.0 to 1.0)
  sizeScale?: number; // custom scale multiplier
  fontFamily?: string;
  fontWeight?: number;
  color?: string;
  support?: SupportWord;
  words?: WordTimestamp[];
  scriptText?: string;
  showCursor?: boolean;
}

export interface CaptionStylePreset {
  style_id: string;
  name: string;
  font_family: string;
  font_weight: number;
  font_color: string;
  text_alignment?: 'left' | 'center' | 'right';
  letter_spacing_em?: number;
  background?: string;
  background_blur_px?: number;
  background_border_radius_px?: number;
  background_padding_px?: string;
  outline_enabled?: boolean;
  outline_color?: string;
  outline_width_px?: number;
  shadow_enabled?: boolean;
  shadow_style?: string;
  word_level_timing?: boolean;
  emphasis_enabled?: boolean;
  emphasis_scale?: number;
  emphasis_color?: string;
  emphasis_font_weight?: number;
  highlight_active_word?: boolean;
  caption_grouping?: {
    minimum_words?: number;
    maximum_words?: number;
    target_words_per_cue?: number;
    max_chars_per_line?: number;
    pause_threshold_ms?: number;
  };
  animation: {
    type?: string;
    duration_ms?: number;
    enter_frames: number;
    exit_frames: number;
    initial_scale: number;
    final_scale: number;
    exit_scale?: number;
    fade_in: boolean;
    fade_out: boolean;
    easing?: string;
  };
  layout: {
    horizontal_alignment?: string;
    vertical_position: number;
    top_emphasis_vertical_position?: number;
    safe_margin_percent: number;
    max_width_percent: number;
  };
  rendering: {
    resolution_adaptive: boolean;
    anti_aliasing?: boolean;
    transparent_overlay?: boolean;
    normal_size_pct_of_width: number;
    emphasis_size_pct_of_width: number;
    support_size_pct_of_width: number;
  };
}

export interface VideoCut {
  id?: string;
  source?: string;
  in_seconds: number;
  out_seconds: number;
  speed?: number;
  transform?: {
    scale?: number;
    position?: string;
  };
}

export interface BRollOverlayEvent {
  id?: string;
  asset_path: string;
  asset_id?: string;
  asset_kind?: string;
  start_seconds: number;
  end_seconds: number;
  motion?: string;
  sfx?: string;
  transition?: string;
  position?: string;
  confidence?: number;
  script_text?: string;
  displayMode?: 'card' | 'fullscreen';
  cardBorderRadius?: number;
}

export interface KineticCaptionsVideoProps {
  videoSrc: string;
  cuts?: VideoCut[];
  cues: KineticCue[];
  overlays?: BRollOverlayEvent[];
  preset?: CaptionStylePreset;
  presetId?: string;
  aspectRatio?: '9:16' | '16:9' | '1:1';
}
