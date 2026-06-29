import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, Loader2, Plus, Save, Trash2, Upload, X } from 'lucide-react';
import { listHardwareCatalogOptions } from '../api/catalog';
import type { HardwareCatalogOption } from '../api/catalog';
import {
  downloadProjectDocumentPdf,
  getProject,
  getLocalProjectDocumentPreviewHtml,
  getProjectDocumentPreviewUrl,
  ProjectDocumentOverrides,
  ProjectDocumentType,
  updateProject,
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

interface PaintManualRow {
  id: string;
  color: string;
  article: string;
  name: string;
  imageFile: string;
  imageData: string;
  qty: string;
  clean: string;
  allowance: string;
  totalM: string;
  note: string;
}

const makePaintRowId = () => `paint-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

function normalizePaintRow(row?: Partial<PaintManualRow>): PaintManualRow {
  return {
    id: row?.id || makePaintRowId(),
    color: row?.color || '',
    article: row?.article || '',
    name: row?.name || '',
    imageFile: row?.imageFile || '',
    imageData: row?.imageData || '',
    qty: row?.qty || '',
    clean: row?.clean || '',
    allowance: row?.allowance || '',
    totalM: row?.totalM || '',
    note: row?.note || '',
  };
}

function parsePaintRows(raw?: string): PaintManualRow[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(row => normalizePaintRow(row)) : [];
  } catch {
    return [];
  }
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
  const [previewVersion, setPreviewVersion] = useState(0);
  const [paintRows, setPaintRows] = useState<PaintManualRow[]>([]);
  const [catalog, setCatalog] = useState<HardwareCatalogOption[]>([]);
  const [isSavingPaintRows, setIsSavingPaintRows] = useState(false);

  const token = localStorage.getItem('access_token') ?? '';
  const isGuest = !token;
  const isPaintDocument = docType === 'paint';
  const previewUrl = useMemo(
    () => isGuest ? undefined : `${getProjectDocumentPreviewUrl(projectId, docType)}?token=${encodeURIComponent(token)}&v=${previewVersion}`,
    [docType, isGuest, projectId, token, previewVersion],
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
      setPaintRows([]);
      return;
    }
    loadGuestPreview();
  }, [isOpen, loadGuestPreview]);

  useEffect(() => {
    if (!isOpen || !isPaintDocument) return;
    let cancelled = false;
    getProject(projectId)
      .then(project => {
        if (!cancelled) setPaintRows(parsePaintRows(project.paint_manual_rows));
      })
      .catch(() => {
        if (!cancelled) toast.error('Не удалось загрузить ручные строки покраски');
      });
    listHardwareCatalogOptions()
      .then(rows => {
        if (cancelled) return;
        setCatalog(
          rows
            .filter(row => row.isActive)
            .sort((a, b) => `${a.name} ${a.sku}`.localeCompare(`${b.name} ${b.sku}`, 'ru')),
        );
      })
      .catch(() => {
        if (!cancelled) toast.error('Не удалось загрузить каталог');
      });
    return () => { cancelled = true; };
  }, [isOpen, isPaintDocument, projectId]);

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

  const updatePaintRow = (id: string, updates: Partial<PaintManualRow>) => {
    setPaintRows(rows => rows.map(row => row.id === id ? { ...row, ...updates } : row));
  };

  const addPaintRow = () => {
    setPaintRows(rows => [...rows, normalizePaintRow()]);
  };

  const removePaintRow = (id: string) => {
    setPaintRows(rows => rows.filter(row => row.id !== id));
  };

  const selectCatalogItem = (rowId: string, sku: string) => {
    const item = catalog.find(candidate => candidate.sku === sku);
    updatePaintRow(rowId, {
      article: sku,
      name: item?.name || '',
      imageFile: item?.imageFile || '',
      imageData: '',
    });
  };

  const uploadPaintImage = (rowId: string, file?: File) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      updatePaintRow(rowId, { imageData: String(reader.result || ''), imageFile: '' });
    };
    reader.onerror = () => toast.error('Не удалось загрузить картинку');
    reader.readAsDataURL(file);
  };

  const savePaintRows = async (): Promise<boolean> => {
    setIsSavingPaintRows(true);
    try {
      const cleaned = paintRows
        .map(normalizePaintRow)
        .filter(row => row.article || row.name || row.imageFile || row.imageData);
      await updateProject(projectId, {
        paint_manual_rows: JSON.stringify(cleaned),
      });
      setPaintRows(cleaned);
      toast.success('Строки заявки на покраску сохранены');
      if (isGuest) {
        await loadGuestPreview();
      } else {
        setPreviewVersion(value => value + 1);
      }
      return true;
    } catch {
      toast.error('Не удалось сохранить строки заявки');
      return false;
    } finally {
      setIsSavingPaintRows(false);
    }
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      if (isPaintDocument) {
        const saved = await savePaintRows();
        if (!saved) return;
      }
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
            className="relative w-full max-w-6xl bg-modal border border-tint/25 rounded-2xl sm:rounded-[2rem] shadow-2xl shadow-black/20 overflow-hidden flex flex-col z-10"
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

            {isPaintDocument && (
              <div className="px-5 py-4 sm:px-8 bg-page border-b border-tint/20 space-y-3 flex-shrink-0">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-widest text-fg/45">Ручные строки покраски</div>
                    <div className="text-[11px] text-fg/35 mt-1">Добавляются в PDF вместе с расчетными строками</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={addPaintRow}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-tint/30 bg-tint/10 text-accent text-xs font-bold uppercase tracking-wider hover:bg-tint/20"
                    >
                      <Plus className="w-4 h-4" />
                      Строка
                    </button>
                    <button
                      type="button"
                      onClick={savePaintRows}
                      disabled={isSavingPaintRows}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-accent/30 bg-accent/15 text-accent text-xs font-bold uppercase tracking-wider hover:bg-accent/25 disabled:opacity-50"
                    >
                      {isSavingPaintRows ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                      Сохранить
                    </button>
                  </div>
                </div>

                {paintRows.length > 0 && (
                  <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
                    {paintRows.map(row => (
                      <div
                        key={row.id}
                        className="grid grid-cols-[minmax(150px,1.15fr)_90px_88px_minmax(120px,1fr)_62px_64px_64px_64px_minmax(90px,0.8fr)_86px_34px] gap-2 items-center"
                      >
                        <select
                          value={row.article}
                          onChange={event => selectCatalogItem(row.id, event.target.value)}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                        >
                          <option value="">— из каталога —</option>
                          {catalog.map(item => (
                            <option key={item.id} value={item.sku}>{item.name} {item.sku}</option>
                          ))}
                        </select>
                        <input
                          value={row.article}
                          onChange={event => updatePaintRow(row.id, { article: event.target.value })}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                          placeholder="Артикул"
                        />
                        <input
                          value={row.color}
                          onChange={event => updatePaintRow(row.id, { color: event.target.value })}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                          placeholder="Цвет"
                        />
                        <input
                          value={row.name}
                          onChange={event => updatePaintRow(row.id, { name: event.target.value })}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                          placeholder="Название"
                        />
                        <input
                          value={row.qty}
                          onChange={event => updatePaintRow(row.id, { qty: event.target.value })}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                          placeholder="Кол-во"
                        />
                        <input
                          value={row.clean}
                          onChange={event => updatePaintRow(row.id, { clean: event.target.value })}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                          placeholder="Чист."
                        />
                        <input
                          value={row.allowance}
                          onChange={event => updatePaintRow(row.id, { allowance: event.target.value })}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                          placeholder="+50"
                        />
                        <input
                          value={row.totalM}
                          onChange={event => updatePaintRow(row.id, { totalM: event.target.value })}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                          placeholder="м.п."
                        />
                        <input
                          value={row.note}
                          onChange={event => updatePaintRow(row.id, { note: event.target.value })}
                          className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                          placeholder="Прим."
                        />
                        <label className="h-9 rounded-lg border border-tint/20 bg-black/15 px-2 text-xs flex items-center justify-center gap-1 cursor-pointer hover:border-accent/40">
                          <Upload className="w-3.5 h-3.5" />
                          Картинка
                          <input
                            type="file"
                            accept="image/png,image/jpeg,image/webp"
                            className="hidden"
                            onChange={event => uploadPaintImage(row.id, event.target.files?.[0])}
                          />
                        </label>
                        <button
                          type="button"
                          onClick={() => removePaintRow(row.id)}
                          className="h-9 w-9 rounded-lg border border-red-500/25 bg-red-500/5 text-red-400/75 hover:bg-red-500/15 flex items-center justify-center"
                          aria-label="Удалить строку"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="overflow-y-auto bg-gray-100" style={{ height: isPaintDocument ? 'calc(90vh - 295px)' : 'calc(90vh - 130px)' }}>
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
