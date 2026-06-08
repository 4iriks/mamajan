import type { ProjectFull, ProjectList, SectionOut } from './projects';

export const LOCAL_PROJECTS_KEY = 'raluma-local-projects-v1';

const makeId = () => Date.now() + Math.floor(Math.random() * 100000);
const nowIso = () => new Date().toISOString();

function read(): ProjectFull[] {
  try {
    const raw = localStorage.getItem(LOCAL_PROJECTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(projects: ProjectFull[]) {
  localStorage.setItem(LOCAL_PROJECTS_KEY, JSON.stringify(projects));
}

function touch(project: ProjectFull): ProjectFull {
  return { ...project, updated_at: nowIso() };
}

function toList(project: ProjectFull): ProjectList {
  const { sections: _sections, ...listProject } = project;
  return listProject;
}

function normalizeSection(
  projectId: number,
  section: Partial<SectionOut> & Pick<SectionOut, 'name'>
): SectionOut {
  return {
    id: section.id ?? makeId(),
    project_id: projectId,
    order: section.order ?? 0,
    name: section.name,
    system: section.system ?? 'СЛАЙД',
    width: section.width ?? 2000,
    height: section.height ?? 2400,
    panels: section.panels ?? 3,
    quantity: section.quantity ?? 1,
    glass_type: section.glass_type ?? '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
    painting_type: section.painting_type ?? 'RAL стандарт',
    ral_color: section.ral_color,
    corner_left: section.corner_left ?? false,
    corner_right: section.corner_right ?? false,
    external_width: section.external_width,
    rails: section.rails,
    threshold: section.threshold,
    first_panel_inside: section.first_panel_inside,
    unused_track: section.unused_track,
    inter_glass_profile: section.inter_glass_profile,
    profile_left: section.profile_left,
    profile_right: section.profile_right,
    lock: section.lock,
    handle: section.handle,
    floor_latches_left: section.floor_latches_left ?? false,
    floor_latches_right: section.floor_latches_right ?? false,
    handle_offset: section.handle_offset,
    handle_offset_left: section.handle_offset_left,
    handle_offset_right: section.handle_offset_right,
    profile_left_wall: section.profile_left_wall ?? false,
    profile_left_lock_bar: section.profile_left_lock_bar ?? false,
    profile_left_p_bar: section.profile_left_p_bar ?? false,
    profile_left_handle_bar: section.profile_left_handle_bar ?? false,
    profile_left_bubble: section.profile_left_bubble ?? false,
    profile_right_wall: section.profile_right_wall ?? false,
    profile_right_lock_bar: section.profile_right_lock_bar ?? false,
    profile_right_p_bar: section.profile_right_p_bar ?? false,
    profile_right_handle_bar: section.profile_right_handle_bar ?? false,
    profile_right_bubble: section.profile_right_bubble ?? false,
    lock_left: section.lock_left,
    lock_right: section.lock_right,
    slide_rows: section.slide_rows ?? 1,
    center_handle: section.center_handle,
    center_lock: section.center_lock,
    center_handle_offset: section.center_handle_offset,
    center_floor_latches_left: section.center_floor_latches_left ?? false,
    center_floor_latches_right: section.center_floor_latches_right ?? false,
    book_subtype: section.book_subtype,
    handle_left: section.handle_left,
    handle_right: section.handle_right,
    doors: section.doors,
    door_side: section.door_side,
    door_type: section.door_type,
    door_opening: section.door_opening,
    compensator: section.compensator,
    angle_left: section.angle_left,
    angle_right: section.angle_right,
    book_system: section.book_system,
    door_system: section.door_system,
    cs_shape: section.cs_shape,
    cs_width2: section.cs_width2,
    extra_parts: section.extra_parts,
    comments: section.comments,
    document_overrides: section.document_overrides ?? '{}',
  };
}

export function getLocalProjects(): ProjectList[] {
  return read()
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    .map(toList);
}

export function getLocalProject(id: number): ProjectFull {
  const project = read().find(p => p.id === id);
  if (!project) throw new Error('Проект не найден');
  return project;
}

export function getLocalProjectDocumentPayload(projectId: number) {
  const project = getLocalProject(projectId);
  return {
    project,
    sections: project.sections,
  };
}

export function createLocalProject(data: { number: string; customer: string; production_stages?: number }): ProjectFull {
  const projects = read();
  const createdAt = nowIso();
  const project: ProjectFull = {
    id: makeId(),
    number: data.number,
    customer: data.customer,
    system: '',
    subtype: undefined,
    extra_parts: undefined,
    comments: undefined,
    production_stages: data.production_stages ?? 1,
    current_stage: 1,
    status: 'РАСЧЕТ',
    glass_status: undefined,
    glass_invoice: undefined,
    glass_ready_date: undefined,
    paint_status: undefined,
    paint_ship_date: undefined,
    paint_received_date: undefined,
    order_items: undefined,
    created_at: createdAt,
    updated_at: createdAt,
    created_by: 0,
    sections: [],
  };
  write([project, ...projects]);
  return project;
}

export function updateLocalProject(
  id: number,
  data: Partial<Omit<ProjectList, 'id' | 'created_at' | 'updated_at' | 'created_by'>>
): ProjectFull {
  const projects = read();
  const idx = projects.findIndex(p => p.id === id);
  if (idx === -1) throw new Error('Проект не найден');
  const updated = touch({ ...projects[idx], ...data });
  projects[idx] = updated;
  write(projects);
  return updated;
}

export function deleteLocalProject(id: number) {
  write(read().filter(p => p.id !== id));
}

export function copyLocalProject(id: number): ProjectFull {
  const source = getLocalProject(id);
  const createdAt = nowIso();
  const newId = makeId();
  const copy: ProjectFull = {
    ...source,
    id: newId,
    number: `${source.number}-копия`,
    created_at: createdAt,
    updated_at: createdAt,
    created_by: 0,
    sections: source.sections.map(section => ({
      ...section,
      id: makeId(),
      project_id: newId,
      document_overrides: '{}',
    })),
  };
  write([copy, ...read()]);
  return copy;
}

export function createLocalSection(
  projectId: number,
  data: Omit<SectionOut, 'id' | 'project_id'>
): SectionOut {
  const projects = read();
  const idx = projects.findIndex(p => p.id === projectId);
  if (idx === -1) throw new Error('Проект не найден');
  const maxOrder = projects[idx].sections.reduce((max, section) => Math.max(max, section.order), 0);
  const section = normalizeSection(projectId, { ...data, order: maxOrder + 1 });
  const updated = touch({ ...projects[idx], sections: [...projects[idx].sections, section] });
  projects[idx] = updated;
  write(projects);
  return section;
}

export function updateLocalSection(
  projectId: number,
  sectionId: number,
  data: Partial<SectionOut>
): SectionOut {
  const projects = read();
  const projectIdx = projects.findIndex(p => p.id === projectId);
  if (projectIdx === -1) throw new Error('Проект не найден');
  const sections = projects[projectIdx].sections;
  const sectionIdx = sections.findIndex(section => section.id === sectionId);
  if (sectionIdx === -1) throw new Error('Секция не найдена');
  const updatedSection = normalizeSection(projectId, { ...sections[sectionIdx], ...data });
  sections[sectionIdx] = updatedSection;
  projects[projectIdx] = touch({ ...projects[projectIdx], sections: [...sections] });
  write(projects);
  return updatedSection;
}

export function deleteLocalSection(projectId: number, sectionId: number) {
  const projects = read();
  const projectIdx = projects.findIndex(p => p.id === projectId);
  if (projectIdx === -1) throw new Error('Проект не найден');
  projects[projectIdx] = touch({
    ...projects[projectIdx],
    sections: projects[projectIdx].sections.filter(section => section.id !== sectionId),
  });
  write(projects);
}

export function saveLocalDocumentOverrides(projectId: number, sectionId: number, overrides: Record<string, unknown>) {
  const project = getLocalProject(projectId);
  const section = project.sections.find(item => item.id === sectionId);
  if (!section) throw new Error('Секция не найдена');

  let existing: Record<string, unknown> = {};
  try {
    existing = JSON.parse(section.document_overrides || '{}');
  } catch {
    existing = {};
  }
  return updateLocalSection(projectId, sectionId, {
    document_overrides: JSON.stringify({ ...existing, ...overrides }),
  });
}

export function clearLocalDocumentOverrides(projectId: number, sectionId: number) {
  return updateLocalSection(projectId, sectionId, { document_overrides: '{}' });
}

export function getLocalDocumentPayload(projectId: number, sectionId: number) {
  const project = getLocalProject(projectId);
  const section = project.sections.find(item => item.id === sectionId);
  if (!section) throw new Error('Секция не найдена');
  return {
    project: toList(project),
    section,
  };
}

export function getLocalProjectsSnapshot(): ProjectFull[] {
  return read();
}

export function clearLocalProjects() {
  localStorage.removeItem(LOCAL_PROJECTS_KEY);
}

export function getLocalProjectsSignature() {
  return read().map(project => `${project.id}:${project.updated_at}:${project.sections.length}`).join('|');
}
