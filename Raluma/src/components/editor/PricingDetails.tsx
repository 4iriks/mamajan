import { useState } from 'react';
import type { QuotePriceOverride } from '../../api/quotes';
import type { useProjectEconomics } from '../../hooks/useProjectEconomics';
import { useAuthStore } from '../../store/authStore';
import { money, validMoney } from '../../utils/money';

type State = ReturnType<typeof useProjectEconomics>;
type Row = Record<string, unknown>;
const rows = (value: unknown): Row[] => Array.isArray(value) ? value.filter((row): row is Row => !!row && typeof row === 'object') : [];
const input = 'h-9 min-w-0 w-full rounded-lg border border-tint/30 bg-black/5 px-2 text-xs';
const button = 'rounded-lg border border-tint/30 px-3 py-2 text-xs text-accent disabled:opacity-40';

export function PriceRepair({ state }: { state: State }) {
  const [sku, setSku] = useState('');
  const [price, setPrice] = useState('');
  const [reason, setReason] = useState('');
  const [approval, setApproval] = useState('');
  const [formError, setFormError] = useState('');
  const { isAdmin, canManagePrices } = useAuthStore();
  if (!canManagePrices()) return null;
  const overrides = state.config?.overrides || [];
  const sectionRows = rows(state.internal?.calculation.sections);
  const allowedSkus = new Set(sectionRows.flatMap(section => [...rows(section.bom), ...rows(section.issues)].map(row => String(row.sku || ''))).filter(Boolean));
  const save = async () => {
    if (!sku.trim() || !reason.trim() || !validMoney(price)) { setFormError('Нужны артикул, цена от 0 и причина изменения.'); return; }
    if (!allowedSkus.has(sku.trim())) { setFormError('Разовая цена доступна только для позиции расчётной комплектации секции. Для ручной позиции задайте цену в дополнительных комплектующих; для связанной с каталогом — исправьте каталог.'); return; }
    const next: QuotePriceOverride = { sku: sku.trim(), cost: price.replace(',', '.'), comment: reason.trim() };
    if (await state.saveOverrides([...overrides.filter(row => row.sku !== next.sku), next])) { setSku(''); setPrice(''); setReason(''); setFormError(''); }
  };
  return <>
    {state.internal?.margin_approval.required && <section aria-label="Согласование минимальной цены" className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-xs">
      <h4 className="font-semibold">{state.internal.margin_approval.valid ? 'Цена ниже порога согласована' : 'Нужно согласовать цену ниже порога'}</h4>
      <p className="mt-1">{state.internal.margin_approval.valid ? 'Разрешение действует для текущего расчёта. При изменении цены или состава заказа потребуется повторная проверка.' : isAdmin() ? 'Вы можете разрешить цену ниже минимального порога как администратор. Укажите причину — она сохранится вместе с вашим подтверждением.' : 'Измените цену/скидку либо попросите администратора или суперадминистратора согласовать исключение.'}</p>
      {isAdmin() && !state.internal.margin_approval.valid && <div className="mt-2 flex flex-col gap-2 sm:flex-row"><input className={input} aria-label="Причина разрешения минимальной цены" placeholder="Почему допускается цена ниже порога" value={approval} onChange={event => setApproval(event.target.value)} /><button type="button" className={`${button} shrink-0`} disabled={state.busy || state.refreshing || !approval.trim()} onClick={() => void state.saveOverrides(overrides, approval.trim())}>Разрешить цену ниже порога</button></div>}
      <p className="mt-2 text-fg/65">Разрешение не заменяет недостающие цены и не снимает другие ошибки расчёта. Зафиксированное КП не изменяется автоматически.</p>
    </section>}
    <details className="mt-3 rounded-lg border border-tint/25 p-3 text-xs">
    <summary className="cursor-pointer font-semibold">Разовые цены и разрешения</summary>
    <p className="my-2 text-fg/65">Разовая цена продажи заменяет цену каталога для этого артикула во всём заказе. Это цена детали до общих условий системы: далее применяются общая наценка и скидка системы, дилерские условия и скидки заказа. Себестоимость и минимальная наценка каталога сохраняются. Укажите цену за расчётную единицу и основание.</p>
    {state.internal?.missing_prices.map(row => allowedSkus.has(row.sku) ? <button className={`${button} mr-2 mb-2`} key={row.sku} onClick={() => setSku(row.sku)}>{row.sku} · {row.name} · {row.unit || 'единица каталога'}</button> : <p key={row.sku} className="my-2 text-amber-700">{row.name}: задайте цену в дополнительных комплектующих (ручная позиция) или в каталоге.</p>)}
    {overrides.map(row => <div key={row.sku} className="mb-2 flex flex-wrap items-center gap-2"><b>{row.sku}</b><span>{money(row.cost)} · {row.comment}</span><button disabled={state.busy} className={button} onClick={() => void state.saveOverrides(overrides.filter(item => item.sku !== row.sku))}>Убрать разовую цену</button></div>)}
    <div className="grid gap-2 sm:grid-cols-[120px_130px_1fr_auto]"><input className={input} aria-label="Артикул разовой цены" placeholder="Артикул" value={sku} onChange={event => setSku(event.target.value)} /><input className={input} aria-label="Разовая цена за единицу" placeholder="Цена, ₽/ед." value={price} inputMode="decimal" onChange={event => setPrice(event.target.value)} /><input className={input} aria-label="Причина разовой цены" placeholder="Обоснование" value={reason} onChange={event => setReason(event.target.value)} /><button className={button} disabled={state.busy} onClick={() => void save()}>Применить</button></div>
    {formError && <p role="alert" className="mt-2 text-red-600">{formError}</p>}
    </details>
  </>;
}

