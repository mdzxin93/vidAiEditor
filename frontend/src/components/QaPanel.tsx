import React, { useState } from 'react';
import {
  CheckCircle,
  XCircle,
  Wrench,
  Search,
  Clock,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  History
} from 'lucide-react';
import { QAReportData, EditDecisions } from '../types';
import { runQaInspection, applyQaFixes } from '../api';

interface QaPanelProps {
  projectId: string;
  qaReport: QAReportData | null;
  onRefreshQa: (report: QAReportData) => void;
  onJumpToTime: (seconds: number) => void;
  onApplyFixes: (updatedDecisions: EditDecisions) => void;
}

export const QaPanel: React.FC<QaPanelProps> = ({
  projectId,
  qaReport,
  onRefreshQa,
  onJumpToTime,
  onApplyFixes,
}) => {
  const [isRunningInspect, setIsRunningInspect] = useState(false);
  const [isApplyingFixes, setIsApplyingFixes] = useState(false);

  const handleRunInspect = async () => {
    setIsRunningInspect(true);
    try {
      const report = await runQaInspection(projectId);
      onRefreshQa(report);
    } catch (err: any) {
      alert(`QA Inspection failed: ${err.message}`);
    } finally {
      setIsRunningInspect(false);
    }
  };

  const handleApplyFixes = async () => {
    setIsApplyingFixes(true);
    try {
      const res = await applyQaFixes(projectId);
      if (res.edit_decisions) {
        onApplyFixes(res.edit_decisions);
      }
      // Re-run inspection to see new score
      const updatedReport = await runQaInspection(projectId);
      onRefreshQa(updatedReport);
      alert(`Successfully applied ${res.fixes_applied_count} automated QA fixes!`);
    } catch (err: any) {
      alert(`Applying fixes failed: ${err.message}`);
    } finally {
      setIsApplyingFixes(false);
    }
  };

  const getScoreColor = (score: number, passed: boolean) => {
    if (passed) return 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10';
    if (score >= 80) return 'text-amber-400 border-amber-500/40 bg-amber-500/10';
    return 'text-rose-400 border-rose-500/40 bg-rose-500/10';
  };

  return (
    <div className="flex flex-col h-full bg-[#12161f] border-l border-[#262c38]">
      {/* QA Header */}
      <div className="p-3 border-b border-[#262c38] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Quality Assurance (QA)
          </h2>
        </div>
        <button
          onClick={handleRunInspect}
          disabled={isRunningInspect}
          className="flex items-center gap-1.5 px-2 py-1 bg-[#1a2333] hover:bg-[#232e42] border border-[#2d3a52] text-sky-400 text-[11px] font-medium rounded transition-colors disabled:opacity-50"
        >
          <Search className="w-3 h-3" />
          <span>{isRunningInspect ? 'Inspecting...' : 'Run QA Check'}</span>
        </button>
      </div>

      {/* QA Body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3.5">
        {qaReport ? (
          <>
            {/* QA Score Card with Dual-Gate Explanation */}
            <div className={`p-3 rounded-lg border flex flex-col gap-2 ${getScoreColor(qaReport.quality_score, qaReport.passed)}`}>
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-mono tracking-wider opacity-80">
                    Autonomous QA Score
                  </span>
                  <div className="text-2xl font-black font-mono">
                    {qaReport.quality_score} <span className="text-sm font-normal opacity-70">/ 100</span>
                  </div>
                </div>

                <div className="text-right">
                  {qaReport.passed ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      <CheckCircle className="w-3.5 h-3.5" /> PASSED
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider bg-rose-500/20 text-rose-300 border border-rose-500/30">
                      <XCircle className="w-3.5 h-3.5" /> REJECTED
                    </span>
                  )}
                </div>
              </div>

              {/* Dual Gate explanation */}
              <p className="text-[11px] opacity-90 leading-relaxed border-t border-current/20 pt-1.5">
                {qaReport.summary}
              </p>
            </div>

            {/* Severity Counters */}
            <div className="grid grid-cols-4 gap-1.5 text-center">
              <div className="bg-[#161c26] border border-[#262f3f] p-1.5 rounded">
                <span className="text-[10px] text-rose-400 uppercase font-mono block">Critical</span>
                <span className="text-sm font-bold text-rose-300 font-mono">
                  {qaReport.severity_counts?.critical || 0}
                </span>
              </div>
              <div className="bg-[#161c26] border border-[#262f3f] p-1.5 rounded">
                <span className="text-[10px] text-amber-400 uppercase font-mono block">High</span>
                <span className="text-sm font-bold text-amber-300 font-mono">
                  {qaReport.severity_counts?.high || 0}
                </span>
              </div>
              <div className="bg-[#161c26] border border-[#262f3f] p-1.5 rounded">
                <span className="text-[10px] text-yellow-400 uppercase font-mono block">Medium</span>
                <span className="text-sm font-bold text-yellow-300 font-mono">
                  {qaReport.severity_counts?.medium || 0}
                </span>
              </div>
              <div className="bg-[#161c26] border border-[#262f3f] p-1.5 rounded">
                <span className="text-[10px] text-sky-400 uppercase font-mono block">Low</span>
                <span className="text-sm font-bold text-sky-300 font-mono">
                  {qaReport.severity_counts?.low || 0}
                </span>
              </div>
            </div>

            {/* Auto Fix Button */}
            {qaReport.issues?.some((i) => i.auto_fix_allowed) && (
              <button
                onClick={handleApplyFixes}
                disabled={isApplyingFixes}
                className="w-full flex items-center justify-center gap-2 bg-[#0284c7] hover:bg-[#0369a1] text-white text-xs font-bold py-2 rounded shadow transition-colors disabled:opacity-50"
              >
                <Wrench className="w-3.5 h-3.5" />
                <span>{isApplyingFixes ? 'Applying Fixes...' : 'Auto-Fix Detected Issues'}</span>
              </button>
            )}

            {/* Issues List */}
            <div className="space-y-2 pt-1 border-t border-[#1f2736]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                  Detected Quality Anomalies ({qaReport.issues?.length || 0})
                </span>
              </div>

              {qaReport.issues?.length === 0 ? (
                <div className="p-3 text-center bg-[#151d28] rounded border border-emerald-500/20 text-emerald-400 text-xs flex items-center justify-center gap-1.5">
                  <CheckCircle className="w-4 h-4" />
                  <span>No defects detected. Clean export!</span>
                </div>
              ) : (
                qaReport.issues.map((issue) => {
                  const isCrit = issue.severity === 'critical' || issue.severity === 'high';

                  return (
                    <div
                      key={issue.issue_id}
                      className="bg-[#161c26] border border-[#262f3f] rounded p-2.5 space-y-1.5 hover:border-[#38bdf8]/40 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <span
                          className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded font-bold ${
                            isCrit
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                              : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          }`}
                        >
                          {issue.severity} • {issue.category}
                        </span>

                        <button
                          onClick={() => onJumpToTime(issue.start_seconds)}
                          className="flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300 font-mono"
                          title="Jump to timeline timestamp"
                        >
                          <Clock className="w-3 h-3" />
                          <span>{issue.start_seconds.toFixed(2)}s</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      </div>

                      <p className="text-xs text-slate-200 font-medium leading-snug">
                        {issue.description}
                      </p>

                      <div className="text-[11px] text-slate-400 bg-[#12161f] p-1.5 rounded border border-[#1e2536] flex items-start gap-1.5">
                        <Sparkles className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />
                        <span>Fix: {issue.suggested_fix}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Revision / Fixes History */}
            {qaReport.fixes_applied?.length > 0 && (
              <div className="pt-2 border-t border-[#1f2736]">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5 flex items-center gap-1">
                  <History className="w-3.5 h-3.5" /> Applied Corrections History
                </span>
                <div className="space-y-1 text-[11px] text-slate-400 bg-[#141924] p-2 rounded border border-[#222a38]">
                  {qaReport.fixes_applied.map((fix, idx) => (
                    <div key={idx} className="flex items-center gap-1.5 text-emerald-300">
                      <CheckCircle className="w-3 h-3 shrink-0" />
                      <span>{typeof fix === 'string' ? fix : JSON.stringify(fix)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="text-center p-6 text-slate-500">
            <ShieldAlert className="w-8 h-8 mx-auto mb-2 text-slate-600" />
            <p className="text-xs font-medium">No QA report generated yet</p>
            <p className="text-[11px] text-slate-600 mt-1">
              Click "Run QA Check" to scan timeline for overlay collisions, framing issues, or audio clipping.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
