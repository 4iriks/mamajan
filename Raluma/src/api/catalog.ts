import client from './client';

export type HardwareGroup = 'Профили' | 'Фурнитура' | 'Ручки' | 'Замки' | 'Защёлки' | 'Уплотнители' | 'Крепёж' | 'Расходники' | 'Услуги';
export type CatalogUnit = 'шт' | 'м.п.' | 'м²' | 'компл.' | 'кг';
export type PaintMode = 'Красится' | 'Не красится' | 'Частично';
export type SystemGroupCode = 'SLIDE_1' | 'SLIDE_2' | 'CS';
export type FinishCode = 'COLORLESS' | 'ANOD_UNPAINTED' | 'RAL_STANDARD' | 'RAL_MOIRE' | 'SUBLIMATION';

export interface CatalogFinishVariant {
  id?: number;
  code: FinishCode;
  name: string;
  cost?: string | number;
  profileMarkupPercent: number | string;
  profileDiscountPercent: number | string;
  wasteMarkupPercent: number | string;
  constructionMarkupPercent: number | string;
  constructionDiscountPercent: number | string;
  requiresPaint: boolean;
  isActive: boolean;
}

export interface HardwareCatalogItem {
  id: number;
  sku: string;
  name: string;
  group: HardwareGroup;
  system: string;
  systemGroups?: SystemGroupCode[];
  unit: CatalogUnit;
  purchasePrice: number;
  markupPercent: number;
  profileDiscountPercent?: number;
  weight: number;
  wastePercent: number;
  constructionMarkupPercent?: number;
  constructionDiscountPercent?: number;
  sectionWidthMm: number;
  sectionHeightMm: number;
  imageFile: string;
  photoFile?: string;
  paintMode: PaintMode;
  colorVariants: string[];
  finishVariants?: CatalogFinishVariant[];
  supplier: string;
  isActive: boolean;
  updatedAt: string;
  note: string;
}

export interface HardwareCatalogOption {
  id: number;
  sku: string;
  name: string;
  category: 'profile' | 'component' | 'service';
  unit: string;
  systemGroups?: SystemGroupCode[];
  imageFile?: string;
  paintMode?: PaintMode;
  finishVariants?: CatalogFinishVariant[];
  requiresPaint?: boolean;
  isActive: boolean;
}

export interface ConstructionPriceGroupOption {
  id: number;
  code: string;
  name: string;
}

export interface SystemMarkup {
  code: SystemGroupCode;
  name: string;
  constructionMarkupPercent: number | null;
  mixed: boolean;
}

export interface CatalogPricingBulkRequest {
  item_ids: number[];
  finish_codes: FinishCode[];
  profile_markup_percent?: number;
  profile_discount_percent?: number;
  waste_markup_percent?: number;
  construction_markup_percent?: number;
  construction_discount_percent?: number;
  effective_from?: string;
  reason: string;
}

export interface CatalogPricingChain {
  base: string;
  afterMarkup?: string;
  afterWaste?: string;
  final: string;
}

export interface CatalogPricingBulkRow {
  itemId: number;
  sku: string;
  name: string;
  finishCode: FinishCode;
  finishName: string;
  before: { profile: CatalogPricingChain; construction: CatalogPricingChain };
  after: { profile: CatalogPricingChain; construction: CatalogPricingChain };
}

export interface CatalogPricingBulkResult {
  count: number;
  rows: CatalogPricingBulkRow[];
}

export interface CsSystem {
  id: number;
  code: string;
  name: string;
  outer_profile_item_id: number | null;
  joint_profile_item_id: number | null;
  cover_profile_item_id?: number | null;
  bubble_seal_item_id?: number | null;
  glass_pad_item_id?: number | null;
  is_active: boolean;
  outer_profile?: { id: number; sku: string; name: string } | null;
  joint_profile?: { id: number; sku: string; name: string } | null;
}

export const listHardwareCatalog = async () => {
  const resp = await client.get<HardwareCatalogItem[]>('/api/catalog/hardware');
  return resp.data;
};

export const listHardwareCatalogOptions = async () => {
  const resp = await client.get<HardwareCatalogOption[]>('/api/catalog/hardware/options');
  return resp.data;
};

export const listConstructionPriceGroupOptions = async () => {
  const resp = await client.get<ConstructionPriceGroupOption[]>('/api/catalog/construction-price-groups');
  return resp.data;
};

export const listSystemMarkups = async () => {
  const resp = await client.get<SystemMarkup[]>('/api/catalog/system-markups');
  return resp.data;
};

export const updateSystemMarkup = async (code: SystemGroupCode, constructionMarkupPercent: number) => {
  const resp = await client.put(`/api/catalog/system-markups/${code}`, { constructionMarkupPercent });
  return resp.data;
};

export const previewCatalogPricingBulk = async (data: CatalogPricingBulkRequest) => {
  const resp = await client.post<CatalogPricingBulkResult>('/api/catalog/pricing/bulk/preview', data);
  return resp.data;
};

export const applyCatalogPricingBulk = async (data: CatalogPricingBulkRequest) => {
  const resp = await client.post<CatalogPricingBulkResult>('/api/catalog/pricing/bulk/apply', data);
  return resp.data;
};

export const listCsSystems = async () => {
  const resp = await client.get<CsSystem[]>('/api/catalog/cs-systems');
  return resp.data;
};

export const createCsSystem = async (data: Omit<CsSystem, 'id' | 'outer_profile' | 'joint_profile'>) => {
  const resp = await client.post<CsSystem>('/api/catalog/cs-systems', data);
  return resp.data;
};

export const updateCsSystem = async (id: number, data: Omit<CsSystem, 'id' | 'outer_profile' | 'joint_profile'>) => {
  const resp = await client.put<CsSystem>(`/api/catalog/cs-systems/${id}`, data);
  return resp.data;
};

export const createHardwareCatalogItem = async (data: HardwareCatalogItem) => {
  const resp = await client.post<HardwareCatalogItem>('/api/catalog/hardware', data);
  return resp.data;
};

export const updateHardwareCatalogItem = async (id: number, data: HardwareCatalogItem) => {
  const resp = await client.put<HardwareCatalogItem>(`/api/catalog/hardware/${id}`, data);
  return resp.data;
};

export const archiveHardwareCatalogItem = async (id: number) => {
  const resp = await client.delete<HardwareCatalogItem>(`/api/catalog/hardware/${id}`);
  return resp.data;
};
