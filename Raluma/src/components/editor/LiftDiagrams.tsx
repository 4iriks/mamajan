import React from 'react';
import type { Section } from './types';
import {
  LIFT_DEFAULT_CABLE_SIDE,
  LIFT_DEFAULT_OPENING,
  LIFT_SPLIT_OPENING,
} from './liftConfig';

const VIEW_WIDTH = 760;
const VIEW_HEIGHT = 500;
const MAX_FRAME_WIDTH = 570;
const MAX_FRAME_HEIGHT = 300;
const FRAME_CENTER_Y = 250;

type PanelState = 'fixed' | 'up' | 'down';

function panelStates(panels: number, opening: string): PanelState[] {
  if (panels === 4 && opening === LIFT_SPLIT_OPENING) {
    return ['fixed', 'down', 'down', 'fixed'];
  }
  if (opening === 'Сдвиг вверх') {
    return Array.from({ length: panels }, (_, index) => index === 0 ? 'fixed' : 'up');
  }
  return Array.from({ length: panels }, (_, index) => index === panels - 1 ? 'fixed' : 'down');
}

interface ArrowProps {
  x: number;
  y: number;
  direction: 'up' | 'down';
  panel: number;
}

const Arrow: React.FC<ArrowProps> = ({
  x,
  y,
  direction,
  panel,
}) => {
  const sign = direction === 'down' ? 1 : -1;
  const startY = y - sign * 18;
  const endY = y + sign * 18;
  return (
    <g
      data-lift-moving-panel={panel}
      data-direction={direction}
      stroke="var(--theme-accent)"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    >
      <line x1={x} y1={startY} x2={x} y2={endY} />
      <path d={`M ${x - 6} ${endY - sign * 7} L ${x} ${endY} L ${x + 6} ${endY - sign * 7}`} />
    </g>
  );
};

