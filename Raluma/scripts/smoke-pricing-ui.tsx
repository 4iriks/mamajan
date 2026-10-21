import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { UserMe } from '../src/api/auth';
import type { PublicQuote, QuoteConfig, InternalQuoteState } from '../src/api/quotes';
import { money, numericDraft, profilePricingMetres, validMoney } from '../src/utils/money';
import { orderQuoteDiscounts } from '../src/utils/quoteDiscounts';
import { parseExtraComponents, stringifyExtraComponents } from '../src/components/editor/converters';

assert.equal(numericDraft(''), null);
assert.equal(numericDraft(' 1,25 '), 1.25);
assert.equal(validMoney(''), false, 'blank money must not become zero');
assert.equal(validMoney('0'), true, 'intentional zero is allowed');
assert.equal(validMoney('-1'), false);
assert.equal(validMoney('101', 100), false);
assert.equal(validMoney('100', 100), true);
assert.equal(profilePricingMetres('3000', '2'), 6);
assert.equal(profilePricingMetres('3000 мм', '2'), 6);
assert.equal(profilePricingMetres('', '2'), null);
assert.equal(profilePricingMetres('3000', ''), null);
assert.equal(profilePricingMetres('0', '2'), null);
assert.match(money(1525.11 * 1.35), /2\s058,90/);

const rules: QuoteConfig['discounts'] = [
  { id: 'rub', name: 'Общая, ₽', scope: 'order', mode: 'fixed', value: '1000' },
  { id: 'percent', name: 'Общая, %', scope: 'order', mode: 'percent', value: '10' },
  { id: 'category', name: 'Изделия', scope: 'construction', mode: 'percent', value: '5' },
  { id: 'extra', name: 'Дополнительная', scope: 'construction', mode: 'fixed', value: '100' },
];
assert.deepEqual(orderQuoteDiscounts(rules).map(row => row.id), ['category', 'extra', 'percent', 'rub']);
assert.equal(rules[0].id, 'rub', 'ordering must not mutate saved config');
assert.deepEqual(orderQuoteDiscounts(rules.slice(0, 2)).map(row => row.id), orderQuoteDiscounts(rules.slice(0, 2).reverse()).map(row => row.id));

const manual = { id: 'stable-id', name: 'Ручная деталь', sku: '', unitPrice: '200,50', actualCost: '100,25', color: '', size: '3000', qty: '2', unit: 'шт' };
const serialized = JSON.parse(stringifyExtraComponents([manual]))[0];
assert.equal(serialized.id, 'stable-id');
assert.equal(serialized.unit_price, '200.50');
assert.equal(serialized.actual_cost, '100.25');
assert.equal(parseExtraComponents(JSON.stringify([serialized]))[0].unitPrice, '200.50');
assert.equal(Object.hasOwn(JSON.parse(stringifyExtraComponents([manual], false))[0], 'actual_cost'), false, 'ordinary editors must not send private actual cost');

