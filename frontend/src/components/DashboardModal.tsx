import React, { useState } from 'react';
import {
  X,
  Plus,
  Copy,
  Edit2,
  Trash2,
  Check,
  Video,
  Clock,
  Sparkles,
} from 'lucide-react';
import { ProjectSummary } from '../types';

interface DashboardModalProps {
  isOpen: boolean;
  onClose: () => void;
  projects: ProjectSummary[];
  currentProjectId: string | null;
  onSelectProject: (projectId: string) => void;
  onCreateProject: (id: string, title: string, aspect: string) => Promise<void>;
  onRenameProject: (id: string, newTitle: string) => Promise<void>;
  onDuplicateProject: (id: string, newId: string, newTitle: string) => Promise<void>;
  onDeleteProject: (id: string) => Promise<void>;
}

export const DashboardModal: React.FC<DashboardModalProps> = ({
  isOpen,
  onClose,
  projects,
  currentProjectId,
  onSelectProject,
  onCreateProject,
  onRenameProject,
  onDuplicateProject,
  onDeleteProject,
}) => {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newId, setNewId] = useState('');
  const [newAspect, setNewAspect] = useState('9:16');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [renamingTitle, setRenamingTitle] = useState('');

  const [deletingId, setDeletingId] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleTitleChange = (val: string) => {
    setNewTitle(val);
    // Auto-generate kebab ID
    if (!newId || newId === slugify(newTitle)) {
      setNewId(slugify(val));
    }
  };

  const slugify = (text: string) =>
    text
      .toLowerCase()
      .trim()
      .replace(/[^\w\s-]/g, '')
      .replace(/[\s_-]+/g, '-')
      .replace(/^-+|-+$/g, '');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!newTitle.trim()) {
      setErrorMsg('Please enter a project title');
      return;
    }
    const safeId = newId.trim() || slugify(newTitle);
    try {
      await onCreateProject(safeId, newTitle.trim(), newAspect);
      setShowCreateForm(false);
      setNewTitle('');
      setNewId('');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create project');
    }
  };

  const startRename = (p: ProjectSummary) => {
    setEditingId(p.project_id);
    setRenamingTitle(p.title);
  };

  const submitRename = async (id: string) => {
    if (!renamingTitle.trim()) return;
    try {
      await onRenameProject(id, renamingTitle.trim());
      setEditingId(null);
    } catch (err: any) {
      alert(err.message || 'Failed to rename project');
    }
  };

  const handleDuplicate = async (p: ProjectSummary) => {
    const dupId = `${p.project_id}-copy-${Date.now().toString().slice(-4)}`;
    const dupTitle = `${p.title} (Copy)`;
    try {
      await onDuplicateProject(p.project_id, dupId, dupTitle);
    } catch (err: any) {
      alert(err.message || 'Failed to duplicate project');
    }
  };

  const confirmDelete = async (id: string) => {
    try {
      await onDeleteProject(id);
      setDeletingId(null);
    } catch (err: any) {
      alert(err.message || 'Failed to delete project');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-panel border border-subtle rounded-lg max-w-4xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="panel-header px-4 py-3 flex items-center justify-between border-b border-subtle">
          <div className="flex items-center gap-2">
            <Video size={16} className="text-blue-500" />
            <span className="text-sm font-bold text-slate-100">Project Workspace Dashboard</span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1">
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 flex-1 overflow-y-auto">
          {/* Top toolbar */}
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-bold text-slate-100">Your Video Projects</h2>
              <p className="text-xs text-slate-400">
                Create new video productions or load existing saved editing timelines.
              </p>
            </div>
            {!showCreateForm && (
              <button
                onClick={() => setShowCreateForm(true)}
                className="btn btn-primary flex items-center gap-1.5 shadow"
              >
                <Plus size={14} />
                <span>New Project</span>
              </button>
            )}
          </div>

          {/* New Project Form */}
          {showCreateForm && (
            <form
              onSubmit={handleCreate}
              className="bg-surface p-4 rounded-lg border border-blue-500/30 mb-6 shadow-lg animate-fadeIn"
            >
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-1.5">
                <Sparkles size={14} className="text-blue-400" />
                Initialize New Editing Project
              </h3>
              {errorMsg && (
                <div className="p-2 mb-3 bg-rose-950 border border-rose-800 rounded text-rose-300 text-xs">
                  {errorMsg}
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Project Title</label>
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => handleTitleChange(e.target.value)}
                    placeholder="e.g. 90-Minute Focus Reel"
                    className="input-field"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Project ID (kebab-case)</label>
                  <input
                    type="text"
                    value={newId}
                    onChange={(e) => setNewId(e.target.value)}
                    placeholder="90-min-focus-reel"
                    className="input-field font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Aspect Ratio</label>
                  <select
                    value={newAspect}
                    onChange={(e) => setNewAspect(e.target.value)}
                    className="select-field"
                  >
                    <option value="9:16">9:16 Vertical (Reel / TikTok)</option>
                    <option value="16:9">16:9 Landscape (YouTube)</option>
                    <option value="1:1">1:1 Square (Instagram Feed)</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="btn btn-sm"
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-sm btn-primary">
                  Create & Launch Studio
                </button>
              </div>
            </form>
          )}

          {/* Project Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {projects.map((p) => {
              const isSelected = p.project_id === currentProjectId;
              return (
                <div
                  key={p.project_id}
                  className={`bg-surface border rounded-lg p-3 flex flex-col justify-between transition hover:border-slate-500 shadow ${
                    isSelected ? 'border-blue-500 ring-1 ring-blue-500/50 bg-blue-950/20' : 'border-subtle'
                  }`}
                >
                  <div>
                    {/* Card Top: Poster / Thumbnail preview */}
                    <div className="w-full h-28 bg-dark rounded border border-subtle mb-2.5 overflow-hidden relative flex items-center justify-center">
                      {p.poster ? (
                        <img
                          src={`/thumb/${p.project_id}/${p.poster}`}
                          alt={p.title}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        <div className="text-slate-600 flex flex-col items-center gap-1">
                          <Video size={24} />
                          <span className="text-[10px] font-mono">No Preview</span>
                        </div>
                      )}
                      {/* Status Badges */}
                      <div className="absolute top-1.5 left-1.5 flex items-center gap-1">
                        <span className="badge bg-black/70 text-slate-300 border border-slate-700 backdrop-blur-xs">
                          {p.pipeline_type}
                        </span>
                      </div>
                      {p.qa_score !== null && (
                        <div className="absolute top-1.5 right-1.5">
                          <span
                            className={`badge ${
                              p.qa_passed
                                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700'
                                : 'bg-amber-950/80 text-amber-300 border border-amber-700'
                            }`}
                          >
                            QA {p.qa_score}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Title or Inline Edit */}
                    {editingId === p.project_id ? (
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <input
                          type="text"
                          value={renamingTitle}
                          onChange={(e) => setRenamingTitle(e.target.value)}
                          className="input-field text-xs py-1"
                          autoFocus
                        />
                        <button
                          onClick={() => submitRename(p.project_id)}
                          className="btn btn-sm btn-icon btn-primary"
                        >
                          <Check size={12} />
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="btn btn-sm btn-icon"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between gap-1 mb-1">
                        <h4
                          onClick={() => onSelectProject(p.project_id)}
                          className="font-bold text-sm text-slate-100 hover:text-blue-400 cursor-pointer truncate"
                          title={p.title}
                        >
                          {p.title}
                        </h4>
                      </div>
                    )}

                    <div className="text-[11px] font-mono text-slate-400 mb-2 truncate">
                      ID: {p.project_id}
                    </div>

                    <div className="flex items-center gap-3 text-[11px] text-slate-400">
                      <span className="flex items-center gap-1">
                        <Clock size={11} />
                        {p.last_activity ? new Date(p.last_activity * 1000).toLocaleDateString() : 'Recent'}
                      </span>
                      {p.has_edit_decisions && (
                        <span className="text-emerald-400 font-medium">Timeline Active</span>
                      )}
                    </div>
                  </div>

                  {/* Actions footer */}
                  <div className="mt-3 pt-2.5 border-t border-subtle flex items-center justify-between">
                    <button
                      onClick={() => onSelectProject(p.project_id)}
                      className={`btn btn-sm ${
                        isSelected ? 'btn-primary' : 'hover:border-blue-500'
                      }`}
                    >
                      {isSelected ? 'Current Active' : 'Open in Studio'}
                    </button>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => startRename(p)}
                        className="btn btn-sm btn-icon text-slate-400 hover:text-white"
                        title="Rename project"
                      >
                        <Edit2 size={12} />
                      </button>
                      <button
                        onClick={() => handleDuplicate(p)}
                        className="btn btn-sm btn-icon text-slate-400 hover:text-white"
                        title="Duplicate project"
                      >
                        <Copy size={12} />
                      </button>
                      <button
                        onClick={() => setDeletingId(p.project_id)}
                        className="btn btn-sm btn-icon text-slate-400 hover:text-rose-400"
                        title="Delete project"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  {/* Delete Confirmation Dialog */}
                  {deletingId === p.project_id && (
                    <div className="mt-2 p-2 bg-rose-950/80 border border-rose-800 rounded text-xs animate-fadeIn">
                      <p className="text-rose-200 mb-2">Delete project '{p.title}'? (Moved to trash)</p>
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => setDeletingId(null)}
                          className="btn btn-sm py-0.5"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => confirmDelete(p.project_id)}
                          className="btn btn-sm btn-danger py-0.5"
                        >
                          Confirm Delete
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {projects.length === 0 && !showCreateForm && (
            <div className="text-center py-12 text-slate-500">
              <Video size={40} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No video projects found.</p>
              <button
                onClick={() => setShowCreateForm(true)}
                className="btn btn-primary btn-sm mt-3"
              >
                Create your first project
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
