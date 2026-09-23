import type { CsConfig, CsPoint, CsSplitConfig, Section } from './types';

const EPS = 1e-7;

export function normalizeCsConfig(config: CsConfig): CsConfig {
  const edgeTreatments = config.edgeTreatments ?? config.vertices.map((_, index) => (config.profiledEdges?.includes(index) ?? true) ? 'clamp' as const : 'none' as const);
  return { ...config, version: 2, dimensionMode: config.dimensionMode ?? 'installation',
    bubbleDeductionMm: config.bubbleDeductionMm ?? 6, edgeTreatments,
    profiledEdges: edgeTreatments.flatMap((kind, index) => kind === 'clamp' ? [index] : []) };
}

/** Same per-side miter intersections as the authoritative server calculation. */
export function csOffsetContour(vertices: CsPoint[], distances: number[]): CsPoint[] {
  const winding = orientation(vertices);
  const lines = vertices.map((point, index) => {
    const end = vertices[(index + 1) % vertices.length];
    const dx = end.x - point.x, dy = end.y - point.y;
    const length = Math.hypot(dx, dy);
    if (length < EPS) throw new Error('Соседние углы не должны совпадать');
    return { x: point.x - dy / length * winding * distances[index],
      y: point.y + dx / length * winding * distances[index], dx, dy };
  });
  const result = lines.map((b, index) => {
    const a = lines[(index - 1 + lines.length) % lines.length];
    const determinant = a.dx * b.dy - a.dy * b.dx;
    if (Math.abs(determinant) <= EPS) {
      if (Math.abs(distances[(index - 1 + lines.length) % lines.length] - distances[index]) > EPS || a.dx * b.dx + a.dy * b.dy <= 0) throw new Error('На одной прямой задайте одинаковую комплектацию сторон');
      return { x: b.x, y: b.y };
    }
    const factor = ((b.x - a.x) * b.dy - (b.y - a.y) * b.dx) / determinant;
    return { x: a.x + factor * a.dx, y: a.y + factor * a.dy };
  });
  const error = csContourError(result);
  if (error) throw new Error(error);
  result.forEach((point, index) => {
    const end = result[(index + 1) % result.length];
    if ((end.x - point.x) * lines[index].dx + (end.y - point.y) * lines[index].dy <= EPS) throw new Error('Вычеты схлопывают сторону');
  });
  return result;
}

export function csContourFrames(source: CsConfig) {
  const config = normalizeCsConfig(source);
  const light = config.edgeTreatments!.map(kind => kind === 'clamp' ? 40 : kind === 'bubble' ? config.bubbleDeductionMm! : 0);
  const glass = config.edgeTreatments!.map(kind => kind === 'clamp' ? 26 : kind === 'bubble' ? config.bubbleDeductionMm! : 0);
  const installation = config.dimensionMode === 'clear' ? csOffsetContour(config.vertices, light.map(value => -value)) : config.vertices;
  return { installation, clear: csOffsetContour(installation, light), glass: csOffsetContour(installation, glass) };
}

export function csChangeDimensionMode(source: CsConfig, dimensionMode: 'installation' | 'clear'): Partial<Section> {
  const config = normalizeCsConfig(source);
  const frames = csContourFrames(config);
  const target = frames[dimensionMode];
  const bounds = csBounds(target);
  const width = bounds.maxX - bounds.minX, height = bounds.maxY - bounds.minY;
  const translate = (split: CsSplitConfig, offset: number) => ({ ...split, positions: split.positions?.map(value => value - offset) });
  return { width, height, csConfig: { ...config, dimensionMode,
    vertices: target.map(point => ({ x: point.x - bounds.minX, y: point.y - bounds.minY })),
    vertical: translate(config.vertical, bounds.minX), horizontal: translate(config.horizontal, bounds.minY),
    referenceWidth: width, referenceHeight: height } };
}

