import type { ExtraComponent, Section, SystemType } from './types';
import type { SectionOut } from '../../api/projects';
import { bookExtraDoorPanelOptions, normalizeBookSystem } from '../../constants/book';
import { normalizeGlassType } from '../../constants/glass';

export function cloneExtraComponents(rows?: ExtraComponent[]): ExtraComponent[] {
  return (rows ?? []).map(row => ({ ...row }));
}

function optionalId(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

export function parseExtraComponents(raw?: string): ExtraComponent[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((row, index) => ({
        id: typeof row?.id === 'string' ? row.id : `ec-${index}`,
        catalogItemId: optionalId(row?.catalogItemId ?? row?.catalog_item_id),
        finishVariantId: optionalId(row?.finishVariantId ?? row?.finish_variant_id),
        sku: String(row?.sku ?? row?.art ?? ''),
        name: String(row?.name ?? ''),
        category: ['profile', 'component', 'service'].includes(row?.category)
          ? row.category
          : undefined,
        color: String(row?.color ?? ''),
        finishName: String(row?.finishName ?? row?.finish_name ?? row?.color ?? ''),
        requiresPaint: Boolean(row?.requiresPaint ?? row?.requires_paint),
        unitPrice: String(row?.unitPrice ?? row?.unit_price ?? ''),
        size: String(row?.size ?? ''),
        qty: String(row?.qty ?? row?.quantity ?? ''),
        unit: String(row?.unit ?? 'шт'),
        imageFile: String(row?.imageFile ?? row?.image_file ?? ''),
        imageData: String(row?.imageData ?? row?.image_data ?? ''),
        deliveryStage: (
          (row?.deliveryStage ?? row?.delivery_stage) === '1' || (row?.deliveryStage ?? row?.delivery_stage) === '2'
            ? (row.deliveryStage ?? row.delivery_stage)
            : 'both'
        ) as ExtraComponent['deliveryStage'],
      }))
      .filter(row => row.sku || row.name || row.color || row.size || row.qty);
  } catch {
    return [];
  }
}

export function stringifyExtraComponents(rows?: ExtraComponent[]): string {
  const normalized = (rows ?? [])
    .map(row => {
      const isManual = !row.catalogItemId;
      const color = row.color.trim();
      return {
        catalog_item_id: row.catalogItemId,
        finish_variant_id: row.finishVariantId,
        sku: row.sku.trim(),
        name: row.name.trim(),
        category: row.category || (isManual ? 'component' : undefined),
        color,
        finish_name: (row.finishName || '').trim(),
        requires_paint: isManual ? Boolean(color) : Boolean(row.requiresPaint),
        size: row.size.trim(),
        qty: row.qty.trim(),
        unit: row.category === 'profile' ? 'шт' : (row.unit || 'шт').trim() || 'шт',
        image_file: (row.imageFile || '').trim(),
        image_data: (row.imageData || '').trim(),
        delivery_stage: row.deliveryStage || 'both',
      };
    })
    .filter(row => Boolean(row.catalog_item_id || row.sku || row.name));
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
  const hasNewBookFixedPanels = Boolean(
    s.book_left_fixed_left_enabled
    || s.book_left_fixed_right_enabled
    || s.book_right_fixed_left_enabled
    || s.book_right_fixed_right_enabled
  );
  let bookLeftFixedLeftEnabled = s.book_left_fixed_left_enabled ?? false;
  let bookLeftFixedRightEnabled = s.book_left_fixed_right_enabled ?? false;
  let bookRightFixedLeftEnabled = s.book_right_fixed_left_enabled ?? false;
  let bookRightFixedRightEnabled = s.book_right_fixed_right_enabled ?? false;
  let bookLeftFixedLeftWidth = s.book_left_fixed_left_width;
  let bookLeftFixedRightWidth = s.book_left_fixed_right_width;
  let bookRightFixedLeftWidth = s.book_right_fixed_left_width;
  let bookRightFixedRightWidth = s.book_right_fixed_right_width;
  if (!hasNewBookFixedPanels && s.book_extra_fixed_enabled) {
    const legacyFixedRight = (s.book_extra_fixed_side || '').toLowerCase() === 'right';
    if (bookDoorLayout === 'right') {
      bookRightFixedLeftEnabled = !legacyFixedRight;
      bookRightFixedRightEnabled = legacyFixedRight;
      bookRightFixedLeftWidth = !legacyFixedRight ? s.book_extra_fixed_width : undefined;
      bookRightFixedRightWidth = legacyFixedRight ? s.book_extra_fixed_width : undefined;
    } else if (bookDoorLayout === 'both' && legacyFixedRight) {
      bookRightFixedRightEnabled = true;
      bookRightFixedRightWidth = s.book_extra_fixed_width;
    } else if (bookDoorLayout === 'left' && legacyFixedRight) {
      bookLeftFixedRightEnabled = true;
      bookLeftFixedRightWidth = s.book_extra_fixed_width;
    } else {
      bookLeftFixedLeftEnabled = true;
      bookLeftFixedLeftWidth = s.book_extra_fixed_width;
    }
  }
  return {
    id: String(s.id),
    order: s.order,
    name: s.name,
    system: (rawSystem as SystemType) || 'СЛАЙД',
    width: s.width,
    height: s.height,
    panels: s.panels,
    quantity: s.quantity,
    glassType: normalizeGlassType(s.glass_type, rawSystem || 'СЛАЙД'),
    glassSupplied: ['СЛАЙД', 'КНИЖКА'].includes(s.system) ? (s.glass_supplied ?? true) : true,
    priceGroupId: s.price_group_id,
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
    bookLeftDoorWidth: s.book_left_door_width,
    bookRightDoorWidth: s.book_right_door_width,
    bookLeftFixedLeftEnabled,
    bookLeftFixedLeftWidth,
    bookLeftFixedRightEnabled,
    bookLeftFixedRightWidth,
    bookRightFixedLeftEnabled,
    bookRightFixedLeftWidth,
    bookRightFixedRightEnabled,
    bookRightFixedRightWidth,
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
    comments: s.comments,
    documentOverrides: s.document_overrides,
  };
}

