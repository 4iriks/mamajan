import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { listCsSystems, type CsSystem } from '../../api/catalog';
import type { CsCalcPreview } from '../../api/projects';
import { INP, LBL, SEL, type CsConfig, type CsPoint, type Section } from './types';

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

function presetConfig(section: Section, shape = section.csShape || 'Прямоугольник'): CsConfig {
  const width = Math.max(1, section.width || 1);
  const height = Math.max(1, section.height || 1);
  let vertices: CsPoint[];
  if (shape === 'Треугольник') {
    vertices = [{ x: 0, y: 0 }, { x: width, y: 0 }, { x: width / 2, y: height }];
  } else if (shape === 'Трапеция') {
    const top = clamp(section.csWidth2 || width * 0.7, 1, width);
    const offset = (width - top) / 2;
    vertices = [{ x: 0, y: 0 }, { x: width, y: 0 }, { x: offset + top, y: height }, { x: offset, y: height }];
  } else if (shape === 'Сложная форма') {
    vertices = [{ x: 0, y: 0 }, { x: width, y: 0 }, { x: width, y: height * 0.65 }, { x: width * 0.62, y: height }, { x: 0, y: height }];
  } else {
    vertices = [{ x: 0, y: 0 }, { x: width, y: 0 }, { x: width, y: height }, { x: 0, y: height }];
  }
  const bottom = vertices.findIndex((point, index) => point.y === 0 && vertices[(index + 1) % vertices.length].y === 0);
  return {
    version: 1,
    vertices,
    vertical: { count: 0, mode: 'equal', positions: [] },
    horizontal: { count: 0, mode: 'equal', positions: [] },
    profiledEdges: vertices.map((_, index) => index).filter(index => index !== bottom),
    doors: [],
  };
}

function activeConfig(section: Section): CsConfig {
  return section.csConfig?.version === 1 ? section.csConfig : presetConfig(section);
}

function splitPositions(config: CsConfig['vertical'], maximum: number): number[] {
  const count = Math.max(0, Number(config.count) || 0);
  if (config.mode === 'manual') return (config.positions || []).filter(value => value > 0 && value < maximum).sort((a, b) => a - b);
  if (config.mode === 'from-left') return Array.from({ length: count }, (_, index) => (index + 1) * (config.step || maximum / (count + 1))).filter(value => value < maximum);
  if (config.mode === 'from-right') return Array.from({ length: count }, (_, index) => maximum - (index + 1) * (config.step || maximum / (count + 1))).filter(value => value > 0).sort((a, b) => a - b);
  return Array.from({ length: count }, (_, index) => maximum * (index + 1) / (count + 1));
}

function SplitControls({
  title, value, maximum, onChange,
}: {
  title: string;
  value: CsConfig['vertical'];
  maximum: number;
  onChange: (value: CsConfig['vertical']) => void;
}) {
  return <div className="rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
    <div className="mb-3 text-xs font-bold">{title}</div>
    <div className="grid gap-3 sm:grid-cols-2">
      <label>
        <span className={LBL}>Количество линий</span>
        <input type="number" min="0" max="20" value={value.count} onChange={event => onChange({ ...value, count: clamp(Number(event.target.value) || 0, 0, 20) })} className={INP} />
      </label>
      <label>
        <span className={LBL}>Расположение</span>
        <select value={value.mode} onChange={event => onChange({ ...value, mode: event.target.value as CsConfig['vertical']['mode'] })} className={SEL}>
          <option value="equal">Равномерно</option>
          <option value="from-left">С шагом от начала</option>
          <option value="from-right">С шагом от конца</option>
          <option value="manual">Вручную</option>
        </select>
      </label>
      {(value.mode === 'from-left' || value.mode === 'from-right') && <label>
        <span className={LBL}>Шаг, мм</span>
        <input type="number" min="1" value={value.step || ''} onChange={event => onChange({ ...value, step: Number(event.target.value) || undefined })} className={INP} />
      </label>}
      {value.mode === 'manual' && <label className="sm:col-span-2">
        <span className={LBL}>Координаты, мм, через запятую</span>
        <input value={(value.positions || []).join(', ')} onChange={event => {
          const positions = event.target.value.split(/[;,\s]+/).map(Number).filter(number => Number.isFinite(number) && number > 0 && number < maximum);
          onChange({ ...value, count: positions.length, positions });
        }} className={INP} placeholder="1000, 2000" />
      </label>}
    </div>
  </div>;
}

