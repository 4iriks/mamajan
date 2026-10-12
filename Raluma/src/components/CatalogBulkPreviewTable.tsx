import type { CatalogPricingBulkResult } from '../api/catalog';
import { money } from '../utils/money';

export function CatalogBulkPreviewTable({ preview }: { preview: CatalogPricingBulkResult }) {
  const detached = preview.rows.filter(row => row.sourceBefore?.mode === 'auto').length;
  return <div className="mt-5 overflow-hidden rounded-xl border border-tint/25">
    <div className="bg-hi/[0.04] px-4 py-3 text-sm"><b>Будет изменено исполнений: {preview.count}</b></div>
    <p role="status" className="border-y border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm">
      Все выбранные исполнения будут использовать индивидуальные значения.
      {detached > 0 && <> Отключатся от готовых правил: <b>{detached}</b>. Будущие изменения правил больше не будут влиять на их проценты.</>}
      {' '}Незаполненные проценты сохранят текущие значения. Зафиксированные КП не изменятся.
    </p>
    <div className="max-h-72 overflow-auto">
      <table className="w-full min-w-[900px] text-left text-xs">
        <thead className="sticky top-0 bg-surface"><tr><th className="px-3 py-2">Позиция</th><th className="px-3 py-2">Исполнение</th><th className="px-3 py-2">Источник: было → станет</th><th className="px-3 py-2">Профиль: было → станет</th><th className="px-3 py-2">Конструкция: было → станет</th></tr></thead>
        <tbody className="divide-y divide-tint/15">{preview.rows.map(row => <tr key={`${row.itemId}-${row.finishCode}`}>
          <td className="px-3 py-2"><b className="font-mono">{row.sku}</b><div className="text-fg/60">{row.name}</div></td>
          <td className="px-3 py-2">{row.finishName}</td>
          <td className="px-3 py-2">{row.sourceBefore?.label || row.sourceBefore?.name || 'Текущие условия'} → <b>{row.sourceAfter?.label || 'Индивидуальные значения'}</b></td>
          <td className="px-3 py-2 font-mono">{money(row.before.profile.final)} → <b>{money(row.after.profile.final)}</b></td>
          <td className="px-3 py-2 font-mono">{money(row.before.construction.final)} → <b>{money(row.after.construction.final)}</b></td>
        </tr>)}</tbody>
      </table>
    </div>
  </div>;
}
