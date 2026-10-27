import React from 'react';
import {
  FolderOpen,
  Undo2,
  Redo2,
  Play,
  Download,
  ShieldCheck,
  Cpu,
  Layers,
  Sparkles,
  Brain,
  ChevronDown,
  Activity,
} from 'lucide-react';
import { ProjectDetails, SystemMetrics } from '../types';

interface HeaderProps {
  project: ProjectDetails | null;
  metrics: SystemMetrics | null;
  onOpenDashboard: () => void;
  onOpenPersonalization: () => void;
  onOpenJobs: () => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onRenderPreview: () => void;
  onOpenExport: () => void;
  onOpenQa: () => void;
  qaScore: number | null;
  qaPassed: boolean | null;
  activeTab: 'edit' | 'ai' | 'qa';
  setActiveTab: (tab: 'edit' | 'ai' | 'qa') => void;
}

export const Header: React.FC<HeaderProps> = ({
  project,
  metrics,
  onOpenDashboard,
  onOpenPersonalization,
  onOpenJobs,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  onRenderPreview,
  onOpenExport,
  onOpenQa,
  qaScore,
  qaPassed,
  activeTab,
  setActiveTab,
}) => {
  return (
    <header className="h-14 bg-[#0c1017]/95 backdrop-blur-md border-b border-[#1c2433] flex items-center justify-between px-4 z-30 select-none shadow-sm">
      {/* Left: Branding & Project Selector */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5 pr-3 border-r border-[#1c2433]">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-sky-500 via-indigo-600 to-purple-600 flex items-center justify-center font-black text-[11px] text-white shadow-md shadow-sky-500/20 ring-1 ring-white/20">
            OM
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-xs tracking-wider uppercase text-slate-100 flex items-center gap-1.5">
              OpenMontage
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-mono font-semibold">
                STUDIO
              </span>
            </span>
          </div>
        </div>

        {/* Project Selector Button */}
        <button
          onClick={onOpenDashboard}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#141b27] hover:bg-[#1a2333] border border-[#222c3d] hover:border-sky-500/50 text-slate-200 transition-all text-xs font-medium group shadow-inner"
          title="Switch or manage projects"
        >
          <FolderOpen size={14} className="text-sky-400 group-hover:scale-110 transition-transform" />
          <span className="max-w-[170px] truncate font-semibold text-slate-100">
            {project?.title || 'Select Project'}
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#1e2738] text-slate-300 font-mono border border-slate-700/60">
            {project?.aspect_ratio || '9:16'}
          </span>
          <ChevronDown size={12} className="text-slate-500 group-hover:text-slate-300" />
        </button>

        {/* Undo / Redo cluster */}
        <div className="flex items-center gap-1 pl-1">
          <button
            onClick={onUndo}
            disabled={!canUndo}
            className="p-1.5 rounded-md hover:bg-[#1a2333] text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
            title="Undo timeline change (Ctrl+Z)"
          >
            <Undo2 size={14} />
          </button>
          <button
            onClick={onRedo}
            disabled={!canRedo}
            className="p-1.5 rounded-md hover:bg-[#1a2333] text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
            title="Redo (Ctrl+Y)"
          >
            <Redo2 size={14} />
          </button>
        </div>
      </div>

      {/* Center: Segmented Workspace Switcher */}
      <div className="flex items-center bg-[#10151f] p-1 rounded-xl border border-[#1e2738] shadow-inner">
        <button
          onClick={() => setActiveTab('edit')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5 ${
            activeTab === 'edit'
              ? 'bg-gradient-to-r from-sky-600 to-blue-600 text-white shadow-md shadow-sky-600/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-[#161c28]'
          }`}
        >
          <Layers size={13} />
          <span>Timeline Editor</span>
        </button>

        <button
          onClick={() => setActiveTab('ai')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5 ${
            activeTab === 'ai'
              ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md shadow-purple-600/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-[#161c28]'
          }`}
        >
          <Sparkles size={13} className={activeTab === 'ai' ? 'text-white' : 'text-amber-400'} />
          <span>AI Director</span>
        </button>

        <button
          onClick={() => setActiveTab('qa')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5 ${
            activeTab === 'qa'
              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md shadow-emerald-600/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-[#161c28]'
          }`}
        >
          <ShieldCheck size={13} className={activeTab === 'qa' ? 'text-white' : (qaPassed ? 'text-emerald-400' : 'text-amber-400')} />
          <span>Quality Gate</span>
          {qaScore !== null && (
            <span
              className={`text-[10px] px-1.5 py-0.2 rounded font-mono font-bold ${
                qaPassed ? 'bg-emerald-950 text-emerald-300 border border-emerald-700/50' : 'bg-amber-950 text-amber-300 border border-amber-700/50'
              }`}
            >
              {qaScore}
            </span>
          )}
        </button>
      </div>

      {/* Right: Hardware Telemetry, Preview & Export */}
      <div className="flex items-center gap-2">
        {/* System metrics pill */}
        {metrics && (
          <div
            className="hidden lg:flex items-center gap-2.5 px-3 py-1 rounded-lg bg-[#10151f] border border-[#1e2738] text-[11px] font-mono text-slate-400 shadow-inner"
            title={`${metrics.hardware_note}\nRAM: ${metrics.ram_used_gb} GB used / ${metrics.ram_total_gb} GB total`}
          >
            <div className="flex items-center gap-1">
              <Cpu size={12} className="text-sky-400" />
              <span>{metrics.cpu_percent.toFixed(0)}%</span>
            </div>
            <span className="text-slate-700">|</span>
            <div className="flex items-center gap-1">
              <Activity size={12} className={metrics.ram_percent > 80 ? 'text-rose-400' : 'text-emerald-400'} />
              <span>{metrics.ram_percent.toFixed(0)}%</span>
            </div>
          </div>
        )}

        {/* Background Jobs & Queue Telemetry */}
        <button
          onClick={onOpenJobs}
          className="px-2.5 py-1.5 rounded-lg border border-sky-900/60 bg-sky-950/20 hover:bg-sky-950/50 text-sky-300 flex items-center gap-1.5 transition text-xs font-medium relative hover:border-sky-500/50"
          title="Open Background Jobs & Queue Manager"
        >
          <Layers size={13} className="text-sky-400" />
          <span>Jobs</span>
          {metrics && (metrics.queued_jobs > 0 || (metrics.interrupted_jobs ?? 0) > 0) && (
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shadow-sm shadow-amber-400" />
          )}
        </button>

        {/* Personalization & Editing Memory */}
        <button
          onClick={onOpenPersonalization}
          className="px-2.5 py-1.5 rounded-lg border border-purple-900/60 bg-purple-950/20 hover:bg-purple-950/50 text-purple-300 flex items-center gap-1.5 transition text-xs font-medium hover:border-purple-500/50"
          title="Editing Memory & Personalization Settings"
        >
          <Brain size={13} className="text-purple-400" />
          <span>Memory</span>
        </button>

        {/* QA quick indicator */}
        <button
          onClick={onOpenQa}
          className={`px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 text-xs font-medium border transition ${
            qaScore !== null && qaPassed
              ? 'border-emerald-700/60 bg-emerald-950/30 text-emerald-300 hover:bg-emerald-950/60 hover:border-emerald-500'
              : qaScore !== null && !qaPassed
              ? 'border-amber-700/60 bg-amber-950/30 text-amber-300 hover:bg-amber-950/60 hover:border-amber-500'
              : 'border-[#1e2738] bg-[#10151f] text-slate-300 hover:border-slate-500 hover:bg-[#161c28]'
          }`}
          title="Open QA Inspection Panel"
        >
          <ShieldCheck size={13} />
          <span>{qaScore !== null ? `QA ${qaScore}` : 'QA'}</span>
        </button>

        {/* Render Preview Draft */}
        <button
          onClick={onRenderPreview}
          className="px-3 py-1.5 rounded-lg border border-[#2a364a] hover:border-sky-500/60 bg-[#141b27] hover:bg-[#1c2536] text-slate-200 flex items-center gap-1.5 transition-all text-xs font-medium group shadow-sm"
          title="Render fast preview draft"
        >
          <Play size={13} className="text-emerald-400 fill-emerald-400/80 group-hover:scale-110 transition-transform" />
          <span>Preview</span>
        </button>

        {/* Final Export */}
        <button
          onClick={onOpenExport}
          className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-sky-500 via-sky-600 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white flex items-center gap-1.5 transition-all text-xs font-semibold shadow-md shadow-sky-600/30 ring-1 ring-white/20 active:scale-95"
          title="Export final MP4 video"
        >
          <Download size={13} />
          <span>Export MP4</span>
        </button>
      </div>
    </header>
  );
};
