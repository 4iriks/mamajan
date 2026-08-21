import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Download,
  AlertTriangle,
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
  getInternalQuote,
  getPublicQuote,
  InternalQuoteState,
  PublicQuote,
  QuoteDiscountRule,
  refreshQuote,
  updateQuoteConfig,
} from '../api/quotes';
import { useAuthStore } from '../store/authStore';

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
const makeDiscountId = () => `discount-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

function emptyDiscount(): QuoteDiscountRule {
  return {
    id: makeDiscountId(),
    name: 'Скидка',
    scope: 'order',
    mode: 'percent',
    value: '0',
  };
}

function formatQuoteMoney(value?: string | number) {
  return `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽`;
}

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
  const [internalQuote, setInternalQuote] = useState<InternalQuoteState | null>(null);
  const [isQuoteLoading, setIsQuoteLoading] = useState(false);
  const [isQuoteSaving, setIsQuoteSaving] = useState(false);
  const { user } = useAuthStore();

  const token = localStorage.getItem('access_token') ?? '';
  const isGuest = !token;
  const isPaintDocument = docType === 'paint';
  const isDeliveryDocument = docType === 'delivery';
  const isCommercialDocument = docType === 'commercial' || docType === 'contract_appendix';
  const isSketchDocument = docType === 'sketch';
  const canEditCommercial = Boolean(user && user.role !== 'dealer');
  const hasDocumentEditor = isPaintDocument || isDeliveryDocument || isCommercialDocument;
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

  const loadCommercialQuote = useCallback(async () => {
    if (!isOpen || !isCommercialDocument || isGuest) return;
    setIsQuoteLoading(true);
    try {
      const publicState = await getPublicQuote(projectId);
      setQuote(publicState);
      if (canEditCommercial) {
        setInternalQuote(await getInternalQuote(projectId));
      } else {
        setInternalQuote(null);
      }
    } catch (error) {
      toast.error(requestError(error, 'Не удалось рассчитать коммерческое предложение'));
    } finally {
      setIsQuoteLoading(false);
    }
  }, [canEditCommercial, isCommercialDocument, isGuest, isOpen, projectId]);

  useEffect(() => {
    if (!isOpen) {
      setPreviewSrcDoc('');
      setIsDirty(false);
      setPaintRows([]);
      setPaintColors([]);
      setDeliveryData(parseDeliveryData());
      setQuote(null);
      setInternalQuote(null);
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

  const patchCommercialConfig = (
    updates: Partial<InternalQuoteState['config']>,
  ) => {
    setInternalQuote(current => current ? {
      ...current,
      config: { ...current.config, ...updates },
    } : current);
    setIsDirty(true);
  };

  const updateDiscount = (id: string, updates: Partial<QuoteDiscountRule>) => {
    if (!internalQuote) return;
    patchCommercialConfig({
      discounts: (internalQuote.config.discounts || []).map(discount => (
        discount.id === id ? { ...discount, ...updates } : discount
      )),
    });
  };

  const addDiscount = () => {
    if (!internalQuote) return;
    patchCommercialConfig({
      discounts: [...(internalQuote.config.discounts || []), emptyDiscount()],
    });
  };

  const removeDiscount = (id: string) => {
    if (!internalQuote) return;
    patchCommercialConfig({
      discounts: (internalQuote.config.discounts || []).filter(discount => discount.id !== id),
    });
  };

  const saveCommercialConfig = async (): Promise<boolean> => {
    if (!internalQuote) return false;
    setIsQuoteSaving(true);
    try {
      const config = internalQuote.config;
      await updateQuoteConfig(projectId, {
        validity_days: config.validity_days,
        manufacturing_term: config.manufacturing_term,
        payment_terms: config.payment_terms,
        services: config.services,
        discounts: config.discounts || [],
      });
      await loadCommercialQuote();
      setPreviewVersion(value => value + 1);
      setIsDirty(false);
      toast.success('Условия коммерческого предложения сохранены');
      return true;
    } catch (error) {
      toast.error(requestError(error, 'Не удалось сохранить условия предложения'));
      return false;
    } finally {
      setIsQuoteSaving(false);
    }
  };

  const handleRefreshQuote = async () => {
    setIsQuoteSaving(true);
    try {
      setQuote(await refreshQuote(projectId));
      if (canEditCommercial) {
        setInternalQuote(await getInternalQuote(projectId));
      }
      setPreviewVersion(value => value + 1);
      setIsDirty(false);
      toast.success('Цены и редакция коммерческого предложения обновлены');
    } catch (error) {
      toast.error(requestError(error, 'Не удалось обновить коммерческое предложение'));
      await loadCommercialQuote();
    } finally {
      setIsQuoteSaving(false);
    }
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
                  {isDirty && <span className="ml-2 text-yellow-400">● правки попадут в документ</span>}
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
              <div className="px-5 py-4 sm:px-8 bg-page border-b border-tint/20 flex-shrink-0 max-h-[42vh] overflow-y-auto">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-xs font-bold uppercase tracking-widest text-fg/45">Расчёт стоимости</div>
                      {quote && (
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                          quote.status === 'fixed'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                            : 'border-yellow-500/30 bg-yellow-500/10 text-yellow-300'
                        }`}>
                          Редакция {quote.revision} · {quote.status === 'fixed' ? 'зафиксирована' : 'черновик'}
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-fg/35 mt-1">
                      PDF фиксирует первую редакцию; Word до первого PDF использует текущий черновик.
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {canEditCommercial && internalQuote && (
                      <button
                        type="button"
                        onClick={saveCommercialConfig}
                        disabled={isQuoteSaving}
                        className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-accent/30 bg-accent/15 text-accent text-xs font-bold uppercase tracking-wider hover:bg-accent/25 disabled:opacity-50"
                      >
                        {isQuoteSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Сохранить
                      </button>
                    )}
                    {canEditCommercial && quote?.status === 'fixed' && quote.stale && (
                      <button
                        type="button"
                        onClick={handleRefreshQuote}
                        disabled={isQuoteSaving || !quote?.export_allowed}
                        className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-tint/30 bg-tint/10 text-fg/70 text-xs font-bold uppercase tracking-wider hover:bg-tint/20 disabled:opacity-40"
                        title="Проверить актуальный расчёт и зафиксировать следующую редакцию"
                      >
                        <RefreshCw className={`w-4 h-4 ${isQuoteSaving ? 'animate-spin' : ''}`} />
                        Обновить цены
                      </button>
                    )}
                  </div>
                </div>

                {isQuoteLoading && !quote ? (
                  <div className="h-24 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-accent" /></div>
                ) : quote ? (
                  <div className="mt-4 space-y-4">
                    {quote.stale && (
                      <div className="flex items-start gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-200">
                        <AlertTriangle className="w-4 h-4 mt-0.5 flex-none" />
                        Проект, каталог или условия изменились после расчёта. Для новой редакции нажмите «Обновить цены».
                      </div>
                    )}

                    {canEditCommercial && internalQuote ? (
                      <div className="space-y-3">
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-[120px_minmax(180px,1fr)_repeat(3,minmax(105px,135px))] xl:items-end">
                          <label className="space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Срок действия, дней</span>
                            <input
                              type="number" min="1" max="365"
                              value={internalQuote.config.validity_days}
                              onChange={event => patchCommercialConfig({ validity_days: Number(event.target.value) })}
                              className="h-10 w-full rounded-lg border border-tint/20 bg-black/15 px-2 text-xs outline-none focus:border-accent/50"
                            />
                          </label>
                          <label className="space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Условия оплаты</span>
                            <input
                              value={internalQuote.config.payment_terms}
                              onChange={event => patchCommercialConfig({ payment_terms: event.target.value })}
                              placeholder="Например: 70/30"
                              className="h-10 w-full rounded-lg border border-tint/20 bg-black/15 px-2 text-xs outline-none focus:border-accent/50"
                            />
                          </label>
                          <div className="flex h-[46px] flex-col justify-center rounded-lg border border-tint/20 bg-black/10 px-3">
                            <div className="text-[9px] uppercase tracking-wider text-fg/35">До скидки</div>
                            <div className="mt-0.5 truncate text-xs font-bold">{formatQuoteMoney(quote.totals.before_discount)}</div>
                          </div>
                          <div className="flex h-[46px] flex-col justify-center rounded-lg border border-tint/20 bg-black/10 px-3">
                            <div className="text-[9px] uppercase tracking-wider text-fg/35">Скидка</div>
                            <div className="mt-0.5 truncate text-xs font-bold text-accent">{formatQuoteMoney(quote.totals.discount)}</div>
                          </div>
                          <div className="flex h-[46px] flex-col justify-center rounded-lg border border-accent/30 bg-accent/10 px-3">
                            <div className="text-[9px] uppercase tracking-wider text-accent/70">Итого</div>
                            <div className="mt-0.5 truncate text-xs font-bold text-accent">{formatQuoteMoney(quote.totals.grand_total)}</div>
                          </div>
                        </div>

                        <div className="border-t border-tint/15 pt-3">
                          <div className="mb-2 flex items-center justify-between gap-3">
                            <div>
                              <div className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Скидки</div>
                              <div className="mt-0.5 text-[10px] text-fg/30">На весь заказ или выбранную категорию, в процентах либо рублях.</div>
                            </div>
                            <button type="button" onClick={addDiscount} className="inline-flex items-center gap-1.5 rounded-lg border border-tint/25 px-2.5 py-1.5 text-xs text-accent hover:bg-tint/10">
                              <Plus className="h-3.5 w-3.5" /> Скидка
                            </button>
                          </div>
                          {(internalQuote.config.discounts || []).length > 0 && (
                            <div className="space-y-2">
                              {(internalQuote.config.discounts || []).map(discount => (
                                <div key={discount.id} className="grid grid-cols-[minmax(130px,1fr)_150px_105px_34px] gap-2">
                                  <input value={discount.name} onChange={event => updateDiscount(discount.id, { name: event.target.value })} placeholder="Название" className="h-9 rounded-lg border border-tint/20 bg-black/15 px-2 text-xs outline-none focus:border-accent/50" />
                                  <select value={discount.scope} onChange={event => updateDiscount(discount.id, { scope: event.target.value as QuoteDiscountRule['scope'] })} className="h-9 rounded-lg border border-tint/20 bg-black/15 px-2 text-xs outline-none focus:border-accent/50">
                                    <option value="order">Весь заказ</option>
                                    <option value="construction">Конструкции</option>
                                    <option value="profile">Профили</option>
                                    <option value="component">Комплектующие</option>
                                    <option value="service">Услуги</option>
                                  </select>
                                  <div className="flex overflow-hidden rounded-lg border border-tint/20 bg-black/15">
                                    <input type="number" min="0" step="0.01" value={discount.value} onChange={event => updateDiscount(discount.id, { value: event.target.value })} className="min-w-0 flex-1 bg-transparent px-2 text-xs outline-none" />
                                    <button type="button" onClick={() => updateDiscount(discount.id, { mode: discount.mode === 'percent' ? 'fixed' : 'percent' })} className="border-l border-tint/20 px-2 text-xs font-bold text-accent">{discount.mode === 'percent' ? '%' : '₽'}</button>
                                  </div>
                                  <button type="button" onClick={() => removeDiscount(discount.id)} aria-label="Удалить скидку" className="flex h-9 w-9 items-center justify-center rounded-lg border border-red-500/25 text-red-400/75 hover:bg-red-500/10"><Trash2 className="h-4 w-4" /></button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                      </div>
                    ) : (
                      <div className="ml-auto grid w-full max-w-lg grid-cols-3 gap-2">
                        <div className="rounded-lg border border-tint/20 bg-black/10 px-3 py-2">
                          <div className="text-[9px] uppercase tracking-wider text-fg/35">До скидки</div>
                          <div className="mt-0.5 truncate text-xs font-bold">{formatQuoteMoney(quote.totals.before_discount)}</div>
                        </div>
                        <div className="rounded-lg border border-tint/20 bg-black/10 px-3 py-2">
                          <div className="text-[9px] uppercase tracking-wider text-fg/35">Скидка</div>
                          <div className="mt-0.5 truncate text-xs font-bold text-accent">{formatQuoteMoney(quote.totals.discount)}</div>
                        </div>
                        <div className="rounded-lg border border-accent/30 bg-accent/10 px-3 py-2">
                          <div className="text-[9px] uppercase tracking-wider text-accent/70">Итого</div>
                          <div className="mt-0.5 truncate text-xs font-bold text-accent">{formatQuoteMoney(quote.totals.grand_total)}</div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            )}

            <div className="overflow-y-auto bg-gray-100" style={{ height: isCommercialDocument ? 'min(40vh, 520px)' : hasDocumentEditor ? 'calc(90vh - 295px)' : 'calc(90vh - 130px)' }}>
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
              <div className="flex items-center gap-2 flex-wrap justify-end">
                {([
                  ['pdf', 'PDF', Download],
                  ...(isSketchDocument || isPaintDocument || docType === 'glass' || docType === 'hardware_order' || isCommercialDocument
                    ? [['docx', 'Word', FileText] as const]
                    : []),
                  ...(isPaintDocument || docType === 'glass' || docType === 'hardware_order' || isDeliveryDocument
                    ? [['xlsx', 'Excel', FileSpreadsheet] as const]
                    : []),
                ] as const).map(([format, label, Icon]) => (
                  <button
                    key={format}
                    onClick={() => handleDownload(format)}
                    disabled={downloadingFormat !== null || (isCommercialDocument && !quote?.export_allowed)}
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
