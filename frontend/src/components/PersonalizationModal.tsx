import React, { useState, useEffect } from 'react';
import {
  Brain,
  Sliders,
  CheckCircle2,
  XCircle,
  Trash2,
  RotateCcw,
  Download,
  Upload,
  Sparkles,
  Layers,
  Palette,
  ZoomIn,
  Type,
  Scissors,
  Check,
  X,
  Plus,
  RefreshCw,
  Database,
  ShieldCheck,
  Clock
} from 'lucide-react';
import {
  fetchPreferencesSettings,
  updatePreferencesSettings,
  fetchPreferences,
  updatePreference,
  deletePreference,
  resetAllPreferences,
  fetchCorrections,
  approveCorrection,
  rejectCorrection,
  fetchStylePresets,
  activateStylePreset,
  deleteStylePreset,
  exportPreferencesData,
  importPreferencesData,
  exportDataset
} from '../api';

interface PersonalizationModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentProjectId?: string;
  onPreferencesUpdated?: () => void;
}

export const PersonalizationModal: React.FC<PersonalizationModalProps> = ({
  isOpen,
  onClose,
  currentProjectId,
  onPreferencesUpdated,
}) => {
  const [activeTab, setActiveTab] = useState<'preferences' | 'presets' | 'corrections' | 'backup'>('preferences');
  const [settings, setSettings] = useState<any>({ personalization_enabled: true, active_preset_id: 'educational-explainer' });
  const [preferences, setPreferences] = useState<any[]>([]);
  const [presets, setPresets] = useState<any[]>([]);
  const [corrections, setCorrections] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadAllData();
    }
  }, [isOpen]);

  const showStatus = (msg: string) => {
    setStatusMsg(msg);
    setTimeout(() => setStatusMsg(null), 3500);
  };

  const loadAllData = async () => {
    setLoading(true);
    try {
      const [sData, pData, prData, cData] = await Promise.all([
        fetchPreferencesSettings().catch(() => ({ personalization_enabled: true })),
        fetchPreferences().catch(() => []),
        fetchStylePresets().catch(() => []),
        fetchCorrections(currentProjectId).catch(() => []),
      ]);
      setSettings(sData);
      setPreferences(pData);
      setPresets(prData);
      setCorrections(cData);
    } catch (err: any) {
      console.error('Failed to load personalization data', err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleGlobal = async () => {
    const updated = !settings.personalization_enabled;
    try {
      await updatePreferencesSettings({ personalization_enabled: updated });
      setSettings({ ...settings, personalization_enabled: updated });
      showStatus(`Personalization ${updated ? 'enabled' : 'disabled'}`);
      onPreferencesUpdated?.();
    } catch (err: any) {
      alert(`Error updating settings: ${err.message}`);
    }
  };

  const handleTogglePref = async (pref: any) => {
    try {
      await updatePreference(pref.preference_id, { enabled: !pref.enabled });
      setPreferences(preferences.map(p => p.preference_id === pref.preference_id ? { ...p, enabled: !p.enabled } : p));
      showStatus(`Preference '${pref.preference_id}' ${!pref.enabled ? 'enabled' : 'disabled'}`);
      onPreferencesUpdated?.();
    } catch (err: any) {
      alert(`Failed to update preference: ${err.message}`);
    }
  };

  const handleDeletePref = async (prefId: string) => {
    if (!confirm(`Are you sure you want to permanently delete preference '${prefId}'?`)) return;
    try {
      await deletePreference(prefId);
      setPreferences(preferences.filter(p => p.preference_id !== prefId));
      showStatus(`Preference permanently deleted.`);
      onPreferencesUpdated?.();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const handleResetAll = async () => {
    if (!confirm('Warning: This will purge all learned preferences and reset OpenMontage memory to factory defaults. Continue?')) return;
    try {
      await resetAllPreferences();
      await loadAllData();
      showStatus('Personalization memory reset to defaults.');
      onPreferencesUpdated?.();
    } catch (err: any) {
      alert(`Reset failed: ${err.message}`);
    }
  };

  const handleApproveCorrection = async (corrId: string, applyToFuture: boolean) => {
    try {
      await approveCorrection(corrId, applyToFuture);
      showStatus(applyToFuture ? 'Approved and saved to editing memory!' : 'Applied to current project only.');
      await loadAllData();
      onPreferencesUpdated?.();
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    }
  };

  const handleRejectCorrection = async (corrId: string) => {
    try {
      await rejectCorrection(corrId);
      showStatus('Correction ignored.');
      await loadAllData();
    } catch (err: any) {
      alert(`Reject failed: ${err.message}`);
    }
  };

  const handleActivatePreset = async (presetId: string) => {
    try {
      await activateStylePreset(presetId);
      setSettings({ ...settings, active_preset_id: presetId });
      showStatus(`Activated preset '${presetId}'`);
      onPreferencesUpdated?.();
    } catch (err: any) {
      alert(`Activate failed: ${err.message}`);
    }
  };

  const handleExportData = async () => {
    try {
      const data = await exportPreferencesData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `openmontage_preferences_${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showStatus('Preferences exported successfully.');
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    }
  };

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      await importPreferencesData(parsed, true);
      showStatus('Preferences imported and verified!');
      await loadAllData();
      onPreferencesUpdated?.();
    } catch (err: any) {
      alert(`Import error: ${err.message}`);
    }
  };

  const handleExportDataset = async () => {
    try {
      const ds = await exportDataset(true);
      const blob = new Blob([JSON.stringify(ds, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `openmontage_training_dataset_${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showStatus(`Exported ${ds.total_examples} fine-tuning examples.`);
    } catch (err: any) {
      alert(`Dataset export error: ${err.message}`);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl bg-[#161a23] border border-[#262c38] rounded-xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#262c38] bg-[#12161f]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center text-white shadow">
              <Brain size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                Intelligent Editing Memory & Personalization
                <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-purple-950 text-purple-300 border border-purple-800">
                  Phase 10
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Local-first preference store learned from explicitly approved manual corrections.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Master Personalization Switch */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1a202c] border border-slate-700 text-xs">
              <span className="text-slate-300 font-medium">Personalization:</span>
              <button
                onClick={handleToggleGlobal}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                  settings.personalization_enabled ? 'bg-purple-600' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                    settings.personalization_enabled ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
              <span className={`text-[11px] font-mono ${settings.personalization_enabled ? 'text-purple-300' : 'text-slate-400'}`}>
                {settings.personalization_enabled ? 'ON' : 'OFF'}
              </span>
            </div>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 p-1 rounded-md hover:bg-slate-800 transition"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Status Toast */}
        {statusMsg && (
          <div className="bg-purple-900/60 border-b border-purple-700 text-purple-200 px-6 py-1.5 text-xs flex items-center gap-2">
            <CheckCircle2 size={13} className="text-purple-400" />
            <span>{statusMsg}</span>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex border-b border-[#262c38] px-6 bg-[#131720]">
          <button
            onClick={() => setActiveTab('preferences')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
              activeTab === 'preferences'
                ? 'border-purple-500 text-purple-300 bg-purple-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sliders size={14} />
            Learned Preferences ({preferences.length})
          </button>
          <button
            onClick={() => setActiveTab('presets')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
              activeTab === 'presets'
                ? 'border-purple-500 text-purple-300 bg-purple-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Palette size={14} />
            Style Presets ({presets.length})
          </button>
          <button
            onClick={() => setActiveTab('corrections')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
              activeTab === 'corrections'
                ? 'border-purple-500 text-purple-300 bg-purple-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock size={14} />
            Recent Corrections ({corrections.length})
          </button>
          <button
            onClick={() => setActiveTab('backup')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
              activeTab === 'backup'
                ? 'border-purple-500 text-purple-300 bg-purple-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database size={14} />
            Backup & Training Dataset
          </button>
        </div>

        {/* Tab Content Body */}
        <div className="p-6 overflow-y-auto flex-1 text-xs">
          {/* 1. LEARNED PREFERENCES TAB */}
          {activeTab === 'preferences' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2">
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">Active Learned Preferences</h3>
                  <p className="text-slate-400 text-[11px]">
                    Preferences influence future AI planning decisions when matching video contexts occur.
                  </p>
                </div>
                <button
                  onClick={handleResetAll}
                  className="px-2.5 py-1 text-xs text-rose-400 hover:bg-rose-950/40 border border-rose-900 rounded flex items-center gap-1.5 transition"
                >
                  <RotateCcw size={12} />
                  Reset to Defaults
                </button>
              </div>

              {preferences.length === 0 ? (
                <div className="p-8 border border-dashed border-slate-700 rounded-lg text-center text-slate-400 space-y-2">
                  <Brain size={28} className="mx-auto text-slate-500 opacity-60" />
                  <p className="font-medium text-slate-300">No approved editing preferences yet.</p>
                  <p className="text-[11px] text-slate-500 max-w-md mx-auto">
                    When you modify zoom, captions, or graphic types in the Inspector, click "Approve as Preference" to store it here.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {preferences.map((p) => (
                    <div
                      key={p.preference_id}
                      className={`p-3 rounded-lg border transition ${
                        p.enabled
                          ? 'bg-[#181d28] border-slate-700/80'
                          : 'bg-[#13161d] border-slate-800 opacity-60'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase font-bold bg-slate-800 text-slate-300 border border-slate-700">
                            {p.category}
                          </span>
                          <span className="font-semibold text-slate-200">{p.parameter_key}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleTogglePref(p)}
                            className={`p-1 rounded text-xs ${
                              p.enabled ? 'text-emerald-400 hover:bg-emerald-950/50' : 'text-slate-500 hover:bg-slate-800'
                            }`}
                            title={p.enabled ? 'Disable preference' : 'Enable preference'}
                          >
                            <CheckCircle2 size={14} />
                          </button>
                          <button
                            onClick={() => handleDeletePref(p.preference_id)}
                            className="p-1 rounded text-rose-400 hover:bg-rose-950/50"
                            title="Permanently delete from disk"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      <div className="mt-2.5 p-2 rounded bg-black/40 font-mono text-[11px] text-purple-300 flex items-center justify-between">
                        <span>Preferred Value:</span>
                        <span className="font-bold text-slate-100">{JSON.stringify(p.preferred_value)}</span>
                      </div>

                      <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400">
                        <span>Confidence: {(p.confidence * 100).toFixed(0)}%</span>
                        <span>Reinforced: {p.times_approved}x</span>
                        <span>
                          {p.context_constraints?.target_aspect ? `Aspect: ${p.context_constraints.target_aspect}` : 'Global'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 2. STYLE PRESETS TAB */}
          {activeTab === 'presets' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2">
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">Editorial Style Presets</h3>
                  <p className="text-slate-400 text-[11px]">
                    Reusable production bundles defining typography, pacing thresholds, zoom intensity, and visual colors.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {presets.map((preset) => {
                  const isActive = settings.active_preset_id === preset.preset_id;
                  return (
                    <div
                      key={preset.preset_id}
                      className={`p-3.5 rounded-lg border flex flex-col justify-between transition ${
                        isActive
                          ? 'bg-purple-950/20 border-purple-600 shadow-md ring-1 ring-purple-600/50'
                          : 'bg-[#181d28] border-slate-700/80 hover:border-slate-600'
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between">
                          <h4 className="font-bold text-slate-100 text-xs flex items-center gap-2">
                            {preset.title}
                            {preset.is_builtin && (
                              <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-slate-800 text-slate-300">
                                Built-in
                              </span>
                            )}
                          </h4>
                          {isActive && (
                            <span className="text-[10px] px-2 py-0.5 rounded font-semibold bg-purple-600 text-white shadow">
                              ACTIVE
                            </span>
                          )}
                        </div>
                        <p className="text-slate-400 text-[11px] mt-1">{preset.description}</p>

                        <div className="mt-3 grid grid-cols-2 gap-2 text-[10px] text-slate-300 bg-black/30 p-2 rounded">
                          <div>Zoom: <span className="text-purple-300 font-mono">{preset.zoom_scale}x ({preset.zoom_intensity})</span></div>
                          <div>Aspect: <span className="text-purple-300 font-mono">{preset.target_aspect}</span></div>
                          <div>Words/Group: <span className="text-purple-300 font-mono">{preset.words_per_page}</span></div>
                          <div>Pacing Cut: <span className="text-purple-300 font-mono">{preset.min_pause_cut_duration}s</span></div>
                        </div>
                      </div>

                      <div className="mt-3 pt-2 border-t border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: preset.caption_highlight_color }} />
                          <span className="text-[10px] text-slate-400 font-mono">{preset.caption_highlight_color}</span>
                        </div>

                        {!isActive ? (
                          <button
                            onClick={() => handleActivatePreset(preset.preset_id)}
                            className="px-2.5 py-1 text-xs rounded bg-purple-600/80 hover:bg-purple-600 text-white font-medium transition"
                          >
                            Set Active
                          </button>
                        ) : (
                          <span className="text-emerald-400 text-[11px] flex items-center gap-1">
                            <Check size={12} /> Active Preset
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 3. RECENT CORRECTIONS AUDIT TAB */}
          {activeTab === 'corrections' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2">
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">Recent User Corrections</h3>
                  <p className="text-slate-400 text-[11px]">
                    Manual modifications recorded from timeline actions. Only explicitly approved corrections become learned preferences.
                  </p>
                </div>
                <button
                  onClick={loadAllData}
                  className="px-2 py-1 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 rounded flex items-center gap-1 transition"
                >
                  <RefreshCw size={12} /> Refresh
                </button>
              </div>

              {corrections.length === 0 ? (
                <div className="p-8 border border-dashed border-slate-700 rounded-lg text-center text-slate-400">
                  <Clock size={24} className="mx-auto text-slate-500 opacity-60 mb-2" />
                  <p className="font-medium text-slate-300">No corrections logged yet.</p>
                  <p className="text-[11px] text-slate-500">
                    Modifications made to zoom, colors, or cuts in the timeline will appear here for review.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {corrections.map((c) => {
                    const isPending = c.approval_status === 'pending_review';
                    const isApproved = c.approval_status === 'approved';
                    const isUndo = c.approval_status === 'undo_op';
                    return (
                      <div
                        key={c.correction_id}
                        className="p-3 rounded-lg border border-slate-800 bg-[#181d28] flex flex-col md:flex-row md:items-center justify-between gap-3"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-mono uppercase bg-slate-800 text-slate-300">
                              {c.category}
                            </span>
                            <span className="font-semibold text-slate-200">{c.parameter_key}</span>
                            <span
                              className={`text-[10px] px-2 py-0.2 rounded font-mono font-bold ${
                                isApproved
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                  : isPending
                                  ? 'bg-amber-950 text-amber-300 border border-amber-800'
                                  : isUndo
                                  ? 'bg-slate-800 text-slate-400'
                                  : 'bg-rose-950 text-rose-300 border border-rose-800'
                              }`}
                            >
                              {c.approval_status}
                            </span>
                          </div>

                          <div className="flex items-center gap-4 text-[11px] font-mono">
                            <span className="text-slate-400">
                              AI Original: <span className="text-amber-400">{JSON.stringify(c.original_ai_value)}</span>
                            </span>
                            <span className="text-slate-500">→</span>
                            <span className="text-slate-400">
                              Your Correction: <span className="text-emerald-400 font-bold">{JSON.stringify(c.user_corrected_value)}</span>
                            </span>
                          </div>

                          {c.user_note && <p className="text-[10px] text-slate-500 italic">"{c.user_note}"</p>}
                        </div>

                        {/* Approval Actions */}
                        {isPending && (
                          <div className="flex items-center gap-1.5 shrink-0">
                            <button
                              onClick={() => handleApproveCorrection(c.correction_id, true)}
                              className="px-2.5 py-1 text-xs rounded bg-purple-600 hover:bg-purple-500 text-white font-medium flex items-center gap-1 shadow"
                              title="Remember this preferred value for future video edits"
                            >
                              <CheckCircle2 size={12} />
                              Learn for Future
                            </button>
                            <button
                              onClick={() => handleApproveCorrection(c.correction_id, false)}
                              className="px-2 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                              title="Keep for this project only"
                            >
                              Project Only
                            </button>
                            <button
                              onClick={() => handleRejectCorrection(c.correction_id)}
                              className="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800"
                              title="Ignore this edit"
                            >
                              <XCircle size={15} />
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* 4. BACKUP, IMPORT & TRAINING DATASET TAB */}
          {activeTab === 'backup' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-semibold text-slate-200">Import & Export Preferences</h3>
                <p className="text-slate-400 text-[11px]">
                  Safely migrate your learned editing profiles and style presets across workstations.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
                  <div className="p-4 rounded-lg bg-[#181d28] border border-slate-700 flex flex-col justify-between">
                    <div>
                      <h4 className="font-semibold text-slate-200 flex items-center gap-2">
                        <Download size={14} className="text-purple-400" /> Export Preferences JSON
                      </h4>
                      <p className="text-slate-400 text-[11px] mt-1">
                        Download your learned editing parameters, custom style presets, and configuration settings.
                      </p>
                    </div>
                    <button
                      onClick={handleExportData}
                      className="mt-4 px-3 py-1.5 rounded bg-purple-600 hover:bg-purple-500 text-white font-medium text-xs flex items-center justify-center gap-2"
                    >
                      <Download size={13} /> Export JSON File
                    </button>
                  </div>

                  <div className="p-4 rounded-lg bg-[#181d28] border border-slate-700 flex flex-col justify-between">
                    <div>
                      <h4 className="font-semibold text-slate-200 flex items-center gap-2">
                        <Upload size={14} className="text-blue-400" /> Import Preferences JSON
                      </h4>
                      <p className="text-slate-400 text-[11px] mt-1">
                        Upload a previously exported preferences file. Validates schema and prevents path traversal.
                      </p>
                    </div>
                    <label className="mt-4 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs flex items-center justify-center gap-2 cursor-pointer border border-slate-600">
                      <Upload size={13} /> Select JSON File
                      <input type="file" accept=".json" onChange={handleImportFile} className="hidden" />
                    </label>
                  </div>
                </div>
              </div>

              {/* Section 11: Structured Opt-in Training Dataset */}
              <div className="pt-4 border-t border-slate-800">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                      <Database size={15} className="text-emerald-400" />
                      Future Model Fine-Tuning Dataset (Opt-In)
                    </h3>
                    <p className="text-slate-400 text-[11px] mt-1 max-w-xl">
                      Exports high-quality human corrections paired with original AI proposals into a structured dataset.
                      Does not train any neural model now; strictly prepares structured data for future model adaptation.
                    </p>
                  </div>
                  <button
                    onClick={handleExportDataset}
                    className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs flex items-center gap-2 shadow"
                  >
                    <Download size={13} />
                    Export Dataset
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-[#262c38] bg-[#12161f] flex items-center justify-between text-xs text-slate-500">
          <span>Priority Rules: Tier 1 (User Prompt) &gt; Tier 2 (Video Bounds) &gt; Tier 3 (Learned Memory) &gt; Tier 4 (Defaults)</span>
          <button
            onClick={onClose}
            className="px-4 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
