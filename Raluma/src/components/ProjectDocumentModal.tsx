import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Download,
  Maximize2,
  Minimize2,
  FileSpreadsheet,
  FileText,
  Loader2,
  Plus,
  Save,
  RefreshCw,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { listHardwareCatalogOptions } from '../api/catalog';
import type { HardwareCatalogOption } from '../api/catalog';
import {
  downloadProjectDocument,
  getProject,
  getLocalProjectDocumentPreviewHtml,
  getProjectDocumentPreviewUrl,
  ProjectDocumentOverrides,
  ProjectDocumentType,
  updateProject,
} from '../api/projects';
import type { DocumentFileFormat, SectionOut } from '../api/projects';
import { toast } from '../store/toastStore';
import {
  getPublicQuote,
  getInternalQuote,
  PublicQuote,
  refreshQuote,
  freezeQuote,
  getQuoteRevision,
  listQuoteRevisions,
  type QuoteRevision,
} from '../api/quotes';
import { useAuthStore } from '../store/authStore';
import { money } from '../utils/money';
import { captureQuoteConfirmation, type QuoteConfirmation } from '../utils/quoteConfirmation';
import { QuoteConfirmationDialog } from './QuoteConfirmationDialog';

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

type DeliveryDateMode = 'blank' | 'today' | 'custom';

interface DeliveryNoteData {
  dateMode: DeliveryDateMode;
  date: string;
  note: string;
  contact: string;
  delivery: string;
  places: Record<string, string>;
}

