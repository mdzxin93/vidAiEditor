import React, { useState } from 'react';
import {
  Sparkles,
  Bot,
  Scissors,
  ZoomIn,
  Type,
  FileCode,
  Layers,
  CheckCircle,
  Brain,
  Camera,
} from 'lucide-react';
import { MediaItem, AspectRatio } from '../types';
import { analyzeFootage, generateEditorialPlan, generateKineticCaptions, exportKineticCaptions } from '../api';

interface AiPanelProps {
  projectId: string;
  primaryVideo: MediaItem | null;
  mediaList: MediaItem[];
  currentAspectRatio: AspectRatio;
  onAnalysisStarted: (jobId: string) => void;
  onEditGenerationStarted: (jobId: string) => void;
  hasEditDecisions?: boolean;
}

export const AiPanel: React.FC<AiPanelProps> = ({
  projectId,
  primaryVideo,
  mediaList,
  currentAspectRatio,
  onAnalysisStarted,
  onEditGenerationStarted,
  hasEditDecisions,
}) => {
  const [instruction, setInstruction] = useState<string>(
    'Cut dead air, highlight key value propositions with punchy stat cards, and add dynamic viral-style captions.'
  );
  const [editingMode, setEditingMode] = useState<'autonomous' | 'script'>('autonomous');
  const [referenceVideo, setReferenceVideo] = useState<string>('');
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>(currentAspectRatio);
  const [cutAggressiveness, setCutAggressiveness] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');
  const [zoomIntensity, setZoomIntensity] = useState<'subtle' | 'dynamic' | 'punchy'>('dynamic');
  const [videoStyle, setVideoStyle] = useState<'dynamic_zoom' | 'static'>('dynamic_zoom');
  const [captionPreset, setCaptionPreset] = useState<string>('kinetic_podcast_reference');
  const [qualityPreset] = useState<string>('fast');
  const [enablePersonalization, setEnablePersonalization] = useState<boolean>(true);
  const [selectedPreset, setSelectedPreset] = useState<string>('educational-explainer');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingCaptions, setIsGeneratingCaptions] = useState(false);

  const referenceVideos = mediaList.filter((m) => m.category === 'reference');

  const handleGenerateCaptions = async () => {
    if (!primaryVideo) {
      alert('Please select or upload primary footage first.');
      return;
    }
    setIsGeneratingCaptions(true);
    try {
      const res = await generateKineticCaptions(projectId, {
        video_path: primaryVideo.relative_path,
        preset_id: captionPreset,
        video_style: videoStyle,
        zoom_intensity: zoomIntensity,
        words_per_cue: 2,
        emphasis_frequency: 0.25,
      });
      onEditGenerationStarted(res.job_id);
    } catch (err: any) {
      alert(`Kinetic caption generation failed: ${err.message}`);
    } finally {
      setIsGeneratingCaptions(false);
    }
  };

  const handleExportSubtitles = async (fmt: 'srt' | 'vtt' | 'ass') => {
    try {
      const res = await exportKineticCaptions(projectId, {
        format: fmt,
        preset_id: captionPreset,
      });
      alert(`Exported ${fmt.toUpperCase()} successfully to: ${res.relative_path}`);
    } catch (err: any) {
      alert(`Subtitle export failed: ${err.message}`);
    }
  };

  const handleAnalyze = async () => {
    if (!primaryVideo) {
      alert('Please select or upload primary footage before analyzing.');
      return;
    }
    setIsAnalyzing(true);
    try {
      const res = await analyzeFootage(projectId, {
        video_path: primaryVideo.relative_path,
        quality_preset: qualityPreset,
      });
      onAnalysisStarted(res.job_id);
    } catch (err: any) {
      alert(`Analysis failed: ${err.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleGenerateEdit = async () => {
    if (!primaryVideo) {
      alert('Please select or upload primary footage first.');
      return;
    }
    setIsGenerating(true);
    try {
      const res = await generateEditorialPlan(projectId, {
        user_instruction: instruction,
        video_path: primaryVideo.relative_path,
        reference_video_path: referenceVideo || undefined,
        mode: editingMode,
        target_aspect: aspectRatio,
        cut_aggressiveness: cutAggressiveness,
        zoom_intensity: zoomIntensity,
        caption_preset: captionPreset,
        quality_preset: qualityPreset,
        enable_personalization: enablePersonalization,
        preset_id: selectedPreset,
      } as any);
      onEditGenerationStarted(res.job_id);
    } catch (err: any) {
      alert(`Edit generation failed: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#12161f] border-r border-[#262c38]">
      {/* Header */}
      <div className="p-3 border-b border-[#262c38] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-400" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">AI Editorial Director</h2>
        </div>
        <span className="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-1.5 py-0.5 rounded font-mono">
          SmolVLM + Whisper
        </span>
      </div>

      {/* Form Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3.5">
        {/* Source Status */}
        <div className="bg-[#171d28] p-2.5 rounded border border-[#232b3b] flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 block uppercase font-mono">Target Footage</span>
            <span className="text-xs font-medium text-slate-200 truncate max-w-[180px] block" title={primaryVideo?.name || 'No video selected'}>
              {primaryVideo ? primaryVideo.name : 'None selected (Upload in Media)'}
            </span>
          </div>
          {primaryVideo ? (
            <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
              <CheckCircle className="w-3 h-3" /> Ready
            </span>
          ) : (
            <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
              Missing
            </span>
          )}
        </div>

        {/* Editing Mode */}
        <div>
          <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1.5">
            Editorial Mode
          </label>
          <div className="grid grid-cols-2 gap-1.5">
            <button
              onClick={() => setEditingMode('autonomous')}
              className={`p-2 rounded text-left border transition-all ${
                editingMode === 'autonomous'
                  ? 'bg-[#1e2a3d] border-[#38bdf8] text-white'
                  : 'bg-[#161c26] border-[#222a38] text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center gap-1.5 text-xs font-medium">
                <Bot className="w-3.5 h-3.5 text-[#38bdf8]" />
                <span>Autonomous</span>
              </div>
              <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">
                AI finds highlights, cuts pauses & inserts graphics automatically.
              </p>
            </button>

            <button
              onClick={() => setEditingMode('script')}
              className={`p-2 rounded text-left border transition-all ${
                editingMode === 'script'
                  ? 'bg-[#1e2a3d] border-[#38bdf8] text-white'
                  : 'bg-[#161c26] border-[#222a38] text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center gap-1.5 text-xs font-medium">
                <FileCode className="w-3.5 h-3.5 text-amber-400" />
                <span>Script Guided</span>
              </div>
              <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">
                Follows structured text instructions and exact visual pacing cues.
              </p>
            </button>
          </div>
        </div>

        {/* Natural Language Prompt */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
              Natural Language Brief
            </label>
            <span className="text-[10px] text-slate-500">English prompt</span>
          </div>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            rows={3}
            placeholder="e.g. Cut dead air, add dramatic zooms on key statements, insert stat cards for numbers..."
            className="w-full bg-[#161c26] border border-[#262f3f] rounded p-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-[#38bdf8] transition-colors resize-none"
          />
        </div>

        {/* Reference Video Option */}
        <div>
          <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
            Reference Video Style (Optional)
          </label>
          <select
            value={referenceVideo}
            onChange={(e) => setReferenceVideo(e.target.value)}
            className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-[#38bdf8]"
          >
            <option value="">No reference style (Use defaults)</option>
            {referenceVideos.map((ref) => (
              <option key={ref.name} value={ref.relative_path}>
                {ref.name} (Style Transfer)
              </option>
            ))}
          </select>
        </div>

        {/* Pacing & Style Controls */}
        <div className="space-y-2.5 pt-1 border-t border-[#1f2736]">
          {/* Aspect Ratio */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              Aspect Ratio
            </span>
            <div className="flex bg-[#161c26] p-0.5 rounded border border-[#262f3f]">
              {(['9:16', '16:9', '1:1'] as AspectRatio[]).map((ar) => (
                <button
                  key={ar}
                  onClick={() => setAspectRatio(ar)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                    aspectRatio === ar
                      ? 'bg-[#0284c7] text-white font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {ar}
                </button>
              ))}
            </div>
          </div>

          {/* Cut Aggressiveness */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300 flex items-center gap-1.5">
              <Scissors className="w-3.5 h-3.5 text-slate-400" />
              Pacing Cuts
            </span>
            <div className="flex bg-[#161c26] p-0.5 rounded border border-[#262f3f]">
              {(['conservative', 'balanced', 'aggressive'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setCutAggressiveness(mode)}
                  className={`px-2 py-0.5 rounded text-[10px] capitalize transition-colors ${
                    cutAggressiveness === mode
                      ? 'bg-[#1e2a3d] text-[#38bdf8] font-semibold border border-[#38bdf8]/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

          {/* Personalization & Editing Memory (Phase 10) */}
          <div className="bg-[#171d28] p-2.5 rounded border border-purple-900/40 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-purple-300 font-medium flex items-center gap-1.5">
                <Brain className="w-3.5 h-3.5 text-purple-400" />
                Apply Editing Memory
              </span>
              <button
                type="button"
                onClick={() => setEnablePersonalization(!enablePersonalization)}
                className={`relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                  enablePersonalization ? 'bg-purple-600' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    enablePersonalization ? 'translate-x-3' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {enablePersonalization && (
              <div className="pt-1 border-t border-purple-950">
                <label className="text-[10px] text-slate-400 block mb-1">Style Preset Profile:</label>
                <select
                  value={selectedPreset}
                  onChange={(e) => setSelectedPreset(e.target.value)}
                  className="w-full bg-[#12161f] border border-slate-700 rounded px-2 py-1 text-[11px] text-slate-200 focus:outline-none focus:border-purple-500"
                >
                  <option value="educational-explainer">Educational Explainer (Subtle zoom, 4 wpg)</option>
                  <option value="high-energy-short">High-Energy Viral Short (1.4x zoom, snappy)</option>
                  <option value="minimal-professional">Minimal Professional (Clean, no zoom)</option>
                  <option value="technology-demo">Technology Demo (Monospace, KPI benchmarks)</option>
                </select>
              </div>
            )}
          </div>

          {/* Zoom Intensity */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300 flex items-center gap-1.5">
              <ZoomIn className="w-3.5 h-3.5 text-slate-400" />
              Zoom Punch
            </span>
            <div className="flex bg-[#161c26] p-0.5 rounded border border-[#262f3f]">
              {(['subtle', 'dynamic', 'punchy'] as const).map((z) => (
                <button
                  key={z}
                  onClick={() => setZoomIntensity(z)}
                  className={`px-2 py-0.5 rounded text-[10px] capitalize transition-colors ${
                    zoomIntensity === z
                      ? 'bg-[#1e2a3d] text-amber-400 font-semibold border border-amber-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {z}
                </button>
              ))}
            </div>
          </div>

          {/* Framing Style (Dynamic Zoom vs Static) */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300 flex items-center gap-1.5">
              <Camera className="w-3.5 h-3.5 text-slate-400" />
              Framing Style
            </span>
            <div className="flex bg-[#161c26] p-0.5 rounded border border-[#262f3f]">
              <button
                type="button"
                onClick={() => setVideoStyle('dynamic_zoom')}
                className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
                  videoStyle === 'dynamic_zoom'
                    ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                ⚡ Punch Zoom
              </button>
              <button
                type="button"
                onClick={() => setVideoStyle('static')}
                className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
                  videoStyle === 'static'
                    ? 'bg-sky-500/20 text-sky-300 font-semibold border border-sky-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🎥 Static Frame
              </button>
            </div>
          </div>

          {/* Caption Preset */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-300 flex items-center gap-1.5">
                <Type className="w-3.5 h-3.5 text-amber-400" />
                Kinetic Captions Style
              </span>
            </div>
            <select
              value={captionPreset}
              onChange={(e) => setCaptionPreset(e.target.value)}
              className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-amber-400"
            >
              <option value="kinetic_podcast_reference">★ Cinematic Kinetic Podcast (Reference)</option>
              <option value="minimal_white">Minimal White (Inter Display Clean)</option>
              <option value="bold_word_pop">Bold Word Pop (Black 900 Weight)</option>
              <option value="editorial_typography">Editorial Typography (Stacked 2-Tier)</option>
              <option value="clean_podcast">Clean Podcast (Balanced 2-3 Words)</option>
              <option value="animated_social_captions">Animated Social Captions</option>
            </select>

            {/* Quick Export Subtitle Pills */}
            <div className="flex items-center justify-between mt-1.5 pt-1.5 border-t border-[#1c2433]">
              <span className="text-[10px] text-slate-400 font-mono">Export Subtitles:</span>
              <div className="flex gap-1">
                {(['srt', 'vtt', 'ass'] as const).map((fmt) => (
                  <button
                    key={fmt}
                    type="button"
                    onClick={() => handleExportSubtitles(fmt)}
                    className="px-1.5 py-0.5 rounded bg-[#161c26] hover:bg-[#1f2738] border border-[#2d384d] text-slate-300 text-[9px] uppercase font-mono transition"
                    title={`Download .${fmt} subtitle file`}
                  >
                    .{fmt}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="pt-2 border-t border-[#1f2736] space-y-2">
          {/* Kinetic Captions Dedicated Button */}
          <button
            onClick={handleGenerateCaptions}
            disabled={!primaryVideo || isGeneratingCaptions}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-amber-600 via-orange-600 to-amber-700 hover:from-amber-500 hover:to-orange-600 text-white text-xs font-bold py-2 rounded shadow-lg shadow-amber-950/40 transition-all disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4 text-amber-200 animate-spin-slow" />
            <span>{isGeneratingCaptions ? 'Synthesizing Kinetic Captions...' : '⚡ Generate Kinetic Captions (Reference)'}</span>
          </button>

          <button
            onClick={handleAnalyze}
            disabled={!primaryVideo || isAnalyzing}
            className="w-full flex items-center justify-center gap-2 bg-[#1a2333] hover:bg-[#222e42] border border-[#2d3a52] text-slate-200 text-xs font-semibold py-2 rounded transition-colors disabled:opacity-50"
          >
            <Bot className="w-3.5 h-3.5 text-[#38bdf8]" />
            <span>{isAnalyzing ? 'Analyzing Raw Video...' : '1. Analyze Footage (Whisper + Vision)'}</span>
          </button>

          <button
            onClick={handleGenerateEdit}
            disabled={!primaryVideo || isGenerating}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#0284c7] to-[#0ea5e9] hover:from-[#0369a1] hover:to-[#0284c7] text-white text-xs font-bold py-2.5 rounded shadow-lg shadow-sky-900/30 transition-all disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4 text-amber-300 animate-spin-slow" />
            <span>{isGenerating ? 'Synthesizing Edit...' : '2. Generate Editorial Plan'}</span>
          </button>
        </div>

        {/* Decisions Banner */}
        {hasEditDecisions && (
          <div className="p-2.5 bg-emerald-950/30 border border-emerald-500/20 rounded flex items-center gap-2 text-[11px] text-emerald-300">
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Timeline synchronized with generated cuts and motion graphics.</span>
          </div>
        )}
      </div>
    </div>
  );
};