Object.defineProperty(globalThis, 'localStorage', { value: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, configurable: true });
const { useAuthStore } = await import('../src/store/authStore');
const { ProjectEconomics } = await import('../src/components/editor/ProjectEconomics');
const { PriceRepair } = await import('../src/components/editor/PricingDetails');
const user: UserMe = { id: 1, username: 'manager', display_name: 'Менеджер', role: 'user', customer: null, can_manage_prices: false, is_active: true, created_at: '', last_login: null };
useAuthStore.setState({ user });
const quote: PublicQuote = { project: { id: 1, number: '1', customer: 'Заказчик' }, revision: 1, status: 'draft', fixed_at: null, currency: 'RUB', money_presentation_version: 2, lines: [], totals: { before_discount: '100.40', discount: '0.00', subtotal: '100.40', grand_total: '100.00', document_before_discount: '100.40', document_discount: '0.00', document_grand_total: '100.00', rounding_adjustment: '-0.40' }, validity_days: 14, valid_until: '', manufacturing_term: '', payment_terms: '', discounts: [], missing_price_count: 1, warnings: ['Не задана цена ручной детали'], export_allowed: false, stale: false };
const config: QuoteConfig = { validity_days: 14, manufacturing_term: '', payment_terms: '', services: [], discounts: rules.slice(0, 3), overrides: [], margin_override_comment: '' };
const internal: InternalQuoteState = { revision: 1, status: 'draft', stale: false, config, missing_prices: [{ sku: 'MANUAL', name: 'Ручная деталь', unit: 'шт', reason: 'missing_price' }], pending_warnings: [], margin_approval: { required: false, valid: false, context_signature: '', target_revision: 1, approved_revision: null, comment: '', approved_by: null, approved_at: null }, calculation: { dealer_terms: { dealer_markup_percent: '99999' }, sections: [] } };
const state = { quote, currentQuote: quote, config, internal, dirty: false, busy: false, refreshing: false, error: '', patch: () => {}, save: async () => true, reload: async () => {}, saveOverrides: async () => true };
const publicHtml = renderToStaticMarkup(<ProjectEconomics state={state} />);
assert.match(publicHtml, /Расчёт неполный/);
assert.match(publicHtml, /Учтённая часть, не итог/);
assert.match(publicHtml, /Не задана цена ручной детали/);
assert.match(publicHtml, /Округление итога/);
assert.doesNotMatch(publicHtml, /99999/);
assert.doesNotMatch(publicHtml, /Причина разовой цены/);
assert.match(publicHtml, /Дополнительные правила \(0\)/);
useAuthStore.setState({ user: { ...user, role: 'admin' } });
const privateHtml = renderToStaticMarkup(<ProjectEconomics state={state} />);
assert.match(privateHtml, /99999/);
assert.match(privateHtml, /Разовые цены и разрешения/);
assert.match(privateHtml, /задайте цену в дополнительных комплектующих/);
const agreed = { ...quote, status: 'fixed' as const, stale: true, export_allowed: true, warnings: [], totals: { ...quote.totals, grand_total: '1000.00' } };
const current = { ...quote, export_allowed: true, warnings: [], totals: { ...quote.totals, grand_total: '800.00' } };
const frozenHtml = renderToStaticMarkup(<ProjectEconomics state={{ ...state, quote: agreed, currentQuote: current, internal: { ...internal, stale: true, pending_quote: current } }} />);
assert.match(frozenHtml, /Зафиксированное КП №/);
assert.match(frozenHtml, /Текущий расчёт заказа/);
assert.match(frozenHtml, /1\s000,00/);
assert.match(frozenHtml, /800,00/);
assert.match(frozenHtml, /-200,00/);
assert.match(frozenHtml, /создайте новую редакцию/);
const unchangedFixedState = { ...state, quote: { ...agreed, stale: false }, currentQuote: { ...current, totals: agreed.totals } };
const unchangedFixedHtml = renderToStaticMarkup(<ProjectEconomics state={unchangedFixedState} />);
assert.match(unchangedFixedHtml, /совпадает с КП/);
assert.match(unchangedFixedHtml, /Расчёт сохранён/);
for (const pendingState of [{ dirty: true }, { refreshing: true }, { error: 'Не удалось обновить расчёт' }]) {
  const lastCalculationHtml = renderToStaticMarkup(<ProjectEconomics state={{ ...unchangedFixedState, ...pendingState }} />);
  assert.match(lastCalculationHtml, /Последний успешный расчёт/);
  assert.match(lastCalculationHtml, /Последняя рассчитанная сумма:/);
  assert.doesNotMatch(lastCalculationHtml, /совпадает с КП/);
  assert.doesNotMatch(lastCalculationHtml, /Расчёт сохранён/);
  assert.doesNotMatch(lastCalculationHtml, /Текущая сумма:/);
}
const blockedPendingHtml = renderToStaticMarkup(<ProjectEconomics state={{ ...state, quote: agreed, currentQuote: quote }} />);
assert.match(blockedPendingHtml, /новую редакцию КП пока нельзя зафиксировать/);
assert.match(blockedPendingHtml, /Ранее зафиксированное КП остаётся доступным/);
assert.doesNotMatch(blockedPendingHtml, /Изменение к КП:/, 'An incomplete calculation is not a meaningful price delta');
const unknownOverrideHtml = renderToStaticMarkup(<ProjectEconomics state={{ ...state, quote: agreed, currentQuote: current, internal: { ...internal, calculation: { sections: [{ section_id: 1, name: 'Тест', bom: [{ sku: 'UNKNOWN-OVERRIDE', quantity: '1', unit: 'шт', cost_known: false, sale_price_override: '50', base_cost_total: '0', internal_total: '50' }] }] } } }} />);
assert.match(unknownOverrideHtml, /Разовая цена продажи:/);
assert.match(unknownOverrideHtml, /не задана/);
const approvalState = { ...state, internal: { ...internal, margin_approval: { ...internal.margin_approval, required: true } } };
for (const role of ['admin', 'superadmin'] as const) {
  useAuthStore.setState({ user: { ...user, role, can_manage_prices: false } });
  const approvalHtml = renderToStaticMarkup(<PriceRepair state={approvalState} />);
  assert.match(approvalHtml, /^<section aria-label="Согласование минимальной цены"/, 'Approval must be visible outside the collapsed advanced settings');
  assert.match(approvalHtml, /Разрешить цену ниже порога/);
  assert.match(approvalHtml, /Причина разрешения минимальной цены/);
  assert.match(approvalHtml, /disabled=""[^>]*>Разрешить цену ниже порога/, 'A reason is required');
  assert.match(approvalHtml, /не заменяет недостающие цены/);
  const approvedHtml = renderToStaticMarkup(<PriceRepair state={{ ...approvalState, internal: { ...approvalState.internal, margin_approval: { ...approvalState.internal.margin_approval, valid: true } } }} />);
  assert.match(approvedHtml, /Цена ниже порога согласована/);
  assert.doesNotMatch(approvedHtml, /Причина разрешения минимальной цены/);
}
for (const role of ['user', 'dealer'] as const) {
  useAuthStore.setState({ user: { ...user, role, can_manage_prices: true } });
  const approvalHtml = renderToStaticMarkup(<PriceRepair state={approvalState} />);
  assert.doesNotMatch(approvalHtml, /Разрешить цену ниже порога/);
  if (role === 'user') assert.match(approvalHtml, /попросите администратора или суперадминистратора/);
}
console.log('Pricing frontend smoke passed: money precision, units, discounts, manual prices/privacy, states and approval permissions.');
