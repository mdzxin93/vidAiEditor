import {
  EditDecisions,
  JobRecord,
  MediaItem,
  ProjectDetails,
  ProjectSummary,
  QAReportData,
  SystemMetrics,
} from './types';

const BASE_URL = '';

export async function fetchMetrics(): Promise<SystemMetrics> {
  const res = await fetch(`${BASE_URL}/api/system/metrics`);
  if (!res.ok) throw new Error('Failed to fetch system metrics');
  return res.json();
}

export async function fetchPresets(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/presets`);
  if (!res.ok) throw new Error('Failed to fetch presets');
  return res.json();
}

export async function fetchProjects(): Promise<ProjectSummary[]> {
  const res = await fetch(`${BASE_URL}/api/projects`);
  if (!res.ok) throw new Error('Failed to fetch projects');
  return res.json();
}

export async function createProject(params: {
  project_id: string;
  title: string;
  pipeline_type?: string;
  aspect_ratio?: string;
}): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create project' }));
    throw new Error(err.detail || 'Failed to create project');
  }
  return res.json();
}

export async function fetchProjectDetails(projectId: string): Promise<ProjectDetails> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}`);
  if (!res.ok) throw new Error(`Project ${projectId} not found`);
  return res.json();
}

export async function renameProject(projectId: string, title: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to rename project');
  return res.json();
}

export async function duplicateProject(
  projectId: string,
  newProjectId: string,
  newTitle: string
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/duplicate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_project_id: newProjectId, new_title: newTitle }),
  });
  if (!res.ok) throw new Error('Failed to duplicate project');
  return res.json();
}

export async function deleteProject(projectId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete project');
  return res.json();
}

export async function fetchProjectMedia(projectId: string): Promise<MediaItem[]> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/media`);
  if (!res.ok) throw new Error('Failed to fetch media assets');
  return res.json();
}

export async function uploadMedia(
  projectId: string,
  file: File,
  category: string = 'video'
): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('category', category);

  const res = await fetch(`${BASE_URL}/api/project/${projectId}/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export async function analyzeFootage(
  projectId: string,
  options: { video_path?: string; quality_preset?: string } = {}
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Analysis failed' }));
    throw new Error(err.detail || 'Analysis request failed');
  }
  return res.json();
}

export async function generateEditorialPlan(
  projectId: string,
  params: {
    user_instruction: string;
    video_path?: string;
    reference_video_path?: string;
    mode?: string;
    target_aspect?: string;
    cut_aggressiveness?: string;
    zoom_intensity?: string;
    caption_preset?: string;
    quality_preset?: string;
  }
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/generate-edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Edit generation failed' }));
    throw new Error(err.detail || 'Generation request failed');
  }
  return res.json();
}

export async function fetchEditDecisions(projectId: string): Promise<EditDecisions> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/edit-decisions`);
  if (!res.ok) throw new Error('Failed to load edit decisions');
  const data = await res.json();
  return data.edit_decisions;
}

export async function saveEditDecisions(
  projectId: string,
  editDecisions: EditDecisions,
  commitMessage: string = 'Timeline update'
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/edit-decisions`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edit_decisions: editDecisions, commit_message: commitMessage }),
  });
  if (!res.ok) throw new Error('Failed to save timeline changes');
  return res.json();
}

export async function fetchProjectHistory(projectId: string): Promise<any[]> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/history`);
  if (!res.ok) return [];
  return res.json();
}

export async function revertToHistorySnapshot(
  projectId: string,
  snapshotId: string
): Promise<EditDecisions> {
  const res = await fetch(
    `${BASE_URL}/api/project/${projectId}/history/revert?snapshot_id=${encodeURIComponent(
      snapshotId
    )}`,
    { method: 'POST' }
  );
  if (!res.ok) throw new Error('Failed to revert history snapshot');
  const data = await res.json();
  return data.edit_decisions;
}

export async function triggerRender(
  projectId: string,
  params: {
    mode: 'preview' | 'final';
    composition_id?: string;
    resolution?: string;
    fps?: number;
    output_filename?: string;
    render_preset?: 'fast_preview' | 'balanced' | 'final_quality';
  }
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Render failed' }));
    throw new Error(err.detail || 'Render request failed');
  }
  return res.json();
}

export async function fetchJobs(projectId?: string): Promise<JobRecord[]> {
  const url = projectId ? `${BASE_URL}/api/jobs?project_id=${encodeURIComponent(projectId)}` : `${BASE_URL}/api/jobs`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch jobs list');
  return res.json();
}

export async function fetchJobStatus(jobId: string): Promise<JobRecord> {
  const res = await fetch(`${BASE_URL}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error('Job not found');
  return res.json();
}

