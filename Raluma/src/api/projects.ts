import client from './client';
import {
  clearLocalDocumentOverrides,
  clearLocalProjects,
  copyLocalProject,
  createLocalProject,
  createLocalSection,
  deleteLocalProject,
  deleteLocalSection,
  getLocalDocumentPayload,
  getLocalProject,
  getLocalProjects,
  getLocalProjectsSignature,
  getLocalProjectDocumentPayload,
  getLocalProjectsSnapshot,
  saveLocalDocumentOverrides,
  updateLocalProject,
  updateLocalSection,
} from './localProjects';

export interface ProjectList {
  id: number;
  number: string;
  customer: string;
  system?: string;
  subtype?: string;
  extra_parts?: string;
  comments?: string;
  production_stages?: number;
  current_stage?: number;
  status?: string;
  glass_status?: string;
  glass_invoice?: string;
  glass_ready_date?: string;
  paint_status?: string;
  paint_ship_date?: string;
  paint_received_date?: string;
  order_items?: string;
  paint_manual_rows?: string;
  delivery_note_data?: string;
  created_at: string;
  updated_at: string;
  created_by: number;
}

export interface ProjectFull extends ProjectList {
  sections: SectionOut[];
}

export interface SectionOut {
  id: number;
  project_id: number;
  order: number;
  name: string;
  system?: string;
  width: number;
  height: number;
  panels: number;
  quantity: number;
  glass_type: string;
  painting_type: string;
  ral_color?: string;
  corner_left: boolean;
  corner_right: boolean;
  external_width?: number;
  rails?: number;
  threshold?: string;
  first_panel_inside?: string;
  unused_track?: string;
  inter_glass_profile?: string;
  profile_left?: string;
  profile_right?: string;
  lock?: string;
  handle?: string;
  floor_latches_left: boolean;
  floor_latches_right: boolean;
  handle_offset?: number;
  handle_offset_left?: number;
  handle_offset_right?: number;
  profile_left_wall?: boolean;
  profile_left_lock_bar?: boolean;
  profile_left_p_bar?: boolean;
  profile_left_handle_bar?: boolean;
  profile_left_bubble?: boolean;
  profile_right_wall?: boolean;
  profile_right_lock_bar?: boolean;
  profile_right_p_bar?: boolean;
  profile_right_handle_bar?: boolean;
  profile_right_bubble?: boolean;
  lock_left?: string;
  lock_right?: string;
  slide_rows?: number;
  center_handle?: string;
  center_lock?: string;
  center_handle_offset?: number;
  center_floor_latches_left?: boolean;
  center_floor_latches_right?: boolean;
  book_subtype?: string;
  handle_left?: string;
  handle_right?: string;
  doors?: number;
  door_side?: string;
  door_type?: string;
  door_opening?: string;
  compensator?: string;
  angle_left?: number;
  angle_right?: number;
  book_system?: string;
  lift_filling_type?: string;
  lift_filling_custom?: string;
  lift_control_type?: string;
  lift_remote_1ch_qty?: number;
  lift_remote_6ch_qty?: number;
  lift_cable_side?: string;
  lift_opening_type?: string;
  door_system?: string;
  cs_shape?: string;
  cs_width2?: number;
  extra_parts?: string;
  extra_components?: string;
  comments?: string;
  document_overrides?: string;
}

const hasAuthToken = () => Boolean(localStorage.getItem('access_token'));

export type ProjectDocumentType =
  | 'commercial'
  | 'paint'
  | 'glass'
  | 'delivery'
  | 'hardware_order';
export type DocumentFileFormat = 'pdf' | 'docx' | 'xlsx';
export type ProjectDocumentOverrides = Partial<{
  project_number: string;
  project_customer: string;
}>;

export interface SlideCalcGlass {
  position: string;
  width_mm: number;
  height_mm: number;
  qty: number;
  glass_profile_length: number;
}

export interface SlideCalcProfile {
  article: string;
  name: string;
  length_mm: number;
  qty: number;
  painted: boolean;
  image?: string | null;
  section_width_mm: number;
  section_height_mm: number;
  paint_mode: string;
  color_variants: string[];
  paint_note: string;
}

export interface SlideCalcPanelGlass {
  panel: number;
  position: string;
  width_mm: number;
  height_mm: number;
  glass_profile_length: number;
}

