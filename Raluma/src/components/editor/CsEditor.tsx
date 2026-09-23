import { useEffect, useId, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { listCsSystems, type CsSystem } from '../../api/catalog';
import type { CsCalcPreview } from '../../api/projects';
import { INP, LBL, SEL, type CsConfig, type CsPoint, type Section } from './types';
import { csAngleEnd, csBounds, csContourError, csSide, csSideEnd, csSplitPositions, csVertexAngle, parseCsPositions } from './csGeometry';
import { CsNumberInput } from './CsNumberInput';

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

function SplitControls({
  title, value, minimum, maximum, onChange,
}: {
  title: string;
  value: CsConfig['vertical'];
  minimum: number;
  maximum: number;
  onChange: (value: CsConfig['vertical']) => void;
}) {
  const [coordinateDraft, setCoordinateDraft] = useState<string | null>(null);
  const coordinateText = coordinateDraft ?? (value.positions || []).join(', ');
  const parsed = parseCsPositions(coordinateText, minimum, maximum);
  return <div className="rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
    <div className="mb-3 text-xs font-bold">{title}</div>
    <div className="grid gap-3 sm:grid-cols-2">
      <div key={value.mode}><CsNumberInput label="Количество линий" max={20} integer live readOnly={value.mode === 'manual'} value={value.count} onChange={count => onChange({ ...value, count })} /></div>
      <label>
        <span className={LBL}>Расположение</span>
        <select value={value.mode} onChange={event => {
          setCoordinateDraft(null);
          const mode = event.target.value as CsConfig['vertical']['mode'];
          const positions = csSplitPositions(value, minimum, maximum);
          onChange({ ...value, mode, ...(mode === 'manual' ? { positions, count: positions.length } : {}) });
        }} className={SEL}>
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
        <input value={coordinateText} onChange={event => {
          // Keep the literal draft, including separators and partially typed numbers.
          setCoordinateDraft(event.target.value);
          const next = parseCsPositions(event.target.value, minimum, maximum);
          if (!next.error) onChange({ ...value, count: next.positions.length, positions: next.positions });
        }} onBlur={() => { if (!parsed.error) setCoordinateDraft(null); }}
          aria-invalid={Boolean(parsed.error)} className={INP} placeholder="1000, 2000" />
        {parsed.error && <span className="mt-1 block text-xs text-red-400" role="alert">{parsed.error}</span>}
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
  const [vertexSelection, setVertexSelection] = useState({ sectionId: section.id, index: 0 });
  const [sideSelection, setSideSelection] = useState({ sectionId: section.id, index: 0 });
  const [geometryError, setGeometryError] = useState('');
  const draggingVertex = useRef<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const clipId = useId();
  const config = useMemo(() => activeConfig(section), [section]);
  const selectedVertex = vertexSelection.sectionId === section.id ? Math.min(vertexSelection.index, config.vertices.length - 1) : 0;
  const selectedSide = sideSelection.sectionId === section.id ? Math.min(sideSelection.index, config.vertices.length - 1) : 0;
  const setSelectedVertex = (index: number) => { setVertexSelection({ sectionId: section.id, index }); setGeometryError(''); };
  const setSelectedSide = (index: number) => { setSideSelection({ sectionId: section.id, index }); setGeometryError(''); };
  const width = Math.max(1, section.width || 1);
  const height = Math.max(1, section.height || 1);
  const bounds = csBounds(config.vertices);
  const vertical = csSplitPositions(config.vertical, bounds.minX, bounds.maxX);
  const horizontal = csSplitPositions(config.horizontal, bounds.minY, bounds.maxY);
  const diagramUnit = Math.max(width, height);
  const padding = diagramUnit * 0.09;
  const side = csSide(config.vertices, selectedSide);
  const sideLabel = (index: number) => `С${index + 1}: У${index + 1} → У${(index + 1) % config.vertices.length + 1}`;

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
    setSelectedVertex(0);
    setSelectedSide(0);
    update({ csShape: shape, csConfig: presetConfig(section, shape) });
  };
  const pointerPoint = (event: ReactPointerEvent<SVGSVGElement>): CsPoint => {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return { x: 0, y: 0 };
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const local = point.matrixTransform(matrix.inverse());
    return {
      x: Math.round(clamp(local.x, 0, width)),
      y: Math.round(clamp(height - local.y, 0, height)),
    };
  };
  const updateVertex = (index: number, point: CsPoint) => {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)
      || point.x < -0.001 || point.x > width + 0.001 || point.y < -0.001 || point.y > height + 0.001) {
      setGeometryError('Вершина выходит за габариты изделия. Увеличьте ширину/высоту или задайте другое значение.');
      return;
    }
    const vertices = config.vertices.map((value, vertexIndex) => vertexIndex === index
      ? { x: clamp(point.x, 0, width), y: clamp(point.y, 0, height) } : value);
    const error = csContourError(vertices);
    setGeometryError(error || '');
    if (!error) commitConfig({ ...config, vertices });
  };
  const addVertex = () => {
    const edge = selectedSide;
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
    if (config.vertices.length <= 3) return;
    const oldCount = config.vertices.length;
    const previousEdge = (selectedVertex - 1 + oldCount) % oldCount;
    const mergedEdge = selectedVertex === 0 ? oldCount - 2 : selectedVertex - 1;
    const vertices = config.vertices.filter((_, index) => index !== selectedVertex);
    const error = csContourError(vertices);
    if (error) { setGeometryError(error); return; }
    const profiledEdges = Array.from(new Set<number>(config.profiledEdges.map(index => {
      if (index === previousEdge || index === selectedVertex) return mergedEdge;
      return index < selectedVertex ? index : index - 1;
    }))).sort((a, b) => a - b);
    commitConfig({ ...config, vertices, profiledEdges });
    setSelectedVertex(Math.max(0, selectedVertex - 1));
    setSelectedSide(mergedEdge);
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

    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_290px]">
      <div className="overflow-hidden rounded-2xl border border-tint/30 bg-white p-3 xl:sticky xl:top-3">
        <p className="mb-2 text-xs text-[#174d57]">У — угол, С — сторона. Нажмите для выбора. Угол можно перетащить.</p>
        <svg ref={svgRef} viewBox={`${-padding} ${-padding} ${width + padding * 2} ${height + padding * 2}`} className="h-auto max-h-[500px] w-full touch-none select-none"
          aria-label="Контур ЦС с обозначениями углов и сторон"
          onPointerMove={event => {
            if (draggingVertex.current === null) return;
            updateVertex(draggingVertex.current, pointerPoint(event));
          }} onPointerUp={() => { draggingVertex.current = null; }} onPointerCancel={() => { draggingVertex.current = null; }}
          onLostPointerCapture={() => { draggingVertex.current = null; }}>
          <defs><clipPath id={clipId}><polygon points={config.vertices.map(point => `${point.x},${height - point.y}`).join(' ')} /></clipPath></defs>
          <polygon points={config.vertices.map(point => `${point.x},${height - point.y}`).join(' ')} fill="#dff3f7" stroke="#174d57" strokeWidth={Math.max(width, height) / 300} />
          <g clipPath={`url(#${clipId})`}>
          {vertical.map(position => <line key={`v-${position}`} x1={position} x2={position} y1={0} y2={height} stroke="#758e96" strokeDasharray="18 12" strokeWidth={Math.max(width, height) / 500} />)}
          {horizontal.map(position => <line key={`h-${position}`} x1={0} x2={width} y1={height - position} y2={height - position} stroke="#758e96" strokeDasharray="18 12" strokeWidth={Math.max(width, height) / 500} />)}
          </g>
          {config.vertices.map((start, index) => {
            const end = config.vertices[(index + 1) % config.vertices.length];
            return <g key={`edge-${index}`} onClick={() => setSelectedSide(index)} className="cursor-pointer">
              <title>{sideLabel(index)} · {Math.round(csSide(config.vertices, index).length)} мм</title>
              <line x1={start.x} y1={height - start.y} x2={end.x} y2={height - end.y} stroke={selectedSide === index ? '#b45309' : config.profiledEdges.includes(index) ? '#008573' : '#174d57'} strokeWidth={diagramUnit / (selectedSide === index ? 150 : 230)} />
              <line x1={start.x} y1={height - start.y} x2={end.x} y2={height - end.y} stroke="transparent" strokeWidth={diagramUnit / 30} />
              <text x={(start.x + end.x) / 2} y={height - (start.y + end.y) / 2 - diagramUnit / 55} textAnchor="middle" fill="#713f12" stroke="white" strokeWidth={diagramUnit / 250} paintOrder="stroke" fontSize={diagramUnit / 42} fontWeight="700">С{index + 1}</text>
            </g>;
          })}
          {(calc?.panes || []).map(pane => {
            const x = pane.polygon.reduce((sum, point) => sum + point.x, 0) / pane.polygon.length;
            const y = pane.polygon.reduce((sum, point) => sum + point.y, 0) / pane.polygon.length;
            return <text key={`pane-${pane.number}`} x={x} y={height - y} textAnchor="middle" dominantBaseline="middle" fill="#102f35" fontSize={diagramUnit / 42} fontWeight="700" pointerEvents="none">Ст{pane.number}</text>;
          })}
          {config.vertices.map((point, index) => <g key={`point-${index}`} className="cursor-move"
            onPointerDown={event => { event.preventDefault(); svgRef.current?.setPointerCapture(event.pointerId); draggingVertex.current = index; setSelectedVertex(index); }}>
            <title>Угол У{index + 1}: X {Math.round(point.x)}, Y {Math.round(point.y)} мм</title>
            <circle cx={point.x} cy={height - point.y} r={diagramUnit / 50} fill={selectedVertex === index ? '#ff9f1c' : '#ffffff'} stroke="#174d57" strokeWidth={diagramUnit / 280} />
            <text x={point.x} y={height - point.y + diagramUnit / 20} textAnchor="middle" fill="#123e48" stroke="white" strokeWidth={diagramUnit / 220} paintOrder="stroke" fontSize={diagramUnit / 36} fontWeight="700">У{index + 1}</text>
          </g>)}
        </svg>
        <p className="mt-2 text-xs text-[#174d57]">X — вправо, Y — вверх; отсчёт от левого нижнего угла габаритов. Зелёные стороны — с профилем, оранжевая — выбранная.</p>
      </div>
      <div className="space-y-3">
        <div key={`${section.id}-vertex-${selectedVertex}`} className="space-y-3 rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
          <label><span className={LBL}>Выбранный угол</span><select value={selectedVertex} onChange={event => setSelectedVertex(Number(event.target.value))} className={SEL}>
            {config.vertices.map((_, index) => <option key={index} value={index}>У{index + 1} — угол {index + 1}</option>)}
          </select></label>
          <div className="grid grid-cols-2 gap-2">
            <CsNumberInput label="X, мм" value={config.vertices[selectedVertex].x} max={width} onChange={x => updateVertex(selectedVertex, { ...config.vertices[selectedVertex], x })} />
            <CsNumberInput label="Y, мм" value={config.vertices[selectedVertex].y} max={height} onChange={y => updateVertex(selectedVertex, { ...config.vertices[selectedVertex], y })} />
          </div>
          <CsNumberInput label="Внутренний угол, °" value={csVertexAngle(config.vertices, selectedVertex)} min={0.1} max={359.9}
            onChange={angle => updateVertex((selectedVertex + 1) % config.vertices.length, csAngleEnd(config.vertices, selectedVertex, angle))} />
          <p className="text-xs text-fg/65">При изменении угла движется У{(selectedVertex + 1) % config.vertices.length + 1}. Длина стороны С{selectedVertex + 1} сохраняется. Числа применяются по Enter или при выходе из поля.</p>
          <button type="button" onClick={removeVertex} disabled={config.vertices.length <= 3} className="flex items-center gap-2 rounded-lg border border-red-500/25 px-3 py-2 text-xs text-fg disabled:opacity-30"><Trash2 className="h-4 w-4" /> Удалить У{selectedVertex + 1}</button>
        </div>
        <div key={`${section.id}-side-${selectedSide}`} className="space-y-3 rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
          <label><span className={LBL}>Выбранная сторона</span><select value={selectedSide} onChange={event => setSelectedSide(Number(event.target.value))} className={SEL}>
            {config.vertices.map((_, index) => <option key={index} value={index}>{sideLabel(index)}</option>)}
          </select></label>
          <div className="grid grid-cols-2 gap-2">
            <CsNumberInput label="Длина, мм" value={side.length} min={1} onChange={length => updateVertex((selectedSide + 1) % config.vertices.length, csSideEnd(config.vertices, selectedSide, length, side.angle))} />
            <CsNumberInput label="Наклон, °" value={side.angle} max={360} onChange={angle => updateVertex((selectedSide + 1) % config.vertices.length, csSideEnd(config.vertices, selectedSide, side.length, angle))} />
          </div>
          <p className="text-xs text-fg/65">Начало У{selectedSide + 1} неподвижно, меняется конец У{(selectedSide + 1) % config.vertices.length + 1}. 0° — вправо, 90° — вверх.</p>
          <button type="button" onClick={addVertex} className="flex items-center justify-center gap-2 rounded-xl border border-accent/30 bg-accent/10 px-3 py-2 text-xs font-bold text-accent"><Plus className="h-4 w-4" /> Добавить угол на С{selectedSide + 1}</button>
          <p className="text-xs text-fg/65">Новый угол появится посередине стороны. Нумерация следующих углов и сторон изменится.</p>
        </div>
        {geometryError && <p role="alert" className="rounded-xl border border-red-500/40 p-3 text-xs text-fg">{geometryError}</p>}
        <div className="rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
          <div className="mb-2 text-xs font-bold">Зажимной профиль по сторонам</div>
          <div className="space-y-1.5">{config.vertices.map((_, index) => <label key={index} className="flex items-center gap-2 text-xs"><input type="checkbox" checked={config.profiledEdges.includes(index)} onChange={() => { setSelectedSide(index); commitConfig({ ...config, profiledEdges: config.profiledEdges.includes(index) ? config.profiledEdges.filter(value => value !== index) : [...config.profiledEdges, index].sort((a, b) => a - b) }); }} /> {sideLabel(index)}</label>)}</div>
        </div>
      </div>
    </div>

    <div key={section.id} className="grid gap-3 xl:grid-cols-2">
      <SplitControls title="Вертикальное деление" value={config.vertical} minimum={bounds.minX} maximum={bounds.maxX} onChange={value => commitConfig({ ...config, vertical: value })} />
      <SplitControls title="Горизонтальное деление" value={config.horizontal} minimum={bounds.minY} maximum={bounds.maxY} onChange={value => commitConfig({ ...config, horizontal: value })} />
    </div>

    {calc && <div className="rounded-2xl border border-tint/25 bg-hi/[0.025] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-bold">Предварительная ведомость ЦС</h4><span className="text-xs text-fg/45">Стекло: {calc.glass_area_m2.toFixed(2)} м² · полотен: {calc.panes.length}</span></div>
      <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-xs"><thead><tr className="text-fg/40"><th className="py-2">Артикул</th><th>Наименование</th><th>Длина</th><th>Кол-во</th></tr></thead><tbody className="divide-y divide-tint/15">{calc.profiles.map(row => <tr key={row.role}><td className="py-2 font-mono font-bold">{row.article}</td><td>{row.name}</td><td>{row.total_length_mm} мм</td><td>{row.pieces} шт</td></tr>)}</tbody></table></div>
      {calc.warnings.map(warning => <div key={warning} className="mt-2 flex gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200"><AlertTriangle className="h-4 w-4 flex-shrink-0" />{warning}</div>)}
    </div>}
    <div className="rounded-xl border border-tint/20 bg-hi/[0.02] px-4 py-3 text-xs text-fg/45">Входные группы и дверная фурнитура зарезервированы для этапа 2.</div>
  </div>;
}