export async function cancelJob(jobId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/cancel`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to cancel job');
  return res.json();
}

export async function retryJob(jobId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/retry`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to retry job');
  return res.json();
}

export async function recoverJob(jobId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/recover`, { method: 'POST' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to recover job');
  }
  return res.json();
}

export async function deleteJob(jobId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/jobs/${jobId}`, { method: 'DELETE' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to delete job');
  }
  return res.json();
}

export async function clearCompletedJobs(projectId?: string): Promise<any> {
  const url = projectId ? `${BASE_URL}/api/jobs/clear-completed?project_id=${encodeURIComponent(projectId)}` : `${BASE_URL}/api/jobs/clear-completed`;
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to clear completed jobs');
  }
  return res.json();
}

export async function fetchCacheStats(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/cache/stats`);
  if (!res.ok) throw new Error('Failed to fetch cache stats');
  return res.json();
}

export async function clearCache(scope: string = 'all'): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/cache/clear?scope=${encodeURIComponent(scope)}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to clear cache');
  return res.json();
}

export async function runQaInspection(projectId: string, videoPath?: string): Promise<QAReportData> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/qa-inspect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_path: videoPath }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'QA inspection failed' }));
    throw new Error(err.detail || 'QA inspection failed');
  }
  const data = await res.json();
  return data.qa_report;
}

export async function fetchQaReport(projectId: string): Promise<QAReportData | null> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/qa-report`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.qa_report || null;
}

export async function applyQaFixes(
  projectId: string,
  issueIds?: string[]
): Promise<{ fixes_applied_count: number; edit_decisions: EditDecisions; fixes: any[] }> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/qa-apply-fixes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ issue_ids: issueIds }),
  });
  if (!res.ok) throw new Error('Failed to apply QA fixes');
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase 10: Preferences, Memory & Personalization API
// ---------------------------------------------------------------------------

export async function fetchPreferencesSettings(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/settings`);
  if (!res.ok) throw new Error('Failed to fetch preference settings');
  return res.json();
}

export async function updatePreferencesSettings(settings: any): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error('Failed to update preference settings');
  return res.json();
}

export async function fetchPreferences(category?: string, enabledOnly: boolean = false): Promise<any[]> {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  if (enabledOnly) params.append('enabled_only', 'true');
  const res = await fetch(`${BASE_URL}/api/preferences?${params.toString()}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.preferences || [];
}

export async function updatePreference(preferenceId: string, updates: any): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/${encodeURIComponent(preferenceId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`Failed to update preference ${preferenceId}`);
  return res.json();
}

export async function deletePreference(preferenceId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/${encodeURIComponent(preferenceId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete preference ${preferenceId}`);
  return res.json();
}

export async function resetAllPreferences(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to reset preferences');
  return res.json();
}

export async function fetchCorrections(projectId?: string): Promise<any[]> {
  const url = projectId
    ? `${BASE_URL}/api/preferences/corrections/list?project_id=${encodeURIComponent(projectId)}`
    : `${BASE_URL}/api/preferences/corrections/list`;
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json();
  return data.corrections || [];
}

export async function recordManualCorrection(rec: any): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/corrections/record`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rec),
  });
  if (!res.ok) throw new Error('Failed to record correction');
  return res.json();
}

export async function approveCorrection(
  correctionId: string,
  applyToFuture: boolean = true,
  contextConstraints?: any
): Promise<any> {
  const res = await fetch(
    `${BASE_URL}/api/preferences/corrections/${encodeURIComponent(correctionId)}/approve`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        apply_to_future: applyToFuture,
        context_constraints: contextConstraints,
      }),
    }
  );
  if (!res.ok) throw new Error(`Failed to approve correction ${correctionId}`);
  return res.json();
}

