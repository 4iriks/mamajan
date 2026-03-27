import { useRef, useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Save, RotateCcw, Download, Loader2 } from 'lucide-react';
import { getPreviewUrl, saveDocumentOverrides, downloadPdf } from '../api/projects';
import { toast } from '../store/toastStore';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  sectionId: number;
  projectNumber: string;
  sectionOrder: number;
}

export default function ProductionSheetModal({
  isOpen, onClose, projectId, sectionId, projectNumber, sectionOrder,
}: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const token = localStorage.getItem('access_token') ?? '';
  const previewUrl = `${getPreviewUrl(projectId, sectionId)}?token=${encodeURIComponent(token)}`;

  // Слушаем сообщения из iframe (dirty state)
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'dirty') setIsDirty(true);
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  // Сброс dirty при закрытии/смене секции
  useEffect(() => {
    if (!isOpen) setIsDirty(false);
  }, [isOpen, sectionId]);

  const collectChanges = useCallback((): Record<string, string> => {
    const doc = iframeRef.current?.contentDocument;
    if (!doc) return {};
    const changed: Record<string, string> = {};
    doc.querySelectorAll<HTMLElement>('[data-field]').forEach(el => {
      const field = el.dataset.field!;
      const original = el.dataset.original ?? '';
      const current = el.textContent?.trim() ?? '';
      if (current !== original) changed[field] = current;
    });
    return changed;
  }, []);

  const handleSave = async () => {
    const changes = collectChanges();
    if (Object.keys(changes).length === 0) {
      setIsDirty(false);
      return;
    }
    setIsSaving(true);
    try {
      await saveDocumentOverrides(projectId, sectionId, changes);
      setIsDirty(false);
      toast.success('Правки сохранены');
    } catch {
      toast.error('Ошибка сохранения');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    iframeRef.current?.contentWindow?.location.reload();
    setIsDirty(false);
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const filename = `ПЛ_${projectNumber}_сек${sectionOrder}.pdf`;
      await downloadPdf(projectId, sectionId, filename);
    } catch {
      toast.error('Ошибка генерации PDF');
    } finally {
      setIsDownloading(false);
    }
  };

  const handleClose = () => {
    if (isDirty) {
      if (!window.confirm('Есть несохранённые правки. Закрыть без сохранения?')) return;
    }
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={handleClose}
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
          />
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0, y: 20 }}
            className="relative w-full max-w-5xl bg-[#1a4b54] border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2rem] shadow-2xl overflow-hidden flex flex-col z-10"
            style={{ maxHeight: '95vh' }}
          >
            {/* Header */}
            <div className="px-5 py-4 sm:px-8 sm:py-5 border-b border-[#2a7a8a]/20 flex items-center justify-between flex-shrink-0">
              <div>
                <h2 className="text-lg font-bold">Производственный лист</h2>
                <p className="text-xs text-white/40 mt-0.5">
                  {projectNumber} · Секция {sectionOrder}
                  {isDirty && <span className="ml-2 text-yellow-400">● несохранённые правки</span>}
                </p>
              </div>
              <button onClick={handleClose} className="text-white/20 hover:text-white transition-colors ml-4">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* iframe */}
            <div className="flex-1 overflow-hidden bg-gray-100 min-h-0">
              <iframe
                ref={iframeRef}
                src={previewUrl}
                className="w-full h-full border-0"
                style={{ minHeight: '60vh' }}
                title="Производственный лист"
              />
            </div>

            {/* Footer */}
            <div className="px-5 py-4 sm:px-8 sm:py-5 bg-black/30 border-t border-[#2a7a8a]/20 flex items-center justify-between flex-shrink-0 gap-3 flex-wrap">
              <div className="flex gap-2">
                <button
                  onClick={handleSave}
                  disabled={!isDirty || isSaving}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#00b894] hover:bg-[#00d1a7] text-white font-bold transition-all disabled:opacity-30 disabled:cursor-not-allowed text-sm"
                >
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Сохранить
                </button>
                <button
                  onClick={handleCancel}
                  disabled={!isDirty}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 font-bold transition-all disabled:opacity-30 disabled:cursor-not-allowed text-sm"
                >
                  <RotateCcw className="w-4 h-4" />
                  Отменить
                </button>
              </div>
              <button
                onClick={handleDownload}
                disabled={isDownloading}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-[#2a7a8a] hover:bg-[#3a9aaa] text-white font-bold transition-all disabled:opacity-50 text-sm"
              >
                {isDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Скачать PDF
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
