import React from 'react';

import type { BookCalcPanel, BookCalcPreview } from '../../api/projects';
import { diagramGlassFillColor } from '../../constants/glass';
import type { Section } from './types';


type PanelLayout = BookCalcPanel & { x: number; width: number };

function panelLayout(calc: BookCalcPreview, startX: number, totalWidth: number): PanelLayout[] {
  const totalMm = calc.panels.reduce((sum, panel) => sum + panel.panel_width_mm, 0) || 1;
  let cursor = startX;
  return calc.panels.map(panel => {
    const width = Math.max(10, panel.panel_width_mm / totalMm * totalWidth);
    const item = { ...panel, x: cursor, width };
    cursor += width;
    return item;
  });
}

function roleLabel(role: BookCalcPanel['role']) {
  return {
    standard: 'панель',
    door: 'дверь',
    fixed: 'глухая',
    moving_door: 'доп. дверь',
  }[role];
}

function movementSymbol(direction: BookCalcPanel['movement_direction']) {
  if (direction === 'left') return '←';
  if (direction === 'right') return '→';
  return '•';
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
  const panels = panelLayout(calc, 44, 372);
  const glassFill = diagramGlassFillColor(section.glassType);
  const drawingHeight = 196;

  return (
    <svg
      viewBox="0 0 460 286"
      className="h-auto w-full min-w-[390px]"
      role="img"
      aria-label="КНИЖКА, вид из помещения"
      data-book-room-view
      data-book-panel-total={calc.panels.length}
    >
      <defs>
        <marker id={arrowId} markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L7,3 z" fill="var(--diagram-symbol)" />
        </marker>
      </defs>

      <line x1="36" y1="28" x2="424" y2="28" stroke="var(--diagram-line)" strokeWidth="4" />
      <line x1="36" y1="232" x2="424" y2="232" stroke="var(--diagram-line)" strokeWidth="4" />
      {panels.map((panel, index) => {
        const isDoor = panel.role === 'door' || panel.role === 'moving_door';
        const roleStroke = panel.role === 'fixed'
          ? '#f59e0b'
          : panel.role === 'moving_door' ? '#f97316' : 'var(--diagram-line)';
        const arrowStart = panel.movement_direction === 'right'
          ? panel.x + panel.width * 0.3
          : panel.x + panel.width * 0.7;
        const arrowEnd = panel.movement_direction === 'right'
          ? panel.x + panel.width * 0.72
          : panel.x + panel.width * 0.28;
        return (
          <g
            key={panel.number}
            data-book-panel-number={panel.number}
            data-book-panel-role={panel.role}
            data-book-panel-movement={panel.movement_direction}
          >
            <rect
              x={panel.x + 1}
              y="36"
              width={Math.max(6, panel.width - 2)}
              height={drawingHeight}
              rx="2"
              fill={glassFill}
              fillOpacity={panel.role === 'fixed' ? 0.55 : 0.82}
              stroke={roleStroke}
              strokeWidth={isDoor || panel.role === 'fixed' ? 2.3 : 1.2}
            />
            <text
              x={panel.x + panel.width / 2}
              y="62"
              textAnchor="middle"
              fill="var(--diagram-symbol)"
              fontSize="14"
              fontWeight="800"
            >
              {panel.number}
            </text>
            <text
              x={panel.x + panel.width / 2}
              y="79"
              textAnchor="middle"
              fill="var(--diagram-symbol)"
              opacity="0.72"
              fontSize="8"
              fontWeight="700"
            >
              {roleLabel(panel.role)}
            </text>
            <text
              x={panel.x + panel.width / 2}
              y="215"
              textAnchor="middle"
              fill="var(--diagram-symbol)"
              fontSize="10"
              fontWeight="700"
            >
              {panel.glass_width_mm.toFixed(1)}
            </text>
            {panel.movement_direction !== 'none' && (
              <line
                x1={arrowStart}
                y1="194"
                x2={arrowEnd}
                y2="194"
                stroke="var(--diagram-symbol)"
                strokeWidth="1.5"
                markerEnd={`url(#${arrowId})`}
                data-book-panel-arrow={panel.number}
              />
            )}
            {isDoor && (
              <>
                <path
                  d={`M ${panel.x + 5} 116 Q ${panel.x + panel.width / 2} 88 ${panel.x + panel.width - 5} 116`}
                  fill="none"
                  stroke="var(--diagram-symbol)"
                  strokeWidth="1.2"
                  strokeDasharray="3 3"
                  opacity="0.8"
                  data-book-door-swing={panel.number}
                />
                <circle
                  cx={panel.x + panel.width * (panel.door_side === 'left' ? 0.72 : 0.28)}
                  cy="148"
                  r={panel.door_hardware === 'lock' ? 4.5 : 3}
                  fill="none"
                  stroke="var(--diagram-symbol)"
                  strokeWidth="1.6"
                  data-book-door-hardware={panel.door_hardware || 'lock'}
                />
              </>
            )}
            {index < panels.length - 1 && (
              <circle
                cx={panel.x + panel.width}
                cy="134"
                r="3"
                fill="var(--diagram-symbol)"
                data-book-panel-joint={panel.number}
              />
            )}
          </g>
        );
      })}

      <line x1="44" y1="255" x2="416" y2="255" stroke="var(--diagram-line)" strokeWidth="1" />
      <line x1="44" y1="249" x2="44" y2="261" stroke="var(--diagram-line)" />
      <line x1="416" y1="249" x2="416" y2="261" stroke="var(--diagram-line)" />
      <text x="230" y="274" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="11" fontWeight="700">
        {section.width.toFixed(1)} мм
      </text>
      <text
        x="18"
        y="134"
        textAnchor="middle"
        fill="var(--diagram-symbol)"
        fontSize="10"
        fontWeight="700"
        transform="rotate(-90 18 134)"
      >
        {calc.panels[0]?.glass_height_mm.toFixed(1)} мм
      </text>
    </svg>
  );
}

