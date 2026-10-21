import client from './client';
import type { SystemGroupCode } from './catalog';
import type { SectionOut, SectionCalcPreview } from './projects';

export type SystemCode = SystemGroupCode;
export type GeneralSettings = { markup_percent: string; discount_percent: string };
export type ComponentSettings = GeneralSettings & { waste_percent: string };
export type UnitStages = { after_waste: string; after_markup: string; final: string };
export interface SystemComponent {
  key: string; catalog_item_id: number; finish_variant_id: number | null;
  sku: string; name: string; group: string; finish: string; finish_code: string; unit: string;
  cost: string | null; cost_is_set: boolean; minimum_markup_percent: string;
  configured: boolean; settings: ComponentSettings | null; stages: UnitStages | null;
  draft_settings?: ComponentSettings | null; draft_stages?: UnitStages | null;
}
export interface SystemConfiguration {
  code: SystemCode; name: string; token: string; revision: number;
  general: GeneralSettings; components: SystemComponent[];
}
export interface PricingDraft {
  general?: GeneralSettings; components: Record<string, ComponentSettings>; section_ids: number[];
}
export interface SampleOption {
  section_id: number; project_id: number; label: string; width: number; height: number;
  quantity: number; finish: string; system_code: SystemCode;
}
export interface PricedComponent {
  component_key: string; sku: string; name: string; quantity: string; unit: string;
  internal_total: string; minimum_total: string;
}
export interface SamplePrice {
  bom: PricedComponent[]; issues: { code: string; name: string; sku?: string; detail?: string; component_key?: string; quantity?: string; unit?: string }[];
  complete: boolean; total: string | null; minimum_total: string; below_minimum: boolean;
  stages: GeneralSettings & { subtotal: string; after_markup: string; total: string };
}
export interface SampleResult {
  section_id: number; available: boolean; error?: string;
  section?: SectionOut; calculation?: SectionCalcPreview;
  saved?: SamplePrice; draft?: SamplePrice;
}
export interface PricingPreview {
  token: string; general: GeneralSettings; components: SystemComponent[]; samples: SampleResult[];
}
export interface PricingHistory {
  id: number; kind: string; label: string; effective_from: string; scheduled: boolean;
  created_by: number; reason: string; settings: Partial<ComponentSettings>;
}
const path = (code: SystemCode) => `/api/construction-pricing/systems/${code}`;
export const loadSystemPricing = async (code: SystemCode) => (await client.get<SystemConfiguration>(path(code))).data;
export const listPricingSamples = async (code: SystemCode) => (await client.get<SampleOption[]>(`${path(code)}/samples`)).data;
export const previewSystemPricing = async (code: SystemCode, draft: PricingDraft, signal?: AbortSignal) =>
  (await client.post<PricingPreview>(`${path(code)}/preview`, draft, { signal })).data;
export const saveSystemPricing = async (code: SystemCode, token: string, draft: PricingDraft) =>
  (await client.put<SystemConfiguration>(path(code), { ...draft, token })).data;
export const getSystemPricingHistory = async (code: SystemCode) =>
  (await client.get<PricingHistory[]>(`${path(code)}/history`)).data;
