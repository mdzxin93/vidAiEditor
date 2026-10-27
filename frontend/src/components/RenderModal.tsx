import React, { useState, useEffect } from 'react';
import {
  Film,
  X,
  CheckCircle,
  AlertCircle,
  Terminal,
  Ban
} from 'lucide-react';
import { AspectRatio, JobRecord } from '../types';
import { triggerRender, fetchJobStatus, cancelJob } from '../api';

interface RenderModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  defaultMode: 'preview' | 'final';
  projectAspectRatio: AspectRatio;
  onRenderComplete: (outputVideoUrl: string) => void;
}

export const RenderModal: React.FC<RenderModalProps> = ({
  projectId,
  isOpen,
  onClose,
  defaultMode,
  projectAspectRatio,
  onRenderComplete,
}) => {
  const [mode, setMode] = useState<'preview' | 'final'>(defaultMode);
  const [renderPreset, setRenderPreset] = useState<'fast_preview' | 'balanced' | 'final_quality'>(
    defaultMode === 'preview' ? 'fast_preview' : 'final_quality'
  );
  const [resolution, setResolution] = useState<string>(
    projectAspectRatio === '9:16' ? '1080x1920' : projectAspectRatio === '16:9' ? '1920x1080' : '1080x1080'
  );
  const [fps, setFps] = useState<number>(30);
  const [outputFilename, setOutputFilename] = useState<string>(
    defaultMode === 'preview' ? 'preview_render.mp4' : 'final_export.mp4'
  );
  const [activeJob, setActiveJob] = useState<JobRecord | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  useEffect(() => {
    setMode(defaultMode);
    setRenderPreset(defaultMode === 'preview' ? 'fast_preview' : 'final_quality');
    setOutputFilename(defaultMode === 'preview' ? 'preview_render.mp4' : 'final_export.mp4');
    if (defaultMode === 'preview') {
      setResolution(projectAspectRatio === '9:16' ? '720x1280' : '1280x720');
    } else {
      setResolution(projectAspectRatio === '9:16' ? '1080x1920' : '1920x1080');
    }
  }, [defaultMode, projectAspectRatio]);

  // Poll active job status
  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed' || activeJob.status === 'cancelled') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updated = await fetchJobStatus(activeJob.job_id);
        setActiveJob(updated);
        if (updated.status === 'completed') {
          const videoUrl = `/api/project/${projectId}/media/render/${updated.result?.output_path ? updated.result.output_path.split(/[\\/]/).pop() : outputFilename}`;
          onRenderComplete(videoUrl);
        }
      } catch (err) {
        console.error('Job polling error:', err);
      }
    }, 1200);

    return () => clearInterval(interval);
  }, [activeJob, projectId]);

  if (!isOpen) return null;

  const handleStartRender = async () => {
    setIsStarting(true);
    try {
      const res = await triggerRender(projectId, {
        mode,
        resolution,
        fps,
        output_filename: outputFilename,
        render_preset: renderPreset,
      });
      const initialJob = await fetchJobStatus(res.job_id);
      setActiveJob(initialJob);
    } catch (err: any) {
      alert(`Render trigger failed: ${err.message}`);
    } finally {
      setIsStarting(false);
    }
  };

  const handleCancelJob = async () => {
    if (!activeJob) return;
    try {
      await cancelJob(activeJob.job_id);
      const updated = await fetchJobStatus(activeJob.job_id);
      setActiveJob(updated);
    } catch (err: any) {
      alert(`Cancel failed: ${err.message}`);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#141824] border border-[#262f40] rounded-xl max-w-lg w-full overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-4 py-3 bg-[#111420] border-b border-[#202738] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Film className="w-4 h-4 text-[#38bdf8]" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              {mode === 'preview' ? 'Render Fast Preview' : 'Export Master Video'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded hover:bg-[#1c2333]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 overflow-y-auto space-y-4 text-xs">
          {/* Active Job Progress View */}
          {activeJob && (
            <div className="bg-[#101420] border border-[#222a3b] p-3.5 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-mono block">Job Status</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span
                      className={`text-xs font-bold uppercase font-mono ${
                        activeJob.status === 'completed'
                          ? 'text-emerald-400'
                          : activeJob.status === 'failed'
                          ? 'text-rose-400'
                          : 'text-[#38bdf8]'
                      }`}
                    >
                      {activeJob.status}
                    </span>
                    <span className="text-[11px] text-slate-400">({activeJob.stage})</span>
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-sm font-bold font-mono text-slate-200">
                    {Math.round(activeJob.progress)}%
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="h-2 bg-[#1b2233] rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    activeJob.status === 'completed'
                      ? 'bg-emerald-500'
                      : activeJob.status === 'failed'
                      ? 'bg-rose-500'
                      : 'bg-gradient-to-r from-sky-500 to-cyan-400'
                  }`}
                  style={{ width: `${Math.max(5, activeJob.progress)}%` }}
                />
              </div>

              {/* Logs terminal box */}
              <div className="bg-[#090b10] border border-[#1b2233] rounded p-2 text-[10px] font-mono text-slate-400 h-28 overflow-y-auto space-y-0.5">
                <div className="text-slate-500 flex items-center gap-1 border-b border-[#1b2233] pb-1 mb-1">
                  <Terminal className="w-3 h-3" />
                  <span>Render Logs</span>
                </div>
                {activeJob.logs.map((log, idx) => (
                  <div key={idx} className="leading-tight text-slate-300">
                    {log}
                  </div>
                ))}
              </div>

              {/* Active Job Actions */}
              <div className="flex justify-between items-center pt-1">
                {activeJob.status === 'running' && (
                  <button
                    onClick={handleCancelJob}
                    className="flex items-center gap-1 px-2.5 py-1 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 rounded text-[11px] font-medium"
                  >
                    <Ban className="w-3 h-3" />
                    <span>Cancel Render</span>
                  </button>
                )}

                {activeJob.status === 'completed' && (
                  <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
                    <CheckCircle className="w-4 h-4" />
                    <span>Render completed successfully!</span>
                  </div>
                )}

                {activeJob.status === 'failed' && (
                  <div className="flex items-center gap-1.5 text-rose-400 font-medium">
                    <AlertCircle className="w-4 h-4" />
                    <span>Error: {activeJob.error || 'Rendering failed'}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Form Settings (visible if no job running or job completed) */}
          {(!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed' || activeJob.status === 'cancelled') && (
            <>
              {/* Mode Selection */}
              <div>
                <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1.5">
                  Export Profile
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => {
                      setMode('preview');
                      setRenderPreset('fast_preview');
                      setOutputFilename('preview_render.mp4');
                    }}
                    className={`p-2.5 rounded text-left border transition-all ${
                      mode === 'preview'
                        ? 'bg-[#1e2a3d] border-[#38bdf8] text-white'
                        : 'bg-[#161c26] border-[#222a38] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <div className="font-semibold text-xs text-sky-400">Preview Draft</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      Rapid render for timeline & timing inspection.
                    </div>
                  </button>

                  <button
                    onClick={() => {
                      setMode('final');
                      setRenderPreset('final_quality');
                      setOutputFilename('final_export.mp4');
                    }}
                    className={`p-2.5 rounded text-left border transition-all ${
                      mode === 'final'
                        ? 'bg-[#1e2a3d] border-[#38bdf8] text-white'
                        : 'bg-[#161c26] border-[#222a38] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <div className="font-semibold text-xs text-amber-400">Production Master</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      High-bitrate H.264 MP4 with full springs & captions.
                    </div>
                  </button>
                </div>
              </div>

              {/* Quality Preset Selection (Phase 11) */}
              <div>
                <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1.5">
                  Performance & Quality Preset
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setRenderPreset('fast_preview');
                      setResolution(projectAspectRatio === '9:16' ? '720x1280' : '1280x720');
                    }}
                    className={`p-2 rounded text-left border transition-all ${
                      renderPreset === 'fast_preview'
                        ? 'bg-[#1e2a3d] border-[#38bdf8] text-white shadow-sm'
                        : 'bg-[#161c26] border-[#222a38] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <div className="font-semibold text-xs text-sky-400">🚀 Fast Preview</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      Reduced scale, minimal RAM.
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setRenderPreset('balanced');
                      setResolution(projectAspectRatio === '9:16' ? '720x1280' : '1280x720');
                    }}
                    className={`p-2 rounded text-left border transition-all ${
                      renderPreset === 'balanced'
                        ? 'bg-[#1e2a3d] border-[#38bdf8] text-white shadow-sm'
                        : 'bg-[#161c26] border-[#222a38] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <div className="font-semibold text-xs text-emerald-400">⚖️ Balanced</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      Standard review clarity.
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setRenderPreset('final_quality');
                      setResolution(projectAspectRatio === '9:16' ? '1080x1920' : '1920x1080');
                    }}
                    className={`p-2 rounded text-left border transition-all ${
                      renderPreset === 'final_quality'
                        ? 'bg-[#1e2a3d] border-[#38bdf8] text-white shadow-sm'
                        : 'bg-[#161c26] border-[#222a38] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <div className="font-semibold text-xs text-amber-400">💎 Final Quality</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      1080p master export.
                    </div>
                  </button>
                </div>
              </div>

              {/* Resolution & FPS */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                    Resolution
                  </label>
                  <select
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value)}
                    className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-[#38bdf8]"
                  >
                    <option value="1080x1920">1080 x 1920 (9:16 Vertical HD)</option>
                    <option value="720x1280">720 x 1280 (9:16 Vertical Draft)</option>
                    <option value="1920x1080">1920 x 1080 (16:9 Landscape HD)</option>
                    <option value="1080x1080">1080 x 1080 (1:1 Square)</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                    Frame Rate
                  </label>
                  <select
                    value={fps}
                    onChange={(e) => setFps(parseInt(e.target.value))}
                    className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-[#38bdf8]"
                  >
                    <option value={30}>30 FPS (Standard Web & Social)</option>
                    <option value={60}>60 FPS (Ultra Smooth Motion)</option>
                  </select>
                </div>
              </div>

              {/* Destination Filename */}
              <div>
                <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                  Destination Output File
                </label>
                <input
                  type="text"
                  value={outputFilename}
                  onChange={(e) => setOutputFilename(e.target.value)}
                  className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono"
                />
                <span className="text-[10px] text-slate-500 font-mono mt-1 block">
                  Saved inside project's `renders/` directory.
                </span>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-4 py-3 bg-[#111420] border-t border-[#202738] flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-3 py-1.5 bg-[#1b2230] hover:bg-[#252f42] text-slate-300 rounded text-xs"
          >
            {activeJob?.status === 'completed' ? 'Close Window' : 'Cancel'}
          </button>

          {(!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed' || activeJob.status === 'cancelled') && (
            <button
              onClick={handleStartRender}
              disabled={isStarting}
              className="px-4 py-1.5 bg-[#0284c7] hover:bg-[#0369a1] text-white text-xs font-bold rounded shadow transition-colors flex items-center gap-1.5"
            >
              <Film className="w-3.5 h-3.5" />
              <span>{isStarting ? 'Submitting Job...' : 'Start Rendering'}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