export function BookTopViewSVG({
  section,
  calc,
}: {
  section: Section;
  calc: BookCalcPreview;
}) {
  const prefix = React.useId().replace(/:/g, '');
  const leftArrowId = `${prefix}-book-top-left`;
  const rightArrowId = `${prefix}-book-top-right`;
  const panels = panelLayout(calc, 44, 372);
  const obstacle = calc.normalized_config.obstacle_distance_mm || 0;

  return (
    <svg
      viewBox="0 0 460 246"
      className="h-auto w-full min-w-[390px]"
      role="img"
      aria-label="КНИЖКА, вид сверху"
      data-book-top-view
      data-book-panel-total={calc.panels.length}
    >
      <defs>
        <marker id={leftArrowId} markerWidth="8" markerHeight="8" refX="1" refY="3" orient="auto">
          <path d="M7,0 L7,6 L0,3 z" fill="var(--diagram-symbol)" />
        </marker>
        <marker id={rightArrowId} markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L7,3 z" fill="var(--diagram-symbol)" />
        </marker>
      </defs>

      <rect x="32" y="28" width="396" height="10" rx="3" fill="var(--theme-tint)" opacity="0.45" />
      <text x="230" y="19" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="9" fontWeight="700">
        ПРОЁМ / НАПРАВЛЯЮЩАЯ
      </text>

      {panels.map(panel => {
        const isDoor = panel.role === 'door' || panel.role === 'moving_door';
        const center = panel.x + panel.width / 2;
        const isLeft = panel.movement_direction === 'left';
        const arrowX1 = isLeft ? center + Math.min(28, panel.width * 0.25) : center - Math.min(28, panel.width * 0.25);
        const arrowX2 = isLeft ? center - Math.min(28, panel.width * 0.25) : center + Math.min(28, panel.width * 0.25);
        return (
          <g
            key={panel.number}
            data-book-top-panel={panel.number}
            data-book-panel-role={panel.role}
            data-book-panel-movement={panel.movement_direction}
          >
            <rect
              x={panel.x + 1}
              y="72"
              width={Math.max(6, panel.width - 2)}
              height="14"
              rx="2"
              fill={panel.role === 'fixed' ? '#f59e0b' : 'var(--diagram-glass-clear)'}
              stroke={panel.role === 'moving_door' ? '#f97316' : 'var(--diagram-line)'}
              strokeWidth={isDoor ? 2 : 1}
            />
            <circle cx={panel.x + 2} cy="79" r="2.5" fill="var(--diagram-symbol)" />
            <text x={center} y="68" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="10" fontWeight="800">
              {panel.number}
            </text>
            {panel.movement_direction !== 'none' && (
              <line
                x1={arrowX1}
                y1="107"
                x2={arrowX2}
                y2="107"
                stroke="var(--diagram-symbol)"
                strokeWidth="1.5"
                markerEnd={`url(#${isLeft ? leftArrowId : rightArrowId})`}
                data-book-top-arrow={panel.number}
              />
            )}
            {isDoor && (
              <path
                d={`M ${panel.x + (panel.door_side === 'right' ? panel.width - 2 : 2)} 79 A ${Math.min(panel.width, 60)} ${Math.min(panel.width, 60)} 0 0 ${panel.door_opening?.endsWith('out') ? 1 : 0} ${center} 137`}
                fill="none"
                stroke="var(--diagram-symbol)"
                strokeWidth="1.2"
                strokeDasharray="4 3"
                data-book-top-door-swing={panel.number}
              />
            )}
          </g>
        );
      })}

      {calc.normalized_config.door_layout === 'both' && calc.normalized_config.left_stack_panels && (
        <>
          <line
            x1={panels[calc.normalized_config.left_stack_panels - 1]?.x
              + panels[calc.normalized_config.left_stack_panels - 1]?.width}
            y1="50"
            x2={panels[calc.normalized_config.left_stack_panels - 1]?.x
              + panels[calc.normalized_config.left_stack_panels - 1]?.width}
            y2="124"
            stroke="#f59e0b"
            strokeDasharray="3 3"
            data-book-stack-split
          />
          <text x="230" y="151" textAnchor="middle" fill="#f59e0b" fontSize="9" fontWeight="700">
            ЛЕВЫЙ / ПРАВЫЙ СБОР
          </text>
        </>
      )}

      <line x1="44" y1="171" x2="416" y2="171" stroke="var(--diagram-line)" strokeWidth="1" />
      <line x1="44" y1="166" x2="44" y2="177" stroke="var(--diagram-line)" />
      <line x1="416" y1="166" x2="416" y2="177" stroke="var(--diagram-line)" />
      <text x="230" y="190" textAnchor="middle" fill="var(--diagram-symbol)" fontSize="11" fontWeight="700">
        {section.width.toFixed(1)} мм
      </text>

      {obstacle > 0 && (
        <g data-book-obstacle>
          <line x1="44" y1="211" x2="416" y2="211" stroke="#ef4444" strokeWidth="2" strokeDasharray="6 4" />
          <line x1="32" y1="38" x2="32" y2="211" stroke="#ef4444" strokeWidth="1" />
          <text x="230" y="230" textAnchor="middle" fill="#ef4444" fontSize="10" fontWeight="700">
            Препятствие · {obstacle.toFixed(1)} мм
          </text>
        </g>
      )}
      {!obstacle && (
        <text x="230" y="224" textAnchor="middle" fill="var(--diagram-symbol)" opacity="0.45" fontSize="9">
          Расстояние до препятствия не задано
        </text>
      )}
      <text x="42" y="107" fill="var(--diagram-symbol)" fontSize="11" fontWeight="800">
        {movementSymbol(calc.panels[0]?.movement_direction || 'none')}
      </text>
      <text x="418" y="107" textAnchor="end" fill="var(--diagram-symbol)" fontSize="11" fontWeight="800">
        {movementSymbol(calc.panels.at(-1)?.movement_direction || 'none')}
      </text>
    </svg>
  );
}
