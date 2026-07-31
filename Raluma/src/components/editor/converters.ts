import type { ExtraComponent, Section, SystemType } from './types';
import type { SectionOut } from '../../api/projects';
import { bookExtraDoorPanelOptions, normalizeBookSystem } from '../../constants/book';

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
        unit: String(row?.unit ?? 'шт'),
        imageFile: String(row?.imageFile ?? row?.image_file ?? ''),
        deliveryStage: (
          row?.deliveryStage === '1' || row?.deliveryStage === '2'
            ? row.deliveryStage
            : 'both'
        ) as ExtraComponent['deliveryStage'],
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
      unit: (row.unit || 'шт').trim() || 'шт',
      imageFile: (row.imageFile || '').trim(),
      deliveryStage: row.deliveryStage || 'both',
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
      'Стеклянная ручка': 'Стеклянная ручка RS3017',
      'Ручка-скоба': 'Ручка-скоба 600мм RS30201',
    },
    handleRight: {
      'Стеклянная ручка': 'Стеклянная ручка RS3017',
      'Ручка-скоба': 'Ручка-скоба 600мм RS30201',
    },
    centerHandle: {
      'Стеклянная ручка': 'Стеклянная ручка RS3017',
      'Ручка-скоба': 'Ручка-скоба 600мм RS30201',
    },
    handle: {
      'Ручка-скоба': 'Ручка-скоба 600мм RS30201',
    },
  };
  return replacements[field]?.[value] ?? value;
}

function handleSupportsOffset(value?: string): boolean {
  const handle = (value || '').toLowerCase();
  return handle.includes('rs3017') || handle.includes('стеклян') || handle.includes('скоб');
}

function normalizeBookDoorLayout(side?: string, doors?: number): 'none' | 'left' | 'right' | 'both' {
  const value = (side || '').trim().toLowerCase().replace('ё', 'е');
  if (
    (doors ?? 0) >= 2
    || ['both', 'обе', 'оба', 'левая и правая', 'слева и справа', 'с обеих сторон'].includes(value)
  ) return 'both';
  if (['left', 'левая', 'лев', 'слева'].includes(value)) return 'left';
  if (['right', 'правая', 'прав', 'справа'].includes(value)) return 'right';
  if (['none', 'без', 'без дверей'].includes(value) || doors === 0) return 'none';
  return (doors ?? 0) > 0 ? 'right' : 'none';
}

function normalizeBookHardware(value?: string): 'handle' | 'lock' {
  const normalized = (value || '').trim().toLowerCase();
  return normalized.includes('зам') || normalized.includes('тип 4') || normalized === 'lock'
    ? 'lock'
    : 'handle';
}

function normalizeBookOpening(value?: string): 'inside_in' | 'inside_out' | 'outside_out' | 'outside_in' {
  const normalized = (value || '')
    .trim()
    .toLowerCase()
    .replace('ё', 'е')
    .replaceAll('_', ' ')
    .replaceAll('/', ' ')
    .replace(/\s+/g, ' ');
  const openings: Record<string, 'inside_in' | 'inside_out' | 'outside_out' | 'outside_in'> = {
    'inside in': 'inside_in',
    'inside out': 'inside_out',
    'outside out': 'outside_out',
    'outside in': 'outside_in',
    'изнутри внутрь': 'inside_in',
    'изнутри наружу': 'inside_out',
    'снаружи наружу': 'outside_out',
    'снаружи внутрь': 'outside_in',
    'внутрь': 'inside_in',
    'наружу': 'inside_out',
  };
  return openings[normalized] ?? 'inside_in';
}

