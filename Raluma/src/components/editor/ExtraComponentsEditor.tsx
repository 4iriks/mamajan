import React, { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { listHardwareCatalogOptions } from '../../api/catalog';
import type { HardwareCatalogOption } from '../../api/catalog';
import { toast } from '../../store/toastStore';
import { ExtraComponent, INP, LBL, SEL } from './types';

interface ExtraComponentsEditorProps {
  items?: ExtraComponent[];
  onChange: (items: ExtraComponent[]) => void;
}

const makeId = () => `ec-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

function normalizeItem(item?: Partial<ExtraComponent>): ExtraComponent {
  return {
    id: item?.id ?? makeId(),
    sku: item?.sku ?? '',
    name: item?.name ?? '',
    color: item?.color ?? '',
    size: item?.size ?? '',
    qty: item?.qty ?? '',
  };
}

export const ExtraComponentsEditor: React.FC<ExtraComponentsEditorProps> = ({
  items = [],
  onChange,
}) => {
  const [catalog, setCatalog] = useState<HardwareCatalogOption[]>([]);

  useEffect(() => {
    let cancelled = false;
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
        if (!cancelled) toast.error('Не удалось загрузить каталог комплектующих');
      });
    return () => { cancelled = true; };
  }, []);

  const rows = useMemo(() => items.map(normalizeItem), [items]);

  const commit = (next: ExtraComponent[]) => {
    onChange(next.map(normalizeItem));
  };

  const updateRow = (id: string, updates: Partial<ExtraComponent>) => {
    commit(rows.map(row => row.id === id ? { ...row, ...updates } : row));
  };

  const addRow = () => {
    commit([...rows, normalizeItem()]);
  };

  const removeRow = (id: string) => {
    commit(rows.filter(row => row.id !== id));
  };

  const selectCatalogItem = (row: ExtraComponent, sku: string) => {
    const item = catalog.find(candidate => candidate.sku === sku);
    updateRow(row.id!, {
      sku,
      name: item?.name ?? '',
    });
  };

  return (
    <div className="space-y-3">
      {rows.length > 0 && (
        <div className="hidden lg:grid grid-cols-[minmax(180px,1.4fr)_120px_minmax(120px,0.8fr)_120px_90px_36px] gap-2 px-1">
          {['Название', 'Артикул', 'Цвет', 'Размер, мм', 'Кол-во', ''].map(label => (
            <span key={label} className="text-[9px] font-bold uppercase tracking-widest text-fg/25">
              {label}
            </span>
          ))}
        </div>
      )}

      <div className="space-y-2">
        {rows.map(row => (
          <div
            key={row.id}
            className="grid grid-cols-1 lg:grid-cols-[minmax(180px,1.4fr)_120px_minmax(120px,0.8fr)_120px_90px_36px] gap-2 items-end"
          >
            <div className="space-y-1 lg:space-y-0">
              <label className={`${LBL} lg:hidden`}>Название</label>
              <select
                value={row.sku}
                onChange={e => selectCatalogItem(row, e.target.value)}
                className={SEL}
              >
                <option value="">— Выберите из каталога —</option>
                {catalog.map(item => (
                  <option key={item.id} value={item.sku}>
                    {item.name} {item.sku}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1 lg:space-y-0">
              <label className={`${LBL} lg:hidden`}>Артикул</label>
              <input
                value={row.sku}
                readOnly
                className={`${INP} text-fg/55`}
                placeholder="—"
              />
            </div>

            <div className="space-y-1 lg:space-y-0">
              <label className={`${LBL} lg:hidden`}>Цвет</label>
              <input
                value={row.color}
                onChange={e => updateRow(row.id!, { color: e.target.value })}
                className={INP}
                placeholder="RAL / анод"
              />
            </div>

            <div className="space-y-1 lg:space-y-0">
              <label className={`${LBL} lg:hidden`}>Размер, мм</label>
              <input
                value={row.size}
                onChange={e => updateRow(row.id!, { size: e.target.value })}
                className={INP}
                placeholder="Напр. 1200"
              />
            </div>

            <div className="space-y-1 lg:space-y-0">
              <label className={`${LBL} lg:hidden`}>Кол-во</label>
              <input
                value={row.qty}
                onChange={e => updateRow(row.id!, { qty: e.target.value })}
                className={INP}
                placeholder="шт"
              />
            </div>

            <button
              type="button"
              onClick={() => removeRow(row.id!)}
              className="h-10 w-10 rounded-xl border border-red-500/25 bg-red-500/5 text-red-400/70 hover:bg-red-500/15 hover:text-red-300 transition-colors flex items-center justify-center"
              aria-label="Удалить комплектующее"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {rows.length === 0 && (
        <div className="rounded-xl border border-dashed border-tint/30 bg-hi/[0.03] px-4 py-5 text-center text-xs font-bold uppercase tracking-widest text-fg/25">
          Дополнительные комплектующие не добавлены
        </div>
      )}

      <button
        type="button"
        onClick={addRow}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-tint/35 bg-tint/10 text-accent text-xs font-bold uppercase tracking-wider hover:bg-tint/20 transition-colors"
      >
        <Plus className="w-4 h-4" />
        Добавить комплектующее
      </button>
    </div>
  );
};
