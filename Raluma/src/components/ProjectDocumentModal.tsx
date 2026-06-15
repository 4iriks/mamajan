import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, Loader2, X } from 'lucide-react';
import {
  downloadProjectDocumentPdf,
  getLocalProjectDocumentPreviewHtml,
  getProjectDocumentPreviewUrl,
  ProjectDocumentOverrides,
  ProjectDocumentType,
} from '../api/projects';
import { toast } from '../store/toastStore';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  projectNumber: string;
  docType: ProjectDocumentType;
  title: string;
}

export default function ProjectDocumentModal({
  isOpen,
  onClose,
  projectId,
  projectNumber,
  docType,
  title,
}: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [previewSrcDoc, setPreviewSrcDoc] = useState('');
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const token = localStorage.getItem('access_token') ?? '';
  const isGuest = !token;
  const previewUrl = useMemo(
    () => isGuest ? undefined : `${getProjectDocumentPreviewUrl(projectId, docType)}?token=${encodeURIComponent(token)}`,
    [docType, isGuest, projectId, token],
  );

  const loadGuestPreview = useCallback(async () => {
    if (!isGuest || !isOpen) return;
    setIsPreviewLoading(true);
    try {
      setPreviewSrcDoc(await getLocalProjectDocumentPreviewHtml(projectId, docType));
    } catch {
      setPreviewSrcDoc("<p style='padding:20px;font-family:sans-serif'>Не удалось открыть документ</p>");
      toast.error('Не удалось открыть документ');
    } finally {
      setIsPreviewLoading(false);
    }
  }, [docType, isGuest, isOpen, projectId]);

  useEffect(() => {
    if (!isOpen) {
      setPreviewSrcDoc('');
      setIsDirty(false);
      return;
    }
    loadGuestPreview();
  }, [isOpen, loadGuestPreview]);

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'dirty' && docType === 'glass') setIsDirty(true);
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [docType]);

  const collectChanges = useCallback((): ProjectDocumentOverrides => {
    if (docType !== 'glass') return {};
    const doc = iframeRef.current?.contentDocument;
    if (!doc) return {};

    const changed: ProjectDocumentOverrides = {};
    doc.querySelectorAll<HTMLElement>('[data-field]').forEach(el => {
      const field = el.dataset.field as keyof ProjectDocumentOverrides | undefined;
      if (field !== 'project_number' && field !== 'project_customer') return;
      const original = el.dataset.original ?? '';
      const current = el.textContent?.trim() ?? '';
      if (current !== original) changed[field] = current;
    });
    return changed;
  }, [docType]);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const changes = collectChanges();
      await downloadProjectDocumentPdf(projectId, docType, `${title}_${projectNumber}.pdf`, changes);
      setIsDirty(false);
    } catch {
      toast.error('Ошибка генерации PDF');
    } finally {
      setIsDownloading(false);
    }
  };

  const handleClose = () => {
    if (isDirty && !window.confirm('Есть несохранённые правки в документе. Закрыть без скачивания?')) {
      return;
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
            className="relative w-full max-w-5xl bg-modal border border-tint/25 rounded-2xl sm:rounded-[2rem] shadow-2xl shadow-black/20 overflow-hidden flex flex-col z-10"
            style={{ maxHeight: '95vh' }}
          >
            <div className="px-5 py-4 sm:px-8 sm:py-5 border-b border-tint/20 flex items-center justify-between flex-shrink-0">
              <div>
                <h2 className="text-lg font-bold">{title}</h2>
                <p className="text-xs text-fg/40 mt-0.5">
                  {projectNumber}
                  {isDirty && <span className="ml-2 text-yellow-400">● правки попадут в PDF</span>}
                </p>
              </div>
              <button onClick={handleClose} className="text-fg/20 hover:text-fg transition-colors ml-4">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto bg-gray-100" style={{ height: 'calc(90vh - 130px)' }}>
              {isPreviewLoading ? (
                <div className="h-full flex items-center justify-center bg-gray-100">
                  <Loader2 className="w-8 h-8 text-gray-500 animate-spin" />
                </div>
              ) : (
                <iframe
                  ref={iframeRef}
                  src={previewUrl}
                  srcDoc={isGuest ? previewSrcDoc : undefined}
                  className="w-full h-full border-0 block"
                  title={title}
                />
              )}
            </div>

            <div className="px-5 py-4 sm:px-8 sm:py-5 bg-page border-t border-tint/20 flex items-center justify-end flex-shrink-0">
              <button
                onClick={handleDownload}
                disabled={isDownloading}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-accent/15 hover:bg-accent/25 text-accent border border-accent/30 font-bold transition-all disabled:opacity-50 text-sm"
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
