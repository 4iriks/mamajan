export type BookProfileSystem = 'B25' | 'B16' | 'B17' | 'C16' | 'C17';

export const BOOK_PROFILE_SYSTEMS: Array<{
  value: BookProfileSystem;
  label: string;
}> = [
  { value: 'B25', label: 'B25' },
  { value: 'B16', label: 'B16' },
  { value: 'B17', label: 'B17' },
  { value: 'C16', label: 'C16' },
  { value: 'C17', label: 'C17' },
];

const BOOK_SYSTEM_ALIASES: Record<string, BookProfileSystem> = {
  'В25': 'B25',
  'В16': 'B16',
  'В17': 'B17',
  'С16': 'C16',
  'С17': 'C17',
  // Первая версия формы сохраняла эти значения, но считала их как B25.
  'С КАРЕТКОЙ': 'B25',
  'БЕЗ КАРЕТКИ': 'B25',
};

export function normalizeBookSystem(value?: string): BookProfileSystem {
  const raw = (value || '').trim().toUpperCase().replaceAll('Ё', 'Е');
  if (!raw) return 'B25';
  if (BOOK_PROFILE_SYSTEMS.some(item => item.value === raw)) {
    return raw as BookProfileSystem;
  }
  return BOOK_SYSTEM_ALIASES[raw] || 'B25';
}

export function bookExtraDoorPanelOptions({
  panelCount,
  doorLayout,
  extraFixedEnabled,
  extraFixedSide,
  leftFixedLeftEnabled,
  leftFixedRightEnabled,
  rightFixedLeftEnabled,
  rightFixedRightEnabled,
}: {
  panelCount: number;
  doorLayout?: string;
  extraFixedEnabled?: boolean;
  extraFixedSide?: string;
  leftFixedLeftEnabled?: boolean;
  leftFixedRightEnabled?: boolean;
  rightFixedLeftEnabled?: boolean;
  rightFixedRightEnabled?: boolean;
}): number[] {
  const hasNewFixedPanels = Boolean(
    leftFixedLeftEnabled
    || leftFixedRightEnabled
    || rightFixedLeftEnabled
    || rightFixedRightEnabled
  );
  const leftDoor = doorLayout === 'left' || doorLayout === 'both';
  const rightDoor = doorLayout === 'right' || doorLayout === 'both';
  const roles: Array<'standard' | 'door' | 'fixed'> = [];
  const baseDoorCount = Number(leftDoor) + Number(rightDoor);
  const standardCount = Math.max(0, panelCount - baseDoorCount);

  if (hasNewFixedPanels) {
    if (leftDoor && leftFixedLeftEnabled) roles.push('fixed');
    if (leftDoor) roles.push('door');
    if (leftDoor && leftFixedRightEnabled) roles.push('fixed');
    roles.push(...Array.from({ length: standardCount }, () => 'standard' as const));
    if (rightDoor && rightFixedLeftEnabled) roles.push('fixed');
    if (rightDoor) roles.push('door');
    if (rightDoor && rightFixedRightEnabled) roles.push('fixed');
  } else {
    roles.push(...Array.from({ length: panelCount }, () => 'standard' as const));
    const fixedPanel = extraFixedEnabled
      ? extraFixedSide === 'right' ? roles.length : 0
      : undefined;
    if (fixedPanel !== undefined) roles.splice(fixedPanel, 0, 'fixed');
    const movingIndices = roles
      .map((role, index) => role !== 'fixed' ? index : -1)
      .filter(index => index >= 0);
    if (leftDoor && movingIndices[0] !== undefined) roles[movingIndices[0]] = 'door';
    if (rightDoor && movingIndices.at(-1) !== undefined) roles[movingIndices.at(-1)!] = 'door';
  }

  return roles
    .map((role, index) => role === 'standard' ? index + 1 : 0)
    .filter(Boolean);
}