export function apiToLocal(s: SectionOut): Section {
  // Backwards compat: migrate legacy 'ДВЕРЬ' value
  const rawSystem = s.system === 'ДВЕРЬ' ? 'КОМПЛЕКТАЦИЯ' : s.system;
  const centerHandle = normalizeLegacyValue('centerHandle', s.center_handle);
  const handleLeft = normalizeLegacyValue('handleLeft', s.handle_left);
  const handleRight = normalizeLegacyValue('handleRight', s.handle_right);
  const bookDoorLayout = normalizeBookDoorLayout(s.door_side, s.doors);
  const legacyBookHardware = normalizeBookHardware(s.door_type);
  const legacyBookOpening = normalizeBookOpening(s.door_opening);
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
    handleOffsetLeft: handleSupportsOffset(handleLeft) ? s.handle_offset_left : undefined,
    handleOffsetRight: handleSupportsOffset(handleRight) ? s.handle_offset_right : undefined,
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
    centerHandleOffset: handleSupportsOffset(centerHandle)
      ? s.center_handle_offset
      : undefined,
    centerFloorLatchesLeft: s.center_floor_latches_left ?? false,
    centerFloorLatchesRight: s.center_floor_latches_right ?? false,
    bookSubtype: s.book_subtype,
    handleLeft,
    handleRight,
    doors: bookDoorLayout === 'both' ? 2 : bookDoorLayout === 'none' ? 0 : 1,
    doorSide: bookDoorLayout,
    doorType: s.door_type,
    doorOpening: s.door_opening,
    compensator: s.compensator,
    angleLeft: s.angle_left,
    angleRight: s.angle_right,
    bookSystem: normalizeBookSystem(s.book_system),
    bookLeftDoorHardware: s.book_left_door_hardware
      ?? (bookDoorLayout === 'left' || bookDoorLayout === 'both' ? legacyBookHardware : undefined),
    bookRightDoorHardware: s.book_right_door_hardware
      ?? (bookDoorLayout === 'right' || bookDoorLayout === 'both' ? legacyBookHardware : undefined),
    bookLeftDoorOpening: s.book_left_door_opening
      ?? (bookDoorLayout === 'left' || bookDoorLayout === 'both' ? legacyBookOpening : undefined),
    bookRightDoorOpening: s.book_right_door_opening
      ?? (bookDoorLayout === 'right' || bookDoorLayout === 'both' ? legacyBookOpening : undefined),
    bookObstacleDistance: s.book_obstacle_distance,
    bookLeftStackPanels: s.book_left_stack_panels,
    bookHandleHeight: s.book_handle_height,
    bookExtraFixedEnabled: s.book_extra_fixed_enabled ?? false,
    bookExtraFixedWidth: s.book_extra_fixed_width,
    bookExtraFixedSide: s.book_extra_fixed_side,
    bookExtraDoorEnabled: s.book_extra_door_enabled ?? false,
    bookExtraDoorPanel: s.book_extra_door_panel,
    bookExtraDoorWidth: s.book_extra_door_width,
    bookExtraDoorOpening: s.book_extra_door_opening,
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
  const extraDoorOptions = bookExtraDoorPanelOptions({
    panelCount: s.panels,
    doorLayout: s.doorSide,
    extraFixedEnabled: s.bookExtraFixedEnabled,
    extraFixedSide: s.bookExtraFixedSide,
  });
  const extraDoorPanel = extraDoorOptions.includes(s.bookExtraDoorPanel || 0)
    ? s.bookExtraDoorPanel
    : extraDoorOptions[0];
  const physicalBookPanels = s.panels + (s.bookExtraFixedEnabled ? 1 : 0);
  const leftBookStackPanels = Math.max(
    1,
    Math.min(s.bookLeftStackPanels || Math.floor(physicalBookPanels / 2), physicalBookPanels - 1),
  );
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
    handle_offset_left: handleSupportsOffset(s.handleLeft) ? s.handleOffsetLeft : undefined,
    handle_offset_right: handleSupportsOffset(s.handleRight) ? s.handleOffsetRight : undefined,
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
    center_handle_offset: handleSupportsOffset(s.centerHandle)
      ? s.centerHandleOffset
      : undefined,
    center_floor_latches_left: s.centerFloorLatchesLeft,
    center_floor_latches_right: s.centerFloorLatchesRight,
    book_subtype: s.bookSubtype,
    handle_left: s.handleLeft,
    handle_right: s.handleRight,
    doors: s.doors, door_side: s.doorSide, door_type: s.doorType,
    door_opening: s.doorOpening, compensator: s.compensator,
    angle_left: s.angleLeft,
    angle_right: s.angleRight,
    book_system: normalizeBookSystem(s.bookSystem),
    book_left_door_hardware: s.bookLeftDoorHardware,
    book_right_door_hardware: s.bookRightDoorHardware,
    book_left_door_opening: s.bookLeftDoorOpening,
    book_right_door_opening: s.bookRightDoorOpening,
    book_obstacle_distance: s.bookObstacleDistance,
    book_left_stack_panels: s.doorSide === 'both'
      ? leftBookStackPanels
      : s.bookLeftStackPanels,
    book_handle_height: s.bookHandleHeight,
    book_extra_fixed_enabled: s.bookExtraFixedEnabled ?? false,
    book_extra_fixed_width: s.bookExtraFixedWidth,
    book_extra_fixed_side: s.bookExtraFixedSide,
    book_extra_door_enabled: s.bookExtraDoorEnabled ?? false,
    book_extra_door_panel: s.bookExtraDoorEnabled ? extraDoorPanel : undefined,
    book_extra_door_width: s.bookExtraDoorWidth,
    book_extra_door_opening: s.bookExtraDoorOpening,
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