export function LiftRoomViewSVG({ section }: { section: Section }) {
  const panels = Math.min(4, Math.max(2, section.panels || 2));
  const opening = section.liftOpeningType || LIFT_DEFAULT_OPENING;
  const cableSide = section.liftCableSide || LIFT_DEFAULT_CABLE_SIDE;
  const safeWidth = Math.max(1, section.width || 1);
  const safeHeight = Math.max(1, section.height || 1);
  const ratio = safeWidth / safeHeight;

  let frameWidth = MAX_FRAME_WIDTH;
  let frameHeight = frameWidth / ratio;
  if (frameHeight > MAX_FRAME_HEIGHT) {
    frameHeight = MAX_FRAME_HEIGHT;
    frameWidth = frameHeight * ratio;
  }

  const frameX = (VIEW_WIDTH - frameWidth) / 2;
  const frameY = FRAME_CENTER_Y - frameHeight / 2;
  const panelHeight = frameHeight / panels;
  const states = panelStates(panels, opening);
  const cableOnLeft = cableSide === 'Слева';
  const cableX = cableOnLeft ? frameX : frameX + frameWidth;
  const cableTextX = cableOnLeft ? frameX - 8 : frameX + frameWidth + 8;
  const cableTextAnchor = cableOnLeft ? 'end' : 'start';
  const dimensionY = frameY + frameHeight + 36;
  const dimensionX = frameX + frameWidth + 34;

  return (
    <svg
      viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      role="img"
      aria-label={`ЛИФТ, ${panels} панели, ${opening}, ввод кабеля ${cableSide.toLowerCase()}`}
      data-lift-diagram="room"
      data-lift-panels={panels}
      data-lift-opening={opening}
      data-cable-side={cableSide}
      data-frame-width={frameWidth.toFixed(3)}
      data-frame-height={frameHeight.toFixed(3)}
      style={{ width: '100%', height: 'auto', maxWidth: VIEW_WIDTH, display: 'block', margin: '0 auto' }}
    >
      <text
        x={cableTextX}
        y={48}
        textAnchor={cableTextAnchor}
        fill="#ef4444"
        fontSize="13"
        fontWeight="700"
      >
        ВВОД КАБЕЛЯ {cableSide.toUpperCase()}
      </text>
      <path
        d={`M ${cableTextX} 56 L ${cableX} ${frameY - 15} L ${cableX} ${frameY + 3}`}
        fill="none"
        stroke="#ef4444"
        strokeWidth="1.5"
      />

      <rect
        x={frameX}
        y={frameY}
        width={frameWidth}
        height={frameHeight}
        fill="var(--theme-accent)"
        fillOpacity="0.045"
        stroke="var(--theme-accent)"
        strokeOpacity="0.8"
        strokeWidth="2.5"
      />
      <rect
        x={frameX + 7}
        y={frameY + 7}
        width={Math.max(0, frameWidth - 14)}
        height={Math.max(0, frameHeight - 14)}
        fill="none"
        stroke="var(--theme-accent)"
        strokeOpacity="0.42"
        strokeWidth="1.4"
      />
      <line
        data-lift-profile="top"
        x1={frameX}
        y1={frameY}
        x2={frameX + frameWidth}
        y2={frameY}
        stroke="var(--theme-accent)"
        strokeOpacity="0.9"
        strokeWidth="8"
      />
      <line
        data-lift-profile="bottom"
        x1={frameX}
        y1={frameY + frameHeight}
        x2={frameX + frameWidth}
        y2={frameY + frameHeight}
        stroke="var(--theme-accent)"
        strokeOpacity="0.82"
        strokeWidth="4"
      />

      {Array.from({ length: panels - 1 }, (_, index) => {
        const y = frameY + panelHeight * (index + 1);
        return (
          <line
            key={`separator-${index}`}
            x1={frameX + 7}
            y1={y}
            x2={frameX + frameWidth - 7}
            y2={y}
            stroke="var(--theme-accent)"
            strokeOpacity="0.55"
            strokeWidth="1.5"
          />
        );
      })}

      {states.map((state, index) => {
        const centerX = frameX + frameWidth / 2;
        const centerY = frameY + panelHeight * index + panelHeight / 2;
        if (state === 'fixed') {
          return (
            <text
              key={`panel-${index}`}
              x={centerX}
              y={centerY + 5}
              textAnchor="middle"
              fill="var(--theme-accent)"
              fillOpacity="0.78"
              fontSize={Math.max(11, Math.min(17, panelHeight * 0.18))}
              fontWeight="700"
              data-lift-fixed-panel={index + 1}
            >
              ГЛУХАЯ
            </text>
          );
        }
        return (
          <Arrow
            key={`panel-${index}`}
            x={centerX}
            y={centerY}
            direction={state}
            panel={index + 1}
          />
        );
      })}

      <g stroke="var(--theme-accent)" strokeOpacity="0.45" strokeWidth="1.2">
        <line x1={frameX} y1={dimensionY} x2={frameX + frameWidth} y2={dimensionY} />
        <line x1={frameX} y1={dimensionY - 6} x2={frameX} y2={dimensionY + 6} />
        <line x1={frameX + frameWidth} y1={dimensionY - 6} x2={frameX + frameWidth} y2={dimensionY + 6} />
        <line x1={dimensionX} y1={frameY} x2={dimensionX} y2={frameY + frameHeight} />
        <line x1={dimensionX - 6} y1={frameY} x2={dimensionX + 6} y2={frameY} />
        <line x1={dimensionX - 6} y1={frameY + frameHeight} x2={dimensionX + 6} y2={frameY + frameHeight} />
      </g>
      <text
        x={frameX + frameWidth / 2}
        y={dimensionY + 22}
        textAnchor="middle"
        fill="var(--theme-accent)"
        fillOpacity="0.62"
        fontSize="14"
        fontWeight="700"
      >
        {Math.round(safeWidth)}
      </text>
      <text
        x={dimensionX + 22}
        y={frameY + frameHeight / 2}
        textAnchor="middle"
        dominantBaseline="middle"
        transform={`rotate(90 ${dimensionX + 22} ${frameY + frameHeight / 2})`}
        fill="var(--theme-accent)"
        fillOpacity="0.62"
        fontSize="14"
        fontWeight="700"
      >
        {Math.round(safeHeight)}
      </text>
    </svg>
  );
}
