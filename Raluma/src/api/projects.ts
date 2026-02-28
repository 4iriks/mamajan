import client from './client';

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
  door_system?: string;
  cs_shape?: string;
  cs_width2?: number;
  extra_parts?: string;
  comments?: string;
}

// Projects
export const getProjects = () =>
  client.get<ProjectList[]>('/api/projects').then(r => r.data);

export const getProject = (id: number) =>
  client.get<ProjectFull>(`/api/projects/${id}`).then(r => r.data);

export const createProject = (data: { number: string; customer: string; production_stages?: number }) =>
  client.post<ProjectFull>('/api/projects', data).then(r => r.data);

export const updateProject = (id: number, data: Partial<Omit<ProjectList, 'id' | 'created_at' | 'updated_at' | 'created_by'>>) =>
  client.put<ProjectFull>(`/api/projects/${id}`, data).then(r => r.data);

export const deleteProject = (id: number) =>
  client.delete(`/api/projects/${id}`);

export const copyProject = (id: number) =>
  client.post<ProjectFull>(`/api/projects/${id}/copy`).then(r => r.data);

// Sections
export const createSection = (projectId: number, data: Omit<SectionOut, 'id' | 'project_id'>) =>
  client.post<SectionOut>(`/api/projects/${projectId}/sections`, data).then(r => r.data);

export const updateSection = (projectId: number, sectionId: number, data: Partial<SectionOut>) =>
  client.put<SectionOut>(`/api/projects/${projectId}/sections/${sectionId}`, data).then(r => r.data);

export const deleteSection = (projectId: number, sectionId: number) =>
  client.delete(`/api/projects/${projectId}/sections/${sectionId}`);
