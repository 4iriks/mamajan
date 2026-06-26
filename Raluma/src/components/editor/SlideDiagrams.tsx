import React from 'react';
import { SlideCalcPreview } from '../../api/projects';
import { Section } from './types';

// ── SVG Схема сверху (СЛАЙД) ──────────────────────────────────────────────────

function expandGlassWidths(calc: SlideCalcPreview | null | undefined, panels: number, fallbackWidth: number) {
  if (!calc?.glass?.length || panels <= 0) {
    return Array.from({ length: Math.max(panels, 1) }, () => Math.ceil(fallbackWidth / Math.max(panels, 1)));
  }

  const findWidth = (needle: string) => {
    const item = calc.glass.find(glass => glass.qty > 0 && glass.position.toLowerCase().includes(needle));
    return item?.width_mm;
  };

  const edge = findWidth('крайн');
  const left = findWidth('лев');
  const right = findWidth('прав');
  const center = findWidth('централь');
  const middle = findWidth('промеж') ?? edge ?? left ?? right ?? fallbackWidth / panels;

  if (panels === 1) return [Math.ceil(middle)];
  if (center && panels >= 4) {
    const sideMiddleCount = Math.floor(Math.max(panels - 4, 0) / 2);
    const widths = [
      left ?? middle,
      ...Array.from({ length: sideMiddleCount }, () => middle),
      center,
      center,
      ...Array.from({ length: sideMiddleCount }, () => middle),
      right ?? middle,
    ];
    return widths.slice(0, panels).map(width => Math.ceil(width));
  }

  const widths = Array.from({ length: panels }, (_, index) => {
    if (index === 0) return left ?? edge ?? middle;
    if (index === panels - 1) return right ?? edge ?? middle;
    return middle;
  });

  return widths.map(width => Math.ceil(width));
}

function buildPanelLayout(widthsMm: number[], startPx: number, totalPx: number) {
  const totalMm = widthsMm.reduce((sum, width) => sum + Math.max(width, 0), 0) || 1;
  let cursor = startPx;
  return widthsMm.map(widthMm => {
    const widthPx = Math.max(1, (Math.max(widthMm, 0) / totalMm) * totalPx);
    const item = { x: cursor, width: widthPx, widthMm };
    cursor += widthPx;
    return item;
  });
}

function findProfileDimension(
  calc: SlideCalcPreview | null | undefined,
  articles: string[],
  key: 'section_width_mm' | 'section_height_mm',
  fallback: number,
) {
  const found = calc?.profiles?.find(profile => articles.includes(profile.article));
  const value = found?.[key];
  return typeof value === 'number' && value > 0 ? value : fallback;
}

type SideAssemblyVariant = 'lock-handle' | 'p-handle' | 'p-bubble';

function sideAssemblyBaseWidth(variant: SideAssemblyVariant | null) {
  if (variant === 'lock-handle') return 100;
  if (variant === 'p-handle') return 82;
  if (variant === 'p-bubble') return 56;
  return 0;
}

function sideAssemblyVariant(
  lockBar: boolean,
  pBar: boolean,
  handleBar: boolean,
  bubble: boolean,
): SideAssemblyVariant | null {
  if (lockBar && handleBar) return 'lock-handle';
  if (pBar && handleBar) return 'p-handle';
  if (pBar && bubble) return 'p-bubble';
  return null;
}

