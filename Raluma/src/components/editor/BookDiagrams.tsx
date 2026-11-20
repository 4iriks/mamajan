import React from 'react';

import type { BookCalcPanel, BookCalcPreview } from '../../api/projects';
import { diagramGlassFillColor } from '../../constants/glass';
import type { Section } from './types';


type PanelLayout = BookCalcPanel & { x: number; width: number };

function panelLayout(calc: BookCalcPreview, startX: number, totalWidth: number): PanelLayout[] {
  const totalMm = calc.panels.reduce((sum, panel) => sum + panel.panel_width_mm, 0) || 1;
  let cursor = startX;
  return calc.panels.map((panel, index) => {
    const width = index === calc.panels.length - 1
      ? startX + totalWidth - cursor
      : panel.panel_width_mm / totalMm * totalWidth;
    const item = { ...panel, x: cursor, width: Math.max(2, width) };
    cursor += width;
    return item;
  });
}

function formatMm(value: number): string {
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
}

function doorConvergesRight(panel: BookCalcPanel): boolean {
  if (panel.door_side) return panel.door_side === 'left';
  return panel.movement_direction === 'left';
}

function opensToRoom(panel: BookCalcPanel): boolean {
  return panel.door_opening === 'inside_in' || panel.door_opening === 'outside_in';
}

export function BookRoomViewSVG({
  section,
  calc,
}: {
  section: Section;
  calc: BookCalcPreview;
}) {
  const prefix = React.useId().replace(/:/g, '');
  const arrowId = `${prefix}-book-room-arrow`;
  const panels = panelLayout(calc, 20, 416);
  const glassFill = diagramGlassFillColor(section.glassType);
  const top = 12;
  const bottom = top + Math.max(150, Math.min(250, 416 * section.height / Math.max(section.width, 1)));
  const drawingHeight = bottom - top;
  const handleHeightMm = Number(calc.normalized_config.handle_height_mm ?? section.bookHandleHeight ?? 1000);
  const handleY = bottom - Math.max(0, Math.min(1, handleHeightMm / Math.max(section.height, 1))) * drawingHeight;

  return (
    <svg
      viewBox={`0 0 480 ${bottom + 64}`}
      className="h-auto w-full min-w-0"
      role="img"
      aria-label="КНИЖКА, вид из помещения"
      data-book-room-view
      data-book-panel-total={calc.panels.length}
    >
      <defs>
        <marker id={arrowId} markerWidth="7" markerHeight="7" refX="5.5" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="var(--diagram-symbol)" />
        </marker>
      </defs>

      {panels.map(panel => {
        const isDoor = panel.role === 'door' || panel.role === 'moving_door';
        const roleStroke = panel.role === 'fixed'
          ? '#b7791f'
          : panel.role === 'moving_door' ? '#c05621' : 'var(--diagram-line)';
        const cx = panel.x + panel.width / 2;
        const arrowStart = panel.movement_direction === 'right' ? cx - 10 : cx + 10;
        const arrowEnd = panel.movement_direction === 'right' ? cx + 10 : cx - 10;
        const outerX = doorConvergesRight(panel) ? panel.x : panel.x + panel.width;
        const convergenceX = doorConvergesRight(panel) ? panel.x + panel.width : panel.x;
        return (
          <g
            key={panel.number}
            data-book-panel-number={panel.number}
            data-book-panel-role={panel.role}
            data-book-panel-movement={panel.movement_direction}
          >
            <rect
              x={panel.x}
              y={top + 6}
              width={panel.width}
              height={drawingHeight - 12}
              fill={glassFill}
              fillOpacity={panel.role === 'fixed' ? 0.5 : 0.78}
              stroke={roleStroke}
              strokeWidth="0.8"
            />
            {[top, bottom - 6].map(y => <rect key={y} x={panel.x} y={y} width={panel.width} height="6" fill="var(--diagram-line)" fillOpacity="0.25" stroke={roleStroke} strokeWidth="1" data-book-glass-profile={panel.number} />)}
            {panel.role === 'fixed' && (
              <>
                <path
                  d={`M ${panel.x + 5} ${top + 10} L ${panel.x + panel.width - 5} ${bottom - 10} M ${panel.x + panel.width - 5} ${top + 10} L ${panel.x + 5} ${bottom - 10}`}
                  stroke={roleStroke}
                  strokeWidth="0.8"
                  opacity="0.55"
                  data-book-fixed-hatch={panel.number}
                />
                <text x={cx} y={top + 48} textAnchor="middle" fill={roleStroke} fontSize="9" fontWeight="800">
                  ГЛУХАЯ
                </text>
              </>
            )}
            <text x={cx} y={top + 28} textAnchor="middle" fill="var(--diagram-symbol)" fontSize="14" fontWeight="800">
              {panel.number}
            </text>
            <text x={cx} y={bottom + 18} textAnchor="middle" fill="var(--diagram-symbol)" fontSize="11.5" fontWeight="700">
              {formatMm(panel.glass_width_mm)}
            </text>
            {panel.role !== 'door' && panel.role !== 'fixed' && panel.movement_direction !== 'none' && (
              <line
                x1={arrowStart}
                y1={bottom - 32}
                x2={arrowEnd}
                y2={bottom - 32}
                stroke="var(--diagram-symbol)"
                strokeWidth="1.4"
                markerEnd={`url(#${arrowId})`}
                data-book-panel-arrow={panel.number}
              />
            )}
            {isDoor && (
              <>
                <path
                  d={`M ${outerX} ${top + 6} L ${convergenceX} ${top + drawingHeight * 0.5} L ${outerX} ${bottom - 6}`}
                  fill="none"
                  stroke="var(--diagram-symbol)"
                  strokeWidth="1"
                  data-book-door-v={panel.number}
                  data-book-door-v-direction={doorConvergesRight(panel) ? 'right' : 'left'}
                />
                <g
                  data-book-door-hardware={panel.door_hardware || 'lock'}
                  data-book-handle-height-mm={handleHeightMm.toFixed(1)}
                  data-book-handle-y={handleY.toFixed(2)}
                >
                  {panel.door_hardware === 'handle'
                    ? <rect x={panel.x + panel.width * (doorConvergesRight(panel) ? 0.72 : 0.28) - 3} y={handleY - 3} width="6" height="6" fill="var(--diagram-symbol)" fillOpacity="0.3" stroke="var(--diagram-symbol)" strokeWidth="0.8" />
                    : <circle cx={panel.x + panel.width * (doorConvergesRight(panel) ? 0.72 : 0.28)} cy={handleY} r="3.5" fill="none" stroke="var(--diagram-symbol)" strokeWidth="1" />}
                </g>
              </>
            )}
          </g>
        );
      })}

      <line x1="20" y1={bottom + 42} x2="436" y2={bottom + 42} stroke="var(--diagram-line)" strokeWidth="1" />
      {[20, 436].map(x => <line key={x} x1={x} y1={bottom + 38} x2={x} y2={bottom + 46} stroke="var(--diagram-line)" />)}
      <text x="228" y={bottom + 36} textAnchor="middle" fill="var(--diagram-symbol)" fontSize="13" fontWeight="700">
        {formatMm(section.width)} мм
      </text>
      <line x1="452" y1={top} x2="452" y2={bottom} stroke="var(--diagram-line)" />
      {[top, bottom].map(y => <line key={y} x1="448" y1={y} x2="456" y2={y} stroke="var(--diagram-line)" />)}
      <text x="470" y={(top + bottom) / 2} textAnchor="middle" fill="var(--diagram-symbol)" fontSize="13" fontWeight="700" transform={`rotate(-90 470 ${(top + bottom) / 2})`}>
        {formatMm(section.height)} мм
      </text>
      <text x="228" y={bottom + 59} textAnchor="middle" fill="var(--diagram-symbol)" fontSize="10" fontWeight="700">
        ПОМЕЩЕНИЕ
      </text>
    </svg>
  );
}

