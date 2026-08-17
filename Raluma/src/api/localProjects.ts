import type { ProjectFull, ProjectList, SectionOut } from './projects';
import { defaultGlassType, normalizeGlassType } from '../constants/glass';
import { normalizeBookSystem } from '../constants/book';

export const LOCAL_PROJECTS_KEY = 'raluma-local-projects-v1';

const makeId = () => Date.now() + Math.floor(Math.random() * 100000);
const nowIso = () => new Date().toISOString();

function handleSupportsOffset(value?: string): boolean {
  const handle = (value || '').toLowerCase();
  return handle.includes('rs3017') || handle.includes('стеклян') || handle.includes('скоб');
}

function read(): ProjectFull[] {
  try {
    const raw = localStorage.getItem(LOCAL_PROJECTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.map(project => normalizeProject(project))
      : [];
  } catch {
    return [];
  }
}

function parseExtraComponents(raw?: string): Array<Record<string, unknown>> {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object')
      : [];
  } catch {
    return [];
  }
}

function extraComponentKey(row: Record<string, unknown>): string {
  const value = (...keys: string[]) => {
    const key = keys.find(candidate => row[candidate] !== undefined && row[candidate] !== null);
    return key ? String(row[key]).trim().toLocaleLowerCase('ru') : '';
  };
  return JSON.stringify([
    value('catalog_item_id', 'catalogItemId'),
    value('finish_variant_id', 'finishVariantId'),
    value('sku', 'art', 'article'),
    value('name'),
    value('color'),
    value('finish_name', 'finishName'),
    value('size'),
    value('unit'),
    value('deliveryStage', 'delivery_stage', 'stage'),
  ]);
}

function migrateLocalSectionExtras(project: ProjectFull): string {
  const merged = new Map<string, Record<string, unknown>>();
  const add = (source: Record<string, unknown>, multiplier = 1) => {
    const row = { ...source };
    const quantity = Number(row.qty ?? row.quantity ?? 0);
    const migratedQuantity = Number.isFinite(quantity) ? quantity * multiplier : 0;
    row.qty = migratedQuantity;
    delete row.quantity;
    const key = extraComponentKey(row);
    const existing = merged.get(key);
    if (existing) {
      existing.qty = Number(existing.qty ?? 0) + migratedQuantity;
    } else {
      merged.set(key, row);
    }
  };

  parseExtraComponents(project.extra_components).forEach(row => add(row));
  (project.sections || []).forEach(section => {
    const multiplier = Math.max(1, Number(section.quantity) || 1);
    parseExtraComponents(section.extra_components).forEach(row => add(row, multiplier));
  });
  return JSON.stringify([...merged.values()]);
}