export function SlideSchemeSVG({ section, calc }: { section: Section; calc?: SlideCalcPreview | null }) {
  const {
    panels, rails = 3, firstPanelInside = 'Справа', unusedTrack,
    width: sectionWidth,
  } = section;
  const is2row = (section.slideRows ?? 1) === 2;
  const railCount = rails as number;

  const rowH   = 34;
  const topPad = 28;
  const botPad = 42;
  const leftW  = 118;
  const rightW = 118;
  const railAreaW = 380;
  const svgW = leftW + railAreaW + rightW;
  const svgH = topPad + railCount * rowH + botPad;

  const effectiveUnusedTrack = unusedTrack ?? (is2row ? 'Внешний' : (panels < railCount ? 'Внутренний' : undefined));
  const activeRails2row = Math.min(railCount, Math.max(1, Math.ceil(panels / 2)));
  const unusedCount = Math.max(0, railCount - (is2row ? activeRails2row : panels));
  const unusedRailSet = new Set<number>(
    effectiveUnusedTrack === 'Внешний'
      ? Array.from({ length: unusedCount }, (_, i) => i)
      : effectiveUnusedTrack === 'Внутренний'
        ? Array.from({ length: unusedCount }, (_, i) => railCount - 1 - i)
        : []
  );

  const availableRails = Array.from({ length: railCount }, (_, i) => i)
    .filter(i => !unusedRailSet.has(i));

  const mirrorRails = !is2row && firstPanelInside === 'Слева';
  const panelRailMap = Array.from({ length: panels }, (_, pi) => {
    const calcRail = calc?.panel_rails?.[pi];
    if (typeof calcRail === 'number') return calcRail;
    const railIdx = mirrorRails ? (availableRails.length - 1 - pi) : pi;
    return availableRails[railIdx] ?? availableRails[railIdx % Math.max(availableRails.length, 1)] ?? pi % railCount;
  });

  const panelWidthsMm = expandGlassWidths(calc, panels, sectionWidth || railAreaW);
  const panelLayout = buildPanelLayout(panelWidthsMm, leftW, railAreaW);
  const slideLeft = firstPanelInside === 'Справа';

  const scaleBaseMm = Math.max(sectionWidth || panelWidthsMm.reduce((sum, width) => sum + width, 0), 1);
  const mmToPx = (mm: number, minPx = 0) => Math.max(minPx, (mm / scaleBaseMm) * railAreaW);
  const interGlassText = (section.interGlassProfile ?? '').toLowerCase();
  const hasInterGlassProfile = Boolean(interGlassText) && !interGlassText.includes('без');
  const interGlassArticle = interGlassText.includes('rs1006')
    ? 'RS1006'
    : interGlassText.includes('rs3061') || interGlassText.includes('rs1004') || interGlassText.includes('зацеп')
      ? 'RS3061'
      : 'RS2061';
  const interGlassPx = mmToPx(findProfileDimension(calc, [interGlassArticle], 'section_width_mm', 20), 6);
  const leftSideVariant = sideAssemblyVariant(
    section.profileLeftLockBar,
    section.profileLeftPBar,
    section.profileLeftHandleBar,
    section.profileLeftBubble,
  );
  const rightSideVariant = sideAssemblyVariant(
    section.profileRightLockBar,
    section.profileRightPBar,
    section.profileRightHandleBar,
    section.profileRightBubble,
  );
  const sideAssemblyScale = 0.9;
  const sideAssemblyOverlap = 16;
  const leftAssemblyVisualWidth = sideAssemblyBaseWidth(leftSideVariant) * sideAssemblyScale;
  const rightAssemblyVisualWidth = sideAssemblyBaseWidth(rightSideVariant) * sideAssemblyScale;
  const schemeLeftX = leftSideVariant ? leftW - leftAssemblyVisualWidth + sideAssemblyOverlap - 4 : leftW;
  const schemeRightX = rightSideVariant ? leftW + railAreaW + rightAssemblyVisualWidth - sideAssemblyOverlap + 4 : leftW + railAreaW;

  const renderInterGlassProfile = (x: number, y: number, index: number, dir: number) => {
    const h = 20;
    const top = y - h / 2;
    const bottom = y + h / 2;
    const innerX = x + dir * interGlassPx;

    return (
      <g key={`inter-${index}`}>
        <path
          data-profile="inter-glass"
          data-dir={dir}
          d={`M ${innerX} ${top} L ${x} ${top} L ${x} ${bottom} L ${innerX} ${bottom}`}
          fill="none"
          stroke="var(--theme-accent)"
          strokeWidth="1.6"
          strokeOpacity="0.72"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <line
          x1={x}
          y1={top + 4}
          x2={innerX}
          y2={top + 4}
          stroke="var(--theme-accent)"
          strokeWidth="0.9"
          strokeOpacity="0.45"
        />
      </g>
    );
  };

  const renderSideAssembly = (
    side: 'left' | 'right',
    variant: SideAssemblyVariant | null,
    _hasWall: boolean,
    railIndex: number,
  ) => {
    if (!variant) return null;

    const cy = topPad + railIndex * rowH + rowH / 2;
    const visualWidth = sideAssemblyBaseWidth(variant) * sideAssemblyScale;
    const x = side === 'left'
      ? leftW - visualWidth + sideAssemblyOverlap
      : leftW + railAreaW + visualWidth - sideAssemblyOverlap;
    const transform = side === 'right'
      ? `translate(${x} ${cy}) scale(-${sideAssemblyScale} ${sideAssemblyScale})`
      : `translate(${x} ${cy}) scale(${sideAssemblyScale})`;
    const stroke = 'var(--theme-accent)';
    const profileFill = 'var(--theme-page)';

    const renderHandleProfile = (offsetX: number) => (
      <g>
        <line x1={offsetX + 12} y1={-22} x2={offsetX + 12} y2={22} stroke={stroke} strokeWidth="2" strokeOpacity="0.72" />
        <line x1={offsetX + 5} y1={-22} x2={offsetX + 19} y2={-22} stroke={stroke} strokeWidth="2" strokeOpacity="0.72" strokeLinecap="round" />
        <line x1={offsetX + 5} y1={22} x2={offsetX + 19} y2={22} stroke={stroke} strokeWidth="2" strokeOpacity="0.72" strokeLinecap="round" />
        <line x1={offsetX + 2} y1={-4} x2={offsetX + 34} y2={-4} stroke={stroke} strokeWidth="1.8" strokeOpacity="0.56" />
        <line x1={offsetX + 2} y1={4} x2={offsetX + 34} y2={4} stroke={stroke} strokeWidth="1.8" strokeOpacity="0.56" />
      </g>
    );

    if (variant === 'lock-handle') {
      return (
        <g key={`${side}-side-assembly`} transform={transform} data-side-assembly={variant}>
          <rect x={1} y={-12} width={32} height={24} fill={profileFill} fillOpacity="0.68" stroke={stroke} strokeWidth="1.7" strokeOpacity="0.74" />
          <line x1={3} y1={-8} x2={8} y2={-8} stroke={stroke} strokeWidth="1" strokeOpacity="0.38" />
          <line x1={3} y1={8} x2={8} y2={8} stroke={stroke} strokeWidth="1" strokeOpacity="0.38" />
          <path d="M 33 -10 H 55 V -4 H 43 V 4 H 55 V 10 H 33 Z" fill={profileFill} fillOpacity="0.72" stroke={stroke} strokeWidth="1.7" strokeOpacity="0.74" strokeLinejoin="round" />
          <path d="M 42 -7 C 35 -3 35 3 42 7" fill="none" stroke={stroke} strokeWidth="1.45" strokeOpacity="0.58" strokeLinecap="round" />
          <path d="M 53 -5 H 69 M 53 5 H 69 M 61 -5 V 5" fill="none" stroke={stroke} strokeWidth="1.35" strokeOpacity="0.62" strokeLinecap="round" />
          <path d="M 69 -5 H 84 V -1 H 76 V 1 H 84 V 5 H 69" fill="none" stroke={stroke} strokeWidth="1.45" strokeOpacity="0.74" strokeLinejoin="round" />
          {renderHandleProfile(66)}
        </g>
      );
    }

    if (variant === 'p-handle') {
      return (
        <g key={`${side}-side-assembly`} transform={transform} data-side-assembly={variant}>
          <path d="M 2 -13 H 34 V -7 H 13 V 7 H 34 V 13 H 2 Z" fill={profileFill} fillOpacity="0.72" stroke={stroke} strokeWidth="1.7" strokeOpacity="0.74" strokeLinejoin="round" />
          <path d="M 8 -8 C 17 -4 17 4 8 8" fill="none" stroke={stroke} strokeWidth="1.35" strokeOpacity="0.58" strokeLinecap="round" />
          <path d="M 33 -5 H 50 M 33 5 H 50 M 42 -5 V 5" fill="none" stroke={stroke} strokeWidth="1.35" strokeOpacity="0.62" strokeLinecap="round" />
          {renderHandleProfile(47)}
        </g>
      );
    }

    return (
      <g key={`${side}-side-assembly`} transform={transform} data-side-assembly={variant}>
        <path d="M 2 -13 H 34 V -8 H 12 V 8 H 34 V 13 H 2 Z" fill={profileFill} fillOpacity="0.72" stroke={stroke} strokeWidth="1.7" strokeOpacity="0.74" strokeLinejoin="round" />
        <path d="M 16 -8 C 4 -5 4 5 16 8" fill="none" stroke={stroke} strokeWidth="1.7" strokeOpacity="0.62" strokeLinecap="round" />
        <line x1={18} y1={-7} x2={18} y2={7} stroke={stroke} strokeWidth="1.1" strokeOpacity="0.4" />
        <path d="M 31 -5 H 54 M 31 5 H 54" fill="none" stroke={stroke} strokeWidth="1.35" strokeOpacity="0.62" strokeLinecap="round" />
      </g>
    );
  };

  return (
    <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} className="w-full drop-shadow-[0_0_15px_rgba(79,209,197,0.08)]" style={{ maxWidth: svgW }}>

      {/* Labels: УЛИЦА (top) / ПОМЕЩЕНИЕ (bottom) */}
      <text x={leftW + railAreaW / 2} y={12} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.45" fontWeight="bold" letterSpacing="1.5">УЛИЦА</text>
      <text x={leftW + railAreaW / 2} y={topPad + railCount * rowH + 14} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.45" fontWeight="bold" letterSpacing="1.5">ПОМЕЩЕНИЕ</text>

      {/* Boundary lines (top + bottom of opening) */}
      <line x1={schemeLeftX} y1={topPad - 2} x2={schemeRightX} y2={topPad - 2} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />
      <line x1={schemeLeftX} y1={topPad + railCount * rowH + 2} x2={schemeRightX} y2={topPad + railCount * rowH + 2} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />

      {/* Vertical boundary lines */}
      <line x1={schemeLeftX} y1={topPad - 4} x2={schemeLeftX} y2={topPad + railCount * rowH + 4} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.5" />
      <line x1={schemeRightX} y1={topPad - 4} x2={schemeRightX} y2={topPad + railCount * rowH + 4} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.5" />

      {/* Rails */}
      {Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        const isUnused = unusedRailSet.has(ri);
        return (
          <line key={ri}
            x1={schemeLeftX} y1={cy} x2={schemeRightX} y2={cy}
            stroke={isUnused ? 'var(--theme-tint)' : 'var(--theme-accent)'}
            strokeWidth={isUnused ? 1 : 1.5}
            strokeOpacity={isUnused ? 0.22 : 0.55}
            strokeDasharray={isUnused ? '5 5' : undefined}
          />
        );
      })}

      {/* Panels */}
      {Array.from({ length: panels }, (_, pi) => {
        const ri = panelRailMap[pi];
        const cy = topPad + ri * rowH + rowH / 2;
        const layout = panelLayout[pi];
        const px = layout.x;
        const panelW = layout.width;
        const panelNum = is2row ? pi + 1 : (firstPanelInside === 'Справа' ? panels - pi : pi + 1);
        const rx = px + (pi === 0 ? 5 : -6);
        const rRight = px + panelW + (pi === panels - 1 ? -5 : 6);
        const rw = rRight - rx;
        const cx = px + panelW / 2;
        return (
          <g key={pi}>
            <rect x={rx} y={cy - 9} width={rw} height={18} rx="2"
              fill="var(--theme-accent)" fillOpacity="0.13" stroke="var(--theme-accent)" strokeWidth="1.4" strokeOpacity="0.75" />
            {layout.widthMm ? (
              <text x={cx} y={cy + 5} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.9" fontWeight="bold">{layout.widthMm} · №{panelNum}</text>
            ) : (
              <text x={cx} y={cy + 5} textAnchor="middle" fontSize="9" fill="var(--theme-accent)" fillOpacity="0.9" fontWeight="bold">{panelNum}</text>
            )}
          </g>
        );
      })}

      {hasInterGlassProfile && panelLayout.slice(0, -1).map((layout, pi) => {
        const ownerIndex = !is2row && firstPanelInside === 'Справа' ? pi + 1 : pi;
        const ri = panelRailMap[ownerIndex] ?? panelRailMap[pi];
        const cy = topPad + ri * rowH + rowH / 2;
        const dir = is2row ? (pi < panels / 2 ? 1 : -1) : (firstPanelInside === 'Справа' ? 1 : -1);
        return renderInterGlassProfile(layout.x + layout.width, cy, pi, dir);
      })}

      {renderSideAssembly('left', leftSideVariant, section.profileLeftWall, panelRailMap[0] ?? 0)}
      {renderSideAssembly('right', rightSideVariant, section.profileRightWall, panelRailMap[panels - 1] ?? railCount - 1)}

      {/* Direction arrow */}
      {(() => {
        const ay = topPad + railCount * rowH + 22;
        const ax = leftW + railAreaW / 2;
        const aLen = 130;
        const arrowHead = 10;
        const labelX = slideLeft ? ax - aLen / 2 - 6 : ax + aLen / 2 + 6;
        if (is2row) {
          return (
            <g>
              <line x1={ax - aLen / 2} y1={ay} x2={ax + aLen / 2} y2={ay} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.6" />
              <polyline points={`${ax - aLen/2 + arrowHead},${ay - arrowHead/1.5} ${ax - aLen/2},${ay} ${ax - aLen/2 + arrowHead},${ay + arrowHead/1.5}`} stroke="var(--theme-accent)" strokeWidth="2" fill="none" strokeOpacity="0.6" />
              <polyline points={`${ax + aLen/2 - arrowHead},${ay - arrowHead/1.5} ${ax + aLen/2},${ay} ${ax + aLen/2 - arrowHead},${ay + arrowHead/1.5}`} stroke="var(--theme-accent)" strokeWidth="2" fill="none" strokeOpacity="0.6" />
              <text x={ax} y={ay + 14} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.5" fontWeight="bold">сдвиг</text>
            </g>
          );
        }
        return (
          <g>
            <line x1={ax - aLen / 2} y1={ay} x2={ax + aLen / 2} y2={ay} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.6" />
            {slideLeft ? (
              <polyline points={`${ax - aLen/2 + arrowHead},${ay - arrowHead/1.5} ${ax - aLen/2},${ay} ${ax - aLen/2 + arrowHead},${ay + arrowHead/1.5}`} stroke="var(--theme-accent)" strokeWidth="2" fill="none" strokeOpacity="0.6" />
            ) : (
              <polyline points={`${ax + aLen/2 - arrowHead},${ay - arrowHead/1.5} ${ax + aLen/2},${ay} ${ax + aLen/2 - arrowHead},${ay + arrowHead/1.5}`} stroke="var(--theme-accent)" strokeWidth="2" fill="none" strokeOpacity="0.6" />
            )}
            <text x={labelX} y={ay + 4} textAnchor={slideLeft ? 'end' : 'start'} fontSize="8" fill="var(--theme-accent)" fillOpacity="0.5" fontWeight="bold">сдвиг</text>
          </g>
        );
      })()}
    </svg>
  );
}

