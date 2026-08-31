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
  const panels = panelLayout(calc, 48, 356);
  const glassFill = diagramGlassFillColor(section.glassType);
  const top = 32;
  const bottom = 222;
  const drawingHeight = bottom - top;
  const handleHeightMm = Number(calc.normalized_config.handle_height_mm ?? section.bookHandleHeight ?? 1000);
  const handleY = bottom - Math.max(0, Math.min(1, handleHeightMm / Math.max(section.height, 1))) * drawingHeight;

  return (
    <svg
      viewBox="0 0 460 292"
      className="h-auto w-full min-w-[390px]"
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

      <text x="226" y="16" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="9" fontWeight="700">
        ВИД ИЗ ПОМЕЩЕНИЯ
      </text>
      <rect x="44" y="27" width="364" height="200" fill="none" stroke="var(--diagram-line)" strokeWidth="3" />
      {panels.map((panel, index) => {
        const isDoor = panel.role === 'door' || panel.role === 'moving_door';
        const roleStroke = panel.role === 'fixed'
          ? '#b7791f'
          : panel.role === 'moving_door' ? '#c05621' : 'var(--diagram-line)';
        const cx = panel.x + panel.width / 2;
        const arrowStart = panel.movement_direction === 'right' ? cx - 10 : cx + 10;
        const arrowEnd = panel.movement_direction === 'right' ? cx + 10 : cx - 10;
        const outerX = doorConvergesRight(panel) ? panel.x + 5 : panel.x + panel.width - 5;
        const convergenceX = doorConvergesRight(panel) ? panel.x + panel.width - 5 : panel.x + 5;
        return (
          <g
            key={panel.number}
            data-book-panel-number={panel.number}
            data-book-panel-role={panel.role}
            data-book-panel-movement={panel.movement_direction}
          >
            <rect
              x={panel.x + 1}
              y={top}
              width={Math.max(1, panel.width - 2)}
              height={drawingHeight}
              fill={glassFill}
              fillOpacity={panel.role === 'fixed' ? 0.5 : 0.78}
              stroke={roleStroke}
              strokeWidth={isDoor || panel.role === 'fixed' ? 2 : 1}
            />
            {panel.role === 'fixed' && (
              <>
                <path
                  d={`M ${panel.x + 5} ${top + 7} L ${panel.x + panel.width - 5} ${bottom - 7} M ${panel.x + panel.width - 5} ${top + 7} L ${panel.x + 5} ${bottom - 7}`}
                  stroke={roleStroke}
                  strokeWidth="1"
                  opacity="0.55"
                  data-book-fixed-hatch={panel.number}
                />
                <text x={cx} y="82" textAnchor="middle" fill={roleStroke} fontSize="7" fontWeight="800">
                  ГЛУХАЯ
                </text>
              </>
            )}
            <text x={cx} y="61" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="12" fontWeight="800">
              {panel.number}
            </text>
            <text x={cx} y="244" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="8.5" fontWeight="700">
              {formatMm(panel.glass_width_mm)}
            </text>
            {panel.movement_direction !== 'none' && (
              <line
                x1={arrowStart}
                y1="184"
                x2={arrowEnd}
                y2="184"
                stroke="var(--diagram-symbol)"
                strokeWidth="1.4"
                markerEnd={`url(#${arrowId})`}
                data-book-panel-arrow={panel.number}
              />
            )}
            {isDoor && (
              <>
                <path
                  d={`M ${outerX} 91 L ${convergenceX} 128 L ${outerX} 165`}
                  fill="none"
                  stroke="var(--diagram-symbol)"
                  strokeWidth="2"
                  data-book-door-v={panel.number}
                  data-book-door-v-direction={doorConvergesRight(panel) ? 'right' : 'left'}
                />
                <circle
                  cx={doorConvergesRight(panel) ? panel.x + panel.width * 0.72 : panel.x + panel.width * 0.28}
                  cy={handleY}
                  r={panel.door_hardware === 'lock' ? 4 : 2.8}
                  fill="none"
                  stroke="var(--diagram-symbol)"
                  strokeWidth="1.5"
                  data-book-door-hardware={panel.door_hardware || 'lock'}
                  data-book-handle-height-mm={handleHeightMm.toFixed(1)}
                  data-book-handle-y={handleY.toFixed(2)}
                />
              </>
            )}
            {index < panels.length - 1 && (
              <circle cx={panel.x + panel.width} cy="128" r="2.5" fill="var(--diagram-symbol)" data-book-panel-joint={panel.number} />
            )}
          </g>
        );
      })}

      <line x1="48" y1="260" x2="404" y2="260" stroke="var(--diagram-line)" strokeWidth="1" />
      <line x1="48" y1="255" x2="48" y2="265" stroke="var(--diagram-line)" />
      <line x1="404" y1="255" x2="404" y2="265" stroke="var(--diagram-line)" />
      <text x="226" y="279" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="10" fontWeight="700">
        {formatMm(section.width)} мм
      </text>
      <line x1="426" y1="32" x2="426" y2="222" stroke="var(--diagram-line)" />
      <line x1="421" y1="32" x2="431" y2="32" stroke="var(--diagram-line)" />
      <line x1="421" y1="222" x2="431" y2="222" stroke="var(--diagram-line)" />
      <text x="442" y="127" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="9" fontWeight="700" transform="rotate(-90 442 127)">
        {formatMm(section.height)} мм
      </text>
      <text x="226" y="290" textAnchor="middle" fill="var(--diagram-symbol)" opacity="0.55" fontSize="8" fontWeight="700">
        ПОМЕЩЕНИЕ
      </text>
    </svg>
  );
}

