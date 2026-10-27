import React from 'react';
import {
  Sliders,
  Type,
  Sparkles,
  Scissors,
  ZoomIn,
  Trash2,
  Brain,
} from 'lucide-react';
import { EditDecisions, Overlay, Cut } from '../types';
import { recordManualCorrection } from '../api';

interface InspectorProps {
  editDecisions: EditDecisions | null;
  selectedItemId: string | null;
  selectedItemType: 'cut' | 'overlay' | 'caption' | null;
  onUpdateDecisions: (updated: EditDecisions, commitMsg?: string) => void;
  onDeselect: () => void;
}

export const Inspector: React.FC<InspectorProps> = ({
  editDecisions,
  selectedItemId,
  selectedItemType,
  onUpdateDecisions,
  onDeselect,
}) => {
  if (!editDecisions) {
    return (
      <div className="h-full bg-[#12161f] border-l border-[#262c38] p-4 text-slate-500 text-xs flex flex-col items-center justify-center text-center">
        <Sliders className="w-8 h-8 mb-2 text-slate-600" />
        <p>No project loaded</p>
      </div>
    );
  }

  // Find currently selected overlay or cut
  const selectedOverlay =
    selectedItemType === 'overlay'
      ? editDecisions.overlays.find((o) => o.id === selectedItemId)
      : null;

  const selectedCut =
    selectedItemType === 'cut'
      ? editDecisions.cuts.find((c) => c.id === selectedItemId)
      : null;

  const selectedCaptionCue =
    selectedItemType === 'caption'
      ? editDecisions.subtitles?.cues?.find((c) => c.id === selectedItemId)
      : null;

  // Helper to update selected caption cue
  const updateCaptionField = (field: string, value: any) => {
    if (!selectedCaptionCue || !editDecisions.subtitles?.cues) return;
    const updatedCues = editDecisions.subtitles.cues.map((c) =>
      c.id === selectedCaptionCue.id ? { ...c, [field]: value } : c
    );
    onUpdateDecisions(
      {
        ...editDecisions,
        subtitles: {
          ...editDecisions.subtitles,
          cues: updatedCues,
        },
      },
      `Update ${field} on caption cue ${selectedCaptionCue.id}`
    );
  };

  const deleteCaptionCue = () => {
    if (!selectedCaptionCue || !editDecisions.subtitles?.cues) return;
    const updatedCues = editDecisions.subtitles.cues.filter((c) => c.id !== selectedCaptionCue.id);
    onUpdateDecisions(
      {
        ...editDecisions,
        subtitles: {
          ...editDecisions.subtitles,
          cues: updatedCues,
        },
      },
      `Delete caption cue ${selectedCaptionCue.id}`
    );
    onDeselect();
  };

  const splitCaptionCue = () => {
    if (!selectedCaptionCue || !editDecisions.subtitles?.cues) return;
    const words = selectedCaptionCue.text.trim().split(/\s+/);
    if (words.length < 2) return;
    const midIdx = Math.floor(words.length / 2);
    const midTime = (selectedCaptionCue.start + selectedCaptionCue.end) / 2;
    const firstHalfText = words.slice(0, midIdx).join(' ');
    const secondHalfText = words.slice(midIdx).join(' ');

    const cue1 = {
      ...selectedCaptionCue,
      text: firstHalfText,
      end: parseFloat(midTime.toFixed(2)),
    };
    const cue2 = {
      ...selectedCaptionCue,
      id: `cue_${Date.now()}`,
      text: secondHalfText,
      start: parseFloat(midTime.toFixed(2)),
      mode: 'normal' as const,
      emphasis_word: undefined,
      support_words: undefined,
    };

    const updatedCues: any[] = [];
    for (const c of editDecisions.subtitles.cues) {
      if (c.id === selectedCaptionCue.id) {
        updatedCues.push(cue1, cue2);
      } else {
        updatedCues.push(c);
      }
    }
    onUpdateDecisions(
      {
        ...editDecisions,
        subtitles: {
          ...editDecisions.subtitles,
          cues: updatedCues,
        },
      },
      `Split caption cue ${selectedCaptionCue.id}`
    );
  };

  // Helper to update selected overlay
  const updateOverlayField = (field: keyof Overlay, value: any) => {
    if (!selectedOverlay) return;
    const updatedOverlays = editDecisions.overlays.map((o) =>
      o.id === selectedOverlay.id ? { ...o, [field]: value } : o
    );
    onUpdateDecisions(
      { ...editDecisions, overlays: updatedOverlays },
      `Update ${field} on overlay ${selectedOverlay.id}`
    );
  };

  const updateOverlayContent = (contentField: string, value: any) => {
    if (!selectedOverlay) return;
    const updatedOverlays = editDecisions.overlays.map((o) =>
      o.id === selectedOverlay.id
        ? { ...o, content: { ...o.content, [contentField]: value } }
        : o
    );
    onUpdateDecisions(
      { ...editDecisions, overlays: updatedOverlays },
      `Update content.${contentField} on overlay ${selectedOverlay.id}`
    );
  };

  // Helper to update selected cut
  const updateCutField = (field: keyof Cut, value: any) => {
    if (!selectedCut) return;
    const updatedCuts = editDecisions.cuts.map((c) =>
      c.id === selectedCut.id ? { ...c, [field]: value } : c
    );
    onUpdateDecisions(
      { ...editDecisions, cuts: updatedCuts },
      `Update cut ${selectedCut.id}`
    );
  };

  const updateCutTransform = (transformField: string, value: any) => {
    if (!selectedCut) return;
    const updatedCuts = editDecisions.cuts.map((c) =>
      c.id === selectedCut.id
        ? {
            ...c,
            transform: {
              ...c.transform,
              [transformField]: value,
            },
          }
        : c
    );
    onUpdateDecisions(
      { ...editDecisions, cuts: updatedCuts },
      `Update zoom transform on cut ${selectedCut.id}`
    );
  };

  return (
    <div className="flex flex-col h-full bg-[#12161f] border-l border-[#262c38]">
      {/* Inspector Header */}
      <div className="p-3 border-b border-[#262c38] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sliders className="w-4 h-4 text-[#38bdf8]" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Properties Inspector
          </h2>
        </div>
        {selectedItemId && (
          <button
            onClick={onDeselect}
            className="text-[10px] text-slate-400 hover:text-white px-1.5 py-0.5 rounded hover:bg-[#1f2738]"
          >
            Deselect
          </button>
        )}
      </div>

      {/* Inspector Body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* CASE 1: OVERLAY SELECTED */}
        {selectedOverlay && (
          <div className="space-y-3.5">
            <div className="flex items-center justify-between pb-2 border-b border-[#202736]">
              <span className="text-xs font-bold text-sky-400 flex items-center gap-1.5 uppercase font-mono">
                <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                {selectedOverlay.type.replace('_', ' ')}
              </span>
              <span className="text-[10px] text-slate-500 font-mono">{selectedOverlay.id}</span>
            </div>

            {/* Template Type Selector */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Remotion Template
              </label>
              <select
                value={selectedOverlay.type}
                onChange={(e) => updateOverlayField('type', e.target.value)}
                className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-[#38bdf8]"
              >
                <option value="stat_card">Stat Card (Metric Punch)</option>
                <option value="text_card">Text Card (Headline & Bullet)</option>
                <option value="callout">Callout (Tip / Warning / Quote)</option>
                <option value="hero_title">Hero Title (Opening Sting)</option>
                <option value="comparison">Comparison (Left vs Right)</option>
              </select>
            </div>

            {/* Timing Range */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Timing (Seconds)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[10px] text-slate-400 block mb-0.5">Start Time</span>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={selectedOverlay.in_seconds}
                    onChange={(e) => updateOverlayField('in_seconds', parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block mb-0.5">End Time</span>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={selectedOverlay.out_seconds}
                    onChange={(e) => updateOverlayField('out_seconds', parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono"
                  />
                </div>
              </div>
              <div className="text-[10px] text-slate-500 font-mono mt-1 text-right">
                Duration: {(selectedOverlay.out_seconds - selectedOverlay.in_seconds).toFixed(2)}s
              </div>
            </div>

            {/* Placement & Position */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Screen Placement
              </label>
              <select
                value={selectedOverlay.position || 'upper_third'}
                onChange={(e) => updateOverlayField('position', e.target.value)}
                className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-[#38bdf8]"
              >
                <option value="upper_third">Upper Third (Above Speaker)</option>
                <option value="lower_third">Lower Third (Classic Overlay)</option>
                <option value="upper_window">Upper Window (Compact Card)</option>
                <option value="left_panel">Left Panel</option>
                <option value="right_panel">Right Panel</option>
                <option value="full_overlay">Full Screen Splash</option>
              </select>
            </div>

            {/* Animation Style */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Spring Physics Animation
              </label>
              <div className="grid grid-cols-4 gap-1">
                {(['spring', 'pop', 'slide', 'fade'] as const).map((anim) => (
                  <button
                    key={anim}
                    onClick={() => updateOverlayField('animation', anim)}
                    className={`py-1 rounded text-[10px] uppercase font-mono capitalize transition-colors ${
                      (selectedOverlay.animation || 'spring') === anim
                        ? 'bg-[#0284c7] text-white font-bold'
                        : 'bg-[#161c26] text-slate-400 hover:text-slate-200 border border-[#262f3f]'
                    }`}
                  >
                    {anim}
                  </button>
                ))}
              </div>
            </div>

            {/* Color Palette */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Accent Color
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={selectedOverlay.accentColor || '#38bdf8'}
                  onChange={(e) => updateOverlayField('accentColor', e.target.value)}
                  className="w-8 h-8 rounded bg-transparent cursor-pointer border border-[#262f3f]"
                />
                <input
                  type="text"
                  value={selectedOverlay.accentColor || '#38bdf8'}
                  onChange={(e) => updateOverlayField('accentColor', e.target.value)}
                  className="flex-1 bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            {/* Template Specific Content Fields */}
            <div className="pt-2 border-t border-[#1f2736] space-y-2.5">
              <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block">
                Text & Content Values
              </span>

              {/* Stat card fields */}
              {selectedOverlay.type === 'stat_card' && (
                <>
                  <div>
                    <span className="text-[10px] text-slate-400 block mb-0.5">Big Metric Value</span>
                    <input
                      type="text"
                      value={selectedOverlay.content?.value || ''}
                      onChange={(e) => updateOverlayContent('value', e.target.value)}
                      placeholder="+84%"
                      className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-amber-300 font-mono font-bold"
                    />
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block mb-0.5">Label</span>
                    <input
                      type="text"
                      value={selectedOverlay.content?.label || ''}
                      onChange={(e) => updateOverlayContent('label', e.target.value)}
                      placeholder="Conversion Boost"
                      className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200"
                    />
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block mb-0.5">Trend Direction</span>
                    <select
                      value={selectedOverlay.content?.trend || 'positive'}
                      onChange={(e) => updateOverlayContent('trend', e.target.value)}
                      className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200"
                    >
                      <option value="positive">Positive (Up Green)</option>
                      <option value="negative">Negative (Down Red)</option>
                      <option value="neutral">Neutral (Blue)</option>
                    </select>
                  </div>
                </>
              )}

              {/* Text card & Callout fields */}
              {(selectedOverlay.type === 'text_card' ||
                selectedOverlay.type === 'callout' ||
                selectedOverlay.type === 'hero_title') && (
                <>
                  <div>
                    <span className="text-[10px] text-slate-400 block mb-0.5">Title / Headline</span>
                    <input
                      type="text"
                      value={selectedOverlay.content?.title || ''}
                      onChange={(e) => updateOverlayContent('title', e.target.value)}
                      placeholder="Key Takeaway"
                      className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-semibold"
                    />
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block mb-0.5">Body / Subtitle</span>
                    <textarea
                      rows={2}
                      value={selectedOverlay.content?.subtitle || selectedOverlay.content?.text || ''}
                      onChange={(e) => {
                        updateOverlayContent('subtitle', e.target.value);
                        updateOverlayContent('text', e.target.value);
                      }}
                      placeholder="Enter descriptive copy..."
                      className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 resize-none"
                    />
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* CASE 2: CUT SELECTED */}
        {selectedCut && (
          <div className="space-y-3.5">
            <div className="flex items-center justify-between pb-2 border-b border-[#202736]">
              <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5 uppercase font-mono">
                <Scissors className="w-3.5 h-3.5 text-emerald-300" />
                Video Cut
              </span>
              <span className="text-[10px] text-slate-500 font-mono">{selectedCut.id}</span>
            </div>

            {/* Cut Timing */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Source Cut Window
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[10px] text-slate-400 block mb-0.5">In (Sec)</span>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={selectedCut.in_seconds}
                    onChange={(e) => updateCutField('in_seconds', parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block mb-0.5">Out (Sec)</span>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={selectedCut.out_seconds}
                    onChange={(e) => updateCutField('out_seconds', parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono"
                  />
                </div>
              </div>
            </div>

            {/* Dynamic Zoom Intensity */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                  <ZoomIn className="w-3 h-3 text-emerald-400" />
                  Dynamic Camera Zoom
                </label>
                <span className="text-[10px] text-emerald-400 font-mono">
                  {selectedCut.transform?.scale || 1.0}x
                </span>
              </div>
              <input
                type="range"
                min="1.0"
                max="1.75"
                step="0.05"
                value={selectedCut.transform?.scale || 1.0}
                onChange={(e) => updateCutTransform('scale', parseFloat(e.target.value))}
                className="w-full h-1 bg-[#232d3f] rounded appearance-none accent-emerald-500"
              />
              <div className="flex justify-between text-[9px] text-slate-500 font-mono mt-1">
                <span>1.0x (Wide)</span>
                <span>1.25x (Punch)</span>
                <span>1.75x (Tight)</span>
              </div>

              {/* Save as Preferred Zoom (Phase 10) */}
              <button
                type="button"
                onClick={async () => {
                  try {
                    await recordManualCorrection({
                      project_id: 'current',
                      category: 'zoom',
                      parameter_key: 'zoom_scale',
                      original_ai_value: 1.25,
                      user_corrected_value: selectedCut.transform?.scale || 1.10,
                      editing_context: { target_aspect: editDecisions.metadata?.target_aspect || '9:16' },
                      approval_status: 'approved',
                      original_decision_provenance: selectedCut.transform?.zoom_provenance || {},
                      user_note: `User set preferred zoom to ${selectedCut.transform?.scale || 1.10}x from Inspector`,
                    });
                    alert(`Zoom preference ${selectedCut.transform?.scale || 1.10}x approved for future video edits!`);
                  } catch (err: any) {
                    alert(`Failed to save preference: ${err.message}`);
                  }
                }}
                className="w-full mt-2 py-1 px-2 rounded bg-purple-950/40 hover:bg-purple-900/60 border border-purple-700/60 text-purple-300 text-[10px] flex items-center justify-center gap-1.5 transition"
                title="Approve this zoom level as future editing preference"
              >
                <Brain className="w-3 h-3 text-purple-400" />
                <span>Save as Future Preferred Zoom ({selectedCut.transform?.scale || 1.0}x)</span>
              </button>
            </div>

            {/* Speed Multiplier */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Playback Speed
              </label>
              <div className="grid grid-cols-4 gap-1">
                {[0.8, 1.0, 1.25, 1.5].map((spd) => (
                  <button
                    key={spd}
                    onClick={() => updateCutField('speed', spd)}
                    className={`py-1 rounded text-[10px] font-mono transition-colors ${
                      (selectedCut.speed || 1.0) === spd
                        ? 'bg-emerald-600 text-white font-bold'
                        : 'bg-[#161c26] text-slate-400 hover:text-slate-200 border border-[#262f3f]'
                    }`}
                  >
                    {spd}x
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* CASE 3: CAPTION CUE SELECTED */}
        {selectedCaptionCue && (
          <div className="space-y-3.5">
            <div className="flex items-center justify-between pb-2 border-b border-[#202736]">
              <span className="text-xs font-bold text-amber-400 flex items-center gap-1.5 uppercase font-mono">
                <Type className="w-3.5 h-3.5 text-amber-300" />
                Kinetic Caption Cue
              </span>
              <span className="text-[10px] text-slate-500 font-mono">{selectedCaptionCue.id}</span>
            </div>

            {/* Cue Text */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Spoken Text
              </label>
              <input
                type="text"
                value={selectedCaptionCue.text}
                onChange={(e) => updateCaptionField('text', e.target.value)}
                className="w-full bg-[#161c26] border border-[#262f3f] rounded p-2 text-xs text-white font-medium focus:outline-none focus:border-amber-400"
              />
            </div>

            {/* Timing In / Out */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Display Timing
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[10px] text-slate-400 block mb-0.5">Start (Sec)</span>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    value={selectedCaptionCue.start}
                    onChange={(e) => updateCaptionField('start', parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block mb-0.5">End (Sec)</span>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    value={selectedCaptionCue.end}
                    onChange={(e) => updateCaptionField('end', parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#161c26] border border-[#262f3f] rounded p-1.5 text-xs text-slate-200 font-mono"
                  />
                </div>
              </div>
            </div>

            {/* Cue Mode (Normal, Emphasis, Stack) */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Editorial Styling Mode
              </label>
              <div className="grid grid-cols-3 gap-1">
                {(['normal', 'emphasis', 'stack'] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => updateCaptionField('mode', m)}
                    className={`py-1.5 rounded text-[10px] font-mono capitalize transition-colors ${
                      selectedCaptionCue.mode === m
                        ? 'bg-amber-600 text-white font-bold shadow'
                        : 'bg-[#161c26] text-slate-400 hover:text-slate-200 border border-[#262f3f]'
                    }`}
                  >
                    {m === 'normal' ? 'Regular' : m === 'emphasis' ? 'Emphasis' : '2-Tier Stack'}
                  </button>
                ))}
              </div>
            </div>

            {/* Emphasis Word (if emphasis or stack) */}
            {selectedCaptionCue.mode !== 'normal' && (
              <div className="bg-[#171d28] p-2.5 rounded border border-amber-500/30 space-y-2">
                <div>
                  <span className="text-[10px] text-amber-300 font-semibold uppercase block mb-1">
                    {selectedCaptionCue.mode === 'stack' ? 'Hero Word (Large Bottom)' : 'Emphasized Word'}
                  </span>
                  <input
                    type="text"
                    value={selectedCaptionCue.emphasis_word || ''}
                    onChange={(e) => updateCaptionField('emphasis_word', e.target.value)}
                    placeholder="e.g. STRUGGLES"
                    className="w-full bg-[#12161f] border border-amber-500/40 rounded p-1.5 text-xs text-amber-200 font-bold focus:outline-none"
                  />
                </div>

                {selectedCaptionCue.mode === 'stack' && (
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase block mb-1">
                      Support Words (Small Top)
                    </span>
                    <input
                      type="text"
                      value={selectedCaptionCue.support_words || ''}
                      onChange={(e) => updateCaptionField('support_words', e.target.value)}
                      placeholder="e.g. on my"
                      className="w-full bg-[#12161f] border border-[#262f3f] rounded p-1.5 text-xs text-slate-300 focus:outline-none"
                    />
                  </div>
                )}

                <div>
                  <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                    <span>Emphasis Scale</span>
                    <span className="font-mono text-amber-400">{selectedCaptionCue.scale || 1.85}x</span>
                  </div>
                  <input
                    type="range"
                    min="1.2"
                    max="2.5"
                    step="0.05"
                    value={selectedCaptionCue.scale || 1.85}
                    onChange={(e) => updateCaptionField('scale', parseFloat(e.target.value))}
                    className="w-full h-1 bg-[#232d3f] rounded appearance-none accent-amber-500"
                  />
                </div>
              </div>
            )}

            {/* Typography Weight */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Inter Display Weight
              </label>
              <div className="grid grid-cols-3 gap-1">
                {[
                  { w: 700, label: 'Bold' },
                  { w: 800, label: 'ExtraBold' },
                  { w: 900, label: 'Black' },
                ].map(({ w, label }) => (
                  <button
                    key={w}
                    onClick={() => updateCaptionField('font_weight', w)}
                    className={`py-1 rounded text-[10px] font-mono transition-colors ${
                      (selectedCaptionCue.font_weight || 800) === w
                        ? 'bg-amber-600 text-white font-bold'
                        : 'bg-[#161c26] text-slate-400 hover:text-slate-200 border border-[#262f3f]'
                    }`}
                  >
                    {label} ({w})
                  </button>
                ))}
              </div>
            </div>

            {/* Vertical Position */}
            <div>
              <div className="flex justify-between text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                <span>Vertical Position (Y)</span>
                <span className="font-mono text-amber-400">
                  {((selectedCaptionCue.position?.y ?? 0.48) * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.85"
                step="0.01"
                value={selectedCaptionCue.position?.y ?? 0.48}
                onChange={(e) =>
                  updateCaptionField('position', {
                    ...(selectedCaptionCue.position || { x: 0.5 }),
                    y: parseFloat(e.target.value),
                  })
                }
                className="w-full h-1 bg-[#232d3f] rounded appearance-none accent-amber-500"
              />
              <div className="flex justify-between text-[9px] text-slate-500 font-mono mt-1">
                <span>Top (15%)</span>
                <span>Center (48%)</span>
                <span>Bottom (80%)</span>
              </div>
            </div>

            {/* Cue Actions: Split & Delete */}
            <div className="pt-2 border-t border-[#202736] flex gap-2">
              <button
                type="button"
                onClick={splitCaptionCue}
                className="flex-1 py-1.5 px-2 rounded bg-[#1e2a3d] hover:bg-[#25354d] border border-[#38bdf8]/40 text-sky-300 text-xs flex items-center justify-center gap-1.5 transition"
              >
                <Scissors className="w-3.5 h-3.5 text-sky-400" />
                <span>Split Cue</span>
              </button>

              <button
                type="button"
                onClick={deleteCaptionCue}
                className="py-1.5 px-3 rounded bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800/40 text-rose-300 text-xs flex items-center justify-center gap-1 transition"
                title="Remove cue"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* CASE 4: NO SELECTION (PROJECT & CAPTIONS SUMMARY) */}
        {!selectedOverlay && !selectedCut && !selectedCaptionCue && (
          <div className="space-y-4">
            <div>
              <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-2">
                Composition Info
              </span>
              <div className="bg-[#161c26] p-2.5 rounded border border-[#232b3b] space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Render Engine:</span>
                  <span className="text-slate-200 font-mono">{editDecisions.render_runtime || 'Remotion'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Renderer Family:</span>
                  <span className="text-slate-200 font-mono">{editDecisions.renderer_family || 'TalkingHead'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Cuts:</span>
                  <span className="text-slate-200 font-mono">{editDecisions.cuts.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Overlays:</span>
                  <span className="text-slate-200 font-mono">{editDecisions.overlays.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Captions Count:</span>
                  <span className="text-slate-200 font-mono">
                    {editDecisions.subtitles?.words?.length || 0} words
                  </span>
                </div>
              </div>
            </div>

            {/* Captions Preset Switcher */}
            <div>
              <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Dynamic Captions Toggle
              </label>
              <div className="flex items-center justify-between bg-[#161c26] p-2 rounded border border-[#232b3b]">
                <span className="text-xs text-slate-300">Word-level Captions</span>
                <input
                  type="checkbox"
                  checked={editDecisions.subtitles?.enabled ?? true}
                  onChange={(e) => {
                    const updated = {
                      ...editDecisions,
                      subtitles: {
                        ...editDecisions.subtitles,
                        enabled: e.target.checked,
                      },
                    };
                    onUpdateDecisions(updated, 'Toggle subtitles');
                  }}
                  className="rounded bg-[#202738] accent-[#0284c7]"
                />
              </div>
            </div>

            <p className="text-[11px] text-slate-500 italic">
              Click any cut or overlay on the timeline to edit its timing, typography, spring animations, and zoom properties.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