export interface SlideCalcPreview {
  profiles: SlideCalcProfile[];
  glass: SlideCalcGlass[];
  panel_rails: number[];
  panel_glass?: SlideCalcPanelGlass[];
  torque?: {
    torque_nm: number;
    drive_count: number;
    warning: string;
  } | null;
  warnings?: string[];
}

// Documents
export const getPreviewUrl = (projectId: number, sectionId: number) =>
  `/api/projects/${projectId}/sections/${sectionId}/preview`;

export const getProjectDocumentPreviewUrl = (projectId: number, docType: ProjectDocumentType) =>
  `/api/projects/${projectId}/documents/${docType}/preview`;

export const saveDocumentOverrides = (projectId: number, sectionId: number, overrides: Record<string, unknown>) =>
  hasAuthToken()
    ? client.patch(`/api/projects/${projectId}/sections/${sectionId}/overrides`, { overrides })
    : Promise.resolve(saveLocalDocumentOverrides(projectId, sectionId, overrides));

export const clearDocumentOverrides = (projectId: number, sectionId: number) =>
  hasAuthToken()
    ? client.delete(`/api/projects/${projectId}/sections/${sectionId}/overrides`)
    : Promise.resolve(clearLocalDocumentOverrides(projectId, sectionId));

export const getLocalPreviewHtml = async (projectId: number, sectionId: number) => {
  const payload = getLocalDocumentPayload(projectId, sectionId);
  const resp = await client.post<string>('/api/projects/local/sections/preview', payload, {
    responseType: 'text',
  });
  return resp.data;
};

export const calculateLocalSection = async (section: Partial<SectionOut>) => {
  const resp = await client.post<SlideCalcPreview>('/api/projects/local/sections/calc', {
    project: { number: 'preview', customer: '' },
    section: {
      name: 'Секция',
      ...section,
    },
  });
  return resp.data;
};

export const getLocalProjectDocumentPreviewHtml = async (projectId: number, docType: ProjectDocumentType) => {
  const payload = getLocalProjectDocumentPayload(projectId);
  const resp = await client.post<string>(`/api/projects/local/documents/${docType}/preview`, payload, {
    responseType: 'text',
  });
  return resp.data;
};

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export const downloadSectionDocument = async (
  projectId: number,
  sectionId: number,
  format: DocumentFileFormat,
  filename: string,
) => {
  const resp = hasAuthToken()
    ? await client.get(`/api/projects/${projectId}/sections/${sectionId}/${format}`, { responseType: 'blob' })
    : await client.post(
      `/api/projects/local/sections/${format}`,
      getLocalDocumentPayload(projectId, sectionId),
      { responseType: 'blob' },
    );
  triggerBlobDownload(resp.data, filename);
};

export const downloadPdf = (
  projectId: number,
  sectionId: number,
  filename: string,
) => downloadSectionDocument(projectId, sectionId, 'pdf', filename);

function applyProjectDocumentOverrides(
  payload: { project: Partial<ProjectList>; sections: SectionOut[] },
  overrides?: ProjectDocumentOverrides,
) {
  if (!overrides || Object.keys(overrides).length === 0) return payload;
  return {
    ...payload,
    project: {
      ...payload.project,
      number: Object.prototype.hasOwnProperty.call(overrides, 'project_number')
        ? String(overrides.project_number ?? '')
        : payload.project.number,
      customer: Object.prototype.hasOwnProperty.call(overrides, 'project_customer')
        ? String(overrides.project_customer ?? '')
        : payload.project.customer,
    },
  };
}

export const downloadProjectDocument = async (
  projectId: number,
  docType: ProjectDocumentType,
  format: DocumentFileFormat,
  filename: string,
  overrides?: ProjectDocumentOverrides,
) => {
  const hasOverrides = Boolean(overrides && Object.keys(overrides).length > 0);
  let resp;
  if (hasOverrides) {
    const payload = hasAuthToken()
      ? await client.get<ProjectFull>(`/api/projects/${projectId}`).then(r => ({
        project: r.data,
        sections: r.data.sections,
      }))
      : getLocalProjectDocumentPayload(projectId);
    resp = await client.post(
      `/api/projects/local/documents/${docType}/${format}`,
      applyProjectDocumentOverrides(payload, overrides),
      { responseType: 'blob' },
    );
  } else {
    resp = hasAuthToken()
      ? await client.get(
        `/api/projects/${projectId}/documents/${docType}/${format}`,
        { responseType: 'blob' },
      )
      : await client.post(
        `/api/projects/local/documents/${docType}/${format}`,
        getLocalProjectDocumentPayload(projectId),
        { responseType: 'blob' },
      );
  }
  triggerBlobDownload(resp.data, filename);
};