// ── SVG: Вид из помещения ─────────────────────────────────────────────────────

export function SlideRoomViewSVG({ section, calc }: { section: Section; calc?: SlideCalcPreview | null }) {
  const panels  = section.panels;
  const is2row = (section.slideRows ?? 1) === 2;
  const firstRight = (section.firstPanelInside ?? 'Справа') === 'Справа';
  const rails = section.rails ?? 3;
  const W  = section.width;
  const Hh = section.height;

  const handleLeft = section.handleLeft || 'Без';
  const handleRight = section.handleRight || 'Без';
  const lockLeft = section.lockLeft || 'Без';
  const lockRight = section.lockRight || 'Без';
  const floorLatchLeft = section.floorLatchesLeft;
  const floorLatchRight = section.floorLatchesRight;
  const centerHandle = section.centerHandle || 'Без ручки (глухие)';
  const centerLock = section.centerLock || 'Без';
  const centerIsDeaf = centerHandle === 'Без ручки (глухие)' || centerHandle === '';
  const centerLeftIdx = Math.max(0, Math.floor(panels / 2) - 1);
  const centerRightIdx = Math.min(panels - 1, Math.floor(panels / 2));

  const leftIsDeaf = (handleLeft === 'Без' || handleLeft.toLowerCase().includes('глухая'))
    && lockLeft === 'Без' && !section.profileLeftHandleBar;
  const rightIsDeaf = (handleRight === 'Без' || handleRight.toLowerCase().includes('глухая'))
    && lockRight === 'Без' && !section.profileRightHandleBar;

  const vbW = 540, vbH = 330;
  const maxDrawingW = 400;
  const maxDrawingH = 210;
  const drawingOriginX = 50;
  const drawingOriginY = 35;
  const safeW = Math.max(W, 1);
  const safeH = Math.max(Hh, 1);
  const drawingScale = Math.min(maxDrawingW / safeW, maxDrawingH / safeH);
  const fW = safeW * drawingScale;
  const fH = safeH * drawingScale;
  const fX = drawingOriginX + (maxDrawingW - fW) / 2;
  const fY = drawingOriginY + (maxDrawingH - fH) / 2;

  const topProfileMm = findProfileDimension(calc, rails === 5 ? ['RS1315'] : ['RS1313'], 'section_height_mm', 53);
  const thresholdArticles = rails === 5
    ? ['RS2325', 'RS23251']
    : ['RS2323', 'RS23231'];
  const bottomProfileMm = findProfileDimension(calc, thresholdArticles, 'section_height_mm', 23);
  const sideProfileMm = Math.max(
    section.profileLeftWall || section.profileRightWall
      ? findProfileDimension(calc, rails === 5 ? ['RS2335'] : ['RS2333'], 'section_height_mm', 16)
      : 0,
    16,
  );
  const minProfilePx = 4;
  const topPx = Math.max(minProfilePx, topProfileMm * drawingScale);
  const bottomPx = Math.max(minProfilePx, bottomProfileMm * drawingScale);
  const sidePx = Math.max(minProfilePx, sideProfileMm * drawingScale);

  const iX = fX + sidePx, iY = fY + topPx;
  const iW = Math.max(1, fW - 2 * sidePx);
  const iH = Math.max(1, fH - topPx - bottomPx);
  const panelWidthsMm = expandGlassWidths(calc, panels, W);
  const panelLayout = buildPanelLayout(panelWidthsMm, iX, iW);
  const arrowLeft = firstRight;

  // Left side = i=0, Right side = i=panels-1 (visual position, not panel number)
  const leftPanelIdx = 0;
  const rightPanelIdx = panels - 1;

  // Lock symbols stay at frame edges; handles shift inward onto door panel
  const lockLeftX = fX + 5;
  const lockRightX = fX + fW - 5;
  const handleInset = Math.min(20, Math.max(10, iW * 0.08));
  const handleLeftX = iX + handleInset;
  const handleRightX = iX + iW - handleInset;
  const symY = iY + iH / 2;

  const renderHandleSymbol = (handle: string, x: number) => {
    const h = handle.toLowerCase();
    if (h.includes('кноб') || h.includes('rs3014')) {
      return <circle cx={x} cy={symY} r={6} fill="var(--theme-accent)" fillOpacity="0.6" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />;
    }
    if (h.includes('скоба')) {
      return <line x1={x} y1={symY - 26} x2={x} y2={symY + 26} stroke="var(--theme-accent)" strokeWidth="3" strokeOpacity="0.7" />;
    }
    if (h.includes('стеклян') || h.includes('rs3017')) {
      return <rect x={x - 5} y={symY - 5} width={10} height={10} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />;
    }
    return null;
  };

  const renderLockSymbol = (lock: string, x: number) => {
    const l = lock.toLowerCase();
    if (l.includes('1стор') || l.includes('1-сторон')) {
      return <line x1={x} y1={symY - 12} x2={x} y2={symY + 12} stroke="var(--theme-accent)" strokeWidth="2.5" strokeOpacity="0.7" />;
    }
    if (l.includes('2стор') || l.includes('2-сторон') || l.includes('ключ')) {
      const kx = x + 12;
      return (
        <g>
          <line x1={x} y1={symY - 12} x2={x} y2={symY + 12} stroke="var(--theme-accent)" strokeWidth="2.5" strokeOpacity="0.7" />
          <circle cx={kx} cy={symY - 5} r={5} fill="none" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.8" />
          <line x1={kx} y1={symY} x2={kx} y2={symY + 12} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.8" />
          <line x1={kx} y1={symY + 6} x2={kx + 4} y2={symY + 6} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.8" />
          <line x1={kx} y1={symY + 9} x2={kx + 3} y2={symY + 9} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.8" />
        </g>
      );
    }
    return null;
  };

  return (
    <svg viewBox={`0 0 ${vbW} ${vbH}`} className="w-full" style={{ maxWidth: 540, maxHeight: 330 }}>

      <rect x={fX} y={fY} width={fW} height={topPx} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX} y={fY + fH - bottomPx} width={fW} height={bottomPx} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX} y={fY} width={sidePx} height={fH} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX + fW - sidePx} y={fY} width={sidePx} height={fH} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX} y={fY} width={fW} height={fH} fill="none" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />
      {topPx >= minProfilePx && (
        <text x={fX + fW / 2} y={fY + Math.max(8, topPx / 2 + 3)} textAnchor="middle" fontSize="7" fill="var(--theme-accent)" fillOpacity="0.42">
          {Math.round(topProfileMm)}
        </text>
      )}
      {bottomPx >= minProfilePx && (
        <text x={fX + fW / 2} y={fY + fH - Math.max(3, bottomPx / 2 - 3)} textAnchor="middle" fontSize="7" fill="var(--theme-accent)" fillOpacity="0.42">
          {Math.round(bottomProfileMm)}
        </text>
      )}

      {Array.from({ length: panels }).map((_, i) => {
        const layout = panelLayout[i];
        const px = layout.x;
        const pW = layout.width;
        const cx = px + pW / 2;
        const cy = iY + iH / 2;
        const num = is2row ? i + 1 : (firstRight ? panels - i : i + 1);
        const aLen = Math.min(22, pW * 0.45);
        const isLeftPanel = i === leftPanelIdx;
        const isRightPanel = i === rightPanelIdx;
        const isCenterPanel = is2row && (i === centerLeftIdx || i === centerRightIdx);
        const isDeaf = (isLeftPanel && leftIsDeaf) || (isRightPanel && rightIsDeaf) || (isCenterPanel && centerIsDeaf);
        const panelArrowLeft = is2row ? i < panels / 2 : arrowLeft;

        return (
          <g key={i}>
            <rect x={px} y={iY} width={pW} height={iH} fill="var(--theme-accent)" fillOpacity="0.07" />

            {i < panels - 1 && (
              <rect x={px + pW - 2} y={iY} width={4} height={iH}
                fill="var(--theme-page)" stroke="var(--theme-accent)" strokeWidth="0.4" strokeOpacity="0.25" />
            )}

            {/* Deaf panel — big X */}
            {isDeaf && (
              <g>
                <line x1={px + 15} y1={iY + 15} x2={px + pW - 15} y2={iY + iH - 15} stroke="var(--theme-accent)" strokeWidth="1.2" strokeOpacity="0.35" />
                <line x1={px + pW - 15} y1={iY + 15} x2={px + 15} y2={iY + iH - 15} stroke="var(--theme-accent)" strokeWidth="1.2" strokeOpacity="0.35" />
              </g>
            )}

            <text x={cx} y={cy - 12} textAnchor="middle" fontSize="14"
              fill="var(--theme-accent)" fillOpacity="0.85" fontWeight="bold" fontFamily="monospace">
              {num}
            </text>

            {!isDeaf && (
              <>
                <line
                  x1={panelArrowLeft ? cx + aLen / 2 : cx - aLen / 2}
                  y1={cy + 5}
                  x2={panelArrowLeft ? cx - aLen / 2 : cx + aLen / 2}
                  y2={cy + 5}
                  stroke="var(--theme-accent)" strokeWidth="1.3" strokeOpacity="0.55"
                />
                {panelArrowLeft ? (
                  <polyline
                    points={`${cx - aLen / 2 + 6},${cy + 1} ${cx - aLen / 2},${cy + 5} ${cx - aLen / 2 + 6},${cy + 9}`}
                    stroke="var(--theme-accent)" strokeWidth="1.3" fill="none" strokeOpacity="0.55"
                  />
                ) : (
                  <polyline
                    points={`${cx + aLen / 2 - 6},${cy + 1} ${cx + aLen / 2},${cy + 5} ${cx + aLen / 2 - 6},${cy + 9}`}
                    stroke="var(--theme-accent)" strokeWidth="1.3" fill="none" strokeOpacity="0.55"
                  />
                )}
              </>
            )}
            {isCenterPanel && !centerIsDeaf && renderHandleSymbol(centerHandle, cx)}
            {isCenterPanel && centerLock !== 'Без' && centerLock && (
              <rect x={cx - 5} y={cy + 18} width={10} height={7} rx={1.5} fill="var(--theme-accent)" fillOpacity="0.45" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.75" />
            )}

            {/* Floor latches — small squares at bottom edge */}
            {isLeftPanel && floorLatchLeft && (
              <rect x={iX + 8} y={iY + iH - 2} width={8} height={8} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />
            )}
            {isRightPanel && floorLatchRight && (
              <rect x={iX + iW - 16} y={iY + iH - 2} width={8} height={8} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />
            )}
            {is2row && i === centerLeftIdx && section.centerFloorLatchesLeft && (
              <rect x={px + Math.max(6, pW - 16)} y={iY + iH - 2} width={8} height={8} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />
            )}
            {is2row && i === centerRightIdx && section.centerFloorLatchesRight && (
              <rect x={px + 8} y={iY + iH - 2} width={8} height={8} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />
            )}
          </g>
        );
      })}

      {Array.from({ length: panels }).map((_, i) => {
        const layout = panelLayout[i];
        const dx1 = layout.x;
        const dx2 = layout.x + layout.width;
        const dy  = fY + fH + 18;
        const cx  = (dx1 + dx2) / 2;
        const panelWmm = layout.widthMm;
        return (
          <g key={i}>
            <line x1={dx1 + 3} y1={dy} x2={dx2 - 3} y2={dy} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.35" />
            <line x1={dx1 + 3} y1={dy - 4} x2={dx1 + 3} y2={dy + 4} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.35" />
            <line x1={dx2 - 3} y1={dy - 4} x2={dx2 - 3} y2={dy + 4} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.35" />
            <text x={cx} y={dy + 14} textAnchor="middle" fontSize="14" fontWeight="bold" fill="var(--theme-accent)" fillOpacity="0.55">{panelWmm}</text>
          </g>
        );
      })}

      {/* Handle symbols on door panel, lock symbols at frame edges */}
      {renderHandleSymbol(handleLeft, handleLeftX)}
      {renderLockSymbol(lockLeft, lockLeftX)}
      {renderHandleSymbol(handleRight, handleRightX)}
      {renderLockSymbol(lockRight, lockRightX)}

      <line x1={iX} y1={fY + fH + 38} x2={iX + iW} y2={fY + fH + 38} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.3" />
      <line x1={iX}      y1={fY + fH + 32} x2={iX}      y2={fY + fH + 44} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.3" />
      <line x1={iX + iW} y1={fY + fH + 32} x2={iX + iW} y2={fY + fH + 44} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.3" />
      <text x={iX + iW / 2} y={fY + fH + 52} textAnchor="middle" fontSize="10" fill="var(--theme-accent)" fillOpacity="0.5">{W}</text>

      <line x1={fX + fW + 18} y1={fY} x2={fX + fW + 18} y2={fY + fH} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.3" />
      <line x1={fX + fW + 12} y1={fY}      x2={fX + fW + 24} y2={fY}      stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.3" />
      <line x1={fX + fW + 12} y1={fY + fH} x2={fX + fW + 24} y2={fY + fH} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.3" />
      <text
        x={fX + fW + 34} y={fY + fH / 2}
        textAnchor="middle" fontSize="10" fill="var(--theme-accent)" fillOpacity="0.5"
        transform={`rotate(90,${fX + fW + 34},${fY + fH / 2})`}
      >{Hh}</text>
    </svg>
  );
}