const makePaintRowId = () => `paint-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
function requestError(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: unknown }).message);
  }
  return fallback;
}

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

function projectPaintColors(sections: SectionOut[]): string[] {
  const colors = new Set<string>();
  sections.forEach(section => {
    if (!(section.painting_type || '').toLowerCase().includes('ral')) return;
    const ral = (section.ral_color || '').trim();
    colors.add(ral ? `RAL ${ral}` : 'RAL');
  });
  return [...colors].sort((a, b) => a.localeCompare(b, 'ru'));
}

function parseDeliveryData(raw?: string): DeliveryNoteData {
  const fallback: DeliveryNoteData = {
    dateMode: 'blank',
    date: new Date().toISOString().slice(0, 10),
    note: '',
    contact: '',
    delivery: '',
    places: {},
  };
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw) as Partial<DeliveryNoteData>;
    const dateMode = ['blank', 'today', 'custom'].includes(String(parsed.dateMode))
      ? parsed.dateMode as DeliveryDateMode
      : fallback.dateMode;
    return {
      ...fallback,
      ...parsed,
      dateMode,
      places: parsed.places && typeof parsed.places === 'object' ? parsed.places : {},
    };
  } catch {
    return fallback;
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
  const [downloadingFormat, setDownloadingFormat] = useState<DocumentFileFormat | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [previewVersion, setPreviewVersion] = useState(0);
  const [paintRows, setPaintRows] = useState<PaintManualRow[]>([]);
  const [paintColors, setPaintColors] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<HardwareCatalogOption[]>([]);
  const [isSavingPaintRows, setIsSavingPaintRows] = useState(false);
  const [deliveryData, setDeliveryData] = useState<DeliveryNoteData>(() => parseDeliveryData());
  const [isSavingDelivery, setIsSavingDelivery] = useState(false);
  const [quote, setQuote] = useState<PublicQuote | null>(null);
  const [pendingQuote, setPendingQuote] = useState<PublicQuote | null>(null);
  const [previewToken, setPreviewToken] = useState('');
  const [quoteConfirmation, setQuoteConfirmation] = useState<QuoteConfirmation | null>(null);
  const [revisions, setRevisions] = useState<QuoteRevision[]>([]);
  const [selectedRevision, setSelectedRevision] = useState<number>();
  const quoteLoadVersion = useRef(0);
  const [fullScreen, setFullScreen] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [isQuoteLoading, setIsQuoteLoading] = useState(false);
  const [isQuoteSaving, setIsQuoteSaving] = useState(false);
  const { user } = useAuthStore();

  const token = localStorage.getItem('access_token') ?? '';
  const isGuest = !token;
  const isPaintDocument = docType === 'paint';
  const isDeliveryDocument = docType === 'delivery';
  const isCommercialDocument = docType === 'commercial' || docType === 'contract_appendix';
  const isSketchDocument = docType === 'sketch';
  const isCostReportDocument = docType === 'cost_report';
  const canEditCommercial = Boolean(user && user.role !== 'dealer');
  const hasDocumentEditor = isPaintDocument || isDeliveryDocument || isCommercialDocument;
  const previewUrl = useMemo(
    () => isGuest ? undefined : `${getProjectDocumentPreviewUrl(projectId, docType)}?token=${encodeURIComponent(token)}&v=${previewVersion}${isCommercialDocument && selectedRevision !== undefined ? `&quote_revision=${selectedRevision}` : ''}`,
    [docType, isGuest, isCommercialDocument, projectId, token, previewVersion, selectedRevision],
  );

  useEffect(() => {
    if (isCommercialDocument && iframeRef.current?.contentDocument?.body) iframeRef.current.contentDocument.body.style.zoom = String(zoom / 100);
  }, [isCommercialDocument, zoom]);
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

  const loadCommercialQuote = useCallback(async () => {
    setQuoteConfirmation(null);
    if (!isOpen || !isCommercialDocument || isGuest) return;
    setIsQuoteLoading(true);
    setPendingQuote(null);
    setPreviewToken('');
    const loadVersion = ++quoteLoadVersion.current;
    try {
      const [publicState, history, current] = await Promise.all([
        selectedRevision === undefined ? getPublicQuote(projectId) : getQuoteRevision(projectId, selectedRevision),
        listQuoteRevisions(projectId),
        canEditCommercial && selectedRevision === undefined ? getInternalQuote(projectId) : null,
      ]);
      if (loadVersion !== quoteLoadVersion.current) return;
      setQuote(publicState);
      setRevisions(history);
      setPendingQuote(current?.pending_quote ?? null);
      setPreviewToken(current?.preview_token ?? '');
    } catch (error) {
      if (loadVersion !== quoteLoadVersion.current) return;
      setQuote(null);
      toast.error(requestError(error, 'Не удалось рассчитать коммерческое предложение'));
    } finally {
      if (loadVersion === quoteLoadVersion.current) setIsQuoteLoading(false);
    }
  }, [canEditCommercial, isCommercialDocument, isGuest, isOpen, projectId, selectedRevision]);

  useEffect(() => {
    if (!isOpen) {
      quoteLoadVersion.current += 1;
      setQuoteConfirmation(null);
      setPreviewSrcDoc('');
      setIsDirty(false);
      setPaintRows([]);
      setPaintColors([]);
      setDeliveryData(parseDeliveryData());
      setQuote(null);
      setPendingQuote(null);
      setPreviewToken('');
      setSelectedRevision(undefined);
      setRevisions([]);
      return;
    }
    loadGuestPreview();
    loadCommercialQuote();
  }, [isOpen, loadCommercialQuote, loadGuestPreview]);

  useEffect(() => {
    if (!isOpen || !isPaintDocument) return;
    let cancelled = false;
    getProject(projectId)
      .then(project => {
        if (cancelled) return;
        const colors = projectPaintColors(project.sections);
        const defaultColor = colors.length === 1 ? colors[0] : '';
        setPaintColors(colors);
        setPaintRows(
          parsePaintRows(project.paint_manual_rows).map(row => (
            row.color || !defaultColor ? row : { ...row, color: defaultColor }
          )),
        );
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
    if (!isOpen || !isDeliveryDocument) return;
    let cancelled = false;
    getProject(projectId)
      .then(project => {
        if (cancelled) return;
        setDeliveryData(parseDeliveryData(project.delivery_note_data));
      })
      .catch(() => {
        if (!cancelled) toast.error('Не удалось загрузить реквизиты накладной');
      });
    return () => { cancelled = true; };
  }, [isDeliveryDocument, isOpen, projectId]);

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'dirty' && (docType === 'glass' || docType === 'delivery')) setIsDirty(true);
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [docType]);

  const updateDeliveryData = (updates: Partial<DeliveryNoteData>) => {
    setDeliveryData(current => ({ ...current, ...updates }));
    setIsDirty(true);
  };

  const collectDeliveryPlaces = useCallback(() => {
    const places: Record<string, string> = {};
    const doc = iframeRef.current?.contentDocument;
    doc?.querySelectorAll<HTMLElement>('[data-delivery-place-key]').forEach(element => {
      const key = element.dataset.deliveryPlaceKey;
      if (key) places[key] = element.textContent?.trim() || '';
    });
    return places;
  }, []);

  const saveDeliveryData = async (
    showToast = true,
    refreshPreview = true,
  ): Promise<boolean> => {
    setIsSavingDelivery(true);
    try {
      const savedData: DeliveryNoteData = {
        ...deliveryData,
        places: {
          ...deliveryData.places,
          ...collectDeliveryPlaces(),
        },
      };
      await updateProject(projectId, {
        delivery_note_data: JSON.stringify(savedData),
      });
      setDeliveryData(savedData);
      setIsDirty(false);
      if (showToast) toast.success('Накладная сохранена');
      if (refreshPreview) {
        if (isGuest) await loadGuestPreview();
        else setPreviewVersion(value => value + 1);
      }
      return true;
    } catch {
      toast.error('Не удалось сохранить накладную');
      return false;
    } finally {
      setIsSavingDelivery(false);
    }
  };

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
    setIsDirty(true);
  };

  const addPaintRow = () => {
    setPaintRows(rows => [
      ...rows,
      normalizePaintRow({ color: paintColors.length === 1 ? paintColors[0] : '' }),
    ]);
    setIsDirty(true);
  };

  const removePaintRow = (id: string) => {
    setPaintRows(rows => rows.filter(row => row.id !== id));
    setIsDirty(true);
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
      setIsDirty(false);
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

  const handleRefreshQuote = () => {
    if (isQuoteSaving || isQuoteLoading || selectedRevision !== undefined) return;
    setQuoteConfirmation(captureQuoteConfirmation('revision', projectId, pendingQuote, previewToken, quote));
  };

  const handleFreezeQuote = () => {
    if (isQuoteSaving || isQuoteLoading || selectedRevision !== undefined) return;
    setQuoteConfirmation(captureQuoteConfirmation('freeze', projectId, pendingQuote, previewToken, quote));
  };

  const confirmQuote = async () => {
    const confirmed = quoteConfirmation;
    if (!confirmed || isQuoteSaving || isQuoteLoading || confirmed.projectId !== projectId || selectedRevision !== undefined) return;
    setIsQuoteSaving(true);
    try {
      if (confirmed.action === 'revision') {
        await refreshQuote(confirmed.projectId, confirmed.previewToken);
        setIsDirty(false);
      } else {
        setQuote(await freezeQuote(confirmed.projectId, confirmed.previewToken));
      }
      await loadCommercialQuote();
      setPreviewVersion(value => value + 1);
      toast.success(confirmed.action === 'revision' ? 'Цены и редакция коммерческого предложения обновлены' : 'КП зафиксировано');
    } catch (error) {
      setQuoteConfirmation(null);
      toast.error(requestError(error, 'Не удалось зафиксировать КП'));
      await loadCommercialQuote();
    }
    finally { setIsQuoteSaving(false); }
  };

  const handleDownload = async (format: DocumentFileFormat) => {
    setDownloadingFormat(format);
    try {
      if (isCommercialDocument && !quote?.export_allowed) {
        toast.error('Экспорт заблокирован: заполните отсутствующие цены и устраните предупреждения');
        return;
      }
      if (isPaintDocument) {
        const saved = await savePaintRows();
        if (!saved) return;
      }
      if (isDeliveryDocument) {
        const saved = await saveDeliveryData(false, false);
        if (!saved) return;
      }
      const changes = collectChanges();
      await downloadProjectDocument(
        projectId,
        docType,
        format,
        `${title}_${projectNumber}.${format}`,
        changes,
        isCommercialDocument ? selectedRevision : undefined,
      );
      setIsDirty(false);
      if (isCommercialDocument) {
        await loadCommercialQuote();
        setPreviewVersion(value => value + 1);
      }
    } catch (error) {
      toast.error(requestError(error, `Ошибка генерации ${format.toUpperCase()}`));
    } finally {
      setDownloadingFormat(null);
    }
  };

  const handleClose = () => {
    if (isDirty && !window.confirm('Есть несохранённые правки в документе. Закрыть без скачивания?')) {
      return;
    }
    setQuoteConfirmation(null);
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className={`fixed inset-0 z-50 flex items-center justify-center ${fullScreen ? "" : "p-3"}`}>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={handleClose}
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
          />
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0, y: 20 }}
            className={`relative w-full ${fullScreen ? "h-screen" : "max-w-7xl"} bg-modal border border-tint/25 rounded-2xl sm:rounded-[2rem] shadow-2xl shadow-black/20 overflow-hidden flex flex-col z-10`}
            style={{ maxHeight: fullScreen ? '100dvh' : '96dvh' }}
          >
            {quoteConfirmation && <QuoteConfirmationDialog confirmation={quoteConfirmation} busy={isQuoteSaving || isQuoteLoading} onConfirm={() => void confirmQuote()} onCancel={() => setQuoteConfirmation(null)} />}
            <div className="px-5 py-4 sm:px-8 sm:py-5 border-b border-tint/20 flex items-center justify-between flex-shrink-0">
              <div>
                <h2 className="text-lg font-bold">{title}</h2>
                <p className="text-xs text-fg/40 mt-0.5">
                  {projectNumber}
                  {isDirty && <span className="ml-2 text-yellow-400">● правки попадут в документ</span>}
                </p>
              </div>
              <button aria-label="Закрыть документ" onClick={handleClose} className="text-fg/20 hover:text-fg transition-colors ml-4">
                <X className="w-5 h-5" />
              </button>
            </div>

            {isPaintDocument && (
              <div className="px-5 py-4 sm:px-8 bg-page border-b border-tint/20 space-y-3 flex-shrink-0">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-widest text-fg/45">Ручные строки покраски</div>
                    <div className="text-[11px] text-fg/35 mt-1">Добавляются в документы вместе с расчетными строками</div>
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
                    <datalist id={`paint-colors-${projectId}`}>
                      {paintColors.map(color => <option key={color} value={color} />)}
                    </datalist>
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
                          list={`paint-colors-${projectId}`}
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
                          placeholder="С припуском"
                          title="Полная длина с припуском: RS1313 и RS1315 +80 мм, остальные +50 мм. Пусто — рассчитать автоматически."
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

            {isDeliveryDocument && (
              <div className="px-5 py-4 sm:px-8 bg-page border-b border-tint/20 flex-shrink-0">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <div className="text-xs font-bold uppercase tracking-widest text-fg/45">Реквизиты накладной</div>
                  <button
                    type="button"
                    onClick={() => saveDeliveryData()}
                    disabled={isSavingDelivery}
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-accent/30 bg-accent/15 text-accent text-xs font-bold uppercase tracking-wider hover:bg-accent/25 disabled:opacity-50"
                  >
                    {isSavingDelivery ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Сохранить
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Дата</span>
                    <select
                      value={deliveryData.dateMode}
                      onChange={event => updateDeliveryData({ dateMode: event.target.value as DeliveryDateMode })}
                      className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                    >
                      <option value="blank">Не заполнять</option>
                      <option value="today">Сегодня</option>
                      <option value="custom">Указать дату</option>
                    </select>
                  </label>
                  {deliveryData.dateMode === 'custom' ? (
                    <label className="space-y-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Дата накладной</span>
                      <input
                        type="date"
                        value={deliveryData.date}
                        onChange={event => updateDeliveryData({ date: event.target.value })}
                        className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                      />
                    </label>
                  ) : null}
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Контактное лицо</span>
                    <input
                      value={deliveryData.contact}
                      onChange={event => updateDeliveryData({ contact: event.target.value })}
                      className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Доставка / выгрузка / монтаж</span>
                    <input
                      value={deliveryData.delivery}
                      onChange={event => updateDeliveryData({ delivery: event.target.value })}
                      className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                    />
                  </label>
                  <label className="space-y-1 sm:col-span-2 lg:col-start-1 lg:col-span-3">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Примечание</span>
                    <input
                      value={deliveryData.note}
                      onChange={event => updateDeliveryData({ note: event.target.value })}
                      className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                    />
                  </label>
                </div>
              </div>
            )}

            {isCommercialDocument && (
              <div className="px-4 py-2 border-b border-tint/20 flex flex-wrap items-center gap-3 text-xs">
                {isQuoteLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                {quote && <span>Редакция {quote.revision} · {quote.status === 'fixed' ? 'зафиксирована' : 'черновик'}</span>}
                {quote?.stale && <span className="text-amber-600">Есть изменения после расчёта</span>}
                {canEditCommercial && selectedRevision === undefined && quote?.status === 'draft' && (
                  <button type="button" disabled={isQuoteSaving || isQuoteLoading || !pendingQuote?.export_allowed || !previewToken} onClick={() => void handleFreezeQuote()} className="rounded-lg border border-accent/35 px-2 py-1 text-accent disabled:opacity-40">Зафиксировать КП</button>
                )}
                {canEditCommercial && selectedRevision === undefined && quote?.status === 'fixed' && quote.stale && (
                  <button type="button" disabled={isQuoteSaving || isQuoteLoading || !pendingQuote?.export_allowed || !previewToken} onClick={handleRefreshQuote} className="flex gap-1 items-center text-accent disabled:opacity-40">
                    <RefreshCw className="h-3 w-3" /> Новая редакция
                  </button>
                )}
                <label className="flex items-center gap-1">Редакция<select aria-label="Редакция КП" className="rounded border border-tint/30 bg-page px-1 py-1" disabled={isQuoteSaving || isQuoteLoading} value={selectedRevision ?? ''} onChange={event => { setQuoteConfirmation(null); setQuote(null); setSelectedRevision(event.target.value ? Number(event.target.value) : undefined); setPreviewVersion(value => value + 1); }}><option value="">Текущая</option>{revisions.map(revision => <option key={revision.revision} value={revision.revision}>№{revision.revision} · {new Date(revision.fixed_at).toLocaleDateString('ru-RU')} · {revision.grand_total} ₽</option>)}</select></label>
                {selectedRevision !== undefined && <span className="text-fg/65">Архивная редакция · только просмотр и экспорт</span>}
                {quote?.status === 'draft' && <span className="text-fg/65">Черновик: экспорт не фиксирует цену</span>}
                <span className="text-fg/50">Стоимость и скидки — на экране заказа</span>
                <label className="ml-auto flex items-center gap-1">Масштаб
                  <select aria-label="Масштаб документа" value={zoom} onChange={event => setZoom(Number(event.target.value))} className="rounded border border-tint/30 bg-page px-1 py-1">
                    {[50, 65, 80, 100, 125, 150].map(value => <option key={value} value={value}>{value}%</option>)}
                  </select>
                </label>
                <button type="button" onClick={() => setFullScreen(value => !value)} aria-label={fullScreen ? 'Выйти из полноэкранного просмотра' : 'Полноэкранный просмотр'}>
                  {fullScreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                </button>
              </div>
            )}
            {isCommercialDocument && selectedRevision === undefined && quote?.status === 'fixed' && quote.stale && <div className="border-b border-tint/20 bg-surface/30 px-4 py-3 text-xs" aria-label="Проверка новой редакции">
              <div className="flex flex-wrap gap-x-6 gap-y-2"><span>В документе: <b>{money(quote.totals.grand_total)}</b> · КП №{quote.revision}</span>{pendingQuote && <><span>{pendingQuote.export_allowed ? 'Текущий расчёт:' : 'Учтённая часть, не итог:'} <b>{money(pendingQuote.totals.grand_total)}</b></span>{pendingQuote.export_allowed && <span>Изменение: <b>{Number(pendingQuote.totals.grand_total) - Number(quote.totals.grand_total) > 0 ? '+' : ''}{money(Number(pendingQuote.totals.grand_total) - Number(quote.totals.grand_total))}</b></span>}</>}</div>
              {isQuoteLoading ? <p className="mt-1">Обновляем текущий расчёт…</p> : pendingQuote ? <><p className="mt-1 text-fg/65">Пока вы не подтвердите новую редакцию, просмотр и скачивание используют сохранённое КП. Новые скидки и цены в него не подставляются.</p>{!pendingQuote.export_allowed && <p role="alert" className="mt-2 text-amber-700">Новую редакцию пока нельзя зафиксировать: {pendingQuote.warnings.join(' ')} Исправьте текущий расчёт на экране заказа.</p>}</> : <p role="alert" className="mt-1 text-amber-700">Текущий расчёт не загружен. Закройте и снова откройте документ перед созданием новой редакции.</p>}
            </div>}
            {isCommercialDocument && quote && !quote.export_allowed && <div role="alert" className="border-b border-amber-500/30 bg-amber-500/5 px-4 py-2 text-xs text-amber-700"><b>Расчёт неполный. Экспорт недоступен.</b> {quote.warnings.join(' ')} Вернитесь в «Стоимость заказа», чтобы устранить причины.</div>}

            <div className="overflow-y-auto bg-gray-100" style={{ height: isCommercialDocument ? (fullScreen ? 'calc(100dvh - 170px)' : 'calc(96dvh - 175px)') : hasDocumentEditor ? 'calc(90vh - 295px)' : 'calc(90vh - 130px)' }}>
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
                  onLoad={() => {
                    if (isCommercialDocument && iframeRef.current?.contentDocument?.body) iframeRef.current.contentDocument.body.style.zoom = String(zoom / 100);
                  }}
                />
              )}
            </div>

            <div className="px-5 py-4 sm:px-8 sm:py-5 bg-page border-t border-tint/20 flex items-center justify-end flex-shrink-0">
              <div className="flex items-center gap-2 flex-wrap justify-end">
                {([
                  ['pdf', 'PDF', Download],
                  ...(isSketchDocument || isPaintDocument || docType === 'glass' || docType === 'hardware_order' || isCommercialDocument
                    ? [['docx', 'Word', FileText] as const]
                    : []),
                  ...(isPaintDocument || docType === 'glass' || docType === 'hardware_order' || isDeliveryDocument || isCostReportDocument
                    ? [['xlsx', 'Excel', FileSpreadsheet] as const]
                    : []),
                ] as const).map(([format, label, Icon]) => (
                  <button
                    key={format}
                    onClick={() => handleDownload(format)}
                    disabled={downloadingFormat !== null || (isCommercialDocument && (isQuoteSaving || isQuoteLoading || !quote?.export_allowed))}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent/15 hover:bg-accent/25 text-accent border border-accent/30 font-bold transition-all disabled:opacity-50 text-sm"
                  >
                    {downloadingFormat === format
                      ? <Loader2 className="w-4 h-4 animate-spin" />
                      : <Icon className="w-4 h-4" />}
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