export const downloadProjectDocumentPdf = (
  projectId: number,
  docType: ProjectDocumentType,
  filename: string,
  overrides?: ProjectDocumentOverrides,
) => downloadProjectDocument(
  projectId,
  docType,
  'pdf',
  filename,
  overrides,
);

// Projects
export const getProjects = () =>
  hasAuthToken()
    ? client.get<ProjectList[]>('/api/projects').then(r => r.data)
    : Promise.resolve(getLocalProjects());

export const getProject = (id: number) =>
  hasAuthToken()
    ? client.get<ProjectFull>(`/api/projects/${id}`).then(r => r.data)
    : Promise.resolve(getLocalProject(id));

export const createProject = (data: { number: string; customer: string; production_stages?: number }) =>
  hasAuthToken()
    ? client.post<ProjectFull>('/api/projects', data).then(r => r.data)
    : Promise.resolve(createLocalProject(data));

export const updateProject = (id: number, data: Partial<Omit<ProjectList, 'id' | 'created_at' | 'updated_at' | 'created_by'>>) =>
  hasAuthToken()
    ? client.put<ProjectFull>(`/api/projects/${id}`, data).then(r => r.data)
    : Promise.resolve(updateLocalProject(id, data));

export const deleteProject = (id: number) =>
  hasAuthToken()
    ? client.delete(`/api/projects/${id}`)
    : Promise.resolve(deleteLocalProject(id));

export const copyProject = (id: number) =>
  hasAuthToken()
    ? client.post<ProjectFull>(`/api/projects/${id}/copy`).then(r => r.data)
    : Promise.resolve(copyLocalProject(id));

// Sections
export const createSection = (projectId: number, data: Omit<SectionOut, 'id' | 'project_id'>) =>
  hasAuthToken()
    ? client.post<SectionOut>(`/api/projects/${projectId}/sections`, data).then(r => r.data)
    : Promise.resolve(createLocalSection(projectId, data));

export const updateSection = (projectId: number, sectionId: number, data: Partial<SectionOut>) =>
  hasAuthToken()
    ? client.put<SectionOut>(`/api/projects/${projectId}/sections/${sectionId}`, data).then(r => r.data)
    : Promise.resolve(updateLocalSection(projectId, sectionId, data));

export const deleteSection = (projectId: number, sectionId: number) =>
  hasAuthToken()
    ? client.delete(`/api/projects/${projectId}/sections/${sectionId}`)
    : Promise.resolve(deleteLocalSection(projectId, sectionId));

export const hasLocalProjects = () => getLocalProjectsSnapshot().length > 0;

export const getLocalImportSignature = () => getLocalProjectsSignature();

export const importLocalProjectsToServer = async () => {
  const localProjects = getLocalProjectsSnapshot();
  let importedProjects = 0;
  let importedSections = 0;

  for (const project of localProjects) {
    const created = await client.post<ProjectFull>('/api/projects', {
      number: project.number,
      customer: project.customer,
      production_stages: project.production_stages,
    }).then(r => r.data);

    await client.put<ProjectFull>(`/api/projects/${created.id}`, {
      extra_parts: project.extra_parts,
      comments: project.comments,
      production_stages: project.production_stages,
      current_stage: project.current_stage,
      status: project.status,
      glass_status: project.glass_status,
      glass_invoice: project.glass_invoice,
      glass_ready_date: project.glass_ready_date,
      paint_status: project.paint_status,
      paint_ship_date: project.paint_ship_date,
      paint_received_date: project.paint_received_date,
      order_items: project.order_items,
      paint_manual_rows: project.paint_manual_rows,
      delivery_note_data: project.delivery_note_data,
    });

    for (const section of project.sections.sort((a, b) => a.order - b.order)) {
      const { id: _id, project_id: _projectId, ...sectionData } = section;
      await client.post<SectionOut>(`/api/projects/${created.id}/sections`, sectionData);
      importedSections += 1;
    }

    importedProjects += 1;
  }

  clearLocalProjects();
  return { importedProjects, importedSections };
};