export function csSide(vertices: CsPoint[], index: number) {
  const start = vertices[index];
  const end = vertices[(index + 1) % vertices.length];
  return { length: Math.hypot(end.x - start.x, end.y - start.y),
    angle: (Math.atan2(end.y - start.y, end.x - start.x) * 180 / Math.PI + 360) % 360 };
}

function orientation(vertices: CsPoint[]) {
  return Math.sign(vertices.reduce((area, point, index) => {
    const next = vertices[(index + 1) % vertices.length];
    return area + point.x * next.y - next.x * point.y;
  }, 0)) || 1;
}

export function csVertexAngle(vertices: CsPoint[], index: number) {
  const point = vertices[index];
  const prev = vertices[(index - 1 + vertices.length) % vertices.length];
  const next = vertices[(index + 1) % vertices.length];
  const incoming = Math.atan2(prev.y - point.y, prev.x - point.x);
  const outgoing = Math.atan2(next.y - point.y, next.x - point.x);
  return ((incoming - outgoing) * orientation(vertices) * 180 / Math.PI + 720) % 360;
}

export function csSideEnd(vertices: CsPoint[], index: number, length: number, angle: number): CsPoint {
  const start = vertices[index];
  return { x: start.x + length * Math.cos(angle * Math.PI / 180),
    y: start.y + length * Math.sin(angle * Math.PI / 180) };
}

export function csAngleEnd(vertices: CsPoint[], index: number, angle: number): CsPoint {
  const point = vertices[index];
  const prev = vertices[(index - 1 + vertices.length) % vertices.length];
  const direction = Math.atan2(prev.y - point.y, prev.x - point.x) * 180 / Math.PI;
  return csSideEnd(vertices, index, csSide(vertices, index).length, direction - orientation(vertices) * angle);
}

export function csContourError(vertices: CsPoint[]): string | undefined {
  const cross = (a: CsPoint, b: CsPoint, c: CsPoint) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  let area = 0;
  for (let index = 0; index < vertices.length; index++) {
    const a = vertices[index];
    const b = vertices[(index + 1) % vertices.length];
    if (Math.hypot(b.x - a.x, b.y - a.y) <= EPS) return 'Соседние углы не должны совпадать.';
    area += a.x * b.y - b.x * a.y;
    for (let other = index + 2; other < vertices.length; other++) {
      if (index === 0 && other === vertices.length - 1) continue;
      const c = vertices[other];
      const d = vertices[(other + 1) % vertices.length];
      if (cross(a, b, c) * cross(a, b, d) < -EPS && cross(c, d, a) * cross(c, d, b) < -EPS) {
        return 'Изменение не применено: стороны контура пересекаются.';
      }
    }
  }
  if (Math.abs(area) / 2 <= EPS) return 'Площадь контура должна быть больше нуля.';
}

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
  const inside = (value: number) => Number.isFinite(value) && value > low + 1.5 && value < high - 1.5;
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
  const pane = (span - 3 * count) / (count + 1);
  return pane > EPS ? Array.from({ length: count }, (_, index) => low + pane * (index + 1) + 3 * (index + 0.5)) : [];
}

export function parseCsPositions(text: string, low: number, high: number): { positions: number[]; error?: string } {
  const tokens = text.trim().split(/[;,\s]+/).filter(Boolean);
  const positions = tokens.map(Number);
  if (tokens.some(token => !/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(token)) || positions.some(value => !Number.isFinite(value))) {
    return { positions: [], error: 'Введите координаты числами через запятую, точку с запятой или пробел.' };
  }
  if (positions.some(value => value <= low + 1.5 || value >= high - 1.5)) {
    return { positions: [], error: `Координаты должны быть больше ${low + 1.5} и меньше ${high - 1.5} мм с учётом зазора.` };
  }
  const unique = [...new Set(positions)].sort((a, b) => a - b);
  if (unique.some((value, index) => index > 0 && value - unique[index - 1] <= 3)) return { positions: [], error: 'Между линиями должен помещаться зазор 3 мм и стекло.' };
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