export function PricingDetails({ state }: { state: State }) {
  const { canManagePrices } = useAuthStore();
  const quote = state.currentQuote;
  if (!quote) return null;
  const calculation = state.internal?.calculation || {};
  const dealer = calculation.dealer_terms as Record<string, string> | undefined;
  return <details className="mt-3 rounded-lg border border-tint/20 p-3 text-xs"><summary className="cursor-pointer font-semibold">Как получилась сумма</summary>
    <p className="my-2 text-fg/65">Себестоимость → проценты комплектующих выбранной системы (или разовая цена детали) → общая наценка и скидка системы → наценка и скидка дилера, если заданы → скидки категорий → общая % → общая ₽ → округление только общего итога.</p>
    <p className="my-2 text-fg/65">Суммы строк сохраняют копейки. Цена за единицу показана округлённо; её умножение вручную может отличаться от суммы строки на копейки.</p>
    <div className="overflow-auto"><table className="w-full min-w-[620px] text-left"><thead><tr>{['Позиция', 'Количество', 'До скидок', 'Скидка', 'Итого'].map(label => <th key={label} className="p-2 font-medium text-fg/60">{label}</th>)}</tr></thead><tbody>{quote.lines.map(line => <tr key={line.id} className="border-t border-tint/15"><td className="p-2">{line.name}{line.component_details?.size && <span className="block text-fg/60">{line.component_details.size} мм</span>}{line.component_details?.pricing_quantity && <span className="block text-fg/60">Расчёт: {line.component_details.pricing_quantity} {line.component_details.pricing_unit} · {money(line.component_details.pricing_unit_final_price)}/{line.component_details.pricing_unit} после скидок</span>}</td><td className="p-2">{line.quantity} {line.unit}</td><td className="p-2 whitespace-nowrap">{money(line.line_total_before_discount)}</td><td className="p-2 whitespace-nowrap">{money(line.line_discount_amount)}</td><td className="p-2 whitespace-nowrap font-semibold">{money(line.line_total)}</td></tr>)}</tbody></table></div>
    {canManagePrices() && <details className="mt-3"><summary className="cursor-pointer">Себестоимость и источники цен · служебная информация</summary>
      {rows(calculation.cost_warnings).length > 0 && <p className="my-2 rounded border border-amber-500/30 p-2 text-amber-700">Себестоимость не задана: {rows(calculation.cost_warnings).map(row => String(row.name)).join(', ')}. Это неизвестные затраты, а не нулевые; полную прибыль по заказу оценивать нельзя.</p>}
      {state.quote?.status === 'fixed' && <p className="my-2 text-fg/65">Ниже расшифрован текущий расчёт заказа, а не сохранённая редакция КП. Суммы действующего КП показаны отдельно выше.</p>}
      {dealer && <p className="my-2">Дилер: наценка {dealer.dealer_markup_percent || 0}%; скидки: профиль {dealer.profile_discount_percent || 0}%, изделия {dealer.construction_discount_percent || 0}%, аксессуары {dealer.component_discount_percent || 0}%, услуги {dealer.service_discount_percent || 0}%. Они применяются после настройки системы, до скидок заказа.</p>}
      {rows(calculation.sections).map(section => <details key={String(section.section_id)} className="mt-2"><summary className="cursor-pointer">{String(section.name)} · до условий дилера {money(section.internal_total)} · минимально {money(section.minimum_total)}</summary>{section.system_stages && <p className="my-2">Комплектующие {money((section.system_stages as Row).subtotal)} → общая наценка {String((section.system_stages as Row).markup_percent)}%: {money((section.system_stages as Row).after_markup)} → общая скидка {String((section.system_stages as Row).discount_percent)}%: {money((section.system_stages as Row).total)}.</p>}<div className="overflow-auto"><table className="w-full min-w-[650px]"><thead><tr>{['Артикул / версия', 'Расход', 'Себестоимость', 'После отходов', 'После наценки', 'После процентов детали'].map(label => <th key={label} className="p-2 text-left font-medium">{label}</th>)}</tr></thead><tbody>{rows(section.bom).map((line, index) => {
        const stages = (line.price_stages as { construction?: Row } | undefined)?.construction;
        return <tr key={index} className="border-t border-tint/15"><td className="p-2">{String(line.sku)} / {String(line.price_version_id ?? 'без версии')}<span className="block text-fg/60">{String(line.finish || '')}</span>{line.sale_price_override != null && <span className="block text-amber-700">Разовая цена продажи: {money(line.sale_price_override)}/{String(line.price_unit || line.unit || '')}</span>}</td><td className="p-2">{String(line.quantity)} {String(line.price_unit || line.unit || '')}</td><td className="p-2">{line.cost_known === false ? 'не задана' : money(line.base_cost_total)}</td><td className="p-2">{line.cost_known === false ? '—' : money(stages?.after_waste)}</td><td className="p-2">{line.cost_known === false ? '—' : money(stages?.after_markup)}</td><td className="p-2">{money(line.internal_total)}</td></tr>;
      })}</tbody></table></div></details>)}
      {[...rows(calculation.project_extras), ...rows(calculation.services)].map((row, index) => <p className="mt-2" key={index}>{String(row.name || 'Дополнительная позиция')}: себестоимость {row.cost_known === false ? 'не задана' : money(row.base_cost_total ?? row.actual_cost_total)}; цена до скидок {money(row.internal_total)}{row.pricing_quantity ? `; расчётный расход ${row.pricing_quantity} ${row.pricing_unit}` : ''}.</p>)}
    </details>}
  </details>;
}
