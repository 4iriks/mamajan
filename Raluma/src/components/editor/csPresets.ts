import type { CsConfig, CsPoint, Section } from './types';

export const CS_SHAPES = ['Прямоугольник', 'Трапеция', 'Треугольник', 'Многоугольник'];

export const csShapeLabel = (shape: string) => ({
  'Трапеция': 'Трапеция с наклонным верхом', 'Треугольник': 'Прямоугольный треугольник',
  'Многоугольник': 'Пятиугольник с крышей',
}[shape] || shape);

/** New sections use explicit vertices. The legacy fallback must stay unchanged. */
export function csPreset(section: Pick<Section, 'width' | 'height' | 'csShape' | 'csWidth2' | 'csConfig'>, shape = section.csShape || 'Прямоугольник', legacy = false): CsConfig {
  const w = Math.max(1, section.width || 1), h = Math.max(1, section.height || 1);
  let vertices: CsPoint[];
  if (shape === 'Треугольник') vertices = [{ x: 0, y: 0 }, { x: w, y: 0 }, { x: legacy ? w / 2 : w, y: h }];
  else if (shape === 'Трапеция' && legacy) {
    const top = Math.min(w, Math.max(1, section.csWidth2 || w * 0.7));
    vertices = [{ x: 0, y: 0 }, { x: w, y: 0 }, { x: (w + top) / 2, y: h }, { x: (w - top) / 2, y: h }];
  } else if (shape === 'Трапеция') vertices = [{ x: 0, y: 0 }, { x: w, y: 0 }, { x: w, y: h }, { x: 0, y: h * 0.6 }];
  else if (shape === 'Многоугольник' && !legacy) vertices = [{ x: 0, y: 0 }, { x: w, y: 0 }, { x: w, y: h * 0.7 }, { x: w / 2, y: h }, { x: 0, y: h * 0.7 }];
  else if (shape === 'Сложная форма') vertices = [{ x: 0, y: 0 }, { x: w, y: 0 }, { x: w, y: h * 0.65 }, { x: w * 0.62, y: h }, { x: 0, y: h }];
  else vertices = [{ x: 0, y: 0 }, { x: w, y: 0 }, { x: w, y: h }, { x: 0, y: h }];
  return { version: 2, dimensionMode: 'installation', bubbleDeductionMm: section.csConfig?.bubbleDeductionMm ?? 6,
    vertices, referenceWidth: w, referenceHeight: h, edgeTreatments: vertices.map(() => 'clamp'),
    profiledEdges: vertices.map((_, i) => i), vertical: { count: 0, mode: 'equal', positions: [] },
    horizontal: { count: 0, mode: 'equal', positions: [] }, doors: [] };
}