export function BookTopViewSVG({ section, calc }: { section: Section; calc: BookCalcPreview }) {
  const arrowId = `${React.useId().replace(/:/g, '')}-book-top-arrow`;
  const left = 20, right = 436, span = right - left, center = (left + right) / 2;
  const panels = panelLayout(calc, left, span);
  const length = (panel: BookCalcPanel) => panel.panel_width_mm / Math.max(section.width, 1) * span;
  const groups = (['left', 'right'] as const).map(direction => {
    const stack = panels.filter(p => p.role !== 'fixed' && p.movement_direction === direction);
    if (direction === 'right') stack.reverse();
    const door = stack.find(p => p.role === 'door' || p.role === 'moving_door');
    const room = door ? opensToRoom(door) : true;
    const base = direction === 'left' ? stack[0]?.x ?? left : stack[0] ? stack[0].x + stack[0].width : right;
    return { direction, stack, door, room, base, sign: direction === 'left' ? 1 : -1 };
  }).filter(g => g.stack.length);
  const inside = Math.max(0, ...groups.filter(g => g.room).flatMap(g => g.stack.map(length)));
  const outside = Math.max(0, ...groups.filter(g => !g.room).flatMap(g => g.stack.map(length)));
  const obstacle = Number(calc.normalized_config.obstacle_distance_mm || 0);
  const angles = [Number(calc.normalized_config.angle_left_deg || 0), Number(calc.normalized_config.angle_right_deg || 0)];
  const topExtent = Math.max(outside, angles.some(a => a > 0) ? 55 : 0);
  const roomObstacle = obstacle > 0 && inside > 0;
  const streetObstacle = obstacle > 0 && outside > 0;
  const below = outside > 0;
  const dimensionY = below ? inside + (roomObstacle ? 48 : 0) + 28 : -24;
  const roomY = Math.max(inside + (roomObstacle ? 48 : 0) + 20, below ? dimensionY + 22 : 0);
  const streetY = Math.min(-topExtent - (streetObstacle ? 48 : 18), below ? -18 : -48);
  return <svg viewBox={`0 ${streetY - 16} 480 ${roomY - streetY + 28}`} className="h-auto w-full min-w-0" role="img" aria-label="КНИЖКА, вид сверху" data-book-top-view data-book-panel-total={panels.length}>
    <defs><marker id={arrowId} markerWidth="7" markerHeight="7" refX="5.5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="var(--diagram-symbol)" /></marker></defs>
    <text x={center} y={streetY} textAnchor="middle" fill="var(--diagram-symbol)" fontSize="10">УЛИЦА</text>
    {[-4, 4].map(y => <line key={y} x1={left} y1={y} x2={right} y2={y} stroke="var(--diagram-line)" strokeWidth="1.2" />)}
    {[left, right].map(x => <line key={x} x1={x} y1="-4" x2={x} y2="4" stroke="var(--diagram-line)" strokeWidth="1.2" data-book-top-limit />)}
    {angles.map((angle, i) => angle > 0 && <line key={i} x1={i ? right : left} y1="0" x2={(i ? right : left) + (i ? -1 : 1) * Math.cos((180 - angle) * Math.PI / 180) * 55} y2={-Math.sin((180 - angle) * Math.PI / 180) * 55} stroke="#b7791f" strokeWidth="2" data-book-legacy-angle={i ? 'right' : 'left'} />)}
    {panels.filter(p => p.role === 'fixed').map(panel => <g key={panel.number} data-book-top-fixed={panel.number}>
      <rect x={panel.x} y="-5" width={panel.width} height="10" fill="#f6d89b" stroke="#b7791f" />
      <text x={panel.x + panel.width / 2} y="3" textAnchor="middle" fill="#8b5a14" fontSize="9">Г</text>
    </g>)}
    {groups.map(group => <g key={group.direction} data-book-stack={group.direction} data-book-stack-side={group.room ? 'room' : 'street'} data-book-stack-leaves={group.stack.length}>
      {group.stack.map((panel, index) => {
        const x = group.base + group.sign * index * Math.min(6, span / 4 / group.stack.length);
        const leafLength = length(panel);
        return <g key={panel.number} data-book-stack-panel={panel.number} data-book-panel-role={panel.role}>
          <line x1={x} y1="0" x2={x} y2={(group.room ? 1 : -1) * leafLength} stroke={panel.role === 'moving_door' ? '#c05621' : 'var(--diagram-symbol)'} strokeWidth={panel.role === 'door' ? 2 : 1} strokeDasharray={panel.role === 'moving_door' ? '5 3' : undefined} data-book-leaf-length={leafLength.toFixed(3)} />
        </g>;
      })}
      <line x1={center + (group.direction === 'left' ? -12 : 12)} y1="16" x2={group.base + group.sign * (group.stack.length * 6 + 18)} y2="16" stroke="var(--diagram-symbol)" strokeWidth="1.2" markerEnd={`url(#${arrowId})`} data-book-stack-arrow={group.direction} />
      {group.door && <path d={`M ${group.base + group.sign * length(group.door)} 0 A ${length(group.door)} ${length(group.door)} 0 0 ${(group.sign > 0) === group.room ? 1 : 0} ${group.base} ${(group.room ? 1 : -1) * length(group.door)}`} fill="none" stroke="var(--diagram-symbol)" strokeWidth="0.7" strokeDasharray="4 3" data-book-top-door-swing={group.door.number} data-book-opening-side={group.room ? 'room' : 'street'} />}
    </g>)}
    {([['room', roomObstacle, inside], ['street', streetObstacle, outside]] as const).map(([side, visible, extent]) => visible && <g key={side} data-book-obstacle={side}>
      <line x1={left} y1={(side === 'room' ? 1 : -1) * (extent + 20)} x2={right} y2={(side === 'room' ? 1 : -1) * (extent + 20)} stroke="#dc2626" strokeDasharray="6 4" />
      <text x={center} y={side === 'room' ? extent + 35 : -extent - 28} textAnchor="middle" fill="#dc2626" fontSize="10">до препятствия {formatMm(obstacle)} мм</text>
    </g>)}
    <g data-book-width-dimension data-book-dimension-side={below ? 'room' : 'street'}>
      <line x1={left} y1={dimensionY} x2={right} y2={dimensionY} stroke="var(--diagram-line)" />
      {[left, right].map(x => <line key={x} x1={x} y1={dimensionY - 4} x2={x} y2={dimensionY + 4} stroke="var(--diagram-line)" />)}
      <text x={center} y={dimensionY - 6} textAnchor="middle" fill="var(--diagram-symbol)" fontSize="13" fontWeight="700">{formatMm(section.width)} мм</text>
    </g>
    <text x={center} y={roomY} textAnchor="middle" fill="var(--diagram-symbol)" fontSize="10">ПОМЕЩЕНИЕ</text>
  </svg>;
}