export function CsEditor({
  section, update, calc,
}: {
  section: Section;
  update: (updates: Partial<Section>) => void;
  calc?: CsCalcPreview | null;
}) {
  const [systems, setSystems] = useState<CsSystem[]>([]);
  const [selectedVertex, setSelectedVertex] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const config = useMemo(() => activeConfig(section), [section]);
  const width = Math.max(1, section.width || 1);
  const height = Math.max(1, section.height || 1);
  const vertical = splitPositions(config.vertical, width);
  const horizontal = splitPositions(config.horizontal, height);

  useEffect(() => {
    let cancelled = false;
    listCsSystems().then(rows => {
      if (cancelled) return;
      setSystems(rows);
      if (!section.csSystemId && rows[0]) update({ csSystemId: rows[0].id });
    }).catch(() => setSystems([]));
    return () => { cancelled = true; };
  }, [section.csSystemId, update]);

  const commitConfig = (next: CsConfig) => update({ csConfig: next, panels: Math.max(1, (next.vertical.count + 1) * (next.horizontal.count + 1)) });
  const choosePreset = (shape: string) => {
    setSelectedVertex(null);
    update({ csShape: shape, csConfig: presetConfig(section, shape) });
  };
  const pointerPoint = (event: ReactPointerEvent<SVGSVGElement>): CsPoint => {
    const bounds = svgRef.current?.getBoundingClientRect();
    if (!bounds) return { x: 0, y: 0 };
    return {
      x: Math.round(clamp((event.clientX - bounds.left) / bounds.width * width, 0, width)),
      y: Math.round(clamp((1 - (event.clientY - bounds.top) / bounds.height) * height, 0, height)),
    };
  };
  const updateVertex = (index: number, point: CsPoint) => commitConfig({ ...config, vertices: config.vertices.map((value, vertexIndex) => vertexIndex === index ? point : value) });
  const addVertex = () => {
    let edge = 0;
    let longest = -1;
    config.vertices.forEach((point, index) => {
      const next = config.vertices[(index + 1) % config.vertices.length];
      const length = Math.hypot(next.x - point.x, next.y - point.y);
      if (length > longest) { longest = length; edge = index; }
    });
    const next = config.vertices[(edge + 1) % config.vertices.length];
    const vertices = [...config.vertices];
    vertices.splice(edge + 1, 0, { x: (config.vertices[edge].x + next.x) / 2, y: (config.vertices[edge].y + next.y) / 2 });
    const profiledEdges = config.profiledEdges.flatMap(index => {
      if (index < edge) return [index];
      if (index === edge) return [edge, edge + 1];
      return [index + 1];
    });
    commitConfig({ ...config, vertices, profiledEdges });
    setSelectedVertex(edge + 1);
  };
  const removeVertex = () => {
    if (selectedVertex === null || config.vertices.length <= 3) return;
    const oldCount = config.vertices.length;
    const previousEdge = (selectedVertex - 1 + oldCount) % oldCount;
    const mergedEdge = selectedVertex === 0 ? oldCount - 2 : selectedVertex - 1;
    const vertices = config.vertices.filter((_, index) => index !== selectedVertex);
    const profiledEdges = Array.from(new Set<number>(config.profiledEdges.map(index => {
      if (index === previousEdge || index === selectedVertex) return mergedEdge;
      return index < selectedVertex ? index : index - 1;
    }))).sort((a, b) => a - b);
    commitConfig({ ...config, vertices, profiledEdges });
    setSelectedVertex(null);
  };

  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2">
      <label>
        <span className={LBL}>Система ЦС</span>
        <select value={section.csSystemId || ''} onChange={event => update({ csSystemId: Number(event.target.value) || undefined })} className={SEL}>
          <option value="">Выберите систему</option>
          {systems.map(system => <option key={system.id} value={system.id}>{system.name}</option>)}
        </select>
      </label>
      <div className="rounded-xl border border-amber-400/25 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">
        Расчёт предварительный. Цена ЦС заблокирована до подтверждения формул заказчиком.
      </div>
    </div>

    <div>
      <label className={LBL}>Заготовка контура</label>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {['Прямоугольник', 'Трапеция', 'Треугольник', 'Сложная форма'].map(shape => <button key={shape} type="button" onClick={() => choosePreset(shape)}
          className={`rounded-xl border px-3 py-3 text-xs font-bold ${section.csShape === shape ? 'border-accent/50 bg-accent/10 text-accent' : 'border-tint/20 bg-black/10 text-fg/50'}`}>{shape}</button>)}
      </div>
    </div>

    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_250px]">
      <div className="overflow-hidden rounded-2xl border border-tint/30 bg-white p-3">
        <svg ref={svgRef} viewBox={`0 0 ${width} ${height}`} className="h-auto max-h-[430px] w-full touch-none select-none"
          onPointerMove={event => {
            if (selectedVertex === null || event.buttons !== 1) return;
            updateVertex(selectedVertex, pointerPoint(event));
          }}>
          <polygon points={config.vertices.map(point => `${point.x},${height - point.y}`).join(' ')} fill="#dff3f7" stroke="#174d57" strokeWidth={Math.max(width, height) / 300} />
          {vertical.map(position => <line key={`v-${position}`} x1={position} x2={position} y1={0} y2={height} stroke="#758e96" strokeDasharray="18 12" strokeWidth={Math.max(width, height) / 500} />)}
          {horizontal.map(position => <line key={`h-${position}`} x1={0} x2={width} y1={height - position} y2={height - position} stroke="#758e96" strokeDasharray="18 12" strokeWidth={Math.max(width, height) / 500} />)}
          {config.profiledEdges.map(index => {
            const start = config.vertices[index];
            const end = config.vertices[(index + 1) % config.vertices.length];
            if (!start || !end) return null;
            return <line key={`edge-${index}`} x1={start.x} y1={height - start.y} x2={end.x} y2={height - end.y} stroke="#00a98f" strokeWidth={Math.max(width, height) / 170} strokeLinecap="round" />;
          })}
          {(calc?.panes || []).map(pane => {
            const x = pane.polygon.reduce((sum, point) => sum + point.x, 0) / pane.polygon.length;
            const y = pane.polygon.reduce((sum, point) => sum + point.y, 0) / pane.polygon.length;
            return <text key={`pane-${pane.number}`} x={x} y={height - y} textAnchor="middle" dominantBaseline="middle" fill="#102f35" fontSize={Math.max(width, height) / 35} fontWeight="700">{pane.number}</text>;
          })}
          {config.vertices.map((point, index) => <circle key={`point-${index}`} cx={point.x} cy={height - point.y} r={Math.max(width, height) / 65}
            fill={selectedVertex === index ? '#ff9f1c' : '#ffffff'} stroke="#174d57" strokeWidth={Math.max(width, height) / 280}
            onPointerDown={event => { event.currentTarget.setPointerCapture(event.pointerId); setSelectedVertex(index); }} />)}
        </svg>
      </div>
      <div className="space-y-3">
        <div className="flex gap-2">
          <button type="button" onClick={addVertex} className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-accent/30 bg-accent/10 px-3 py-2 text-xs font-bold text-accent"><Plus className="h-4 w-4" /> Угол</button>
          <button type="button" onClick={removeVertex} disabled={selectedVertex === null || config.vertices.length <= 3} className="flex items-center justify-center rounded-xl border border-red-500/25 bg-red-500/10 px-3 py-2 text-red-300 disabled:opacity-30"><Trash2 className="h-4 w-4" /></button>
        </div>
        {selectedVertex !== null && config.vertices[selectedVertex] && <div className="grid grid-cols-2 gap-2 rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
          <label><span className={LBL}>X, мм</span><input type="number" value={config.vertices[selectedVertex].x} onChange={event => updateVertex(selectedVertex, { ...config.vertices[selectedVertex], x: clamp(Number(event.target.value) || 0, 0, width) })} className={INP} /></label>
          <label><span className={LBL}>Y, мм</span><input type="number" value={config.vertices[selectedVertex].y} onChange={event => updateVertex(selectedVertex, { ...config.vertices[selectedVertex], y: clamp(Number(event.target.value) || 0, 0, height) })} className={INP} /></label>
        </div>}
        <div className="rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
          <div className="mb-2 text-xs font-bold">Зажимной профиль по сторонам</div>
          <div className="space-y-1.5">{config.vertices.map((_, index) => <label key={index} className="flex items-center gap-2 text-xs"><input type="checkbox" checked={config.profiledEdges.includes(index)} onChange={() => commitConfig({ ...config, profiledEdges: config.profiledEdges.includes(index) ? config.profiledEdges.filter(value => value !== index) : [...config.profiledEdges, index].sort((a, b) => a - b) })} /> Сторона {index + 1}</label>)}</div>
        </div>
      </div>
    </div>

    <div className="grid gap-3 xl:grid-cols-2">
      <SplitControls title="Вертикальное деление" value={config.vertical} maximum={width} onChange={value => commitConfig({ ...config, vertical: value })} />
      <SplitControls title="Горизонтальное деление" value={config.horizontal} maximum={height} onChange={value => commitConfig({ ...config, horizontal: value })} />
    </div>

    {calc && <div className="rounded-2xl border border-tint/25 bg-hi/[0.025] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-bold">Предварительная ведомость ЦС</h4><span className="text-xs text-fg/45">Стекло: {calc.glass_area_m2.toFixed(2)} м² · полотен: {calc.panes.length}</span></div>
      <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-xs"><thead><tr className="text-fg/40"><th className="py-2">Артикул</th><th>Наименование</th><th>Длина</th><th>Кол-во</th></tr></thead><tbody className="divide-y divide-tint/15">{calc.profiles.map(row => <tr key={row.role}><td className="py-2 font-mono font-bold">{row.article}</td><td>{row.name}</td><td>{row.total_length_mm} мм</td><td>{row.pieces} шт</td></tr>)}</tbody></table></div>
      {calc.warnings.map(warning => <div key={warning} className="mt-2 flex gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200"><AlertTriangle className="h-4 w-4 flex-shrink-0" />{warning}</div>)}
    </div>}
    <div className="rounded-xl border border-tint/20 bg-hi/[0.02] px-4 py-3 text-xs text-fg/45">Входные группы и дверная фурнитура зарезервированы для этапа 2.</div>
  </div>;
}
