import React, { useState, useRef } from 'react';
import {
  Upload,
  Film,
  Music,
  Video,
  Info,
  CheckCircle,
  Eye,
  FilePlus,
  Sparkles,
  Layers,
  Check,
} from 'lucide-react';
import { MediaItem } from '../types';
import { uploadMedia } from '../api';

interface MediaBinProps {
  projectId: string;
  mediaList: MediaItem[];
  primaryVideo: MediaItem | null;
  onRefreshMedia: () => void;
  onSelectPrimary: (item: MediaItem) => void;
  onPreviewMedia: (item: MediaItem) => void;
}

export const MediaBin: React.FC<MediaBinProps> = ({
  projectId,
  mediaList,
  primaryVideo,
  onRefreshMedia,
  onSelectPrimary,
  onPreviewMedia,
}) => {
  const [activeTab, setActiveTab] = useState<'all' | 'video' | 'broll' | 'audio' | 'reference'>('all');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [selectedMetaItem, setSelectedMetaItem] = useState<MediaItem | null>(null);
  const [uploadCategory, setUploadCategory] = useState<'video' | 'broll' | 'reference' | 'audio' | 'music'>('video');
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const filteredMedia = mediaList.filter((item) => {
    if (activeTab === 'all') return true;
    if (activeTab === 'video') return item.category === 'video';
    if (activeTab === 'broll') return item.category === 'broll';
    if (activeTab === 'audio') return item.category === 'audio' || item.category === 'music';
    if (activeTab === 'reference') return item.category === 'reference';
    return true;
  });

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setIsUploading(true);
    setUploadProgress(`Uploading ${files.length} file(s)...`);

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setUploadProgress(`Uploading (${i + 1}/${files.length}): ${file.name}`);
        await uploadMedia(projectId, file, uploadCategory);
      }
      onRefreshMedia();
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  const formatDate = (timestamp: number) => {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex flex-col h-full bg-[#0d1117] border-r border-[#1c2433] select-none">
      {/* Media Bin Toolbar */}
      <div className="p-3 border-b border-[#1c2433] bg-[#0f141d]/80">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <Film className="w-4 h-4 text-sky-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">Media Assets</h2>
            <span className="text-[10px] bg-[#1a2333] px-2 py-0.5 rounded-full text-sky-400 font-mono font-semibold border border-sky-500/20">
              {mediaList.length}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={uploadCategory}
              onChange={(e) => setUploadCategory(e.target.value as any)}
              className="text-[11px] bg-[#161d2a] text-slate-200 border border-[#273448] rounded-md px-2 py-1 outline-none focus:border-sky-500 cursor-pointer"
            >
              <option value="video">Raw Footage</option>
              <option value="broll">B-Roll Cut</option>
              <option value="reference">Style Ref</option>
              <option value="music">Music/Voice</option>
            </select>

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center gap-1.5 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white text-xs font-semibold px-3 py-1.5 rounded-md shadow-sm transition-all disabled:opacity-50"
              title="Upload media to project"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Import</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="video/*,audio/*,image/*"
              className="hidden"
              onChange={(e) => handleFileUpload(e.target.files)}
            />
          </div>
        </div>

        {/* Upload status banner */}
        {isUploading && (
          <div className="text-[11px] bg-sky-950/60 border border-sky-500/30 text-sky-300 p-2 rounded-lg mb-2 flex items-center gap-2 animate-pulse shadow-inner">
            <Upload className="w-3.5 h-3.5 animate-bounce text-sky-400" />
            <span className="truncate">{uploadProgress}</span>
          </div>
        )}

        {/* Category Filter Pills */}
        <div className="flex items-center gap-1 text-[11px] font-medium text-slate-400 pt-1">
          {(['all', 'video', 'broll', 'audio', 'reference'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-2.5 py-1 rounded-md transition-all capitalize ${
                activeTab === tab
                  ? 'bg-[#1b2536] text-sky-400 font-semibold border border-sky-500/30 shadow-sm'
                  : 'hover:text-slate-200 hover:bg-[#141b26]'
              }`}
            >
              {tab === 'broll' ? 'B-Roll' : tab}
            </button>
          ))}
        </div>
      </div>

      {/* Drag & Drop Zone / Media List */}
      <div
        className={`flex-1 overflow-y-auto p-3 space-y-2 transition-colors ${
          isDragging ? 'bg-sky-500/10 border-2 border-dashed border-sky-400' : ''
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        {filteredMedia.length === 0 ? (
          <div
            onClick={() => fileInputRef.current?.click()}
            className="h-48 flex flex-col items-center justify-center text-center p-6 text-slate-400 border border-dashed border-[#222c3d] hover:border-sky-500/50 hover:bg-[#141b27] rounded-xl transition-all cursor-pointer group mt-2"
          >
            <div className="w-10 h-10 rounded-full bg-[#161d2a] flex items-center justify-center mb-3 group-hover:scale-110 transition-transform border border-[#263347]">
              <Upload className="w-5 h-5 text-sky-400" />
            </div>
            <p className="text-xs font-semibold text-slate-200">Drag & Drop Footage Here</p>
            <p className="text-[11px] text-slate-500 mt-1">or click to browse local files (MP4, MOV, WAV, MP3)</p>
          </div>
        ) : (
          filteredMedia.map((item) => {
            const isPrimary = primaryVideo?.name === item.name;

            return (
              <div
                key={item.name}
                className={`group relative flex items-center gap-3 p-2.5 rounded-xl border transition-all cursor-pointer ${
                  isPrimary
                    ? 'bg-[#142338] border-sky-500 shadow-md shadow-sky-950/40 ring-1 ring-sky-500/30'
                    : 'bg-[#121722] border-[#1e2738] hover:border-[#2f3d54] hover:bg-[#171e2c]'
                }`}
                onClick={() => onPreviewMedia(item)}
              >
                {/* Media Thumbnail / Icon */}
                <div className="w-14 h-11 bg-[#090c12] rounded-lg flex items-center justify-center overflow-hidden shrink-0 border border-[#202a3a] relative shadow-inner">
                  {item.thumbnail_url ? (
                    <img
                      src={item.thumbnail_url}
                      alt={item.name}
                      className="w-full h-full object-cover"
                    />
                  ) : item.is_video ? (
                    <Video className="w-5 h-5 text-sky-400" />
                  ) : item.is_audio ? (
                    <Music className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <Film className="w-5 h-5 text-slate-400" />
                  )}
                  {/* Subtle video tag */}
                  <div className="absolute bottom-0 right-0 px-1 bg-black/80 rounded-tl text-[8px] font-mono text-slate-300">
                    {item.is_video ? 'VID' : item.is_audio ? 'AUD' : 'IMG'}
                  </div>
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-slate-200 truncate" title={item.name}>
                      {item.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-1 font-mono">
                    <span className="capitalize px-1.5 py-0.2 rounded bg-[#1c2434] text-slate-300 font-sans text-[9px] font-medium border border-slate-700/50">
                      {item.category}
                    </span>
                    <span>{formatBytes(item.size_bytes)}</span>
                  </div>
                </div>

                {/* Status & Quick Actions */}
                <div className="flex items-center gap-1">
                  {isPrimary ? (
                    <span className="px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300 border border-sky-500/40 text-[9px] font-bold uppercase tracking-wider flex items-center gap-1">
                      <Check className="w-2.5 h-2.5 text-sky-400" />
                      Primary
                    </span>
                  ) : (
                    item.is_video && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectPrimary(item);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-sky-600 text-slate-400 hover:text-white rounded-md transition-all text-[10px] flex items-center gap-1"
                        title="Set as primary editing footage"
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                      </button>
                    )
                  )}

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedMetaItem(item);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-[#253044] text-slate-400 hover:text-slate-200 rounded-md transition-all"
                    title="Inspect file properties"
                  >
                    <Info className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Metadata Inspector Dialog */}
      {selectedMetaItem && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#141b27] border border-[#273448] rounded-xl max-w-sm w-full p-4 shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-2.5 border-b border-[#222d3d] mb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
                <Info className="w-4 h-4 text-sky-400" />
                Media Properties
              </h3>
              <button
                onClick={() => setSelectedMetaItem(null)}
                className="text-slate-400 hover:text-white text-xs p-1 rounded-md hover:bg-[#1f2838]"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1.5 border-b border-[#1c2433]">
                <span className="text-slate-400">File Name:</span>
                <span className="text-slate-200 font-mono text-[11px] truncate max-w-[200px]" title={selectedMetaItem.name}>
                  {selectedMetaItem.name}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-[#1c2433]">
                <span className="text-slate-400">Category:</span>
                <span className="text-slate-200 font-medium capitalize">{selectedMetaItem.category}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-[#1c2433]">
                <span className="text-slate-400">File Size:</span>
                <span className="text-slate-200 font-mono">{formatBytes(selectedMetaItem.size_bytes)}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-[#1c2433]">
                <span className="text-slate-400">Relative Path:</span>
                <span className="text-slate-300 font-mono text-[10px] break-all">{selectedMetaItem.relative_path}</span>
              </div>
            </div>

            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setSelectedMetaItem(null)}
                className="px-4 py-1.5 bg-[#202a3a] hover:bg-[#2b394e] text-white text-xs font-semibold rounded-lg transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
