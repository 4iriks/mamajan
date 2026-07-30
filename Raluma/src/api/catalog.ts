import client from './client';

export type HardwareGroup = 'Профили' | 'Фурнитура' | 'Ручки' | 'Замки' | 'Защёлки' | 'Уплотнители' | 'Крепёж' | 'Расходники';
export type CatalogUnit = 'шт' | 'м.п.' | 'компл.' | 'кг';
export type PaintMode = 'Красится' | 'Не красится' | 'Частично';

export interface HardwareCatalogItem {
  id: number;
  sku: string;
  name: string;
  group: HardwareGroup;
  system: string;
  unit: CatalogUnit;
  purchasePrice: number;
  markupPercent: number;
  weight: number;
  wastePercent: number;
  sectionWidthMm: number;
  sectionHeightMm: number;
  imageFile: string;
  paintMode: PaintMode;
  colorVariants: string[];
  supplier: string;
  isActive: boolean;
  updatedAt: string;
  note: string;
}

export interface HardwareCatalogOption {
  id: number;
  sku: string;
  name: string;
  unit: string;
  imageFile?: string;
  isActive: boolean;
}

export const listHardwareCatalog = async () => {
  const resp = await client.get<HardwareCatalogItem[]>('/api/catalog/hardware');
  return resp.data;
};

export const listHardwareCatalogOptions = async () => {
  const resp = await client.get<HardwareCatalogOption[]>('/api/catalog/hardware/options');
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