export function localToApi(s: Section, fallbackIndex: number): Omit<SectionOut, 'id' | 'project_id'> {
  const extraDoorOptions = bookExtraDoorPanelOptions({
    panelCount: s.panels,
    doorLayout: s.doorSide,
    extraFixedEnabled: s.bookExtraFixedEnabled,
    extraFixedSide: s.bookExtraFixedSide,
    leftFixedLeftEnabled: s.bookLeftFixedLeftEnabled,
    leftFixedRightEnabled: s.bookLeftFixedRightEnabled,
    rightFixedLeftEnabled: s.bookRightFixedLeftEnabled,
    rightFixedRightEnabled: s.bookRightFixedRightEnabled,
  });
  const extraDoorPanel = extraDoorOptions.includes(s.bookExtraDoorPanel || 0)
    ? s.bookExtraDoorPanel
    : extraDoorOptions[0];
  const leftBookStackPanels = Math.max(
    1,
    Math.min(s.bookLeftStackPanels || Math.floor(s.panels / 2), s.panels - 1),
  );
  return {
    name: s.name, order: s.order ?? fallbackIndex + 1,
    system: s.system,
    width: s.width, height: s.height, panels: s.panels, quantity: s.quantity,
    glass_type: normalizeGlassType(s.glassType, s.system), painting_type: s.paintingType,
    glass_supplied: ['СЛАЙД', 'КНИЖКА'].includes(s.system) ? (s.glassSupplied ?? true) : true,
    price_group_id: s.priceGroupId,
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
    book_left_door_width: s.bookLeftDoorWidth,
    book_right_door_width: s.bookRightDoorWidth,
    book_left_fixed_left_enabled: s.bookLeftFixedLeftEnabled ?? false,
    book_left_fixed_left_width: s.bookLeftFixedLeftWidth,
    book_left_fixed_right_enabled: s.bookLeftFixedRightEnabled ?? false,
    book_left_fixed_right_width: s.bookLeftFixedRightWidth,
    book_right_fixed_left_enabled: s.bookRightFixedLeftEnabled ?? false,
    book_right_fixed_left_width: s.bookRightFixedLeftWidth,
    book_right_fixed_right_enabled: s.bookRightFixedRightEnabled ?? false,
    book_right_fixed_right_width: s.bookRightFixedRightWidth,
    book_obstacle_distance: s.bookObstacleDistance,
    book_left_stack_panels: s.doorSide === 'both'
      ? leftBookStackPanels
      : s.bookLeftStackPanels,
    book_handle_height: s.bookHandleHeight,
    book_extra_fixed_enabled: false,
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
    extra_parts: undefined, comments: s.comments,
    extra_components: '[]',
    document_overrides: s.documentOverrides,
  };
}
