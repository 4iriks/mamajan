import client from './client';
import type { SectionOut } from './projects';

export interface SectionTemplate {
  id: number;
  name: string;
  system: string;
  template_data: Partial<SectionOut>;
  sort_order: number;
  created_by?: number | null;
  created_at: string;
  updated_at: string;
}

export interface SectionTemplatePayload {
  name: string;
  system: string;
  template_data: Partial<SectionOut>;
  sort_order?: number;
}

export const getSectionTemplates = (system?: string) =>
  client.get<SectionTemplate[]>('/api/section-templates', { params: system ? { system } : undefined })
    .then(r => r.data);

export const createSectionTemplate = (data: SectionTemplatePayload) =>
  client.post<SectionTemplate>('/api/section-templates', data).then(r => r.data);

export const updateSectionTemplate = (id: number, data: Partial<SectionTemplatePayload>) =>
  client.patch<SectionTemplate>(`/api/section-templates/${id}`, data).then(r => r.data);

export const deleteSectionTemplate = (id: number) =>
  client.delete(`/api/section-templates/${id}`);