export async function rejectCorrection(correctionId: string): Promise<any> {
  const res = await fetch(
    `${BASE_URL}/api/preferences/corrections/${encodeURIComponent(correctionId)}/reject`,
    { method: 'POST' }
  );
  if (!res.ok) throw new Error(`Failed to reject correction ${correctionId}`);
  return res.json();
}

export async function fetchStylePresets(): Promise<any[]> {
  const res = await fetch(`${BASE_URL}/api/preferences/presets/list`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.presets || [];
}

export async function createOrUpdatePreset(preset: any): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/presets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(preset),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to save preset' }));
    throw new Error(err.detail || 'Failed to save preset');
  }
  return res.json();
}

export async function deleteStylePreset(presetId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/presets/${encodeURIComponent(presetId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete preset ${presetId}`);
  return res.json();
}

export async function activateStylePreset(presetId: string): Promise<any> {
  const res = await fetch(
    `${BASE_URL}/api/preferences/presets/${encodeURIComponent(presetId)}/activate`,
    { method: 'POST' }
  );
  if (!res.ok) throw new Error(`Failed to activate preset ${presetId}`);
  return res.json();
}

export async function exportPreferencesData(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/export/download`);
  if (!res.ok) throw new Error('Failed to export preferences');
  return res.json();
}

export async function importPreferencesData(importData: any, overwrite: boolean = false): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/import/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ import_data: importData, overwrite_existing: overwrite }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Import failed' }));
    throw new Error(err.detail || 'Import failed');
  }
  return res.json();
}

export async function exportDataset(anonymize: boolean = true): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/preferences/dataset/export?anonymize=${anonymize}`);
  if (!res.ok) throw new Error('Failed to export dataset');
  return res.json();
}

export async function fetchWaveform(projectId: string, videoPath?: string, points: number = 800): Promise<{
  ok: boolean;
  media_file: string;
  duration: number;
  points_count: number;
  peaks: number[];
}> {
  const q = new URLSearchParams();
  if (videoPath) q.set('video_path', videoPath);
  q.set('points', String(points));
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/waveform?${q.toString()}`);
  if (!res.ok) throw new Error('Failed to load waveform peaks');
  return res.json();
}

export async function fetchIncrementalAudit(
  projectId: string,
  preset: string = 'fast_preview',
  resolution: string = '540x960'
): Promise<any> {
  const q = new URLSearchParams({ render_preset: preset, resolution });
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/incremental-render-audit?${q.toString()}`);
  if (!res.ok) throw new Error('Failed to load incremental render audit');
  return res.json();
}

export async function fetchSystemModels(): Promise<{
  ok: boolean;
  models_directory: string;
  smolvlm_500m: { name: string; is_installed_locally: boolean; required_for: string; instructions: string };
  whisper: { name: string; is_installed_locally: boolean; required_for: string; instructions: string };
  hardware: { device: string; cuda_available: boolean; ram_recommended_gb: number };
}> {
  const res = await fetch(`${BASE_URL}/api/system/models`);
  if (!res.ok) throw new Error('Failed to fetch system models status');
  return res.json();
}

export async function fetchCaptionPresets(): Promise<{ ok: boolean; presets: any[] }> {
  const res = await fetch(`${BASE_URL}/api/caption-presets`);
  if (!res.ok) throw new Error('Failed to fetch caption presets');
  return res.json();
}

export async function generateKineticCaptions(
  projectId: string,
  params: {
    video_path?: string;
    preset_id?: string;
    video_style?: 'dynamic_zoom' | 'static';
    zoom_intensity?: string;
    model_size?: string;
    language?: string;
    words_per_cue?: number;
    emphasis_frequency?: number;
    vertical_position?: number;
    render_video?: boolean;
  } = {}
): Promise<{ ok: boolean; job_id: string; status: string }> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/captions/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to generate kinetic captions' }));
    throw new Error(err.detail || 'Failed to generate kinetic captions');
  }
  return res.json();
}

export async function exportKineticCaptions(
  projectId: string,
  params: {
    format: 'srt' | 'vtt' | 'ass';
    cues?: any[];
    preset_id?: string;
  }
): Promise<{
  ok: boolean;
  format: string;
  file_path: string;
  relative_path: string;
  content_preview: string;
}> {
  const res = await fetch(`${BASE_URL}/api/project/${projectId}/captions/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to export subtitles' }));
    throw new Error(err.detail || 'Failed to export subtitles');
  }
  return res.json();
}


