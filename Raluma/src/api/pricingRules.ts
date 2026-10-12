import client from './client';

export const pricingFields = [
  ['profile_markup_percent', 'Профиль: наценка'],
  ['profile_discount_percent', 'Профиль: скидка'],
  ['waste_markup_percent', 'Конструкция: отходы'],
  ['construction_markup_percent', 'Конструкция: наценка'],
  ['construction_discount_percent', 'Конструкция: скидка'],
] as const;
export type PricingCoefficients = Record<(typeof pricingFields)[number][0], string>;
export interface RuleVersion extends PricingCoefficients { id: number; name: string; effective_from: string; is_active: boolean; reason?: string }
export interface PricingRule { id: number; name: string; scope: 'default' | 'group'; group_name?: string | null; is_active: boolean; active_version: RuleVersion | null; next_version: RuleVersion | null; versions: RuleVersion[] }
export interface RuleInput extends PricingCoefficients { name: string; scope: 'default' | 'group'; group_name?: string; is_active: boolean; effective_from: string; reason: string }
export interface RuleSource { mode?: string; scope?: string; rule_id?: number; rule_version_id?: number; name?: string; label?: string }
export interface ResolvedPrice extends PricingCoefficients { cost: string; unit: string; source: RuleSource; profile?: { final: string }; construction?: { final: string }; minimum_markup_percent?: string }
export interface RuleBinding { catalog_item_id: number; finish_variant_id: number; sku: string; name: string; group_name: string; finish_name: string; mode: 'individual' | 'auto'; resolved: ResolvedPrice | null }
export interface RulePreviewRow { finish_variant_id: number; sku: string; name: string; finish_name: string; before: ResolvedPrice; after: ResolvedPrice }
export interface RulePreview { count: number; rows: RulePreviewRow[] }
export interface BindingInput { finish_variant_ids: number[]; mode: 'individual' | 'auto'; reason: string }
export const listPricingRules = () => client.get<{ rules: PricingRule[]; groups: string[] }>('/api/pricing/rules').then(response => response.data);
export const savePricingRule = (data: RuleInput, id?: number) => id ? client.put(`/api/pricing/rules/${id}`, data).then(response => response.data) : client.post('/api/pricing/rules', data).then(response => response.data);
export const previewPricingRule = (data: RuleInput & { rule_id?: number }) => client.post<RulePreview>('/api/pricing/rules/preview', data).then(response => response.data);
export const listRuleBindings = () => client.get<{ rows: RuleBinding[] }>('/api/pricing/rule-bindings').then(response => response.data);
export const previewRuleBindings = (data: BindingInput) => client.post<RulePreview>('/api/pricing/rule-bindings/preview', data).then(response => response.data);
export const applyRuleBindings = (data: BindingInput) => client.post<RulePreview>('/api/pricing/rule-bindings/apply', data).then(response => response.data);