function normalizeProject(project: ProjectFull): ProjectFull {
  const sections = Array.isArray(project.sections)
    ? project.sections.map(section => normalizeSection(project.id, section))
    : [];
  return {
    ...project,
    order_number: project.order_number ?? project.number,
    extra_parts: undefined,
    extra_components: migrateLocalSectionExtras(project),
    // Projects saved before this field existed must keep their former work order.
    hardware_installation: project.hardware_installation ?? 'not_installed',
    sections,
  };
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
  const rawBookSide = (section.door_side || '').trim().toLowerCase().replace('ё', 'е');
  const legacyDoors = section.doors ?? 0;
  const bookDoorLayout = (
    legacyDoors >= 2
    || ['both', 'обе', 'оба', 'левая и правая', 'слева и справа', 'с обеих сторон'].includes(rawBookSide)
  )
    ? 'both'
    : ['left', 'левая', 'лев', 'слева'].includes(rawBookSide)
      ? 'left'
      : ['right', 'правая', 'прав', 'справа'].includes(rawBookSide)
        ? 'right'
        : legacyDoors > 0 ? 'right' : 'none';
  const legacyHardware = (
    (section.door_type || '').toLowerCase().includes('зам')
    || (section.door_type || '').toLowerCase().includes('тип 4')
  ) ? 'lock' : 'handle';
  const rawOpening = (section.door_opening || '').trim().toLowerCase().replace('ё', 'е');
  const legacyOpening = rawOpening.includes('снаружи') && rawOpening.includes('наружу')
    ? 'outside_out'
    : rawOpening.includes('снаружи') && rawOpening.includes('внутрь')
      ? 'outside_in'
      : rawOpening.includes('наружу') ? 'inside_out' : 'inside_in';
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
    glass_type: normalizeGlassType(
      section.glass_type?.trim() || defaultGlassType(section.system ?? 'СЛАЙД'),
      section.system ?? 'СЛАЙД',
    ),
    glass_supplied: section.system === 'СЛАЙД' ? (section.glass_supplied ?? true) : true,
    price_group_id: section.price_group_id,
    painting_type: section.painting_type ?? 'RAL стандарт',
    ral_color: section.ral_color ?? '9016 МАТОВЫЙ',
    corner_left: section.corner_left ?? false,
    corner_right: section.corner_right ?? false,
    external_width: section.external_width,
    rails: section.rails,
    threshold: section.threshold ?? 'Стандартный окраш',
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
    handle_offset_left: handleSupportsOffset(section.handle_left)
      ? section.handle_offset_left
      : undefined,
    handle_offset_right: handleSupportsOffset(section.handle_right)
      ? section.handle_offset_right
      : undefined,
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
    book_system: normalizeBookSystem(section.book_system),
    book_left_door_hardware: section.book_left_door_hardware
      ?? (bookDoorLayout === 'left' || bookDoorLayout === 'both' ? legacyHardware : undefined),
    book_right_door_hardware: section.book_right_door_hardware
      ?? (bookDoorLayout === 'right' || bookDoorLayout === 'both' ? legacyHardware : undefined),
    book_left_door_opening: section.book_left_door_opening
      ?? (bookDoorLayout === 'left' || bookDoorLayout === 'both' ? legacyOpening : undefined),
    book_right_door_opening: section.book_right_door_opening
      ?? (bookDoorLayout === 'right' || bookDoorLayout === 'both' ? legacyOpening : undefined),
    book_obstacle_distance: section.book_obstacle_distance,
    book_left_stack_panels: section.book_left_stack_panels,
    book_handle_height: section.book_handle_height,
    book_extra_fixed_enabled: section.book_extra_fixed_enabled ?? false,
    book_extra_fixed_width: section.book_extra_fixed_width,
    book_extra_fixed_side: section.book_extra_fixed_side,
    book_extra_door_enabled: section.book_extra_door_enabled ?? false,
    book_extra_door_panel: section.book_extra_door_panel,
    book_extra_door_width: section.book_extra_door_width,
    book_extra_door_opening: section.book_extra_door_opening,
    lift_filling_type: section.lift_filling_type ?? 'СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
    lift_filling_custom: section.lift_filling_custom,
    lift_control_type: section.lift_control_type ?? 'Пульт ДУ',
    lift_remote_1ch_qty: section.lift_remote_1ch_qty ?? 0,
    lift_remote_6ch_qty: section.lift_remote_6ch_qty ?? 0,
    lift_cable_side: section.lift_cable_side ?? 'Справа',
    lift_opening_type: section.lift_opening_type ?? 'Сдвиг вниз',
    door_system: section.door_system,
    cs_shape: section.cs_shape,
    cs_width2: section.cs_width2,
    extra_parts: undefined,
    extra_components: '[]',
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

export function createLocalProject(data: { number?: string; order_number?: string; customer: string; production_stages?: number }): ProjectFull {
  const projects = read();
  const createdAt = nowIso();
  const project: ProjectFull = {
    id: makeId(),
    number: data.order_number ?? data.number ?? '',
    invoice_number: null,
    order_number: data.order_number ?? data.number ?? '',
    customer: data.customer,
    system: '',
    subtype: undefined,
    extra_parts: undefined,
    extra_components: '[]',
    hardware_installation: 'installed',
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
    paint_manual_rows: undefined,
    delivery_note_data: undefined,
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
    number: '',
    invoice_number: null,
    order_number: null,
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