function stackPanels(calc: BookCalcPreview, direction: 'left' | 'right'): BookCalcPanel[] {
  return calc.panels.filter(panel => panel.role !== 'fixed' && panel.movement_direction === direction);
}

export function BookTopViewSVG({
  section,
  calc,
}: {
  section: Section;
  calc: BookCalcPreview;
}) {
  const prefix = React.useId().replace(/:/g, '');
  const arrowId = `${prefix}-book-top-arrow`;
  const panels = panelLayout(calc, 54, 352);
  const fixedPanels = panels.filter(panel => panel.role === 'fixed');
  const leftPanels = stackPanels(calc, 'left');
  const rightPanels = stackPanels(calc, 'right');
  const obstacle = Number(calc.normalized_config.obstacle_distance_mm || 0);
  const trackY = 135;
  const stackLength = 58;
  const leftOpeningPanel = leftPanels.find(panel => panel.role === 'door' || panel.role === 'moving_door');
  const rightOpeningPanel = rightPanels.find(panel => panel.role === 'door' || panel.role === 'moving_door');
  const leftRoomSide = leftOpeningPanel ? opensToRoom(leftOpeningPanel) : true;
  const rightRoomSide = rightOpeningPanel ? opensToRoom(rightOpeningPanel) : true;
  const legacyLeftAngle = Number(calc.normalized_config.angle_left_deg || 0);
  const legacyRightAngle = Number(calc.normalized_config.angle_right_deg || 0);

  const renderStack = (direction: 'left' | 'right', stack: BookCalcPanel[], roomSide: boolean) => {
    const baseX = direction === 'left' ? 61 : 399;
    const sideSign = roomSide ? 1 : -1;
    const xSign = direction === 'left' ? 1 : -1;
    return (
      <g
        data-book-stack={direction}
        data-book-stack-side={roomSide ? 'room' : 'street'}
        data-book-stack-leaves={stack.length}
      >
        {stack.map((panel, index) => {
          const x = baseX + xSign * index * 4.5;
          const isMainDoor = panel.role === 'door';
          return (
            <g key={`${direction}-${panel.number}`} data-book-stack-panel={panel.number} data-book-panel-role={panel.role}>
              <line
                x1={x}
                y1={trackY}
                x2={x}
                y2={trackY + sideSign * stackLength}
                stroke={panel.role === 'moving_door' ? '#c05621' : 'var(--diagram-symbol)'}
                strokeWidth={isMainDoor ? 3 : panel.role === 'moving_door' ? 2.3 : 1.5}
                strokeDasharray={panel.role === 'moving_door' ? '5 3' : undefined}
              />
              <text
                x={x + (direction === 'left' ? -2 : 2)}
                y={trackY + sideSign * (stackLength + 10)}
                textAnchor={direction === 'left' ? 'end' : 'start'}
                fill="var(--diagram-symbol)"
                fontSize="7"
                fontWeight="800"
              >
                {panel.number}
              </text>
            </g>
          );
        })}
        {stack.length > 0 && (
          <line
            x1={direction === 'left' ? 147 : 313}
            y1={trackY}
            x2={direction === 'left' ? 83 : 377}
            y2={trackY}
            stroke="var(--diagram-symbol)"
            strokeWidth="1.5"
            markerEnd={`url(#${arrowId})`}
            data-book-stack-arrow={direction}
          />
        )}
      </g>
    );
  };

  return (
    <svg
      viewBox="0 0 460 310"
      className="h-auto w-full min-w-[390px]"
      role="img"
      aria-label="КНИЖКА, вид сверху"
      data-book-top-view
      data-book-panel-total={calc.panels.length}
    >
      <defs>
        <marker id={arrowId} markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L7,3 z" fill="var(--diagram-symbol)" />
        </marker>
      </defs>

      <text x="230" y="18" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="8" fontWeight="700">УЛИЦА</text>
      <line x1="48" y1={trackY} x2="412" y2={trackY} stroke="var(--diagram-line)" strokeWidth="5" />
      <line x1="48" y1={trackY - 7} x2="412" y2={trackY - 7} stroke="var(--diagram-line)" strokeWidth="1" />
      <line x1="48" y1={trackY + 7} x2="412" y2={trackY + 7} stroke="var(--diagram-line)" strokeWidth="1" />
      {legacyLeftAngle > 0 && (
        <line
          x1="48"
          y1={trackY}
          x2={48 + Math.cos((180 - legacyLeftAngle) * Math.PI / 180) * 55}
          y2={trackY - Math.sin((180 - legacyLeftAngle) * Math.PI / 180) * 55}
          stroke="#b7791f"
          strokeWidth="4"
          data-book-legacy-angle="left"
        />
      )}
      {legacyRightAngle > 0 && (
        <line
          x1="412"
          y1={trackY}
          x2={412 - Math.cos((180 - legacyRightAngle) * Math.PI / 180) * 55}
          y2={trackY - Math.sin((180 - legacyRightAngle) * Math.PI / 180) * 55}
          stroke="#b7791f"
          strokeWidth="4"
          data-book-legacy-angle="right"
        />
      )}

      {fixedPanels.map(panel => (
        <g key={`fixed-${panel.number}`} data-book-top-fixed={panel.number}>
          <rect x={panel.x + 1} y={trackY - 7} width={Math.max(2, panel.width - 2)} height="14" fill="#f6d89b" stroke="#b7791f" strokeWidth="1.5" />
          <text x={panel.x + panel.width / 2} y={trackY + 3} textAnchor="middle" fill="#8b5a14" fontSize="8" fontWeight="900">Г</text>
        </g>
      ))}

      {renderStack('left', leftPanels, leftRoomSide)}
      {renderStack('right', rightPanels, rightRoomSide)}

      {[leftOpeningPanel, rightOpeningPanel].filter(Boolean).map(panel => {
        const item = panel as BookCalcPanel;
        const direction = item.movement_direction as 'left' | 'right';
        const roomSide = opensToRoom(item);
        const pivotX = direction === 'left' ? 61 : 399;
        const sweep = roomSide ? 1 : 0;
        const endY = trackY + (roomSide ? 48 : -48);
        const endX = pivotX + (direction === 'left' ? 48 : -48);
        return (
          <path
            key={`swing-${item.number}`}
            d={`M ${pivotX} ${trackY} A 48 48 0 0 ${sweep} ${endX} ${endY}`}
            fill="none"
            stroke="var(--diagram-symbol)"
            strokeWidth="1.2"
            strokeDasharray="4 3"
            data-book-top-door-swing={item.number}
            data-book-opening-side={roomSide ? 'room' : 'street'}
          />
        );
      })}

      {obstacle > 0 && Array.from(new Set([
        ...(leftPanels.length ? [leftRoomSide ? 'room' : 'street'] : []),
        ...(rightPanels.length ? [rightRoomSide ? 'room' : 'street'] : []),
      ])).map(side => {
        const roomSide = side === 'room';
        const y = roomSide ? 245 : 45;
        return (
          <g key={side} data-book-obstacle={side}>
            <line x1="48" y1={y} x2="412" y2={y} stroke="#dc2626" strokeWidth="1.5" strokeDasharray="6 4" />
            <line x1="36" y1={trackY} x2="36" y2={y} stroke="#dc2626" strokeWidth="1" />
            <line x1="31" y1={trackY} x2="41" y2={trackY} stroke="#dc2626" />
            <line x1="31" y1={y} x2="41" y2={y} stroke="#dc2626" />
            <text x="230" y={roomSide ? y + 14 : y + 14} textAnchor="middle" fill="#dc2626" fontSize="8" fontWeight="700">
              до препятствия {formatMm(obstacle)} мм
            </text>
          </g>
        );
      })}

      <text x="230" y="218" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="8" fontWeight="700">ПОМЕЩЕНИЕ</text>
      <line x1="54" y1="282" x2="406" y2="282" stroke="var(--diagram-line)" />
      <line x1="54" y1="277" x2="54" y2="287" stroke="var(--diagram-line)" />
      <line x1="406" y1="277" x2="406" y2="287" stroke="var(--diagram-line)" />
      <text x="230" y="302" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="10" fontWeight="700">
        {formatMm(section.width)} мм
      </text>
    </svg>
  );
}
