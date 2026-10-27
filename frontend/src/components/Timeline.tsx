import React, { useRef, useState, useEffect } from 'react';
import {
  Scissors,
  Layers,
  Type,
  Volume2,
  ZoomIn,
  ZoomOut,
  Maximize2,
  AlertTriangle,
  Plus,
  Trash2,
  Sparkles,
} from 'lucide-react';
import { EditDecisions, Overlay, QAIssue } from '../types';
import { fetchWaveform } from '../api';

interface TimelineProps {
  editDecisions: EditDecisions | null;
  currentTime: number;
  duration: number;
  onTimeSeek: (time: number) => void;
  selectedItemId: string | null;
  selectedItemType: 'cut' | 'overlay' | 'caption' | null;
  onSelectItem: (id: string | null, type: 'cut' | 'overlay' | 'caption' | null) => void;
  onUpdateDecisions: (updated: EditDecisions, commitMsg?: string) => void;
  qaIssues?: QAIssue[];
  projectId?: string;
}

export const Timeline: React.FC<TimelineProps> = ({
  editDecisions,
  currentTime,
  duration,
  onTimeSeek,
  selectedItemId,
  selectedItemType,
  onSelectItem,
  onUpdateDecisions,
  qaIssues = [],
  projectId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const trackContainerRef = useRef<HTMLDivElement>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(48); // Zoom level
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [draggedOverlayId, setDraggedOverlayId] = useState<string | null>(null);
  const [dragStartX, setDragStartX] = useState<number>(0);
  const [dragInitialInTime, setDragInitialInTime] = useState<number>(0);
  const [waveformPeaks, setWaveformPeaks] = useState<number[]>([]);

  useEffect(() => {
    if (!projectId) return;
    fetchWaveform(projectId, undefined, 800)
      .then((data) => {
        if (data && data.peaks && data.peaks.length > 0) {
          setWaveformPeaks(data.peaks);
        }
      })
      .catch(() => {
        // Fallback to placeholder gracefully if waveform cannot be generated
      });
  }, [projectId]);

  const totalWidth = Math.max(1200, duration * pixelsPerSecond + 300);

  // Handle Playhead Scrubbing
  const handleTimelineMouseDown = (e: React.MouseEvent) => {
    if (!trackContainerRef.current) return;
    const rect = trackContainerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left + trackContainerRef.current.scrollLeft;
    const newTime = Math.max(0, Math.min(duration, clickX / pixelsPerSecond));
    onTimeSeek(newTime);
    setIsScrubbing(true);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (isScrubbing && trackContainerRef.current) {
      const rect = trackContainerRef.current.getBoundingClientRect();
      const clickX = e.clientX - rect.left + trackContainerRef.current.scrollLeft;
      const newTime = Math.max(0, Math.min(duration, clickX / pixelsPerSecond));
      onTimeSeek(newTime);
    } else if (draggedOverlayId && editDecisions) {
      // Dragging an overlay block
      const deltaX = e.clientX - dragStartX;
      const deltaTime = deltaX / pixelsPerSecond;
      const overlay = editDecisions.overlays.find((o) => o.id === draggedOverlayId);
      if (overlay) {
        const itemDuration = overlay.out_seconds - overlay.in_seconds;
        const newIn = Math.max(0, dragInitialInTime + deltaTime);
        const newOut = newIn + itemDuration;

        const updatedOverlays = editDecisions.overlays.map((o) =>
          o.id === draggedOverlayId
            ? { ...o, in_seconds: parseFloat(newIn.toFixed(2)), out_seconds: parseFloat(newOut.toFixed(2)) }
            : o
        );
        onUpdateDecisions(
          { ...editDecisions, overlays: updatedOverlays },
          `Adjust timing for overlay ${draggedOverlayId}`
        );
      }
    }
  };

  const handleMouseUp = () => {
    setIsScrubbing(false);
    setDraggedOverlayId(null);
  };

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isScrubbing, draggedOverlayId, pixelsPerSecond]);

  // Add a new motion graphic overlay
  const handleAddOverlay = () => {
    if (!editDecisions) return;
    const newOverlay: Overlay = {
      id: `overlay_${Date.now()}`,
      type: 'stat_card',
      in_seconds: parseFloat(currentTime.toFixed(2)),
      out_seconds: parseFloat((currentTime + 3).toFixed(2)),
      position: 'upper_third',
      color: '#ffffff',
      accentColor: '#38bdf8',
      animation: 'spring',
      content: {
        value: '+84%',
        label: 'Efficiency Metric',
        trend: 'positive',
      },
    };

    const updated = {
      ...editDecisions,
      overlays: [...editDecisions.overlays, newOverlay],
    };
    onUpdateDecisions(updated, 'Add new stat_card motion graphic');
    onSelectItem(newOverlay.id, 'overlay');
  };

  // Delete selected item
  const handleDeleteSelected = () => {
    if (!editDecisions || !selectedItemId) return;
    if (selectedItemType === 'overlay') {
      const updated = {
        ...editDecisions,
        overlays: editDecisions.overlays.filter((o) => o.id !== selectedItemId),
      };
      onUpdateDecisions(updated, `Remove overlay ${selectedItemId}`);
      onSelectItem(null, null);
    } else if (selectedItemType === 'cut') {
      if (editDecisions.cuts.length <= 1) {
        alert('Cannot delete the last remaining cut in the timeline.');
        return;
      }
      const updated = {
        ...editDecisions,
        cuts: editDecisions.cuts.filter((c) => c.id !== selectedItemId),
      };
      onUpdateDecisions(updated, `Remove cut ${selectedItemId}`);
      onSelectItem(null, null);
    }
  };

  // Generate ruler markers
  const renderRuler = () => {
    const markers = [];
    const step = pixelsPerSecond >= 70 ? 1 : pixelsPerSecond >= 35 ? 2 : 5;
    for (let sec = 0; sec <= Math.ceil(duration + 15); sec += step) {
      const left = sec * pixelsPerSecond;
      const mm = String(Math.floor(sec / 60)).padStart(2, '0');
      const ss = String(sec % 60).padStart(2, '0');
      markers.push(
        <div
          key={sec}
          className="absolute top-0 bottom-0 border-l border-[#253042] text-[10px] font-mono text-slate-500 pl-1.5 select-none pointer-events-none flex flex-col justify-between"
          style={{ left: `${left}px` }}
        >
          <span className="leading-none pt-1">{`${mm}:${ss}`}</span>
          <div className="w-1.5 h-1 border-t border-slate-600 mb-0.5" />
        </div>
      );
    }
    return markers;
  };

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full bg-[#0a0d13] border-t border-[#1c2433] select-none"
    >
      {/* Timeline Controls Toolbar */}
      <div className="h-10 px-4 bg-[#0e121b] border-b border-[#1c2433] flex items-center justify-between text-xs">
        {/* Actions cluster */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={handleAddOverlay}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#141d2b] hover:bg-[#1a2638] border border-sky-500/30 text-sky-400 hover:text-sky-300 rounded-lg text-xs font-semibold shadow-sm transition-all"
            title="Add motion graphic card at playhead"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Graphic</span>
          </button>

          {selectedItemId && (
            <button
              onClick={handleDeleteSelected}
              className="flex items-center gap-1 px-2.5 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 rounded-lg text-xs font-medium border border-rose-500/30 transition-colors"
              title="Delete selected timeline event (Del)"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-400" />
              <span>Delete</span>
            </button>
          )}

          <div className="h-4 w-px bg-[#20293a] mx-1" />

          {/* Current Selection Indicator */}
          {selectedItemId ? (
            <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono bg-[#121722] px-2 py-1 rounded-md border border-[#1e2738]">
              <span className="w-2 h-2 rounded-full bg-sky-400" />
              <span>Selected:</span>
              <strong className="text-slate-100 uppercase">{selectedItemType}</strong>
            </div>
          ) : (
            <span className="text-[11px] text-slate-500 italic">No clip selected</span>
          )}
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-400 uppercase font-mono font-bold tracking-wider">Zoom</span>
          <button
            onClick={() => setPixelsPerSecond((p) => Math.max(15, p - 10))}
            className="p-1 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-md transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <input
            type="range"
            min="15"
            max="120"
            value={pixelsPerSecond}
            onChange={(e) => setPixelsPerSecond(parseInt(e.target.value))}
            className="w-24 h-1 bg-[#232e40] rounded appearance-none accent-sky-400 cursor-pointer"
          />
          <button
            onClick={() => setPixelsPerSecond((p) => Math.min(120, p + 10))}
            className="p-1 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-md transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setPixelsPerSecond(48)}
            className="p-1 hover:bg-[#18202d] text-slate-400 hover:text-slate-200 rounded-md transition-colors ml-1"
            title="Fit to Default"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Multitrack Canvas Area */}
      <div
        ref={trackContainerRef}
        className="flex-1 overflow-x-auto overflow-y-auto relative bg-[#07090e]"
        onMouseDown={handleTimelineMouseDown}
      >
        <div className="relative h-full" style={{ width: `${totalWidth}px`, minHeight: '270px' }}>
          {/* Time Ruler (top 24px) */}
          <div className="h-6 bg-[#0e121a] border-b border-[#1c2433] relative">
            {renderRuler()}
          </div>

          {/* QA Issue Markers Bar (height 20px) */}
          <div className="h-5 bg-[#0a0d13] border-b border-[#18202c] relative">
            {qaIssues.map((issue) => {
              const left = issue.start_seconds * pixelsPerSecond;
              const width = Math.max(14, (issue.end_seconds - issue.start_seconds) * pixelsPerSecond);
              const isCrit = issue.severity === 'critical' || issue.severity === 'high';

              return (
                <div
                  key={issue.issue_id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onTimeSeek(issue.start_seconds);
                  }}
                  className={`absolute top-0.5 bottom-0.5 rounded px-1.5 flex items-center gap-1 cursor-pointer transition-all hover:scale-105 z-10 ${
                    isCrit ? 'bg-rose-500/30 border border-rose-500 text-rose-300' : 'bg-amber-500/30 border border-amber-500 text-amber-300'
                  }`}
                  style={{ left: `${left}px`, width: `${width}px` }}
                  title={`${issue.severity.toUpperCase()}: ${issue.description} (Click to jump)`}
                >
                  <AlertTriangle className="w-3 h-3 shrink-0" />
                  <span className="text-[9px] font-mono truncate">{issue.category}</span>
                </div>
              );
            })}
          </div>

          {/* Tracks Workspace */}
          <div className="py-2.5 space-y-2.5">
            {/* Track G1: Motion Graphics / Overlays */}
            <div className="h-13 bg-[#0d1017] border-y border-[#1a2230] relative py-1">
              <div className="absolute left-2 top-1.5 text-[9px] font-mono text-purple-400 uppercase tracking-wider flex items-center gap-1 z-20 pointer-events-none bg-black/60 px-1.5 py-0.5 rounded">
                <Layers className="w-3 h-3" /> G1 Overlays
              </div>
              {editDecisions?.overlays.map((overlay) => {
                const left = overlay.in_seconds * pixelsPerSecond;
                const width = Math.max(24, (overlay.out_seconds - overlay.in_seconds) * pixelsPerSecond);
                const isSelected = selectedItemId === overlay.id && selectedItemType === 'overlay';

                return (
                  <div
                    key={overlay.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectItem(overlay.id, 'overlay');
                    }}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      setDraggedOverlayId(overlay.id);
                      setDragStartX(e.clientX);
                      setDragInitialInTime(overlay.in_seconds);
                      onSelectItem(overlay.id, 'overlay');
                    }}
                    className={`absolute top-1 bottom-1 rounded-lg px-2.5 flex flex-col justify-center cursor-move transition-all select-none shadow-sm ${
                      isSelected
                        ? 'bg-gradient-to-r from-purple-600 to-indigo-600 border-2 border-white text-white shadow-lg shadow-purple-950/60 z-20 ring-2 ring-purple-400/50'
                        : 'bg-gradient-to-r from-purple-950/80 to-indigo-950/80 border border-purple-500/40 text-purple-200 hover:border-purple-400 hover:from-purple-900/80'
                    }`}
                    style={{ left: `${left}px`, width: `${width}px` }}
                    title={`Overlay: ${overlay.type} (${overlay.in_seconds}s - ${overlay.out_seconds}s)`}
                  >
                    <div className="flex items-center gap-1 text-[10px] font-bold truncate">
                      <Sparkles className="w-3 h-3 shrink-0 text-amber-300" />
                      <span className="truncate">{overlay.type}</span>
                    </div>
                    <div className="text-[9px] text-purple-200/80 font-mono truncate">
                      {overlay.content?.value || overlay.content?.title || overlay.content?.label || 'Graphic'}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Track V1: Video Cuts */}
            <div className="h-16 bg-[#0e121a] border-y border-[#1a2230] relative py-1">
              <div className="absolute left-2 top-1.5 text-[9px] font-mono text-sky-400 uppercase tracking-wider flex items-center gap-1 z-20 pointer-events-none bg-black/60 px-1.5 py-0.5 rounded">
                <Scissors className="w-3 h-3" /> V1 Primary Cuts
              </div>
              {editDecisions?.cuts.map((cut, idx) => {
                const left = cut.in_seconds * pixelsPerSecond;
                const width = Math.max(24, (cut.out_seconds - cut.in_seconds) * pixelsPerSecond);
                const isSelected = selectedItemId === cut.id && selectedItemType === 'cut';
                const hasZoom = cut.transform?.scale && cut.transform.scale > 1.05;

                return (
                  <div
                    key={cut.id || idx}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectItem(cut.id, 'cut');
                    }}
                    className={`absolute top-1 bottom-1 rounded-lg px-2.5 flex flex-col justify-center cursor-pointer transition-all shadow-sm ${
                      isSelected
                        ? 'bg-gradient-to-r from-sky-600 to-blue-600 border-2 border-white text-white shadow-xl shadow-sky-950/70 z-20 ring-2 ring-sky-400/50'
                        : 'bg-gradient-to-r from-sky-950/80 to-blue-950/80 border border-sky-500/40 text-sky-100 hover:border-sky-400 hover:from-sky-900/80'
                    }`}
                    style={{ left: `${left}px`, width: `${width}px` }}
                  >
                    <div className="flex items-center justify-between text-[10px] font-bold">
                      <span>Cut #{idx + 1}</span>
                      {hasZoom && (
                        <span className="px-1.5 py-0.2 bg-sky-900 text-sky-200 rounded font-mono text-[8px] border border-sky-600/60 font-bold">
                          {cut.transform?.scale}x
                        </span>
                      )}
                    </div>
                    <div className="text-[9px] text-sky-200/70 font-mono mt-0.5">
                      {(cut.out_seconds - cut.in_seconds).toFixed(1)}s
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Track C1: Kinetic Captions / Subtitles */}
            <div className="h-11 bg-[#0d1017] border-y border-[#1a2230] relative overflow-hidden py-1">
              <div className="absolute left-2 top-1 text-[9px] font-mono text-amber-400 uppercase tracking-wider flex items-center gap-1 z-20 pointer-events-none bg-black/70 px-1.5 py-0.5 rounded border border-amber-500/30">
                <Type className="w-3 h-3 text-amber-400" /> C1 Kinetic Captions
              </div>
              {editDecisions?.subtitles?.cues && editDecisions.subtitles.cues.length > 0 ? (
                editDecisions.subtitles.cues.map((cue) => {
                  const left = cue.start * pixelsPerSecond;
                  const width = Math.max(28, (cue.end - cue.start) * pixelsPerSecond);
                  const isSelected = selectedItemId === cue.id && selectedItemType === 'caption';
                  const isEmphasis = cue.mode === 'emphasis';
                  const isStack = cue.mode === 'stack';

                  return (
                    <div
                      key={cue.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectItem(cue.id, 'caption');
                      }}
                      className={`absolute top-1 bottom-1 rounded-md px-1.5 flex items-center justify-between cursor-pointer transition-all text-[9px] font-medium truncate ${
                        isSelected
                          ? 'bg-gradient-to-r from-amber-600 to-orange-600 border-2 border-white text-white shadow-lg shadow-amber-950/80 z-20 ring-2 ring-amber-400/50'
                          : isEmphasis
                          ? 'bg-gradient-to-r from-amber-900/90 to-orange-950/90 border border-amber-400/80 text-amber-200 hover:border-amber-300 font-bold'
                          : isStack
                          ? 'bg-gradient-to-r from-amber-950/80 to-yellow-950/80 border border-yellow-500/50 text-yellow-200 hover:border-yellow-400'
                          : 'bg-amber-950/40 border border-amber-500/30 hover:bg-amber-900/40 text-amber-200/90'
                      }`}
                      style={{ left: `${left}px`, width: `${width}px` }}
                      title={`Cue: "${cue.text}" (${cue.start.toFixed(2)}s - ${cue.end.toFixed(2)}s) [${cue.mode.toUpperCase()}]`}
                    >
                      <span className="truncate">{cue.text}</span>
                      {isEmphasis && (
                        <span className="ml-1 text-[8px] bg-amber-400/20 text-amber-300 px-1 py-0.2 rounded font-mono font-bold shrink-0">
                          ★
                        </span>
                      )}
                      {isStack && (
                        <span className="ml-1 text-[7px] bg-yellow-400/20 text-yellow-300 px-0.5 py-0.2 rounded font-mono shrink-0">
                          2T
                        </span>
                      )}
                    </div>
                  );
                })
              ) : (
                editDecisions?.subtitles?.words?.map((word, idx) => {
                  const left = word.start * pixelsPerSecond;
                  const width = Math.max(14, (word.end - word.start) * pixelsPerSecond);

                  return (
                    <div
                      key={idx}
                      className="absolute top-1 bottom-1 bg-amber-500/20 border border-amber-500/40 hover:bg-amber-500/30 rounded-md px-1 flex items-center justify-center text-[9px] text-amber-200 font-medium truncate"
                      style={{ left: `${left}px`, width: `${width}px` }}
                      title={`Word: "${word.word}" (${word.start}s - ${word.end}s)`}
                    >
                      <span className="truncate">{word.word}</span>
                    </div>
                  );
                })
              )}
            </div>

            {/* Track A1: Audio Waveform */}
            <div className="h-11 bg-[#0c0f16] border-y border-[#18202c] relative overflow-hidden py-1">
              <div className="absolute left-2 top-1 text-[9px] font-mono text-emerald-400 uppercase tracking-wider flex items-center gap-1 z-20 pointer-events-none bg-black/60 px-1.5 py-0.5 rounded">
                <Volume2 className="w-3 h-3" /> A1 Master Audio {waveformPeaks.length > 0 && <span className="text-[9px] text-emerald-400/60 font-mono">({waveformPeaks.length} pts)</span>}
              </div>
              <div
                className="absolute inset-x-0 top-1 bottom-1 bg-emerald-950/20 border border-emerald-800/30 rounded-lg flex items-center px-4 overflow-hidden"
                style={{ width: `${duration * pixelsPerSecond}px` }}
              >
                {waveformPeaks.length > 0 ? (
                  <svg
                    className="w-full h-full opacity-85"
                    viewBox={`0 0 ${waveformPeaks.length} 32`}
                    preserveAspectRatio="none"
                  >
                    {waveformPeaks.map((peak, idx) => {
                      const h = Math.max(2, peak * 28);
                      const y = (32 - h) / 2;
                      return (
                        <rect
                          key={idx}
                          x={idx}
                          y={y}
                          width={0.8}
                          height={h}
                          fill="#34d399"
                          rx={0.3}
                        />
                      );
                    })}
                  </svg>
                ) : (
                  <div className="flex items-center gap-1 w-full opacity-40">
                    {Array.from({ length: Math.min(180, Math.floor(duration * 4)) }).map((_, i) => (
                      <div key={i} className="w-1 bg-emerald-400 rounded-full h-3" />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Interactive Glowing Red Playhead Bar */}
          <div
            className="absolute top-0 bottom-0 pointer-events-none z-30 transition-all duration-75"
            style={{ left: `${currentTime * pixelsPerSecond}px` }}
          >
            <div className="w-3.5 h-3.5 bg-rose-500 rotate-45 -ml-[7px] -mt-1 shadow-lg shadow-rose-500/80" />
            <div className="w-[1.5px] h-full bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.9)]" />
          </div>
        </div>
      </div>
    </div>
  );
};
