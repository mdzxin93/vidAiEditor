import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { DashboardModal } from './components/DashboardModal';
import { MediaBin } from './components/MediaBin';
import { AiPanel } from './components/AiPanel';
import { VideoPlayer } from './components/VideoPlayer';
import { Timeline } from './components/Timeline';
import { Inspector } from './components/Inspector';
import { QaPanel } from './components/QaPanel';
import { RenderModal } from './components/RenderModal';
import { PersonalizationModal } from './components/PersonalizationModal';
import { JobManagerModal } from './components/JobManagerModal';
import {
  ProjectSummary,
  ProjectDetails,
  MediaItem,
  EditDecisions,
  QAReportData,
  SystemMetrics,
} from './types';
import {
  fetchProjects,
  createProject,
  renameProject,
  duplicateProject,
  deleteProject,
  fetchProjectDetails,
  fetchProjectMedia,
  fetchEditDecisions,
  saveEditDecisions,
  fetchMetrics,
  fetchProjectHistory,
  revertToHistorySnapshot,
  fetchQaReport,
} from './api';
import { Film, Sparkles, Sliders, ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  // Navigation & Project selection
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string>('project_demo');
  const [projectDetails, setProjectDetails] = useState<ProjectDetails | null>(null);
  const [isDashboardOpen, setIsDashboardOpen] = useState(false);
  const [isPersonalizationOpen, setIsPersonalizationOpen] = useState(false);
  const [isJobsModalOpen, setIsJobsModalOpen] = useState(false);

  // System telemetry
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);

  // Navigation tab state (Header tabs: 'edit' | 'ai' | 'qa')
  const [headerTab, setHeaderTab] = useState<'edit' | 'ai' | 'qa'>('edit');
  const [leftTab, setLeftTab] = useState<'media' | 'ai'>('media');
  const [rightTab, setRightTab] = useState<'inspector' | 'qa'>('inspector');

  // Media & Video playback state
  const [mediaList, setMediaList] = useState<MediaItem[]>([]);
  const [primaryVideo, setPrimaryVideo] = useState<MediaItem | null>(null);
  const [renderedVideoUrl, setRenderedVideoUrl] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(10);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // Edit Decisions & Multitrack timeline
  const [editDecisions, setEditDecisions] = useState<EditDecisions | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [selectedItemType, setSelectedItemType] = useState<'cut' | 'overlay' | 'caption' | null>(null);
  const [historySnapshots, setHistorySnapshots] = useState<any[]>([]);

  // QA Report state
  const [qaReport, setQaReport] = useState<QAReportData | null>(null);

  // Render & Export Modal
  const [isRenderModalOpen, setIsRenderModalOpen] = useState(false);
  const [renderModalMode, setRenderModalMode] = useState<'preview' | 'final'>('preview');

  // Initial load
  const loadProjects = async () => {
    try {
      const list = await fetchProjects();
      setProjects(list);
      if (list.length > 0 && !currentProjectId) {
        setCurrentProjectId(list[0].project_id);
      }
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  };

  const loadMetrics = async () => {
    try {
      const m = await fetchMetrics();
      setMetrics(m);
    } catch (err) {
      console.error('Failed to load metrics:', err);
    }
  };

  const loadProjectData = useCallback(async (projId: string) => {
    if (!projId) return;
    try {
      const details = await fetchProjectDetails(projId);
      setProjectDetails(details);

      const media = await fetchProjectMedia(projId);
      setMediaList(media);

      // Determine primary video
      const primary = details.primary_video || media.find((m) => m.category === 'video') || null;
      setPrimaryVideo(primary);

      // Check for render exports
      const renderItem = media.find((m) => m.category === 'render');
      if (renderItem) {
        setRenderedVideoUrl(renderItem.media_url);
      } else {
        setRenderedVideoUrl(null);
      }

      // Load edit decisions
      if (details.edit_decisions) {
        setEditDecisions(details.edit_decisions);
      } else {
        try {
          const edits = await fetchEditDecisions(projId);
          setEditDecisions(edits);
        } catch {
          setEditDecisions(null);
        }
      }

      // Load QA report
      if (details.qa_report) {
        setQaReport(details.qa_report);
      } else {
        const qa = await fetchQaReport(projId);
        setQaReport(qa);
      }

      // Load history snapshots
      const hist = await fetchProjectHistory(projId);
      setHistorySnapshots(hist);
    } catch (err) {
      console.error('Failed to load project details:', err);
    }
  }, []);

  useEffect(() => {
    loadProjects();
    loadMetrics();
    const interval = setInterval(loadMetrics, 4000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (currentProjectId) {
      loadProjectData(currentProjectId);
    }
  }, [currentProjectId, loadProjectData]);

  // Update edit decisions and persist to Python disk
  const handleUpdateDecisions = async (updated: EditDecisions, commitMsg: string = 'Timeline edit') => {
    setEditDecisions(updated);
    try {
      await saveEditDecisions(currentProjectId, updated, commitMsg);
      const hist = await fetchProjectHistory(currentProjectId);
      setHistorySnapshots(hist);
    } catch (err) {
      console.error('Failed to save edit decisions:', err);
    }
  };

  // Undo (Revert to previous snapshot)
  const handleUndo = async () => {
    if (historySnapshots.length <= 1) return;
    try {
      const targetSnapshot = historySnapshots[1];
      const reverted = await revertToHistorySnapshot(currentProjectId, targetSnapshot.snapshot_id);
      setEditDecisions(reverted);
      const hist = await fetchProjectHistory(currentProjectId);
      setHistorySnapshots(hist);
    } catch (err) {
      console.error('Undo failed:', err);
    }
  };

  // Dashboard modal handlers
  const handleCreateProject = async (id: string, title: string, aspect: string) => {
    await createProject({ project_id: id, title, aspect_ratio: aspect });
    await loadProjects();
    setCurrentProjectId(id);
  };

  const handleRenameProject = async (id: string, newTitle: string) => {
    await renameProject(id, newTitle);
    await loadProjects();
    if (currentProjectId === id) {
      loadProjectData(id);
    }
  };

  const handleDuplicateProject = async (id: string, newId: string, newTitle: string) => {
    await duplicateProject(id, newId, newTitle);
    await loadProjects();
    setCurrentProjectId(newId);
  };

  const handleDeleteProject = async (id: string) => {
    await deleteProject(id);
    const updated = await fetchProjects();
    setProjects(updated);
    if (currentProjectId === id && updated.length > 0) {
      setCurrentProjectId(updated[0].project_id);
    }
  };

  // Header tab sync
  const handleSetActiveTab = (tab: 'edit' | 'ai' | 'qa') => {
    setHeaderTab(tab);
    if (tab === 'ai') {
      setLeftTab('ai');
    } else if (tab === 'qa') {
      setRightTab('qa');
    } else {
      setLeftTab('media');
      setRightTab('inspector');
    }
  };

  // Global Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName)) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((p) => !p);
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        const step = e.shiftKey ? 1.0 : 1 / 30;
        setCurrentTime((t) => Math.max(0, t - step));
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        const step = e.shiftKey ? 1.0 : 1 / 30;
        setCurrentTime((t) => Math.min(duration, t + step));
      } else if ((e.key === 'z' || e.key === 'Z') && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleUndo();
      } else if (e.key === 'Escape') {
        setSelectedItemId(null);
        setSelectedItemType(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [duration, historySnapshots]);

  return (
    <div className="flex flex-col h-screen w-screen bg-[#090b10] text-slate-100 overflow-hidden font-sans select-none">
      {/* Top Application Header */}
      <Header
        project={projectDetails}
        metrics={metrics}
        onOpenDashboard={() => setIsDashboardOpen(true)}
        onOpenPersonalization={() => setIsPersonalizationOpen(true)}
        onOpenJobs={() => setIsJobsModalOpen(true)}
        canUndo={historySnapshots.length > 1}
        canRedo={false}
        onUndo={handleUndo}
        onRedo={() => {}}
        onRenderPreview={() => {
          setRenderModalMode('preview');
          setIsRenderModalOpen(true);
        }}
        onOpenExport={() => {
          setRenderModalMode('final');
          setIsRenderModalOpen(true);
        }}
        onOpenQa={() => {
          setRightTab('qa');
          setHeaderTab('qa');
        }}
        qaScore={qaReport?.quality_score ?? null}
        qaPassed={qaReport?.passed ?? null}
        activeTab={headerTab}
        setActiveTab={handleSetActiveTab}
      />

      {/* Main Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT DOCK (Media Bin & AI Director) */}
        <div className="w-[330px] flex flex-col shrink-0 bg-[#0d1117] border-r border-[#1c2433]">
          <div className="h-10 px-3 bg-[#0f141d] border-b border-[#1c2433] flex items-center gap-1.5">
            <button
              onClick={() => setLeftTab('media')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                leftTab === 'media'
                  ? 'bg-[#182232] text-sky-400 border border-sky-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#141a24]'
              }`}
            >
              <Film className="w-3.5 h-3.5" />
              <span>Media ({mediaList.length})</span>
            </button>

            <button
              onClick={() => setLeftTab('ai')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                leftTab === 'ai'
                  ? 'bg-[#182232] text-purple-400 border border-purple-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#141a24]'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>AI Director</span>
            </button>
          </div>

          <div className="flex-1 overflow-hidden">
            {leftTab === 'media' ? (
              <MediaBin
                projectId={currentProjectId}
                mediaList={mediaList}
                primaryVideo={primaryVideo}
                onRefreshMedia={() => loadProjectData(currentProjectId)}
                onSelectPrimary={(item) => setPrimaryVideo(item)}
                onPreviewMedia={(item) => {
                  if (item.category === 'render') {
                    setRenderedVideoUrl(item.media_url);
                  } else {
                    setPrimaryVideo(item);
                  }
                }}
              />
            ) : (
              <AiPanel
                projectId={currentProjectId}
                primaryVideo={primaryVideo}
                mediaList={mediaList}
                currentAspectRatio={projectDetails?.aspect_ratio || '9:16'}
                hasEditDecisions={!!editDecisions}
                onAnalysisStarted={() => loadProjectData(currentProjectId)}
                onEditGenerationStarted={() => loadProjectData(currentProjectId)}
              />
            )}
          </div>
        </div>

        {/* CENTER VIEWPORT (Video Player + Multitrack Timeline) */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#07090e]">
          {/* Top Video Preview Player */}
          <div className="flex-1 min-h-[300px]">
            <VideoPlayer
              primaryVideo={primaryVideo}
              renderedVideoUrl={renderedVideoUrl}
              currentTime={currentTime}
              duration={duration}
              isPlaying={isPlaying}
              onTimeUpdate={(t) => setCurrentTime(t)}
              onDurationChange={(d) => setDuration(d)}
              onTogglePlay={() => setIsPlaying((p) => !p)}
              editDecisions={editDecisions}
            />
          </div>

          {/* Bottom Multitrack Timeline */}
          <div className="h-72 shrink-0 border-t border-[#1c2433]">
            <Timeline
              editDecisions={editDecisions}
              currentTime={currentTime}
              duration={duration}
              onTimeSeek={(t) => setCurrentTime(t)}
              selectedItemId={selectedItemId}
              selectedItemType={selectedItemType}
              onSelectItem={(id, type) => {
                setSelectedItemId(id);
                setSelectedItemType(type);
                if (type) setRightTab('inspector');
              }}
              onUpdateDecisions={handleUpdateDecisions}
              qaIssues={qaReport?.issues || []}
              projectId={currentProjectId}
            />
          </div>
        </div>

        {/* RIGHT DOCK (Properties Inspector & QA Quality Gate) */}
        <div className="w-[330px] flex flex-col shrink-0 bg-[#0d1117] border-l border-[#1c2433]">
          <div className="h-10 px-3 bg-[#0f141d] border-b border-[#1c2433] flex items-center gap-1.5">
            <button
              onClick={() => setRightTab('inspector')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                rightTab === 'inspector'
                  ? 'bg-[#182232] text-sky-400 border border-sky-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#141a24]'
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Inspector</span>
            </button>

            <button
              onClick={() => setRightTab('qa')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                rightTab === 'qa'
                  ? 'bg-[#182232] text-emerald-400 border border-emerald-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#141a24]'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>QA Gate {qaReport ? `(${qaReport.quality_score})` : ''}</span>
            </button>
          </div>

          <div className="flex-1 overflow-hidden">
            {rightTab === 'inspector' ? (
              <Inspector
                editDecisions={editDecisions}
                selectedItemId={selectedItemId}
                selectedItemType={selectedItemType}
                onUpdateDecisions={handleUpdateDecisions}
                onDeselect={() => {
                  setSelectedItemId(null);
                  setSelectedItemType(null);
                }}
              />
            ) : (
              <QaPanel
                projectId={currentProjectId}
                qaReport={qaReport}
                onRefreshQa={(rep) => setQaReport(rep)}
                onJumpToTime={(t) => setCurrentTime(t)}
                onApplyFixes={(updated) => handleUpdateDecisions(updated, 'Apply QA Auto-Fixes')}
              />
            )}
          </div>
        </div>
      </div>

      {/* DASHBOARD MODAL */}
      <DashboardModal
        isOpen={isDashboardOpen}
        onClose={() => setIsDashboardOpen(false)}
        projects={projects}
        currentProjectId={currentProjectId}
        onSelectProject={(id: string) => {
          setCurrentProjectId(id);
          setIsDashboardOpen(false);
        }}
        onCreateProject={handleCreateProject}
        onRenameProject={handleRenameProject}
        onDuplicateProject={handleDuplicateProject}
        onDeleteProject={handleDeleteProject}
      />

      {/* RENDER & EXPORT MODAL */}
      <RenderModal
        projectId={currentProjectId}
        isOpen={isRenderModalOpen}
        onClose={() => setIsRenderModalOpen(false)}
        defaultMode={renderModalMode}
        projectAspectRatio={projectDetails?.aspect_ratio || '9:16'}
        onRenderComplete={(videoUrl) => {
          setRenderedVideoUrl(videoUrl);
          loadProjectData(currentProjectId);
        }}
      />

      {/* PERSONALIZATION & EDITING MEMORY MODAL */}
      <PersonalizationModal
        isOpen={isPersonalizationOpen}
        onClose={() => setIsPersonalizationOpen(false)}
        currentProjectId={currentProjectId}
        onPreferencesUpdated={() => {
          loadProjectData(currentProjectId);
        }}
      />

      {/* PERSISTENT JOB MANAGER MODAL */}
      <JobManagerModal
        isOpen={isJobsModalOpen}
        onClose={() => setIsJobsModalOpen(false)}
        currentProjectId={currentProjectId}
      />
    </div>
  );
};
