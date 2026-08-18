import client from './client';

export type HardwareGroup = 'Профили' | 'Фурнитура' | 'Ручки' | 'Замки' | 'Защёлки' | 'Уплотнители' | 'Крепёж' | 'Расходники' | 'Услуги';
export type CatalogUnit = 'шт' | 'м.п.' | 'м²' | 'компл.' | 'кг';
export type PaintMode = 'Красится' | 'Не красится' | 'Частично';
export type SystemGroupCode = 'SLIDE_1' | 'SLIDE_2';
export type FinishCode = 'BASE' | 'ANOD' | 'RAL_STANDARD' | 'RAL_NONSTANDARD';

export interface CatalogFinishVariant {
  id?: number;
  code: FinishCode;
  name: string;
  cost?: string | number;
  profileMarkupPercent: number | string;
  profileDiscountPercent: number | string;
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
