import type { QuoteDiscountRule } from '../../api/quotes';
import type { useProjectEconomics } from '../../hooks/useProjectEconomics';
import { useAuthStore } from '../../store/authStore';
import { categoryNames, money } from '../../utils/money';
import { PriceRepair, PricingDetails } from './PricingDetails';

const quickFields = [
  { scope: 'order', mode: 'fixed', label: 'Общая, ₽' },
  { scope: 'order', mode: 'percent', label: 'Общая, %' },
  { scope: 'construction', mode: 'percent', label: 'На изделия, %' },
  { scope: 'component', mode: 'percent', label: 'На аксессуары, %' },
] as const;
const input = 'h-9 min-w-0 w-full rounded-lg border border-tint/30 bg-black/5 px-2 text-xs';
const button = 'rounded-lg border border-tint/30 px-3 py-2 text-xs text-accent disabled:opacity-40';

export function ProjectEconomics({ state }: { state: ReturnType<typeof useProjectEconomics> }) {
  const { quote, config, internal, dirty, busy, refreshing, error, patch, save, reload } = state;
  const { canManagePrices } = useAuthStore();
  const rules = config?.discounts || [];
  const quickIndices = quickFields.map(field => rules.findIndex(rule => rule.scope === field.scope && rule.mode === field.mode));
  const additionalRules = rules.map((rule, index) => ({ rule, index })).filter(({ index }) => !quickIndices.includes(index));
  const updateRule = (index: number, changes: Partial<QuoteDiscountRule>) => patch({ discounts: rules.map((rule, i) => i === index ? { ...rule, ...changes } : rule) });
  const warnings = [...new Set([...(quote?.warnings || []), ...(internal?.pending_warnings || [])])];
  const incomplete = quote && !quote.export_allowed;
  return <section className="rounded-xl border border-tint/30 bg-surface/40 p-3 mb-3" aria-label="Стоимость и скидки">
    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
      <h3 className="text-sm font-bold">Стоимость заказа</h3>
      <button type="button" disabled={busy || refreshing} onClick={() => dirty ? void save() : void reload()} className={button}>{busy ? 'Сохранение…' : refreshing ? 'Пересчитываем…' : dirty ? 'Сохранить и пересчитать' : 'Обновить расчёт'}</button>
    </div>
    {error && <p role="alert" className="text-xs text-red-600 mb-2">{error}</p>}
    {!quote && !error && <p className="text-xs">Загрузка стоимости…</p>}
    {warnings.length > 0 && <div role={incomplete ? 'alert' : 'status'} className="my-2 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-xs"><b>{incomplete ? 'Расчёт неполный — экспорт КП недоступен' : 'Проверьте расчёт'}</b><ul className="mt-1 list-disc pl-4">{warnings.map(warning => <li key={warning}>{warning}</li>)}</ul></div>}
    {quote && <>
      <div className="grid grid-cols-2 gap-2 my-3 lg:grid-cols-4">{Object.entries(categoryNames).map(([category, label]) => <div key={category} className="rounded-lg bg-black/5 p-2 text-xs"><span className="block text-fg/60">{label}</span><b>{money(quote.lines.filter(line => line.category === category).reduce((sum, line) => sum + Number(line.line_total), 0))}</b></div>)}</div>
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
        <span>До скидок заказа и дилера: <b>{money(quote.totals.before_discount)}</b></span><span>Скидки: <b>{money(quote.totals.discount)}</b></span>
        {quote.money_presentation_version === 2 && <span>Округление итога: <b>{Number(quote.totals.rounding_adjustment || 0) > 0 ? '+' : ''}{money(quote.totals.rounding_adjustment)}</b></span>}
        <span>{incomplete ? 'Учтённая часть, не итог:' : 'Итого:'} <b className={`text-base ${incomplete ? 'text-amber-700' : ''}`}>{money(quote.totals.grand_total)}</b></span>
      </div>
      {(dirty || refreshing || error) && <p className="mt-2 text-xs text-amber-700">{dirty ? 'Есть несохранённые изменения. Суммы обновятся после сохранения.' : 'Не используйте показанную сумму до успешного обновления расчёта.'}</p>}
      <p className="mt-2 text-xs text-fg/65">{quote.status === 'fixed' ? `КП №${quote.revision} зафиксировано: выше его сохранённые цены. ${quote.stale ? 'Есть новые изменения — создайте новую редакцию в окне документа.' : 'Редактирование заказа не переписывает это КП.'}` : 'Черновик: цены ещё не зафиксированы. Фиксация и история — в окне КП.'}</p>
      <PricingDetails state={state} />
    </>}
    {config && <fieldset disabled={busy} className="mt-3">
      <h4 className="mb-2 text-xs font-semibold">Скидки заказа</h4>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">{quickFields.map((field, index) => <label key={field.label} className="text-xs space-y-1"><span>{field.label}</span><input aria-label={field.label} type="number" min="0" max={field.mode === 'percent' ? 100 : undefined} step="0.01" className={input} value={rules[quickIndices[index]]?.value ?? '0'} onChange={event => {
        if (quickIndices[index] >= 0) updateRule(quickIndices[index], { value: event.target.value });
        else patch({ discounts: [...rules, { id: `discount-${crypto.randomUUID()}`, name: field.label, scope: field.scope, mode: field.mode, value: event.target.value }] });
      }} /></label>)}</div>
      <p className="mt-2 text-xs text-fg/60">Порядок: категории → общая в % → общая в ₽. Дилерские условия применяются раньше. Скидка на аксессуары не изменяет отдельную продажу профиля.</p>
      <details className="mt-2 text-xs"><summary className="cursor-pointer text-fg/65">Дополнительные правила ({additionalRules.length})</summary><p className="my-2 text-fg/60">Дополнительные скидки применяются последовательно внутри своего этапа, не заменяют основные. Две скидки по 10% дают общую скидку 19%.</p>
        {additionalRules.map(({ rule, index }) => <div key={rule.id} className="grid grid-cols-[1fr_115px_75px_42px_28px] gap-1 mb-1"><input className={input} value={rule.name} aria-label="Название скидки" onChange={event => updateRule(index, { name: event.target.value })} /><select aria-label="Категория скидки" className={input} value={rule.scope} onChange={event => updateRule(index, { scope: event.target.value as QuoteDiscountRule['scope'] })}><option value="order">Весь заказ</option><option value="construction">Изделия</option><option value="component">Аксессуары</option><option value="profile">Профили</option><option value="service">Услуги</option></select><input aria-label="Величина дополнительной скидки" className={input} type="number" min="0" max={rule.mode === 'percent' ? 100 : undefined} step="0.01" value={rule.value} onChange={event => updateRule(index, { value: event.target.value })} /><button type="button" aria-label="Единица скидки" onClick={() => updateRule(index, { mode: rule.mode === 'percent' ? 'fixed' : 'percent' })}>{rule.mode === 'percent' ? '%' : '₽'}</button><button type="button" aria-label="Удалить скидку" onClick={() => patch({ discounts: rules.filter((_, i) => i !== index) })}>×</button></div>)}
        <button type="button" className={`${button} mt-2`} onClick={() => patch({ discounts: [...rules, { id: `discount-${crypto.randomUUID()}`, name: 'Дополнительная скидка', scope: 'service', mode: 'percent', value: '0' }] })}>+ Добавить правило</button>
      </details>
      <details className="mt-3 text-xs"><summary className="cursor-pointer font-semibold">Услуги ({config.services.length})</summary><p className="my-2 text-fg/60">Цена продажи за единицу услуги — отдельно от необязательной себестоимости. Далее применяются дилерские условия и скидки заказа.</p>
        {config.services.map((service, index) => {
          const update = (changes: Partial<typeof service>) => patch({ services: config.services.map((row, i) => i === index ? { ...row, ...changes } : row) });
          return <div key={service.id} className="mb-2 grid gap-2 rounded-lg border border-tint/25 p-2 sm:grid-cols-2 lg:grid-cols-6"><label className="sm:col-span-2">Название<input className={input} value={service.name} onChange={event => update({ name: event.target.value })} /></label><label>Количество<input className={input} inputMode="decimal" value={service.quantity} onChange={event => update({ quantity: event.target.value })} /></label><label>Единица<select className={input} value={service.unit} onChange={event => update({ unit: event.target.value })}>{[...new Set(['шт.', 'п.м.', 'кв.м.', service.unit])].map(unit => <option key={unit}>{unit}</option>)}</select></label><label>Цена продажи, ₽/ед.<input className={input} inputMode="decimal" value={service.sale_price ?? service.base_cost ?? ''} onChange={event => update({ sale_price: event.target.value })} /></label>{canManagePrices() && <label>Себестоимость, ₽/ед.<input className={input} placeholder="Не задана" inputMode="decimal" value={service.actual_cost ?? ''} onChange={event => update({ actual_cost: event.target.value || null })} /></label>}<button className={button} onClick={() => patch({ services: config.services.filter((_, i) => i !== index) })}>Удалить услугу</button></div>;
        })}
        <button className={button} onClick={() => patch({ services: [...config.services, { id: crypto.randomUUID(), name: '', quantity: '1', unit: 'шт.', sale_price: '' }] })}>+ Добавить услугу</button>
      </details>
      <details className="mt-3 text-xs"><summary className="cursor-pointer font-semibold">Условия договора и срок КП</summary><div className="grid gap-2 mt-2 sm:grid-cols-[1fr_1fr_125px]"><label>Условия оплаты<input aria-label="Условия оплаты" className={input} value={config.payment_terms} onChange={event => patch({ payment_terms: event.target.value })} placeholder="По согласованию" /></label><label>Срок изготовления<input className={input} value={config.manufacturing_term} onChange={event => patch({ manufacturing_term: event.target.value })} /></label><label>КП действует, дней<input className={input} type="number" min="1" max="365" value={config.validity_days} onChange={event => patch({ validity_days: Number(event.target.value) })} /></label></div></details>
    </fieldset>}
    <PriceRepair state={state} />
  </section>;
}
