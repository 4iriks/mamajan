import type { CsConfig, CsPoint, CsSplitConfig, Section } from './types';

const EPS = 1e-7;

export function csBounds(vertices: CsPoint[]) {
  return {
    minX: Math.min(...vertices.map(point => point.x)),
    maxX: Math.max(...vertices.map(point => point.x)),
    minY: Math.min(...vertices.map(point => point.y)),
    maxY: Math.max(...vertices.map(point => point.y)),
  };
}

// Same coordinate origin, limits and filtering as backend _split_positions.
export function csSplitPositions(config: CsSplitConfig, low: number, high: number): number[] {
  const count = Math.max(0, Math.min(20, Math.trunc(Number(config.count) || 0)));
  const inside = (value: number) => Number.isFinite(value) && value > low + EPS && value < high - EPS;
  if (config.mode === 'manual') {
    return [...new Set(config.positions || [])].filter(inside).sort((a, b) => a - b).slice(0, 20);
  }
  const span = Math.max(0, high - low);
  if (config.mode === 'from-left' || config.mode === 'from-right') {
    const step = Math.max(0, config.step ?? (count ? span / (count + 1) : 0));
    if (step <= EPS) return [];
    return Array.from({ length: count }, (_, index) => config.mode === 'from-left'
      ? low + step * (index + 1)
      : high - step * (index + 1)).filter(inside).sort((a, b) => a - b);
  }
  return Array.from({ length: count }, (_, index) => low + span * (index + 1) / (count + 1));
}

export function parseCsPositions(text: string, low: number, high: number): { positions: number[]; error?: string } {
  const tokens = text.trim().split(/[;,\s]+/).filter(Boolean);
  const positions = tokens.map(Number);
  if (tokens.some(token => !/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(token)) || positions.some(value => !Number.isFinite(value))) {
    return { positions: [], error: 'Введите координаты числами через запятую, точку с запятой или пробел.' };
  }
  if (positions.some(value => value <= low + EPS || value >= high - EPS)) {
    return { positions: [], error: `Координаты должны быть больше ${low} и меньше ${high} мм.` };
  }
  const unique = [...new Set(positions)].sort((a, b) => a - b);
  if (unique.length > 20) return { positions: [], error: 'Можно задать не более 20 линий.' };
  return { positions: unique };
}

/** Resize at the section update boundary so saving/calculating sees the same geometry. */
export function csDimensionUpdates(section: Section, updates: Partial<Section>): Partial<Section> {
  const config = section.csConfig;
  if (section.system !== 'ЦС' || !config || updates.csConfig !== undefined
    || (updates.width === undefined && updates.height === undefined)) return updates;

  const bounds = csBounds(config.vertices);
  // Keep the last valid coordinate frame when the user temporarily empties a field.
  const oldWidth = section.width > 0 ? section.width : (config.referenceWidth || Math.max(1, bounds.maxX));
  const oldHeight = section.height > 0 ? section.height : (config.referenceHeight || Math.max(1, bounds.maxY));
  const width = (updates.width ?? section.width) > 0 ? (updates.width ?? section.width) : oldWidth;
  const height = (updates.height ?? section.height) > 0 ? (updates.height ?? section.height) : oldHeight;
  const sx = width / oldWidth;
  const sy = height / oldHeight;
  const scaleSplit = (split: CsSplitConfig, factor: number): CsSplitConfig => ({
    ...split,
    // An explicit step remains a physical distance; manual coordinates follow the contour.
    ...(split.positions ? { positions: split.positions.map(position => position * factor) } : {}),
  });
  const resized: CsConfig = {
    ...config,
    referenceWidth: width,
    referenceHeight: height,
    vertices: config.vertices.map(point => ({ x: point.x * sx, y: point.y * sy })),
    vertical: scaleSplit(config.vertical, sx),
    horizontal: scaleSplit(config.horizontal, sy),
  };
  return { ...updates, csConfig: resized };
}
