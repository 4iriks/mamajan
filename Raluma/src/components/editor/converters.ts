import type { ExtraComponent, Section, SystemType } from './types';
import type { SectionOut } from '../../api/projects';

function parseExtraComponents(raw?: string): ExtraComponent[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((row, index) => ({
        id: typeof row?.id === 'string' ? row.id : `ec-${index}`,
        sku: String(row?.sku ?? row?.art ?? ''),
        name: String(row?.name ?? ''),
        color: String(row?.color ?? ''),
        size: String(row?.size ?? ''),
        qty: String(row?.qty ?? row?.quantity ?? ''),
      }))
      .filter(row => row.sku || row.name || row.color || row.size || row.qty);
  } catch {
    return [];
  }
}

function stringifyExtraComponents(rows?: ExtraComponent[]): string {
  const normalized = (rows ?? [])
    .map(row => ({
      sku: row.sku.trim(),
      name: row.name.trim(),
      color: row.color.trim(),
      size: row.size.trim(),
      qty: row.qty.trim(),
    }))
    .filter(row => row.sku || row.name || row.color || row.size || row.qty);
  return JSON.stringify(normalized);
}

function normalizeLegacyValue(field: string, value?: string): string | undefined {
  if (!value) return value;
  const replacements: Record<string, Record<string, string>> = {
    interGlassProfile: {
      'h-профиль RS1004': 'Профиль с зацепом RS3061',
    },
    lockLeft: {
      '1-сторонний RS3018': 'ЗАМОК-ЗАЩЕЛКА 1стор RS3018',
      'ЗАМОК-ЗАЩЕЛКА 1стор': 'ЗАМОК-ЗАЩЕЛКА 1стор RS3018',
      '2-сторонний с ключом RS3019': 'ЗАМОК двухсторонний с ключом RS3020',
      'ЗАМОК-ЗАЩЕЛКА 2стор с ключом': 'ЗАМОК двухсторонний с ключом RS3020',
    },
    lockRight: {
      '1-сторонний RS3018': 'ЗАМОК-ЗАЩЕЛКА 1стор RS3018',
      'ЗАМОК-ЗАЩЕЛКА 1стор': 'ЗАМОК-ЗАЩЕЛКА 1стор RS3018',
      '2-сторонний с ключом RS3019': 'ЗАМОК двухсторонний с ключом RS3020',
      'ЗАМОК-ЗАЩЕЛКА 2стор с ключом': 'ЗАМОК двухсторонний с ключом RS3020',
    },
    lock: {
      'RS3019 С ключом': 'ЗАМОК двухсторонний с ключом RS3020',
      'ЗАМОК-ЗАЩЕЛКА 2стор с ключом': 'ЗАМОК двухсторонний с ключом RS3020',
    },
    handleLeft: {
      'Ручка-скоба': 'Ручка-скоба 600мм RS30201',
    },
    handleRight: {
      'Ручка-скоба': 'Ручка-скоба 600мм RS30201',
    },
    centerHandle: {
      'Ручка-скоба': 'Ручка-скоба 600мм RS30201',
    },
    handle: {
      'Ручка-скоба': 'Ручка-скоба 600мм RS30201',
    },
  };
  return replacements[field]?.[value] ?? value;
}

function centerHandleSupportsOffset(value?: string): boolean {
  const handle = (value || '').toLowerCase();
  return handle.includes('rs3017') || handle.includes('ручка-скоба');
}

export function apiToLocal(s: SectionOut): Section {
  // Backwards compat: migrate legacy 'ДВЕРЬ' value
  const rawSystem = s.system === 'ДВЕРЬ' ? 'КОМПЛЕКТАЦИЯ' : s.system;
  const centerHandle = normalizeLegacyValue('centerHandle', s.center_handle);
  return {
    id: String(s.id),
    name: s.name,
    system: (rawSystem as SystemType) || 'СЛАЙД',
    width: s.width,
    height: s.height,
    panels: s.panels,
    quantity: s.quantity,
    glassType: s.glass_type,
    paintingType: s.painting_type as Section['paintingType'],
    ralColor: s.ral_color,
    cornerLeft: s.corner_left,
    cornerRight: s.corner_right,
    externalWidth: s.external_width,
    rails: s.rails as 3 | 5 | undefined,
    threshold: s.threshold,
    firstPanelInside: s.first_panel_inside,
    unusedTrack: s.unused_track,
    interGlassProfile: normalizeLegacyValue('interGlassProfile', s.inter_glass_profile),
    profileLeft: s.profile_left,
    profileRight: s.profile_right,
    lock: normalizeLegacyValue('lock', s.lock),
    handle: normalizeLegacyValue('handle', s.handle),
    floorLatchesLeft: s.floor_latches_left,
    floorLatchesRight: s.floor_latches_right,
    handleOffset: s.handle_offset,
    handleOffsetLeft: s.handle_offset_left,
    handleOffsetRight: s.handle_offset_right,
    profileLeftWall: s.profile_left_wall ?? false,
    profileLeftLockBar: s.profile_left_lock_bar ?? false,
    profileLeftPBar: s.profile_left_p_bar ?? false,
    profileLeftHandleBar: s.profile_left_handle_bar ?? false,
    profileLeftBubble: s.profile_left_bubble ?? false,
    profileRightWall: s.profile_right_wall ?? false,
    profileRightLockBar: s.profile_right_lock_bar ?? false,
    profileRightPBar: s.profile_right_p_bar ?? false,
    profileRightHandleBar: s.profile_right_handle_bar ?? false,
    profileRightBubble: s.profile_right_bubble ?? false,
    lockLeft: normalizeLegacyValue('lockLeft', s.lock_left),
    lockRight: normalizeLegacyValue('lockRight', s.lock_right),
    slideRows: s.slide_rows ?? 1,
    centerHandle,
    centerLock: s.center_lock,
    centerHandleOffset: centerHandleSupportsOffset(centerHandle)
      ? s.center_handle_offset
      : undefined,
    centerFloorLatchesLeft: s.center_floor_latches_left ?? false,
    centerFloorLatchesRight: s.center_floor_latches_right ?? false,
    bookSubtype: s.book_subtype,
    handleLeft: normalizeLegacyValue('handleLeft', s.handle_left),
    handleRight: normalizeLegacyValue('handleRight', s.handle_right),
    doors: s.doors,
    doorSide: s.door_side,
    doorType: s.door_type,
    doorOpening: s.door_opening,
    compensator: s.compensator,
    angleLeft: s.angle_left,
    angleRight: s.angle_right,
    bookSystem: s.book_system,
    liftFillingType: s.lift_filling_type,
    liftFillingCustom: s.lift_filling_custom,
    liftControlType: s.lift_control_type,
    liftRemote1chQty: s.lift_remote_1ch_qty ?? 0,
    liftRemote6chQty: s.lift_remote_6ch_qty ?? 0,
    liftCableSide: s.lift_cable_side,
    liftOpeningType: s.lift_opening_type,
    doorSystem: s.door_system,
    csShape: s.cs_shape,
    csWidth2: s.cs_width2,
    extraParts: s.extra_parts,
    extraComponents: parseExtraComponents(s.extra_components),
    comments: s.comments,
    documentOverrides: s.document_overrides,
  };
}

