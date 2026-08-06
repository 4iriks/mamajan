import client from './client';

export type PriceCategory = 'profile' | 'construction' | 'component' | 'service';

export interface PriceVersion {
  id: number;
  catalog_item_id: number;
  cost: string;
  profile_markup_percent: string;
  profile_discount_percent: string;
  waste_markup_percent: string;
  construction_markup_percent: string;
  construction_discount_percent: string;
  category: PriceCategory;
  unit: string;
  min_margin_percent: string;
  effective_from: string;
  created_at: string;
  created_by: number;
  reason: string;
  rollback_of_id?: number | null;
}

export interface PricedCatalogItem {
  id: number;
  sku: string;
  name: string;
  group: string;
  system: string;
  catalog_unit: string;
  supplier: string;
  is_active: boolean;
  active_price: PriceVersion | null;
  next_price: PriceVersion | null;
  history_count: number;
}

export interface PriceVersionInput {
  cost: string;
  profile_markup_percent: string;
  profile_discount_percent: string;
  waste_markup_percent: string;
  construction_markup_percent: string;
  construction_discount_percent: string;
  category: PriceCategory;
  unit: string;
  min_margin_percent: string;
  effective_from: string;
  reason: string;
}

export interface DealerPricingTerms {
  user_id: number;
  dealer_markup_percent: string;
  profile_discount_percent: string;
  construction_discount_percent: string;
  component_discount_percent: string;
  service_discount_percent: string;
  updated_at: string | null;
  updated_by: number | null;
}

export interface PricingSettings {
  id: number;
  include_waste_markup: boolean;
  default_vat_rate: string;
  updated_at: string;
  updated_by: number | null;
}

export const getPricedCatalog = () =>
  client.get<{ items: PricedCatalogItem[]; categories: PriceCategory[]; manual_service_units: string[] }>('/api/pricing/catalog')
    .then(response => response.data);

export const createPriceVersion = (itemId: number, data: PriceVersionInput) =>
  client.post<PriceVersion>(`/api/pricing/catalog/${itemId}/versions`, data)
    .then(response => response.data);

export const getPriceHistory = (itemId: number) =>
  client.get<{ item: { id: number; sku: string; name: string }; versions: PriceVersion[] }>(`/api/pricing/catalog/${itemId}/versions`)
    .then(response => response.data);

export const rollbackPrice = (itemId: number, versionId: number, reason: string, effectiveFrom: string) =>
  client.post<PriceVersion>(`/api/pricing/catalog/${itemId}/rollback/${versionId}`, {
    reason,
    effective_from: effectiveFrom,
  }).then(response => response.data);

export interface BulkPriceRequest {
  item_ids: number[];
  percent: string;
  effective_from: string;
  reason: string;
}

export const previewBulkPriceChange = (data: BulkPriceRequest) =>
  client.post<{ rows: Array<{ item_id: number; sku: string; name: string; old_cost: string; new_cost: string }> }>('/api/pricing/catalog/bulk/preview', data)
    .then(response => response.data);

export const applyBulkPriceChange = (data: BulkPriceRequest) =>
  client.post('/api/pricing/catalog/bulk/apply', data).then(response => response.data);

export const previewPriceImport = async (file: File) => {
  const body = new FormData();
  body.append('file', file);
  return client.post<{ valid: boolean; rows: Array<Record<string, string>>; errors: string[] }>(
    '/api/pricing/catalog/import/preview',
    body,
  ).then(response => response.data);
};

export const applyPriceImport = (rows: Array<Record<string, string>>, reason: string) =>
  client.post('/api/pricing/catalog/import/apply', { rows, reason }).then(response => response.data);

export const getDealerPricingTerms = (userId: number) =>
  client.get<DealerPricingTerms>(`/api/pricing/dealers/${userId}`).then(response => response.data);

export const listPricingDealers = () =>
  client.get<Array<{ id: number; display_name: string; company: string }>>('/api/pricing/dealers')
    .then(response => response.data);

export const updateDealerPricingTerms = (
  userId: number,
  data: Omit<DealerPricingTerms, 'user_id' | 'updated_at' | 'updated_by'>,
) => client.put<DealerPricingTerms>(`/api/pricing/dealers/${userId}`, data).then(response => response.data);

export const getPricingSettings = () =>
  client.get<PricingSettings>('/api/pricing/settings').then(response => response.data);

export const updatePricingSettings = (data: Pick<PricingSettings, 'include_waste_markup' | 'default_vat_rate'>) =>
  client.put<PricingSettings>('/api/pricing/settings', data).then(response => response.data);
