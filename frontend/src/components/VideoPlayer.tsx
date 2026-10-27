import React, { useRef, useEffect, useState } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Maximize2,
  Minimize2,
  ChevronLeft,
  ChevronRight,
  Shield,
  Layers,
  Sparkles,
  Tv,
} from 'lucide-react';
import { EditDecisions, MediaItem } from '../types';

interface VideoPlayerProps {
  primaryVideo: MediaItem | null;
  renderedVideoUrl?: string | null;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  onTimeUpdate: (time: number) => void;
  onDurationChange: (duration: number) => void;
  onTogglePlay: () => void;
  editDecisions?: EditDecisions | null;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  primaryVideo,
  renderedVideoUrl,
  currentTime,
  duration,
  isPlaying,
  onTimeUpdate,
  onDurationChange,
  onTogglePlay,
  editDecisions,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showSafeZones, setShowSafeZones] = useState(false);
  const [showOverlaySimulation, setShowOverlaySimulation] = useState(true);
  const [previewSource, setPreviewSource] = useState<'source' | 'rendered'>('rendered');

  const effectiveVideoSrc =
    previewSource === 'rendered' && renderedVideoUrl
      ? renderedVideoUrl
      : primaryVideo?.media_url;

  // Sync isPlaying state with HTML5 video
  useEffect(() => {
    if (!videoRef.current) return;
    if (isPlaying && videoRef.current.paused) {
      videoRef.current.play().catch(() => {});
    } else if (!isPlaying && !videoRef.current.paused) {
      videoRef.current.pause();
    }
  }, [isPlaying]);

  // Sync external seek with video element
  useEffect(() => {
    if (!videoRef.current) return;
    if (Math.abs(videoRef.current.currentTime - currentTime) > 0.15) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      onDurationChange(videoRef.current.duration || 10);
    }
  };

  const handleStepFrames = (frames: number) => {
    const fps = 30;
    const newTime = Math.max(0, Math.min(duration, currentTime + frames / fps));
    onTimeUpdate(newTime);
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().then(() => setIsFullscreen(true));
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false));
    }
  };

  // Format timecode HH:MM:SS:FF at 30 fps
  const formatTimecode = (seconds: number) => {
    if (isNaN(seconds) || seconds < 0) seconds = 0;
    const totalFrames = Math.floor(seconds * 30);
    const ff = String(totalFrames % 30).padStart(2, '0');
    const ss = String(Math.floor(seconds) % 60).padStart(2, '0');
    const mm = String(Math.floor(seconds / 60) % 60).padStart(2, '0');
    const hh = String(Math.floor(seconds / 3600)).padStart(2, '0');
    return `${hh}:${mm}:${ss}:${ff}`;
  };

  // Find active overlays at current time
  const activeOverlays =
    showOverlaySimulation && editDecisions?.overlays
      ? editDecisions.overlays.filter(
          (o) => currentTime >= o.in_seconds && currentTime <= o.out_seconds
        )
      : [];

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full bg-[#080b11] relative select-none border-b border-[#1c2433]"
    >
      {/* Top Viewport Header / Status Bar */}
      <div className="h-9 px-4 bg-[#0d121b]/90 border-b border-[#1c2433] flex items-center justify-between text-xs text-slate-300">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-sky-400 font-bold tracking-wider text-[13px] bg-[#141b27] px-2 py-0.5 rounded border border-sky-500/20">
            {formatTimecode(currentTime)}
          </span>
          <span className="text-slate-600 font-mono">/</span>
          <span className="font-mono text-slate-400 text-xs">{formatTimecode(duration)}</span>
        </div>

        {/* Source selector & guide toggles */}
        <div className="flex items-center gap-2">
          {renderedVideoUrl && (
            <div className="flex bg-[#121824] rounded-lg border border-[#212c3e] p-0.5 text-[11px] shadow-inner">
              <button
                onClick={() => setPreviewSource('source')}
                className={`px-2 py-0.5 rounded-md font-medium transition-all ${
                  previewSource === 'source' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Raw Footage
              </button>
              <button
                onClick={() => setPreviewSource('rendered')}
                className={`px-2 py-0.5 rounded-md font-medium transition-all ${
                  previewSource === 'rendered' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Rendered Export
              </button>
            </div>
          )}

          <button
            onClick={() => setShowSafeZones(!showSafeZones)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all border ${
              showSafeZones
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/40 shadow-sm'
                : 'text-slate-400 border-transparent hover:border-[#243042] hover:bg-[#141b27]'
            }`}
            title="Toggle safe zone guides for TikTok / Reels"
          >
            <Shield className="w-3.5 h-3.5" />
            <span>Safe Zones</span>
          </button>

          <button
            onClick={() => setShowOverlaySimulation(!showOverlaySimulation)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all border ${
              showOverlaySimulation
                ? 'bg-sky-500/15 text-sky-300 border-sky-500/40 shadow-sm'
                : 'text-slate-400 border-transparent hover:border-[#243042] hover:bg-[#141b27]'
            }`}
            title="Toggle Remotion graphics overlay preview"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Graphics HUD</span>
          </button>
        </div>
      </div>

      {/* Video Viewport Stage */}
      <div className="flex-1 relative flex items-center justify-center overflow-hidden bg-[#05070a] p-4">
        {effectiveVideoSrc ? (
          <div className="relative max-h-full max-w-full flex items-center justify-center rounded-2xl overflow-hidden shadow-2xl shadow-black ring-1 ring-white/10">
            <video
              ref={videoRef}
              src={effectiveVideoSrc}
              className="max-h-[calc(100vh-340px)] object-contain"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onClick={onTogglePlay}
              playsInline
            />

            {/* Safe Zone Overlays (9:16 vertical guides) */}
            {showSafeZones && (
              <div className="absolute inset-0 pointer-events-none flex flex-col justify-between border border-dashed border-cyan-400/40 m-2 rounded-xl">
                {/* Header margin */}
                <div className="h-12 border-b border-rose-500/30 bg-rose-500/10 flex items-center justify-center text-[10px] text-rose-300 font-mono tracking-wider">
                  [ Top Header UI Safe Area ]
                </div>
                <div className="flex-1 flex justify-between">
                  <div className="w-4 border-r border-cyan-500/20" />
                  <div className="w-14 border-l border-amber-500/30 bg-amber-500/10 flex items-center justify-center text-[9px] text-amber-300 font-mono rotate-90 tracking-wider">
                    Action Buttons
                  </div>
                </div>
                <div className="h-16 border-t border-rose-500/30 bg-rose-500/10 flex items-center justify-center text-[10px] text-rose-300 font-mono tracking-wider">
                  [ Bottom Subtitles & Audio Margin ]
                </div>
              </div>
            )}

            {/* Live Remotion-style Graphic Overlays Simulation */}
            {showOverlaySimulation && activeOverlays.length > 0 && (
              <div className="absolute inset-0 pointer-events-none flex flex-col items-center justify-center p-6">
                {activeOverlays.map((overlay) => (
                  <div
                    key={overlay.id}
                    className="max-w-[300px] w-full bg-[#121826]/90 backdrop-blur-md border border-sky-400/50 text-white p-3 rounded-xl shadow-2xl shadow-sky-950/60 animate-in fade-in zoom-in-95 duration-150"
                    style={{
                      borderColor: overlay.accentColor || '#38bdf8',
                    }}
                  >
                    <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-sky-400 mb-1">
                      <Sparkles className="w-3 h-3 text-sky-400" />
                      <span>{overlay.type.replace('_', ' ')}</span>
                    </div>
                    {overlay.content?.value && (
                      <div className="text-2xl font-black text-amber-300 font-mono tracking-tight">
                        {overlay.content.value}
                      </div>
                    )}
                    {(overlay.content?.label || overlay.content?.title) && (
                      <div className="text-xs font-semibold text-slate-100 mt-0.5">
                        {overlay.content.label || overlay.content.title}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center p-8 max-w-sm rounded-2xl border border-dashed border-[#1f2838] bg-[#0c1017]">
            <div className="w-12 h-12 rounded-2xl bg-[#141b27] flex items-center justify-center mb-3 text-sky-400 border border-[#212c3e] shadow-inner">
              <Tv className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-200">No Footage Loaded</h3>
            <p className="text-xs text-slate-500 mt-1">
              Select or import a video from the Media Bin to preview timeline edits and motion graphics.
            </p>
          </div>
        )}
      </div>

      {/* Control Transport Bar */}
      <div className="h-12 px-6 bg-[#0c1017] border-t border-[#1c2433] flex items-center justify-between">
        {/* Playback Transport Controls */}
        <div className="flex items-center gap-2">
          {/* Step Back 1s */}
          <button
            onClick={() => handleStepFrames(-30)}
            className="p-1.5 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-lg transition-colors"
            title="Step Back 1s"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          {/* Step Back 1 Frame */}
          <button
            onClick={() => handleStepFrames(-1)}
            className="px-2 py-1 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-md text-[10px] font-mono border border-transparent hover:border-[#222c3d]"
            title="Step Back 1 Frame"
          >
            -1F
          </button>

          {/* Main Play / Pause Button */}
          <button
            onClick={onTogglePlay}
            className="w-9 h-9 rounded-full bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white flex items-center justify-center shadow-lg shadow-sky-500/25 transition-all hover:scale-105 active:scale-95"
            title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5 fill-white" />}
          </button>

          {/* Step Forward 1 Frame */}
          <button
            onClick={() => handleStepFrames(1)}
            className="px-2 py-1 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-md text-[10px] font-mono border border-transparent hover:border-[#222c3d]"
            title="Step Forward 1 Frame"
          >
            +1F
          </button>

          {/* Step Forward 1s */}
          <button
            onClick={() => handleStepFrames(30)}
            className="p-1.5 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-lg transition-colors"
            title="Step Forward 1s"
          >
            <ChevronRight className="w-4 h-4" />
          </button>

          {/* Reset Playhead */}
          <button
            onClick={() => onTimeUpdate(0)}
            className="p-1.5 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-lg transition-colors ml-1"
            title="Return to Start"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Audio Volume & Fullscreen */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 bg-[#121722] px-2.5 py-1 rounded-lg border border-[#1e2738]">
            <button
              onClick={() => {
                if (videoRef.current) {
                  videoRef.current.muted = !isMuted;
                  setIsMuted(!isMuted);
                }
              }}
              className="text-slate-400 hover:text-slate-200 transition-colors"
            >
              {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
            </button>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={isMuted ? 0 : volume}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setVolume(val);
                if (videoRef.current) videoRef.current.volume = val;
                setIsMuted(val === 0);
              }}
              className="w-18 h-1 bg-[#232e40] rounded appearance-none cursor-pointer accent-sky-400"
            />
          </div>

          <button
            onClick={toggleFullscreen}
            className="p-1.5 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-lg transition-colors"
            title="Toggle Fullscreen"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
};
