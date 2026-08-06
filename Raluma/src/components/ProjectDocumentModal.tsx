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
  QuoteManualService,
  refreshQuote,
  updateQuoteConfig,
  updateQuoteOverrides,
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
const makeServiceId = () => `service-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

function emptyService(): QuoteManualService {
  return { id: makeServiceId(), name: '', quantity: '1', unit: 'шт.', base_cost: '0' };
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
  const [isMarginApprovalDirty, setIsMarginApprovalDirty] = useState(false);
  const { user, canManagePrices } = useAuthStore();

  const token = localStorage.getItem('access_token') ?? '';
  const isGuest = !token;
  const isPaintDocument = docType === 'paint';
  const isDeliveryDocument = docType === 'delivery';
  const isCommercialDocument = docType === 'commercial';
  const canEditCommercial = canManagePrices();
  const canOverrideCommercial = canEditCommercial;
  const canOverrideMargin = user?.role === 'admin' || user?.role === 'superadmin';
  const missingPrices = internalQuote?.missing_prices ?? [];
  const commercialWarnings: string[] = Array.from(new Set<string>(
    internalQuote ? internalQuote.pending_warnings : (quote?.warnings ?? []),
  ));
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
        setIsMarginApprovalDirty(false);
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
      setIsMarginApprovalDirty(false);
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
    if (Object.prototype.hasOwnProperty.call(updates, 'margin_override_comment')) {
      setIsMarginApprovalDirty(true);
    }
    setInternalQuote(current => current ? {
      ...current,
      config: { ...current.config, ...updates },
    } : current);
    setIsDirty(true);
  };

  const updateService = (id: string, updates: Partial<QuoteManualService>) => {
    if (!internalQuote) return;
    patchCommercialConfig({
      services: internalQuote.config.services.map(service => (
        service.id === id ? { ...service, ...updates } : service
      )),
    });
  };

  const addService = () => {
    if (!internalQuote) return;
    patchCommercialConfig({ services: [...internalQuote.config.services, emptyService()] });
  };

  const removeService = (id: string) => {
    if (!internalQuote) return;
    patchCommercialConfig({
      services: internalQuote.config.services.filter(service => service.id !== id),
    });
  };

  const updateMissingPriceOverride = (
    sku: string,
    updates: Partial<{ cost: string; comment: string }>,
  ) => {
    if (!internalQuote) return;
    const current = internalQuote.config.overrides.find(row => row.sku === sku);
    const next = current
      ? internalQuote.config.overrides.map(row => row.sku === sku ? { ...row, ...updates } : row)
      : [...internalQuote.config.overrides, { sku, cost: '', comment: '', ...updates }];
    patchCommercialConfig({ overrides: next });
  };

  const saveCommercialConfig = async (): Promise<boolean> => {
    if (!internalQuote) return false;
    const incompleteOverride = internalQuote.config.overrides.find(row => (
      (row.cost || row.comment.trim()) && (!row.cost || !row.comment.trim())
    ));
    if (canOverrideCommercial && incompleteOverride) {
      toast.error(`Для разовой цены ${incompleteOverride.sku} укажите цену и обоснование`);
      return false;
    }
    setIsQuoteSaving(true);
    try {
      const config = internalQuote.config;
      await updateQuoteConfig(projectId, {
        vat_mode: config.vat_mode,
        vat_rate: config.vat_rate,
        validity_days: config.validity_days,
        manufacturing_term: config.manufacturing_term,
        payment_terms: config.payment_terms,
        services: config.services,
      });
      if (canOverrideCommercial) {
        await updateQuoteOverrides(
          projectId,
          config.overrides.filter(row => row.sku && row.cost && row.comment.trim()),
          canOverrideMargin && isMarginApprovalDirty
            ? config.margin_override_comment
            : undefined,
        );
      }
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
        setIsMarginApprovalDirty(false);
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
                    {(quote.stale || commercialWarnings.length > 0) && (
                      <div className="space-y-2">
                        {quote.stale && (
                          <div className="flex items-start gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-200">
                            <AlertTriangle className="w-4 h-4 mt-0.5 flex-none" />
                            Проект, каталог или условия изменились после расчёта. Для новой редакции нажмите «Обновить цены».
                          </div>
                        )}
                        {commercialWarnings.map(warning => (
                          <div key={warning} className="flex items-start gap-2 rounded-xl border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                            <AlertTriangle className="w-4 h-4 mt-0.5 flex-none" />
                            {warning}
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="rounded-xl border border-tint/20 bg-black/10 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wider text-fg/35">До скидки</div>
                        <div className="mt-1 text-sm font-bold">{formatQuoteMoney(quote.totals.before_discount)}</div>
                      </div>
                      <div className="rounded-xl border border-tint/20 bg-black/10 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wider text-fg/35">Скидка</div>
                        <div className="mt-1 text-sm font-bold text-accent">{formatQuoteMoney(quote.totals.discount)}</div>
                      </div>
                      <div className="rounded-xl border border-tint/20 bg-black/10 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wider text-fg/35">НДС</div>
                        <div className="mt-1 text-sm font-bold">{formatQuoteMoney(quote.totals.vat)}</div>
                      </div>
                      <div className="rounded-xl border border-accent/30 bg-accent/10 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wider text-accent/70">Итого</div>
                        <div className="mt-1 text-sm font-bold text-accent">{formatQuoteMoney(quote.totals.grand_total)}</div>
                      </div>
                    </div>

                    {canEditCommercial && internalQuote && (
                      <div className="space-y-3 border-t border-tint/15 pt-4">
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                          <label className="space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Режим НДС</span>
                            <select
                              value={internalQuote.config.vat_mode}
                              onChange={event => patchCommercialConfig({ vat_mode: event.target.value as InternalQuoteState['config']['vat_mode'] })}
                              className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                            >
                              <option value="none">Без НДС</option>
                              <option value="included">НДС включён</option>
                              <option value="on_top">НДС сверху</option>
                            </select>
                          </label>
                          <label className="space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Ставка НДС, %</span>
                            <input
                              type="number" min="0" max="100" step="0.01"
                              value={internalQuote.config.vat_rate}
                              onChange={event => patchCommercialConfig({ vat_rate: event.target.value })}
                              className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                            />
                          </label>
                          <label className="space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Срок действия, дней</span>
                            <input
                              type="number" min="1" max="365"
                              value={internalQuote.config.validity_days}
                              onChange={event => patchCommercialConfig({ validity_days: Number(event.target.value) })}
                              className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                            />
                          </label>
                          <label className="space-y-1 sm:col-span-2">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Срок изготовления</span>
                            <input
                              value={internalQuote.config.manufacturing_term}
                              onChange={event => patchCommercialConfig({ manufacturing_term: event.target.value })}
                              placeholder="Например: 20 рабочих дней"
                              className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                            />
                          </label>
                          <label className="space-y-1 sm:col-span-2 lg:col-span-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Условия оплаты</span>
                            <input
                              value={internalQuote.config.payment_terms}
                              onChange={event => patchCommercialConfig({ payment_terms: event.target.value })}
                              placeholder="Например: 70/30"
                              className="w-full h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50"
                            />
                          </label>
                        </div>

                        <div>
                          <div className="flex items-center justify-between gap-3 mb-2">
                            <div>
                              <div className="text-[10px] font-bold uppercase tracking-wider text-fg/40">Ручные услуги</div>
                              <div className="text-[10px] text-fg/30 mt-0.5">Базовая цена является внутренней и не попадает в дилерское КП.</div>
                            </div>
                            <button type="button" onClick={addService} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-tint/25 text-xs text-accent hover:bg-tint/10">
                              <Plus className="w-3.5 h-3.5" /> Услуга
                            </button>
                          </div>
                          {internalQuote.config.services.length > 0 && (
                            <div className="space-y-2">
                              {internalQuote.config.services.map(service => (
                                <div key={service.id} className="grid grid-cols-[minmax(150px,1fr)_80px_110px_120px_34px] gap-2">
                                  <input value={service.name} onChange={event => updateService(service.id, { name: event.target.value })} placeholder="Наименование" className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50" />
                                  <input type="number" min="0.01" step="0.01" value={service.quantity} onChange={event => updateService(service.id, { quantity: event.target.value })} placeholder="Кол-во" className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50" />
                                  <select value={service.unit} onChange={event => updateService(service.id, { unit: event.target.value })} className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50">
                                    {['п.м.', 'шт.', 'кв.м.'].map(unit => <option key={unit} value={unit}>{unit}</option>)}
                                  </select>
                                  <input type="number" min="0" step="0.01" value={service.base_cost} onChange={event => updateService(service.id, { base_cost: event.target.value })} placeholder="Базовая цена" className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50" />
                                  <button type="button" onClick={() => removeService(service.id)} aria-label="Удалить услугу" className="h-9 w-9 rounded-lg border border-red-500/25 text-red-400/75 hover:bg-red-500/10 flex items-center justify-center"><Trash2 className="w-4 h-4" /></button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {missingPrices.length > 0 && (
                          <div className="rounded-xl border border-yellow-500/25 bg-yellow-500/5 p-3 space-y-2">
                            <div className="text-[10px] font-bold uppercase tracking-wider text-yellow-300">
                              {canOverrideCommercial ? 'Разовые цены для этого КП' : 'Нет действующих цен в каталоге'}
                            </div>
                            {missingPrices.map(item => {
                              const override = internalQuote.config.overrides.find(row => row.sku === item.sku);
                              return (
                                <div key={item.sku} className={`grid gap-2 items-center ${canOverrideCommercial ? 'grid-cols-[minmax(160px,1fr)_120px_minmax(180px,1fr)]' : 'grid-cols-1'}`}>
                                  <div className="text-xs"><span className="font-mono text-yellow-200">{item.sku}</span><span className="text-fg/40"> · {item.name} · {item.unit}</span></div>
                                  {canOverrideCommercial && (
                                    <>
                                      <input type="number" min="0" step="0.01" value={override?.cost || ''} onChange={event => updateMissingPriceOverride(item.sku, { cost: event.target.value })} placeholder="Цена" className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50" />
                                      <input value={override?.comment || ''} onChange={event => updateMissingPriceOverride(item.sku, { comment: event.target.value })} placeholder="Обязательное обоснование" className="h-9 rounded-lg bg-black/15 border border-tint/20 px-2 text-xs outline-none focus:border-accent/50" />
                                    </>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {canOverrideMargin && internalQuote.margin_approval.required && (
                          <div className="space-y-1">
                            <label className="block space-y-1">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-red-300">Обоснование исключения по минимальной цене</span>
                              <input
                                value={internalQuote.config.margin_override_comment}
                                onChange={event => patchCommercialConfig({ margin_override_comment: event.target.value })}
                                placeholder="Комментарий обязателен для согласования этой редакции"
                                className="w-full h-9 rounded-lg bg-black/15 border border-red-500/25 px-2 text-xs outline-none focus:border-red-400/60"
                              />
                            </label>
                            {internalQuote.margin_approval.valid ? (
                              <div className="text-[10px] text-emerald-300/80">
                                Согласовано для редакции {internalQuote.margin_approval.approved_revision}
                                {internalQuote.margin_approval.approved_by ? ` · пользователь #${internalQuote.margin_approval.approved_by}` : ''}
                                {internalQuote.margin_approval.approved_at ? ` · ${new Date(internalQuote.margin_approval.approved_at).toLocaleString('ru-RU')}` : ''}
                              </div>
                            ) : internalQuote.margin_approval.comment ? (
                              <div className="text-[10px] text-yellow-200/80">
                                Предыдущее согласование недействительно после изменения ценового контекста. Введите новое обоснование.
                              </div>
                            ) : null}
                          </div>
                        )}
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
                  ...(isPaintDocument || docType === 'glass' || docType === 'hardware_order' || isCommercialDocument
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
