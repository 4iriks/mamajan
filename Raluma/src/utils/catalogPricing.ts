import type { CatalogPricingBulkRequest, CatalogPricingBulkResult } from '../api/catalog';
import type { PricingRule, RuleInput, RuleVersion } from '../api/pricingRules';

export interface CatalogBulkPreview {
  request: CatalogPricingBulkRequest;
  result: CatalogPricingBulkResult;
  key: string;
}

export function catalogBulkPreviewKey(state: {
  itemIds: number[];
  finishCodes: string[];
  values: Record<string, string>;
  reason: string;
  filters: string[];
}): string {
  return JSON.stringify({ ...state, itemIds: [...state.itemIds].sort((a, b) => a - b), finishCodes: [...state.finishCodes].sort() });
}

export function confirmedCatalogBulkRequest(preview: CatalogBulkPreview | null, currentKey: string): CatalogPricingBulkRequest | null {
  return preview?.key === currentKey ? preview.request : null;
}

export const ruleDate = (value: string) => new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);

export function newPricingRule(rules: PricingRule[]): RuleInput {
  return { name: '', scope: rules.some(rule => rule.scope === 'default') ? 'group' : 'default', is_active: true, effective_from: '', reason: '', profile_markup_percent: '0', profile_discount_percent: '0', waste_markup_percent: '0', construction_markup_percent: '0', construction_discount_percent: '0' };
}

export function ruleVersionStatus(rule: PricingRule, version: RuleVersion, now = Date.now()): string {
  if (version.id === rule.active_version?.id) return 'Действующая версия';
  const effective = ruleDate(version.effective_from).getTime();
  const superseded = rule.versions.some(row => row.id > version.id && ruleDate(row.effective_from).getTime() === effective);
  return effective > now && !superseded ? 'Запланирована' : 'Архивная версия';
}
