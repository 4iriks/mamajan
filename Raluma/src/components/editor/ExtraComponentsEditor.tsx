import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, PackagePlus, RefreshCw, Search, Trash2 } from 'lucide-react';

import { listHardwareCatalogOptions } from '../../api/catalog';
import type { HardwareCatalogOption } from '../../api/catalog';
import { filterCatalogOptions } from './extraComponentsCatalog';
import { ExtraComponent, INP, LBL, SEL } from './types';

interface ExtraComponentsEditorProps {
  items?: ExtraComponent[];
  onChange: (items: ExtraComponent[]) => void;
}

const makeId = () => `ec-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

function normalizeItem(item?: Partial<ExtraComponent>): ExtraComponent {
  return {
    id: item?.id ?? makeId(),
    catalogItemId: item?.catalogItemId,
    finishVariantId: item?.finishVariantId,
    sku: item?.sku ?? '',
    name: item?.name ?? '',
    category: item?.category,
    color: item?.color ?? '',
    finishName: item?.finishName ?? item?.color ?? '',
    requiresPaint: item?.requiresPaint ?? false,
    unitPrice: item?.unitPrice ?? '',
    size: item?.size ?? '',
    qty: item?.qty ?? '1',
    unit: item?.unit ?? 'шт',
    imageFile: item?.imageFile ?? '',
    deliveryStage: item?.deliveryStage ?? 'both',
  };
}

function assetUrl(filename?: string) {
  return filename
    ? `/api/catalog/profile-assets/${encodeURIComponent(filename)}`
    : '';
}

export const ExtraComponentsEditor: React.FC<ExtraComponentsEditorProps> = ({
  items = [],
  onChange,
}) => {
  const [catalog, setCatalog] = useState<HardwareCatalogOption[]>([]);
  const [query, setQuery] = useState('');
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError('');
    listHardwareCatalogOptions()
      .then(rows => {
        if (!cancelled) setCatalog(filterCatalogOptions(rows, ''));
      })
      .catch(() => {
        if (!cancelled) setLoadError('Не удалось загрузить каталог комплектующих');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [reloadToken]);

  const rows = useMemo(
    () => items.map((item, index) => normalizeItem({
      ...item,
      id: item.id ?? `saved-${index}-${item.sku}`,
    })),
    [items],
  );
  const matches = useMemo(
    () => filterCatalogOptions(catalog, query).slice(0, 30),
    [catalog, query],
  );

  const commit = useCallback((next: ExtraComponent[]) => {
    onChange(next.map(normalizeItem));
  }, [onChange]);

  const updateRow = (id: string, updates: Partial<ExtraComponent>) => {
    commit(rows.map(row => row.id === id ? { ...row, ...updates } : row));
  };

  const addCatalogItem = (item: HardwareCatalogOption) => {
    const availableVariants = (item.finishVariants || []).filter(variant => variant.isActive);
    const firstVariant = availableVariants[0];
    commit([...rows, normalizeItem({
      catalogItemId: item.id,
      finishVariantId: firstVariant?.id,
      sku: item.sku,
      name: item.name,
      category: item.category,
      color: '',
      finishName: firstVariant?.name === 'Без цвета' ? '' : firstVariant?.name || '',
      requiresPaint: firstVariant?.requiresPaint ?? false,
      unitPrice: undefined,
      unit: item.unit || 'шт',
      imageFile: item.imageFile || '',
      qty: '1',
    })]);
    setQuery('');
    setCatalogOpen(false);
  };

  const addManualItem = () => {
    commit([...rows, normalizeItem({
      category: 'component',
      name: '',
      sku: '',
      color: '',
      requiresPaint: false,
      size: '',
      qty: '1',
      unit: 'шт',
    })]);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-tint/25 bg-surface/35 p-3">
        <label className={LBL}>Поиск по артикулу или названию</label>
        <div className="relative mt-1.5">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg/30" />
          <input
            value={query}
            onChange={event => setQuery(event.target.value)}
            onFocus={() => setCatalogOpen(true)}
            onBlur={() => setCatalogOpen(false)}
            onKeyDown={event => {
              if (event.key === 'Escape') setCatalogOpen(false);
            }}
            className={`${INP} pl-10`}
            placeholder="Например, RS1005 или уплотнитель"
            aria-label="Поиск комплектующих"
          />
        </div>

        {loading && (
          <div className="flex items-center gap-2 px-2 py-4 text-xs text-fg/45">
            <Loader2 className="h-4 w-4 animate-spin text-accent" />
            Загружаем каталог…
          </div>
        )}
        {!loading && loadError && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-500/25 bg-red-500/5 px-3 py-2.5 text-xs text-red-300">
            <span>{loadError}</span>
            <button
              type="button"
              onClick={() => setReloadToken(value => value + 1)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-400/30 px-2.5 py-1.5 font-bold"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Повторить
            </button>
          </div>
        )}
        {!loading && !loadError && catalogOpen && (
          <div className="mt-2 max-h-64 space-y-1 overflow-y-auto rounded-xl border border-tint/20 bg-page/60 p-1.5">
            {matches.map(item => (
              <button
                key={item.id}
                type="button"
                onMouseDown={event => event.preventDefault()}
                onClick={() => addCatalogItem(item)}
                className="grid w-full grid-cols-[44px_105px_minmax(0,1fr)_28px] items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-tint/15"
              >
                <span className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg border border-tint/20 bg-white/90">
                  {item.imageFile ? (
                    <img
                      src={assetUrl(item.imageFile)}
                      alt=""
                      className="max-h-full max-w-full object-contain"
                      onError={event => { event.currentTarget.style.display = 'none'; }}
                    />
                  ) : <PackagePlus className="h-4 w-4 text-slate-400" />}
                </span>
                <span className="font-mono text-xs font-bold text-accent">{item.sku}</span>
                <span className="min-w-0 text-xs text-fg/70">{item.name}</span>
                <PackagePlus className="h-4 w-4 text-accent/55" />
              </button>
            ))}
            {matches.length === 0 && (
              <div className="px-3 py-4 text-center text-xs text-fg/35">
                В каталоге ничего не найдено
              </div>
            )}
          </div>
        )}
        <button
          type="button"
          onClick={addManualItem}
          className="mt-3 inline-flex min-h-[42px] items-center gap-2 rounded-xl border border-accent/35 bg-accent/10 px-3.5 py-2 text-xs font-bold text-accent hover:bg-accent/15"
        >
          <PackagePlus className="h-4 w-4" />
          Добавить вручную
        </button>
      </div>

      <div className="space-y-3">
        {rows.map(row => {
            const catalogItem = catalog.find(item => item.id === row.catalogItemId);
            const isManual = !row.catalogItemId;
            const finishVariants = (catalogItem?.finishVariants || []).filter(
              variant => variant.isActive,
            );
            return (
          <article
            key={row.id}
            className="rounded-2xl border border-tint/25 bg-surface/30 p-3 sm:p-4"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-tint/25 bg-white/90 p-1">
                {row.imageFile ? (
                  <img
                    src={assetUrl(row.imageFile)}
                    alt={row.name}
                    className="max-h-full max-w-full object-contain"
                    onError={event => { event.currentTarget.style.display = 'none'; }}
                  />
                ) : <PackagePlus className="h-6 w-6 text-slate-400" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-mono text-xs font-bold text-accent">{row.sku || (isManual ? 'Ручная позиция' : 'Без артикула')}</div>
                <div className="mt-1 text-sm font-semibold text-fg/80">{row.name || (isManual ? 'Заполните название ниже' : 'Без названия')}</div>
              </div>
              <button
                type="button"
                onClick={() => commit(rows.filter(item => item.id !== row.id))}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-red-500/25 bg-red-500/5 text-red-400/70 hover:bg-red-500/15 hover:text-red-300"
                aria-label={`Удалить ${row.sku || row.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6">
              {isManual && (
                <label className="space-y-1 sm:col-span-2">
                  <span className={LBL}>Название *</span>
                  <input
                    value={row.name}
                    onChange={event => updateRow(row.id!, { name: event.target.value })}
                    className={INP}
                    placeholder="Например, уголок монтажный"
                    required
                  />
                </label>
              )}
              {isManual && (
                <label className="space-y-1">
                  <span className={LBL}>Артикул</span>
                  <input
                    value={row.sku}
                    onChange={event => updateRow(row.id!, { sku: event.target.value })}
                    className={INP}
                    placeholder="Необязательно"
                  />
                </label>
              )}
              {finishVariants.length > 0 && (
                <label className="space-y-1">
                  <span className={LBL}>Исполнение</span>
                  <select
                    value={row.finishVariantId || ''}
                    onChange={event => {
                      const variant = finishVariants.find(item => item.id === Number(event.target.value));
                      updateRow(row.id!, {
                        finishVariantId: variant?.id,
                        finishName: variant?.name || '',
                        color: variant?.requiresPaint ? row.color : '',
                        requiresPaint: variant?.requiresPaint ?? false,
                        unitPrice: undefined,
                      });
                    }}
                    className={SEL}
                  >
                    {finishVariants.map(variant => (
                      <option key={variant.id ?? variant.name} value={variant.id}>{variant.name}</option>
                    ))}
                  </select>
                </label>
              )}
              {(isManual || row.requiresPaint) && (
                <label className="space-y-1">
                  <span className={LBL}>Цвет</span>
                  <input
                    value={row.color}
                    onChange={event => updateRow(row.id!, {
                      color: event.target.value,
                      requiresPaint: isManual
                        ? Boolean(event.target.value.trim())
                        : row.requiresPaint,
                    })}
                    className={INP}
                    placeholder="Если указан — попадёт в покраску"
                  />
                </label>
              )}
              <label className="space-y-1">
                <span className={LBL}>Размер</span>
                <input value={row.size} onChange={event => updateRow(row.id!, { size: event.target.value })} className={INP} placeholder="1200 мм" />
              </label>
              <label className="space-y-1">
                <span className={LBL}>Количество</span>
                <input type="number" min="0" step="any" value={row.qty} onChange={event => updateRow(row.id!, { qty: event.target.value })} className={INP} />
              </label>
              <label className="space-y-1">
                <span className={LBL}>Единица</span>
                <div className={`${INP} flex min-h-[42px] items-center text-fg/60`}>
                  {row.unit || 'шт'}
                </div>
              </label>
              <label className="space-y-1">
                <span className={LBL}>Этап</span>
                <select
                  value={row.deliveryStage || 'both'}
                  onChange={event => updateRow(row.id!, {
                    deliveryStage: event.target.value as ExtraComponent['deliveryStage'],
                  })}
                  className={SEL}
                >
                  <option value="both">Оба этапа</option>
                  <option value="1">Этап 1</option>
                  <option value="2">Этап 2</option>
                </select>
              </label>
            </div>
          </article>
            );
          })}
      </div>

      {rows.length === 0 && (
        <div className="rounded-xl border border-dashed border-tint/30 bg-hi/[0.03] px-4 py-5 text-center text-xs font-bold uppercase tracking-widest text-fg/25">
          Выберите позицию из каталога или добавьте её вручную
        </div>
      )}
    </div>
  );
};
