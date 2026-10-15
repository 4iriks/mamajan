import type { CsPoint } from './types';

/** Optional edge treatment, separate from the unchanged calculation polygon. */
export function csTriangleRounding(points: CsPoint[], radius: number) {
  if (!radius || points.length !== 3) return undefined;
  const candidates = points.map((point, index) => {
    const prev = points[(index + 2) % 3], next = points[(index + 1) % 3];
    const la = Math.hypot(prev.x - point.x, prev.y - point.y), lb = Math.hypot(next.x - point.x, next.y - point.y);
    if (Math.min(la, lb) <= 1e-7) throw new Error('Невозможно скруглить вырожденный треугольник');
    const u = { x: (prev.x - point.x) / la, y: (prev.y - point.y) / la };
    const v = { x: (next.x - point.x) / lb, y: (next.y - point.y) / lb };
    const angle = Math.acos(Math.max(-1, Math.min(1, u.x * v.x + u.y * v.y)));
    return { point, index, la, lb, u, v, angle };
  });
  candidates.sort((a, b) => Number(a.angle.toFixed(10)) - Number(b.angle.toFixed(10)) || a.point.y - b.point.y || a.point.x - b.point.x);
  const { point, index, la, lb, u, v, angle } = candidates[0];
  if (angle <= 1e-7) throw new Error('Невозможно скруглить вырожденный треугольник');
  const distance = radius / Math.tan(angle / 2);
  if (distance >= Math.min(la, lb) - 1e-7) throw new Error(`Скругление R${radius} не помещается на стекле: уменьшите радиус или измените размеры`);
  const start = { x: point.x + u.x * distance, y: point.y + u.y * distance };
  const end = { x: point.x + v.x * distance, y: point.y + v.y * distance };
  const centerDistance = radius / Math.sin(angle / 2), bisectorLength = Math.hypot(u.x + v.x, u.y + v.y);
  const center = { x: point.x + (u.x + v.x) / bisectorLength * centerDistance, y: point.y + (u.y + v.y) / bisectorLength * centerDistance };
  const area = points.reduce((sum, p, i) => sum + p.x * points[(i + 1) % 3].y - points[(i + 1) % 3].x * p.y, 0);
  const arc_midpoint = { x: center.x + (point.x - center.x) * radius / centerDistance, y: center.y + (point.y - center.y) * radius / centerDistance };
  return { vertex_index: index, radius_mm: radius, start, end, center, arc_midpoint, sweep: area > 0 ? 1 : 0 };
}

export function csGlassOutline(points: CsPoint[], radius = 0) {
  const corner = csTriangleRounding(points, radius);
  const commands: string[] = [];
  points.forEach((point, index) => {
    const start = corner?.vertex_index === index ? corner.start : point;
    commands.push(`${index ? 'L' : 'M'} ${start.x} ${start.y}`);
    if (corner?.vertex_index === index) commands.push(`A ${radius} ${radius} 0 0 ${corner.sweep} ${corner.end.x} ${corner.end.y}`);
  });
  return { path: `${commands.join(' ')} Z`, corner };
}
