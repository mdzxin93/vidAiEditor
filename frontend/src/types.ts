export type AspectRatio = '9:16' | '16:9' | '1:1';

export interface ProjectSummary {
  project_id: string;
  title: string;
  pipeline_type: string;
  has_pipeline_state?: boolean;
  poster?: string | null;
  live?: boolean;
  last_activity?: number;
  completed_count?: number;
  render_count?: number;
  scene_count?: number;
  has_edit_decisions?: boolean;
  qa_score?: number | null;
  qa_passed?: boolean | null;
}

export interface ProjectDetails {
  project_id: string;
  title: string;
  pipeline_type: string;
  aspect_ratio: AspectRatio;
  created_at?: string;
  media_count: number;
  primary_video?: MediaItem | null;
  has_edits: boolean;
  edit_decisions?: EditDecisions | null;
  qa_report?: QAReportData | null;
}

export interface MediaItem {
  name: string;
  relative_path: string;
  category: 'video' | 'broll' | 'reference' | 'audio' | 'music' | 'render';
  size_bytes: number;
  modified_at: number;
  thumbnail_url?: string | null;
  media_url: string;
  is_video: boolean;
  is_audio: boolean;
  is_image?: boolean;
}

export interface CutTransform {
  scale?: number;
  x?: number;
  y?: number;
  crop?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  zoom_provenance?: any;
}

export interface Cut {
  id: string;
  source?: string;
  in_seconds: number;
  out_seconds: number;
  speed?: number;
  transform?: CutTransform;
  transition_in?: string;
  transition_out?: string;
}

export interface OverlayContent {
  value?: string;
  label?: string;
  title?: string;
  subtitle?: string;
  text?: string;
  callout_type?: 'info' | 'warning' | 'tip' | 'quote';
  trend?: 'positive' | 'negative' | 'neutral';
  leftLabel?: string;
  leftValue?: string;
  rightLabel?: string;
  rightValue?: string;
  chartData?: Array<{ label: string; value: number }>;
}

export interface Overlay {
  id: string;
  type: string; // 'stat_card', 'text_card', 'callout', 'comparison', 'bar_chart', 'hero_title'
  in_seconds: number;
  out_seconds: number;
  position?: 'upper_third' | 'lower_third' | 'upper_window' | 'left_panel' | 'right_panel' | 'full_overlay';
  content?: OverlayContent;
  color?: string;
  accentColor?: string;
  backgroundColor?: string;
  fontSize?: number;
  animation?: 'spring' | 'pop' | 'slide' | 'fade';
}

export interface WordToken {
  word: string;
  start: number;
  end: number;
}

export interface KineticCaptionCue {
  id: string;
  text: string;
  start: number;
  end: number;
  mode: 'normal' | 'emphasis' | 'stack';
  emphasis_word?: string;
  support_words?: string;
  font_weight?: number;
  scale?: number;
  position?: { x: number; y: number };
  animation?: string;
  words?: WordToken[];
}

export interface SubtitlesConfig {
  enabled: boolean;
  style?: string;
  preset_id?: string;
  words?: WordToken[];
  cues?: KineticCaptionCue[];
  exports?: Record<string, string>;
}

export interface EditDecisions {
  version: string;
  render_runtime: string;
  renderer_family: string;
  cuts: Cut[];
  overlays: Overlay[];
  subtitles?: SubtitlesConfig;
  metadata?: {
    target_aspect?: string;
    caption_preset?: string;
    user_instruction?: string;
    talking_head_props?: {
      videoSrc?: string;
      overlays?: Overlay[];
      subtitles?: WordToken[];
      wordsPerPage?: number;
    };
    [key: string]: any;
  };
}

export interface QAIssue {
  issue_id: string;
  category: string;
  start_seconds: number;
  end_seconds: number;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  confidence: number;
  detection_source: string;
  description: string;
  suggested_fix: string;
  auto_fix_allowed: boolean;
  evidence?: Record<string, any>;
}

export interface QAReportData {
  report_id: string;
  video_path: string;
  duration_seconds: number;
  resolution: string;
  quality_score: number;
  passed: boolean;
  has_blockers?: boolean;
  blocking_issues_count?: number;
  passing_threshold?: number;
  severity_counts: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    info?: number;
  };
  issues: QAIssue[];
  fixes_applied: any[];
  summary: string;
}

export type JobStatus =
  | 'queued'
  | 'running'
  | 'analyzing'
  | 'planning'
  | 'rendering'
  | 'quality_check'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'interrupted'
  | 'recoverable';

export interface JobRecord {
  job_id: string;
  project_id: string;
  job_type: string;
  status: JobStatus;
  progress: number;
  stage: string;
  created_at: number;
  started_at?: number | null;
  completed_at?: number | null;
  error?: string | null;
  result?: any;
  logs: string[];
  recoverable?: boolean;
  last_checkpoint?: string | null;
  pid?: number | null;
}

export interface SystemMetrics {
  cpu_percent: number;
  ram_total_gb: number;
  ram_used_gb: number;
  ram_available_gb: number;
  ram_percent: number;
  active_renders: number;
  queued_jobs: number;
  interrupted_jobs?: number;
  hardware_note: string;
}
