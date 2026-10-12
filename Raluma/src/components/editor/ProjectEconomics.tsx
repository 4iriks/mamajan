import type { QuoteDiscountRule } from '../../api/quotes';
import type { useProjectEconomics } from '../../hooks/useProjectEconomics';

const quickFields = [
  { scope: 'order', mode: 'fixed', label: 'Общая, ₽' },
  { scope: 'order', mode: 'percent', label: 'Общая, %' },
  { scope: 'construction', mode: 'percent', label: 'На изделия, %' },
  { scope: 'component', mode: 'percent', label: 'На аксессуары, %' },
] as const;
const input = 'h-8 min-w-0 w-full rounded-lg border border-tint/30 bg-black/5 px-2 text-xs';
const money = (value?: string) => `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽`;

export function ProjectEconomics({ state }: { state: ReturnType<typeof useProjectEconomics> }) {
  const { quote, config, dirty, busy, error, patch, save, reload } = state;
  const rules = config?.discounts || [];
  const quickIndices = quickFields.map(field => rules.findIndex(rule => rule.scope === field.scope && rule.mode === field.mode));
  const updateRule = (index: number, changes: Partial<QuoteDiscountRule>) => patch({ discounts: rules.map((rule, i) => i === index ? { ...rule, ...changes } : rule) });
  return <section className="rounded-xl border border-tint/30 bg-surface/40 p-3 mb-3" aria-label="Стоимость и скидки">
    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
      <h3 className="text-sm font-bold">Стоимость и скидки</h3>
      <button type="button" disabled={busy} onClick={() => dirty ? void save() : void reload()} className="text-xs text-accent border border-tint/30 rounded-lg px-3 py-1.5">
        {busy ? 'Сохранение…' : dirty ? 'Сохранить изменения' : 'Обновить расчёт'}
      </button>
    </div>
    {error && <p role="alert" className="text-xs text-red-500 mb-2">{error}</p>}
    {!quote && !error && <p className="text-xs">Загрузка стоимости…</p>}
    {quote && <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs mb-3">
      <span>До скидки: <b>{money(quote.totals.before_discount)}</b></span>
      <span>Скидка: <b>{money(quote.totals.discount)}</b></span>
      <span>Итого: <b className="text-base">{money(quote.totals.grand_total)}</b></span>
      {dirty && <span className="text-amber-600">Суммы обновятся после сохранения</span>}
    </div>}
    {quote?.status === 'fixed' && <p className="text-xs mb-2 text-fg/65">КП №{quote.revision} зафиксировано. {quote.stale ? 'Есть изменения: итог выше относится к сохранённому КП. Новая редакция создаётся в окне документа.' : 'Изменение скидок не перезаписывает его.'}</p>}
    {config && <fieldset disabled={busy}>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {quickFields.map((field, index) => <label key={field.label} className="text-xs space-y-1">
          <span>{field.label}</span><input aria-label={field.label} type="number" min="0" max={field.mode === 'percent' ? 100 : undefined} step="0.01" className={input}
            value={rules[quickIndices[index]]?.value ?? '0'} onChange={event => {
              if (quickIndices[index] >= 0) updateRule(quickIndices[index], { value: event.target.value });
              else patch({ discounts: [...rules, { id: `discount-${crypto.randomUUID()}`, name: field.label, scope: field.scope, mode: field.mode, value: event.target.value }] });
            }} />
        </label>)}
      </div>
      <div className="grid grid-cols-[1fr_125px] gap-2 mt-2">
        <label className="text-xs space-y-1"><span>Условия оплаты</span><input aria-label="Условия оплаты" className={input} value={config.payment_terms} onChange={event => patch({ payment_terms: event.target.value })} placeholder="По согласованию" /></label>
        <label className="text-xs space-y-1"><span>КП действует, дней</span><input className={input} type="number" min="1" max="365" value={config.validity_days} onChange={event => patch({ validity_days: Number(event.target.value) })} /></label>
      </div>
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-fg/65">Дополнительные правила скидок ({rules.filter((_, i) => !quickIndices.includes(i)).length})</summary>
        <p className="my-2 text-fg/60">Правила применяются в существующем порядке. Основные поля изменяют первое подходящее правило; остальные сохраняются.</p>
        {rules.map((rule, index) => <div key={rule.id} className="grid grid-cols-[1fr_115px_70px_42px_28px] gap-1 mb-1">
          <input className={input} value={rule.name} aria-label="Название скидки" onChange={event => updateRule(index, { name: event.target.value })} />
          <select className={input} value={rule.scope} onChange={event => updateRule(index, { scope: event.target.value as QuoteDiscountRule['scope'] })}>
            <option value="order">Весь заказ</option><option value="construction">Изделия</option><option value="component">Аксессуары</option><option value="profile">Профили</option><option value="service">Услуги</option>
          </select>
          <input className={input} type="number" min="0" step="0.01" value={rule.value} onChange={event => updateRule(index, { value: event.target.value })} />
          <button type="button" onClick={() => updateRule(index, { mode: rule.mode === 'percent' ? 'fixed' : 'percent' })}>{rule.mode === 'percent' ? '%' : '₽'}</button>
          <button type="button" aria-label="Удалить скидку" onClick={() => patch({ discounts: rules.filter((_, i) => i !== index) })}>×</button>
        </div>)}
        <button type="button" className="text-accent mt-1" onClick={() => patch({ discounts: [...rules, { id: `discount-${crypto.randomUUID()}`, name: 'Скидка', scope: 'order', mode: 'percent', value: '0' }] })}>+ Добавить правило</button>
      </details>
    </fieldset>}
  </section>;
}
