import React, { useState, useEffect } from 'react';
import {
  X,
  RotateCcw,
  Ban,
  Terminal,
  Activity,
  HardDrive,
  Cpu,
  Trash2,
  AlertTriangle,
  CheckCircle,
  Clock,
  Layers,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Sparkles
} from 'lucide-react';
import { JobRecord, SystemMetrics } from '../types';
import {
  fetchJobs,
  fetchMetrics,
  cancelJob,
  retryJob,
  recoverJob,
  deleteJob,
  clearCompletedJobs,
  fetchCacheStats,
  clearCache,
} from '../api';

interface JobManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentProjectId?: string;
}

export const JobManagerModal: React.FC<JobManagerModalProps> = ({
  isOpen,
  onClose,
  currentProjectId: _currentProjectId,
}) => {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [cacheStats, setCacheStats] = useState<any>(null);
  const [filter, setFilter] = useState<'all' | 'active' | 'completed' | 'issues'>('all');
  const [expandedLogs, setExpandedLogs] = useState<Record<string, boolean>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [jobsData, metricsData, cacheData] = await Promise.all([
        fetchJobs(),
        fetchMetrics().catch(() => null),
        fetchCacheStats().catch(() => null),
      ]);
      setJobs(jobsData);
      setMetrics(metricsData);
      setCacheStats(cacheData);
    } catch (err) {
      console.error('Failed to load job manager data:', err);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    loadData();
    const interval = setInterval(loadData, 2000);
    return () => clearInterval(interval);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCancel = async (jobId: string) => {
    setActionLoading(jobId);
    try {
      await cancelJob(jobId);
      await loadData();
    } catch (err: any) {
      alert(`Cancel failed: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetry = async (jobId: string) => {
    setActionLoading(jobId);
    try {
      await retryJob(jobId);
      await loadData();
    } catch (err: any) {
      alert(`Retry failed: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRecover = async (jobId: string) => {
    setActionLoading(jobId);
    try {
      await recoverJob(jobId);
      await loadData();
    } catch (err: any) {
      alert(`Recovery failed: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    setActionLoading(jobId);
    try {
      await deleteJob(jobId);
      await loadData();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleClearCompleted = async () => {
    setIsLoading(true);
    try {
      await clearCompletedJobs();
      await loadData();
    } catch (err: any) {
      alert(`Failed to clear finished jobs: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearCache = async () => {
    if (!confirm('Safely clear deterministic analysis and preview caches? Source footage and exports will never be touched.')) {
      return;
    }
    setIsLoading(true);
    try {
      await clearCache('all');
      await loadData();
    } catch (err: any) {
      alert(`Cache eviction failed: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleLogs = (jobId: string) => {
    setExpandedLogs((prev) => ({ ...prev, [jobId]: !prev[jobId] }));
  };

  const filteredJobs = jobs.filter((j) => {
    if (filter === 'active') {
      return ['queued', 'running', 'analyzing', 'planning', 'rendering', 'quality_check'].includes(j.status);
    }
    if (filter === 'completed') {
      return j.status === 'completed';
    }
    if (filter === 'issues') {
      return ['failed', 'cancelled', 'interrupted', 'recoverable'].includes(j.status);
    }
    return true;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> Completed
          </span>
        );
      case 'failed':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-500/15 text-rose-400 border border-rose-500/30 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Failed
          </span>
        );
      case 'cancelled':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-slate-500/15 text-slate-400 border border-slate-500/30 flex items-center gap-1">
            <Ban className="w-3 h-3" /> Cancelled
          </span>
        );
      case 'interrupted':
      case 'recoverable':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-400 border border-amber-500/30 animate-pulse flex items-center gap-1">
            <RotateCcw className="w-3 h-3" /> Recoverable
          </span>
        );
      case 'queued':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1">
            <Clock className="w-3 h-3" /> Queued
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-sky-500/15 text-sky-400 border border-sky-500/30 animate-pulse flex items-center gap-1">
            <Activity className="w-3 h-3 animate-spin" /> {status}
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-[#0b0e14] border border-[#1b2333] rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Top Header */}
        <div className="px-6 py-4 border-b border-[#1b2333] flex items-center justify-between bg-[#0e121a]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-tr from-sky-500/20 to-cyan-500/10 border border-sky-500/30 text-sky-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Persistent Background Jobs
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-normal">
                  SQLite WAL Store
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Crash-recoverable task execution & Intel CPU bounded-resource scheduler
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              className="p-1.5 rounded-lg bg-[#161c26] text-slate-400 hover:text-white border border-[#222a38] transition-colors"
              title="Refresh telemetry"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg bg-[#161c26] text-slate-400 hover:text-white border border-[#222a38] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Live System Resource Telemetry Bar */}
        {metrics && (
          <div className="px-6 py-2.5 bg-[#0d1117] border-b border-[#1b2333] grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="flex items-center gap-2 text-slate-300">
              <Cpu className="w-4 h-4 text-sky-400" />
              <div>
                <span className="text-[10px] text-slate-500 uppercase block font-mono">CPU Load</span>
                <span className="font-semibold font-mono text-slate-200">{metrics.cpu_percent}%</span>
              </div>
            </div>

            <div className="flex items-center gap-2 text-slate-300">
              <HardDrive className="w-4 h-4 text-emerald-400" />
              <div>
                <span className="text-[10px] text-slate-500 uppercase block font-mono">Available RAM</span>
                <span className="font-semibold font-mono text-slate-200">
                  {metrics.ram_available_gb} GB / {metrics.ram_total_gb} GB
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 text-slate-300">
              <Activity className="w-4 h-4 text-cyan-400" />
              <div>
                <span className="text-[10px] text-slate-500 uppercase block font-mono">Active Renders</span>
                <span className="font-semibold font-mono text-slate-200">{metrics.active_renders} active (max 1)</span>
              </div>
            </div>

            <div className="flex items-center gap-2 text-slate-300">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <div>
                <span className="text-[10px] text-slate-500 uppercase block font-mono">Cache Stored</span>
                <span className="font-semibold font-mono text-slate-200">
                  {cacheStats?.total_mb ?? 0} MB
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Filter Controls & Global Actions */}
        <div className="px-6 py-3 border-b border-[#1b2333] flex flex-wrap items-center justify-between gap-3 bg-[#0a0d13]">
          <div className="flex items-center gap-1.5 p-1 bg-[#121722] rounded-xl border border-[#1e2638]">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                filter === 'all'
                  ? 'bg-sky-500 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All Jobs ({jobs.length})
            </button>
            <button
              onClick={() => setFilter('active')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                filter === 'active'
                  ? 'bg-sky-500 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Active ({jobs.filter((j) => ['queued', 'running', 'analyzing', 'planning', 'rendering', 'quality_check'].includes(j.status)).length})
            </button>
            <button
              onClick={() => setFilter('completed')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                filter === 'completed'
                  ? 'bg-sky-500 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Completed ({jobs.filter((j) => j.status === 'completed').length})
            </button>
            <button
              onClick={() => setFilter('issues')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                filter === 'issues'
                  ? 'bg-sky-500 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Interrupted / Failed ({jobs.filter((j) => ['failed', 'cancelled', 'interrupted', 'recoverable'].includes(j.status)).length})
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleClearCache}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-[#161c26] hover:bg-[#1e2638] border border-[#222a38] transition-colors"
              title="Safely evict deterministic cache"
            >
              <HardDrive className="w-3.5 h-3.5 text-amber-400" />
              <span>Purge Cache</span>
            </button>
            <button
              onClick={handleClearCompleted}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-[#161c26] hover:bg-[#1e2638] border border-[#222a38] transition-colors disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5 text-slate-400" />
              <span>Clear Finished</span>
            </button>
          </div>
        </div>

        {/* Jobs List Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {filteredJobs.length === 0 ? (
            <div className="py-16 text-center text-slate-500 space-y-2">
              <Layers className="w-8 h-8 mx-auto stroke-1 opacity-50" />
              <p className="text-sm">No jobs matching current filter.</p>
            </div>
          ) : (
            filteredJobs.map((job) => {
              const isLive = ['queued', 'running', 'analyzing', 'planning', 'rendering', 'quality_check'].includes(job.status);
              const isInterrupted = ['interrupted', 'recoverable', 'failed'].includes(job.status);
              const isLogsOpen = !!expandedLogs[job.job_id];

              return (
                <div
                  key={job.job_id}
                  className="bg-[#10141f] border border-[#1c2436] hover:border-[#2a3752] rounded-xl p-4 transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white font-mono">{job.job_type}</span>
                        {getStatusBadge(job.status)}
                        <span className="text-[10px] font-mono text-slate-500 bg-[#161c28] px-1.5 py-0.5 rounded">
                          {job.job_id}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400 flex items-center gap-3">
                        <span>Project: <strong className="text-slate-300">{job.project_id}</strong></span>
                        <span>•</span>
                        <span>Stage: <span className="text-sky-300">{job.stage}</span></span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {isLive && (
                        <button
                          onClick={() => handleCancel(job.job_id)}
                          disabled={actionLoading === job.job_id}
                          className="px-2.5 py-1 bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
                        >
                          <Ban className="w-3 h-3" />
                          <span>Cancel</span>
                        </button>
                      )}

                      {['interrupted', 'recoverable'].includes(job.status) && job.recoverable !== false && (
                        <button
                          onClick={() => handleRecover(job.job_id)}
                          disabled={actionLoading === job.job_id}
                          className="px-2.5 py-1 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Recover Job</span>
                        </button>
                      )}

                      {job.status === 'failed' && (
                        <button
                          onClick={() => handleRetry(job.job_id)}
                          disabled={actionLoading === job.job_id}
                          className="px-2.5 py-1 bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 text-sky-300 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
                        >
                          <RefreshCw className="w-3 h-3" />
                          <span>Retry</span>
                        </button>
                      )}

                      <button
                        onClick={() => toggleLogs(job.job_id)}
                        className="px-2.5 py-1 bg-[#161c28] hover:bg-[#1e2638] border border-[#253046] text-slate-300 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
                      >
                        <Terminal className="w-3 h-3 text-slate-400" />
                        <span>Logs</span>
                        {isLogsOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>

                      {!isLive && (
                        <button
                          onClick={() => handleDeleteJob(job.job_id)}
                          disabled={actionLoading === job.job_id}
                          className="p-1.5 hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 rounded-lg transition-colors border border-transparent hover:border-rose-500/30"
                          title="Delete / Dismiss job record"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-[11px] font-mono text-slate-400">
                      <span>{job.stage}</span>
                      <span className="font-bold text-slate-200">{Math.round(job.progress)}%</span>
                    </div>
                    <div className="h-2 bg-[#171d2b] rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          job.status === 'completed'
                            ? 'bg-emerald-500'
                            : job.status === 'failed'
                            ? 'bg-rose-500'
                            : isInterrupted
                            ? 'bg-amber-500'
                            : 'bg-gradient-to-r from-sky-500 to-cyan-400'
                        }`}
                        style={{ width: `${Math.max(4, job.progress)}%` }}
                      />
                    </div>
                  </div>

                  {/* Error Callout */}
                  {job.error && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
                      <div className="font-mono text-[11px] overflow-x-auto">{job.error}</div>
                    </div>
                  )}

                  {/* Expandable Logs Terminal */}
                  {isLogsOpen && (
                    <div className="p-3 bg-[#080a0f] border border-[#1b2333] rounded-lg text-[11px] font-mono text-slate-300 max-h-48 overflow-y-auto space-y-1">
                      <div className="text-slate-500 border-b border-[#1b2333] pb-1 mb-1.5 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Terminal className="w-3.5 h-3.5" /> Execution Telemetry Log
                        </span>
                        <span>{job.logs?.length || 0} entries</span>
                      </div>
                      {job.logs && job.logs.length > 0 ? (
                        job.logs.map((log, idx) => (
                          <div key={idx} className="leading-relaxed hover:text-white">
                            {log}
                          </div>
                        ))
                      ) : (
                        <div className="text-slate-600 italic">No execution logs recorded yet.</div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
