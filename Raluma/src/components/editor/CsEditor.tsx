import { useEffect, useLayoutEffect, useId, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { createPortal } from 'react-dom';
import { activeCsConfig, csPreset, CS_SHAPES, csShapeLabel } from './csPresets';
import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { listCsSystems, type CsSystem } from '../../api/catalog';
import type { CsCalcPreview } from '../../api/projects';
import { INP, LBL, SEL, type CsConfig, type CsPoint, type Section } from './types';
import { csAngleEnd, csDimensionUpdates, csBounds, csContourError, csContourFrames, csSide, csSideEnd, csSplitPositions, csVertexAngle, normalizeCsConfig, parseCsPositions } from './csGeometry';
import { CsNumberInput } from './CsNumberInput';

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

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
      <div key={value.mode}><CsNumberInput label="Количество" min={0} max={20} emptyValue={0} integer live readOnly={value.mode === 'manual'} value={value.count} onChange={count => onChange({ ...value, count })} /><p className="mt-1 text-xs text-fg/65">2 деления → 3 заполнения</p></div>
      <label>
        <span className={LBL}>Расположение</span>
        <select value={value.mode} onChange={event => {
          setCoordinateDraft(null);
          const mode = event.target.value as CsConfig['vertical']['mode'];
          const positions = csSplitPositions(value, minimum, maximum);
          onChange({ ...value, mode, ...(mode === 'manual' ? { positions, count: positions.length } : {}) });
        }} className={SEL}>
          <option value="equal">Равномерно</option>
          <option value="from-left">{title.startsWith('Вертик') ? 'С шагом слева' : 'С шагом снизу'}</option>
          <option value="from-right">{title.startsWith('Вертик') ? 'С шагом справа' : 'С шагом сверху'}</option>
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
  section, update, calc, error, diagramContainer,
}: {
  section: Section;
  diagramContainer?: HTMLElement | null;
  update: (updates: Partial<Section>) => void;
  calc?: CsCalcPreview | null;
  error?: string | null;
}) {
  const [systems, setSystems] = useState<CsSystem[]>([]);
  const [vertexSelection, setVertexSelection] = useState({ sectionId: section.id, index: 0 });
  const [sideSelection, setSideSelection] = useState({ sectionId: section.id, index: 0 });
  const [geometryError, setGeometryError] = useState('');
  const [editing, setEditing] = useState<'vertex' | 'side' | 'width' | 'height' | null>(null);
  const draggingVertex = useRef<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const clipId = useId();
  const [pixelScale, setPixelScale] = useState(0.1);
  const config = useMemo(() => activeCsConfig(section), [section]);
  const frames = useMemo(() => {
    try { return { ...csContourFrames(config), error: '' }; }
    catch (error) { return { installation: config.vertices, clear: config.vertices, glass: config.vertices, error: String((error as Error).message) }; }
  }, [config]);
  const selectedVertex = vertexSelection.sectionId === section.id ? Math.min(vertexSelection.index, config.vertices.length - 1) : 0;
  const selectedSide = sideSelection.sectionId === section.id ? Math.min(sideSelection.index, config.vertices.length - 1) : 0;
  const setSelectedVertex = (index: number) => { setVertexSelection({ sectionId: section.id, index }); setGeometryError(''); };
  const setSelectedSide = (index: number) => { setSideSelection({ sectionId: section.id, index }); setGeometryError(''); };
  const width = Math.max(1, section.width || 1);
  const height = Math.max(1, section.height || 1);
  const bounds = csBounds(frames.clear);
  const vertical = csSplitPositions(config.vertical, bounds.minX, bounds.maxX);
  const horizontal = csSplitPositions(config.horizontal, bounds.minY, bounds.maxY);
  const diagramUnit = Math.max(width, height);
  const padding = diagramUnit * 0.24;
  const outerBounds = csBounds(frames.installation);
  const viewMinX = Math.min(0, outerBounds.minX) - padding;
  const viewMinY = Math.min(0, height - outerBounds.maxY) - padding;
  const viewMaxX = Math.max(width, outerBounds.maxX) + padding;
  const viewMaxY = Math.max(height, height - outerBounds.minY) + padding;
  const dimensionLabel = config.dimensionMode === 'clear' ? 'Световой проём' : 'Наружные размеры';
  const diagramFont = Math.max(diagramUnit / 38, 11 / pixelScale);
  useLayoutEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const measure = () => setPixelScale(svg.getScreenCTM()?.a || 0.1);
    const observer = new ResizeObserver(measure);
    observer.observe(svg); measure();
    return () => observer.disconnect();
  }, [diagramContainer, width, height]);

  const side = csSide(config.vertices, selectedSide);
  const isRectangle = section.csShape === 'Прямоугольник' && config.vertices.length === 4 && config.vertices.every((point, index) => {
    const next = config.vertices[(index + 1) % 4];
    return Math.abs(point.x - next.x) < 0.001 || Math.abs(point.y - next.y) < 0.001;
  });
  const dimensionXs = [...new Set<number>(config.vertices.map(point => point.x))].sort((a, b) => a - b);
  const dimensionYs = [...new Set<number>(config.vertices.map(point => point.y))].sort((a, b) => a - b);
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

  const commitConfig = (next: CsConfig) => update({ csConfig: normalizeCsConfig(next), panels: Math.max(1, (next.vertical.count + 1) * (next.horizontal.count + 1)) });
  const choosePreset = (shape: string) => {
    setEditing(null);
    setSelectedVertex(0);
    setSelectedSide(0);
    update({ csShape: shape, csConfig: csPreset(section, shape) });
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
    if (!error) {
      const next = { ...config, vertices };
      try { csContourFrames(next); commitConfig(next); }
      catch (failure) { setGeometryError((failure as Error).message); }
    }
  };
  const addVertex = () => {
    const edge = selectedSide;
    const next = config.vertices[(edge + 1) % config.vertices.length];
    const vertices = [...config.vertices];
    vertices.splice(edge + 1, 0, { x: (config.vertices[edge].x + next.x) / 2, y: (config.vertices[edge].y + next.y) / 2 });
    const edgeTreatments = [...config.edgeTreatments!];
    edgeTreatments.splice(edge + 1, 0, edgeTreatments[edge]);
    commitConfig({ ...config, vertices, edgeTreatments });
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
    if (config.edgeTreatments![previousEdge] !== config.edgeTreatments![selectedVertex]) {
      setGeometryError('Перед удалением угла задайте одинаковую комплектацию двух соседних сторон.'); return;
    }
    const edgeTreatments = config.edgeTreatments!.filter((_, index) => index !== selectedVertex);
    commitConfig({ ...config, vertices, edgeTreatments });
    setSelectedVertex(Math.max(0, selectedVertex - 1));
    setSelectedSide(mergedEdge);
  };

  const updateDimension = (axis: 'width' | 'height', value: number) => {
    const changes = csDimensionUpdates({ ...section, csConfig: config }, { [axis]: value });
    try {
      csContourFrames(changes.csConfig || config);
      setGeometryError('');
      update(changes);
    } catch (failure) { setGeometryError((failure as Error).message); }
  };
  const pointEditorStyle = () => {
    const matrix = svgRef.current?.getScreenCTM(), box = canvasRef.current?.getBoundingClientRect();
    if (editing !== 'vertex' || !matrix || !box) return undefined;
    const point = config.vertices[selectedVertex];
    const screen = new DOMPoint(point.x, height - point.y).matrixTransform(matrix);
    return { position: 'absolute' as const, left: clamp(screen.x - box.left + 12, 8, Math.max(8, box.width - 242)),
      top: clamp(screen.y - box.top + 16, 26, Math.max(26, box.height - 135)), width: 230, maxWidth: 'calc(100% - 16px)',
      background: '#fff', border: '1px solid #afc5cb', borderRadius: 10, padding: 8, boxShadow: '0 3px 14px #123e4825', zIndex: 2 };
  };

  const canvas = (<div ref={canvasRef} className="cs-canvas rounded-xl border border-tint/30 bg-white p-3">
        <p className="mb-2 text-xs text-[#174d57]">{dimensionLabel}. У — угол, С — сторона, З — заполнение.</p>
        <svg ref={svgRef} viewBox={`${viewMinX} ${viewMinY} ${viewMaxX - viewMinX} ${viewMaxY - viewMinY}`} className="h-auto max-h-[500px] w-full touch-none select-none"
          aria-label="Контур ЦС с обозначениями углов и сторон"
          onPointerMove={event => {
            if (draggingVertex.current === null) return;
            updateVertex(draggingVertex.current, pointerPoint(event));
          }} onPointerUp={() => { draggingVertex.current = null; }} onPointerCancel={() => { draggingVertex.current = null; }}
          onLostPointerCapture={() => { draggingVertex.current = null; }}>
          <defs><clipPath id={clipId}><polygon points={config.vertices.map(point => `${point.x},${height - point.y}`).join(' ')} /></clipPath></defs>
          <polygon points={frames.installation.map(point => `${point.x},${height - point.y}`).join(' ')} fill="#e5e7eb" stroke="#174d57" strokeWidth={diagramUnit / 400} />
          <polygon points={frames.clear.map(point => `${point.x},${height - point.y}`).join(' ')} fill="#dff3f7" stroke="#008573" strokeWidth={diagramUnit / 600} />
          <polygon points={frames.glass.map(point => `${point.x},${height - point.y}`).join(' ')} fill="none" stroke="#2563eb" strokeDasharray="14 10" strokeWidth={diagramUnit / 500} />
          {(calc?.panes || []).map(pane => <polygon key={`glass-${pane.number}`} points={pane.polygon.map(point => `${point.x},${height - point.y}`).join(' ')} fill="none" stroke="#2563eb" strokeWidth={diagramUnit / 600} />)}
          <g clipPath={`url(#${clipId})`}>
          {vertical.map(position => <line key={`v-${position}`} x1={position} x2={position} y1={0} y2={height} stroke="#758e96" strokeDasharray="18 12" strokeWidth={Math.max(width, height) / 500} />)}
          {horizontal.map(position => <line key={`h-${position}`} x1={0} x2={width} y1={height - position} y2={height - position} stroke="#758e96" strokeDasharray="18 12" strokeWidth={Math.max(width, height) / 500} />)}
          </g>
          {config.vertices.map((start, index) => {
            const end = config.vertices[(index + 1) % config.vertices.length];
            const midX = (start.x + end.x) / 2, midY = (start.y + end.y) / 2;
            const length = Math.hypot(end.x - start.x, end.y - start.y) || 1;
            const center = config.vertices.reduce((acc, point) => ({ x: acc.x + point.x / config.vertices.length, y: acc.y + point.y / config.vertices.length }), { x: 0, y: 0 });
            let nx = -(end.y - start.y) / length, ny = (end.x - start.x) / length;
            if (nx * (midX - center.x) + ny * (midY - center.y) < 0) { nx *= -1; ny *= -1; }
            const labelX = midX + nx * diagramFont * 1.6, labelY = height - midY - ny * diagramFont * 1.6;
            return <g key={`edge-${index}`} onClick={() => { setSelectedSide(index); setEditing(isRectangle ? (Math.abs(end.y - start.y) < 0.001 ? 'width' : 'height') : 'side'); }} className="cursor-pointer">
              <title>{sideLabel(index)} · {Math.round(csSide(config.vertices, index).length)} мм</title>
              <line x1={start.x} y1={height - start.y} x2={end.x} y2={height - end.y} stroke={selectedSide === index ? '#b45309' : config.profiledEdges.includes(index) ? '#008573' : '#174d57'} strokeWidth={diagramUnit / (selectedSide === index ? 150 : 230)} />
              <line x1={start.x} y1={height - start.y} x2={end.x} y2={height - end.y} stroke="transparent" strokeWidth={diagramUnit / 30} />
              <text x={labelX} y={labelY} transform={Math.abs(end.x - start.x) < 0.001 ? `rotate(-90 ${labelX} ${labelY})` : undefined} textAnchor="middle" fill="#713f12" stroke="white" strokeWidth={diagramUnit / 250} paintOrder="stroke" fontSize={diagramFont} fontWeight="700">С{index + 1} · {Number(csSide(config.vertices, index).length.toFixed(1))} мм</text>
            </g>;
          })}
          {(calc?.panes || []).map(pane => {
            const x = pane.polygon.reduce((sum, point) => sum + point.x, 0) / pane.polygon.length;
            const y = pane.polygon.reduce((sum, point) => sum + point.y, 0) / pane.polygon.length;
            return <text key={`pane-${pane.number}`} x={x} y={height - y} textAnchor="middle" dominantBaseline="middle" fill="#102f35" fontSize={diagramFont} fontWeight="700" pointerEvents="none">З{pane.number}</text>;
          })}
          {config.vertices.map((point, index) => <g key={`point-${index}`} className="cursor-move"
            onPointerDown={event => { if (isRectangle) return; event.preventDefault(); svgRef.current?.setPointerCapture(event.pointerId); draggingVertex.current = index; setSelectedVertex(index); setEditing('vertex'); }}>
            <title>Угол У{index + 1}: Ш {Math.round(point.x)}, В {Math.round(point.y)} мм</title>
            <circle cx={point.x} cy={height - point.y} r={diagramUnit / 50} fill={selectedVertex === index ? '#ff9f1c' : '#ffffff'} stroke="#174d57" strokeWidth={diagramUnit / 280} />
            <text x={point.x + (point.x < width / 2 ? -1 : 1) * diagramUnit / 24} y={height - point.y + (point.y < height / 2 ? 1 : -1) * diagramUnit / 24} textAnchor="middle" fill="#123e48" stroke="white" strokeWidth={diagramUnit / 220} paintOrder="stroke" fontSize={diagramFont} fontWeight="700">У{index + 1}</text>
          </g>)}
          <g stroke="#174d57" fill="#174d57" strokeWidth={diagramUnit / 900} fontSize={diagramFont}>
            {dimensionXs.slice(1).map((x, i) => <g key={`dx-${x}`}><line x1={dimensionXs[i]} x2={x} y1={height + padding * 0.65} y2={height + padding * 0.65} /><text stroke="none" textAnchor="middle" x={(dimensionXs[i] + x) / 2} y={height + padding * 0.6}>{Number((x - dimensionXs[i]).toFixed(1))}</text><line x1={x} x2={x} y1={height + padding * 0.5} y2={height + padding * 0.75} /></g>)}
            {dimensionYs.slice(1).map((y, i) => <g key={`dy-${y}`}><line x1={width + padding * 0.6} x2={width + padding * 0.6} y1={height - dimensionYs[i]} y2={height - y} /><text stroke="none" textAnchor="middle" transform={`translate(${width + padding * 0.55},${height - (dimensionYs[i] + y) / 2}) rotate(-90)`}>{Number((y - dimensionYs[i]).toFixed(1))}</text><line x1={width + padding * 0.45} x2={width + padding * 0.75} y1={height - y} y2={height - y} /></g>)}
            <text className="cursor-pointer" stroke="none" textAnchor="middle" x={width / 2} y={height + padding * 0.95} onClick={() => setEditing('width')}>Ш {Number(width.toFixed(1))} мм ✎</text>
            <text className="cursor-pointer" stroke="none" textAnchor="middle" transform={`translate(${width + padding * 0.94},${height / 2}) rotate(-90)`} onClick={() => setEditing('height')}>В {Number(height.toFixed(1))} мм ✎</text>
          </g>
        </svg>
        <p className="mt-2 text-xs text-[#174d57]">Ш — вправо, В — вверх; отсчёт от левого нижнего угла габаритов. Зелёные стороны — с профилем, оранжевая — выбранная.</p>
        <div className="min-h-[98px]"><div style={pointEditorStyle()} className="cs-dimension-editor min-h-[98px] border-t border-slate-200 pt-2 text-[#123e48]" aria-label="Размеры на эскизе">
          {editing ? <><div className="flex items-center justify-between text-xs font-bold"><span>{editing === 'vertex' ? `У${selectedVertex + 1} — координаты` : editing === 'side' ? `С${selectedSide + 1} — начало неподвижно` : dimensionLabel}</span><button type="button" aria-label="Закрыть ввод размеров" onClick={() => setEditing(null)}>×</button></div>
            <div className="mt-1 grid grid-cols-2 gap-2">
              {editing === 'vertex' && <><CsNumberInput label="Ш, мм" value={config.vertices[selectedVertex].x} max={width} onChange={x => updateVertex(selectedVertex, { ...config.vertices[selectedVertex], x })} /><CsNumberInput label="В, мм" value={config.vertices[selectedVertex].y} max={height} onChange={y => updateVertex(selectedVertex, { ...config.vertices[selectedVertex], y })} /></>}
              {editing === 'side' && <CsNumberInput label="Длина стороны, мм" value={side.length} min={1} onChange={length => updateVertex((selectedSide + 1) % config.vertices.length, csSideEnd(config.vertices, selectedSide, length, side.angle))} />}
              {(editing === 'width' || editing === 'height') && <CsNumberInput label={editing === 'width' ? 'Ширина, мм' : 'Высота, мм'} value={editing === 'width' ? width : height} min={1} onChange={value => updateDimension(editing === 'width' ? 'width' : 'height', value)} />}
            </div></> : <p className="text-xs">Нажмите на размер или угол для точного ввода.</p>}
          {geometryError && <p role="alert" className="mt-1 text-xs text-red-700">{geometryError}</p>}
        </div></div>
      </div>);
  return <div className="space-y-3">
    {diagramContainer ? createPortal(canvas, diagramContainer) : canvas}
    <div className="grid gap-4 sm:grid-cols-2">
      <label>
        <span className={LBL}>Система ЦС</span>
        <select value={section.csSystemId || ''} onChange={event => update({ csSystemId: Number(event.target.value) || undefined })} className={SEL}>
          <option value="">Выберите систему</option>
          {systems.map(system => <option key={system.id} value={system.id}>{system.name}</option>)}
        </select>
      </label>
      <div className="rounded-xl border border-amber-400/25 bg-amber-500/10 px-4 py-3 text-xs text-fg">
        Геометрия по ТЗ Т40Т/Т40К. Коммерческая цена пока не формируется.
      </div>
    </div>

    <div className="grid gap-4 sm:grid-cols-2">
      <details className="rounded-xl border border-tint/25 p-3 text-xs"><summary className="cursor-pointer font-bold">Дополнительные настройки</summary><div className="mt-3"><CsNumberInput label="Вычет RS1002, мм" value={config.bubbleDeductionMm!} max={50} onChange={bubbleDeductionMm => commitConfig({ ...config, bubbleDeductionMm })} /></div></details>
    </div>
    <p className="text-xs text-fg/65">{config.dimensionMode === 'clear' ? 'Вводятся размеры светового проёма.' : 'Вводятся наружные размеры конструкции.'} Стекло только 10 мм, зазор в стыке 3 мм.</p>
    {(error || frames.error) && <div role="alert" className="rounded-xl border border-red-500/40 p-3 text-sm">{error || frames.error}</div>}
    <div>
      <label className={LBL}>Типовая схема</label>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {CS_SHAPES.map(shape => <button key={shape} type="button" onClick={() => choosePreset(shape)}
          className={`rounded-xl border px-3 py-3 text-xs font-bold ${section.csShape === shape ? 'border-accent/50 bg-accent/10 text-accent' : 'border-tint/20 bg-black/10 text-fg/50'}`}>{csShapeLabel(shape)}</button>)}
      </div>
      {!isRectangle && <button type="button" className="mt-2 rounded-lg border border-tint/30 px-3 py-2 text-xs" onClick={() => commitConfig({ ...config, vertices: config.vertices.map(point => ({ x: width - point.x, y: point.y })), vertical: { ...config.vertical, positions: config.vertical.positions?.map(x => width - x).sort((a, b) => a - b), mode: config.vertical.mode === 'from-left' ? 'from-right' : config.vertical.mode === 'from-right' ? 'from-left' : config.vertical.mode } })}>Отразить зеркально</button>}
    </div>

    <div key={section.id} className="grid gap-3 sm:grid-cols-2">
      <SplitControls title="Вертикальное деление" value={config.vertical} minimum={bounds.minX} maximum={bounds.maxX} onChange={value => commitConfig({ ...config, vertical: value })} />
      <SplitControls title="Горизонтальное деление" value={config.horizontal} minimum={bounds.minY} maximum={bounds.maxY} onChange={value => commitConfig({ ...config, horizontal: value })} />
    </div>

    <div className="cs-advanced">
      <div className="space-y-3">
        {!isRectangle && <details key={`${section.id}-vertex-${selectedVertex}`} className="space-y-3 rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
          <summary className="cursor-pointer text-xs font-bold">Дополнительно: координаты углов</summary><label><span className={LBL}>Выбранный угол</span><select value={selectedVertex} onChange={event => setSelectedVertex(Number(event.target.value))} className={SEL}>
            {config.vertices.map((_, index) => <option key={index} value={index}>У{index + 1} — угол {index + 1}</option>)}
          </select></label>
          <div className="grid grid-cols-2 gap-2">
            <CsNumberInput label="Ш, мм" value={config.vertices[selectedVertex].x} max={width} onChange={x => updateVertex(selectedVertex, { ...config.vertices[selectedVertex], x })} />
            <CsNumberInput label="В, мм" value={config.vertices[selectedVertex].y} max={height} onChange={y => updateVertex(selectedVertex, { ...config.vertices[selectedVertex], y })} />
          </div>
          <details><summary className="cursor-pointer text-xs">Дополнительно: угол</summary><CsNumberInput label="Внутренний угол, °" value={csVertexAngle(config.vertices, selectedVertex)} min={0.1} max={359.9}
            onChange={angle => updateVertex((selectedVertex + 1) % config.vertices.length, csAngleEnd(config.vertices, selectedVertex, angle))} />
          <p className="text-xs text-fg/65">При изменении угла движется У{(selectedVertex + 1) % config.vertices.length + 1}. Длина стороны С{selectedVertex + 1} сохраняется. Числа применяются по Enter или при выходе из поля.</p></details>
          <button type="button" onClick={removeVertex} disabled={config.vertices.length <= 3} className="flex items-center gap-2 rounded-lg border border-red-500/25 px-3 py-2 text-xs text-fg disabled:opacity-30"><Trash2 className="h-4 w-4" /> Удалить У{selectedVertex + 1}</button>
        </details>}
        {!isRectangle && <details key={`${section.id}-side-${selectedSide}`} className="space-y-3 rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
          <summary className="cursor-pointer text-xs font-bold">Дополнительно: стороны</summary><label><span className={LBL}>Выбранная сторона</span><select value={selectedSide} onChange={event => setSelectedSide(Number(event.target.value))} className={SEL}>
            {config.vertices.map((_, index) => <option key={index} value={index}>{sideLabel(index)}</option>)}
          </select></label>
          <div className="grid grid-cols-2 gap-2">
            <CsNumberInput label="Длина, мм" value={side.length} min={1} onChange={length => updateVertex((selectedSide + 1) % config.vertices.length, csSideEnd(config.vertices, selectedSide, length, side.angle))} />
            <CsNumberInput label="Наклон, °" value={side.angle} max={360} onChange={angle => updateVertex((selectedSide + 1) % config.vertices.length, csSideEnd(config.vertices, selectedSide, side.length, angle))} />
          </div>
          <p className="text-xs text-fg/65">Начало У{selectedSide + 1} неподвижно, меняется конец У{(selectedSide + 1) % config.vertices.length + 1}. 0° — вправо, 90° — вверх.</p>
          <button type="button" onClick={addVertex} disabled={config.vertices.length >= 20} className="flex items-center justify-center gap-2 rounded-xl border border-accent/30 bg-accent/10 px-3 py-2 text-xs font-bold text-accent disabled:opacity-30"><Plus className="h-4 w-4" /> Добавить угол на С{selectedSide + 1}</button>
          <p className="text-xs text-fg/65">Новый угол появится посередине стороны. Нумерация следующих углов и сторон изменится.</p>
        </details>}
        {geometryError && <p role="alert" className="rounded-xl border border-red-500/40 p-3 text-xs text-fg">{geometryError}</p>}
      </div>
    </div>
    <div className="rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
      <div className="mb-2 text-xs font-bold">Комплектация сторон</div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{config.vertices.map((_, index) => <label key={index} className="block text-xs"><span>{sideLabel(index)}</span><select aria-label={`Комплектация С${index + 1}`} className={SEL} value={config.edgeTreatments![index]} onChange={event => { setSelectedSide(index); const edgeTreatments = [...config.edgeTreatments!]; edgeTreatments[index] = event.target.value as 'clamp' | 'bubble' | 'none'; commitConfig({ ...config, edgeTreatments }); }}><option value="clamp">Т40Т + 2 крышки Т40К</option><option value="bubble">RS1002 — пузырьковый</option><option value="none">Без комплектующих</option></select></label>)}</div>
    </div>

    {calc && <details className="rounded-2xl border border-tint/25 bg-hi/[0.025] p-4">
      <summary className="cursor-pointer text-xs font-bold">Предварительная ведомость ЦС</summary><p className="mb-3 text-xs">Конструкция: {calc.installation_width_mm?.toFixed(1)} × {calc.installation_height_mm?.toFixed(1)} мм · Световой: {calc.clear_width_mm?.toFixed(1)} × {calc.clear_height_mm?.toFixed(1)} мм</p>
      <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-bold">Предварительная ведомость ЦС</h4><span className="text-xs text-fg/45">Стекло: {calc.glass_area_m2.toFixed(2)} м² · полотен: {calc.panes.length}</span></div>
      <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-xs"><thead><tr className="text-fg/40"><th className="py-2">Артикул</th><th>Наименование</th><th>Длина</th><th>Кол-во</th></tr></thead><tbody className="divide-y divide-tint/15">{calc.profiles.map(row => <tr key={row.role}><td className="py-2 font-mono font-bold">{row.article}</td><td>{row.name}</td><td>{row.cutting_text || `${row.total_length_mm.toFixed(1)} мм`}</td><td>{row.pieces} шт</td></tr>)}{calc.hardware?.map(row => <tr key={row.role}><td className="py-2 font-mono">{row.article || '—'}</td><td>{row.name}</td><td>—</td><td>{Number(row.qty.toFixed(3))} {row.unit}</td></tr>)}</tbody></table></div>
      <div className="mt-3 text-xs">{calc.panes.map(pane => <div key={pane.number}>З{pane.number}: {pane.width_mm.toFixed(1)} × {pane.height_mm.toFixed(1)} мм · {pane.area_m2.toFixed(3)} м² · {pane.qty} шт.</div>)}</div>
      {calc.warnings.map(warning => <div key={warning} className="mt-2 flex gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200"><AlertTriangle className="h-4 w-4 flex-shrink-0" />{warning}</div>)}
    </details>}
    <div className="rounded-xl border border-tint/20 bg-hi/[0.02] px-4 py-3 text-xs text-fg/45">Входные группы и дверная фурнитура зарезервированы для этапа 2.</div>
  </div>;
}