export function localToApi(s: Section, order: number): Omit<SectionOut, 'id' | 'project_id'> {
  return {
    name: s.name, order,
    system: s.system,
    width: s.width, height: s.height, panels: s.panels, quantity: s.quantity,
    glass_type: s.glassType, painting_type: s.paintingType,
    ral_color: s.ralColor, corner_left: s.cornerLeft, corner_right: s.cornerRight,
    external_width: s.externalWidth,
    rails: s.rails, threshold: s.threshold, first_panel_inside: s.firstPanelInside,
    unused_track: s.unusedTrack, inter_glass_profile: s.interGlassProfile,
    profile_left: s.profileLeft, profile_right: s.profileRight,
    lock: s.lock, handle: s.handle,
    floor_latches_left: s.floorLatchesLeft, floor_latches_right: s.floorLatchesRight,
    handle_offset: s.handleOffset,
    handle_offset_left: s.handleOffsetLeft,
    handle_offset_right: s.handleOffsetRight,
    profile_left_wall: s.profileLeftWall,
    profile_left_lock_bar: s.profileLeftLockBar,
    profile_left_p_bar: s.profileLeftPBar,
    profile_left_handle_bar: s.profileLeftHandleBar,
    profile_left_bubble: s.profileLeftBubble,
    profile_right_wall: s.profileRightWall,
    profile_right_lock_bar: s.profileRightLockBar,
    profile_right_p_bar: s.profileRightPBar,
    profile_right_handle_bar: s.profileRightHandleBar,
    profile_right_bubble: s.profileRightBubble,
    lock_left: s.lockLeft,
    lock_right: s.lockRight,
    slide_rows: s.slideRows,
    center_handle: s.centerHandle,
    center_lock: s.centerLock,
    center_handle_offset: centerHandleSupportsOffset(s.centerHandle)
      ? s.centerHandleOffset
      : undefined,
    center_floor_latches_left: s.centerFloorLatchesLeft,
    center_floor_latches_right: s.centerFloorLatchesRight,
    book_subtype: s.bookSubtype,
    handle_left: s.handleLeft,
    handle_right: s.handleRight,
    doors: s.doors, door_side: s.doorSide, door_type: s.doorType,
    door_opening: s.doorOpening, compensator: s.compensator,
    angle_left: s.angleLeft, angle_right: s.angleRight, book_system: s.bookSystem,
    lift_filling_type: s.liftFillingType,
    lift_filling_custom: s.liftFillingCustom,
    lift_control_type: s.liftControlType,
    lift_remote_1ch_qty: s.liftRemote1chQty ?? 0,
    lift_remote_6ch_qty: s.liftRemote6chQty ?? 0,
    lift_cable_side: s.liftCableSide,
    lift_opening_type: s.liftOpeningType,
    door_system: s.doorSystem, cs_shape: s.csShape, cs_width2: s.csWidth2,
    extra_parts: s.extraParts, comments: s.comments,
    extra_components: stringifyExtraComponents(s.extraComponents),
    document_overrides: s.documentOverrides,
  };
}

export function localToTemplateData(s: Section): Partial<SectionOut> {
  const data: Partial<SectionOut> = { ...localToApi(s, 0) };
  delete data.name;
  delete data.order;
  delete data.document_overrides;
  delete data.lift_remote_1ch_qty;
  delete data.lift_remote_6ch_qty;
  return data;
}

export function applyTemplateDataToSection(
  section: Section,
  templateData: Partial<SectionOut>,
): Section {
  const currentApi = localToApi(section, 0);
  const merged: SectionOut = {
    ...currentApi,
    ...templateData,
    id: Number.parseInt(section.id, 10) || 0,
    project_id: 0,
    order: currentApi.order,
    name: section.name,
    document_overrides: '{}',
  };
  return apiToLocal(merged);
}
