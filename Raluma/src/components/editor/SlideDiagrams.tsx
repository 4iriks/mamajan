import React from 'react';
import { SlideCalcPreview } from '../../api/projects';
import { Section } from './types';

// ── SVG Схема сверху (СЛАЙД) ──────────────────────────────────────────────────

function expandGlassWidths(calc: SlideCalcPreview | null | undefined, panels: number, fallbackWidth: number) {
  if (!calc?.glass?.length || panels <= 0) {
    return Array.from({ length: Math.max(panels, 1) }, () => Math.round(fallbackWidth / Math.max(panels, 1)));
  }

  const findWidth = (needle: string) => {
    const item = calc.glass.find(glass => glass.qty > 0 && glass.position.toLowerCase().includes(needle));
    return item?.width_mm;
  };

  const edge = findWidth('крайн');
  const left = findWidth('лев');
  const right = findWidth('прав');
  const middle = findWidth('промеж') ?? edge ?? left ?? right ?? fallbackWidth / panels;

  if (panels === 1) return [Math.round(middle)];

  const widths = Array.from({ length: panels }, (_, index) => {
    if (index === 0) return left ?? edge ?? middle;
    if (index === panels - 1) return right ?? edge ?? middle;
    return middle;
  });

  return widths.map(width => Math.round(width));
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

function getSideProfileStack(section: Section, side: 'left' | 'right') {
  const prefix = side === 'left' ? 'profileLeft' : 'profileRight';
  const flags = {
    lockBar: section[`${prefix}LockBar` as keyof Section],
    pBar: section[`${prefix}PBar` as keyof Section],
    handleBar: section[`${prefix}HandleBar` as keyof Section],
    bubble: section[`${prefix}Bubble` as keyof Section],
  };

  const articles: string[] = [];
  if (flags.lockBar) articles.push('RS2081');
  if (flags.pBar) articles.push('RS1082');
  if (flags.handleBar) articles.push('RS112');
  if (flags.bubble) articles.push('RS1002');

  return articles;
}

export function SlideSchemeSVG({ section, calc }: { section: Section; calc?: SlideCalcPreview | null }) {
  const {
    panels, rails = 3, firstPanelInside = 'Справа', unusedTrack,
    width: sectionWidth,
  } = section;
  const railCount = rails as number;

  const rowH   = 34;
  const topPad = 28;
  const botPad = 42;
  const leftW  = 58;
  const rightW = 58;
  const railAreaW = 380;
  const svgW = leftW + railAreaW + rightW;
  const svgH = topPad + railCount * rowH + botPad;

  const effectiveUnusedTrack = unusedTrack ?? (panels < railCount ? 'Внутренний' : undefined);
  const unusedCount = Math.max(0, railCount - panels);
  const unusedRailSet = new Set<number>(
    effectiveUnusedTrack === 'Внешний'
      ? Array.from({ length: unusedCount }, (_, i) => i)
      : effectiveUnusedTrack === 'Внутренний'
        ? Array.from({ length: unusedCount }, (_, i) => railCount - 1 - i)
        : []
  );

  const availableRails = Array.from({ length: railCount }, (_, i) => i)
    .filter(i => !unusedRailSet.has(i));

  const mirrorRails = firstPanelInside === 'Слева';
  const panelRailMap = Array.from({ length: panels }, (_, pi) => {
    const railIdx = mirrorRails ? (availableRails.length - 1 - pi) : pi;
    return availableRails[railIdx] ?? availableRails[railIdx % Math.max(availableRails.length, 1)] ?? pi % railCount;
  });

  const panelWidthsMm = expandGlassWidths(calc, panels, sectionWidth || railAreaW);
  const panelLayout = buildPanelLayout(panelWidthsMm, leftW, railAreaW);
  const slideLeft = firstPanelInside === 'Справа';

  const scaleBaseMm = Math.max(sectionWidth || panelWidthsMm.reduce((sum, width) => sum + width, 0), 1);
  const mmToPx = (mm: number, minPx = 0) => Math.max(minPx, (mm / scaleBaseMm) * railAreaW);
  const wallProfileMm = findProfileDimension(calc, rails === 5 ? ['RS2335'] : ['RS2333'], 'section_height_mm', 16);
  const wallProfilePx = mmToPx(wallProfileMm, 5);
  const sideTopY = topPad - 4;
  const sideBottomY = topPad + railCount * rowH + 4;
  const sideHeight = sideBottomY - sideTopY;
  const leftSideArticles = getSideProfileStack(section, 'left');
  const rightSideArticles = getSideProfileStack(section, 'right');
  const sideProfileWidthMm = (articles: string[]) => Math.max(
    ...articles.map(article => {
      if (article === 'RS2081') return findProfileDimension(calc, ['RS2081'], 'section_width_mm', 57);
      if (article === 'RS112') return findProfileDimension(calc, ['RS112'], 'section_width_mm', 52);
      if (article === 'RS1082') return findProfileDimension(calc, ['RS1082'], 'section_width_mm', 25);
      return 3;
    }),
    0,
  );
  const interGlassIsAluminum = (section.interGlassProfile ?? '').includes('RS2061');
  const interGlassPx = mmToPx(findProfileDimension(calc, ['RS2061'], 'section_width_mm', 20), 6);
  const interGlassDir = firstPanelInside === 'Справа' ? -1 : 1;

  const renderSideStack = (side: 'left' | 'right', articles: string[]) => {
    if (!articles.length) return null;
    const widthPx = mmToPx(sideProfileWidthMm(articles), 7);
    const x = side === 'left' ? leftW - widthPx - 8 : leftW + railAreaW + 8;
    const textX = x + widthPx / 2;
    const label = articles.join('/');

    return (
      <g>
        <rect
          x={x}
          y={sideTopY}
          width={widthPx}
          height={sideHeight}
          rx="2"
          fill="var(--theme-accent)"
          fillOpacity="0.11"
          stroke="var(--theme-accent)"
          strokeWidth="1"
          strokeOpacity="0.5"
        />
        <text
          x={textX}
          y={sideTopY + sideHeight / 2}
          textAnchor="middle"
          fontSize="7"
          fill="var(--theme-accent)"
          fillOpacity="0.65"
          fontWeight="bold"
          transform={`rotate(-90,${textX},${sideTopY + sideHeight / 2})`}
        >
          {label}
        </text>
      </g>
    );
  };

  const renderInterGlassProfile = (x: number, y: number, index: number) => {
    const h = 20;
    const top = y - h / 2;
    const bottom = y + h / 2;
    const innerX = x + interGlassDir * interGlassPx;

    return (
      <g key={`inter-${index}`}>
        <path
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

  return (
    <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} className="w-full drop-shadow-[0_0_15px_rgba(79,209,197,0.08)]" style={{ maxWidth: svgW }}>

      {/* Labels: УЛИЦА (top) / ПОМЕЩЕНИЕ (bottom) */}
      <text x={leftW + railAreaW / 2} y={12} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.45" fontWeight="bold" letterSpacing="1.5">УЛИЦА</text>
      <text x={leftW + railAreaW / 2} y={topPad + railCount * rowH + 14} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.45" fontWeight="bold" letterSpacing="1.5">ПОМЕЩЕНИЕ</text>

      {/* Boundary lines (top + bottom of opening) */}
      <line x1={leftW} y1={topPad - 2} x2={leftW + railAreaW} y2={topPad - 2} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />
      <line x1={leftW} y1={topPad + railCount * rowH + 2} x2={leftW + railAreaW} y2={topPad + railCount * rowH + 2} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />

      {/* Vertical boundary lines */}
      <line x1={leftW} y1={topPad - 4} x2={leftW} y2={topPad + railCount * rowH + 4} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.5" />
      <line x1={leftW + railAreaW} y1={topPad - 4} x2={leftW + railAreaW} y2={topPad + railCount * rowH + 4} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.5" />

      {renderSideStack('left', leftSideArticles)}
      {renderSideStack('right', rightSideArticles)}

      {section.profileLeftWall && (
        <g>
          <rect
            x={leftW}
            y={sideTopY}
            width={wallProfilePx}
            height={sideHeight}
            fill="var(--theme-accent)"
            fillOpacity="0.12"
            stroke="var(--theme-accent)"
            strokeWidth="0.9"
            strokeOpacity="0.5"
          />
          <text x={leftW + wallProfilePx / 2} y={sideTopY + 12} textAnchor="middle" fontSize="7" fill="var(--theme-accent)" fillOpacity="0.65" fontWeight="bold">16</text>
        </g>
      )}
      {section.profileRightWall && (
        <g>
          <rect
            x={leftW + railAreaW - wallProfilePx}
            y={sideTopY}
            width={wallProfilePx}
            height={sideHeight}
            fill="var(--theme-accent)"
            fillOpacity="0.12"
            stroke="var(--theme-accent)"
            strokeWidth="0.9"
            strokeOpacity="0.5"
          />
          <text x={leftW + railAreaW - wallProfilePx / 2} y={sideTopY + 12} textAnchor="middle" fontSize="7" fill="var(--theme-accent)" fillOpacity="0.65" fontWeight="bold">16</text>
        </g>
      )}

      {/* Rails */}
      {Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        const isUnused = unusedRailSet.has(ri);
        return (
          <line key={ri}
            x1={leftW} y1={cy} x2={leftW + railAreaW} y2={cy}
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
        const panelNum = firstPanelInside === 'Справа' ? panels - pi : pi + 1;
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

      {interGlassIsAluminum && panelLayout.slice(0, -1).map((layout, pi) => {
        const ri = panelRailMap[pi];
        const cy = topPad + ri * rowH + rowH / 2;
        return renderInterGlassProfile(layout.x + layout.width, cy, pi);
      })}

      {/* Direction arrow — bigger + "сдвиг" label */}
      {(() => {
        const ay = topPad + railCount * rowH + 22;
        const ax = leftW + railAreaW / 2;
        const aLen = 130;
        const arrowHead = 10;
        const labelX = slideLeft ? ax - aLen / 2 - 6 : ax + aLen / 2 + 6;
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
  const firstRight = (section.firstPanelInside ?? 'Справа') === 'Справа';
  const W  = section.width;
  const Hh = section.height;

  const handleLeft = section.handleLeft || 'Без';
  const handleRight = section.handleRight || 'Без';
  const lockLeft = section.lockLeft || 'Без';
  const lockRight = section.lockRight || 'Без';
  const floorLatchLeft = section.floorLatchesLeft;
  const floorLatchRight = section.floorLatchesRight;

  const leftIsDeaf = (handleLeft === 'Без' || handleLeft.toLowerCase().includes('глухая'))
    && lockLeft === 'Без' && !section.profileLeftHandleBar;
  const rightIsDeaf = (handleRight === 'Без' || handleRight.toLowerCase().includes('глухая'))
    && lockRight === 'Без' && !section.profileRightHandleBar;

  const vbW = 540, vbH = 330;
  const fX = 50, fY = 35, fW = 400, fH = 210;
  const pt = 10;

  const iX = fX + pt, iY = fY + pt;
  const iW = fW - 2 * pt, iH = fH - 2 * pt;
  const panelWidthsMm = expandGlassWidths(calc, panels, W);
  const panelLayout = buildPanelLayout(panelWidthsMm, iX, iW);
  const arrowLeft = firstRight;

  // Left side = i=0, Right side = i=panels-1 (visual position, not panel number)
  const leftPanelIdx = 0;
  const rightPanelIdx = panels - 1;

  // Lock symbols stay at frame edges; handles shift inward onto door panel
  const lockLeftX = fX + 5;
  const lockRightX = fX + fW - 5;
  const handleLeftX = iX + 20;
  const handleRightX = iX + iW - 20;
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

      <rect x={fX} y={fY} width={fW} height={pt} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX} y={fY + fH - pt} width={fW} height={pt} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX} y={fY} width={pt} height={fH} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX + fW - pt} y={fY} width={pt} height={fH} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX} y={fY} width={fW} height={fH} fill="none" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />

      {Array.from({ length: panels }).map((_, i) => {
        const layout = panelLayout[i];
        const px = layout.x;
        const pW = layout.width;
        const cx = px + pW / 2;
        const cy = iY + iH / 2;
        const num = firstRight ? panels - i : i + 1;
        const aLen = Math.min(22, pW * 0.45);
        const isLeftPanel = i === leftPanelIdx;
        const isRightPanel = i === rightPanelIdx;
        const isDeaf = (isLeftPanel && leftIsDeaf) || (isRightPanel && rightIsDeaf);

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
                  x1={arrowLeft ? cx + aLen / 2 : cx - aLen / 2}
                  y1={cy + 5}
                  x2={arrowLeft ? cx - aLen / 2 : cx + aLen / 2}
                  y2={cy + 5}
                  stroke="var(--theme-accent)" strokeWidth="1.3" strokeOpacity="0.55"
                />
                {arrowLeft ? (
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

            {/* Floor latches — small squares at bottom edge */}
            {isLeftPanel && floorLatchLeft && (
              <rect x={iX + 8} y={iY + iH - 2} width={8} height={8} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />
            )}
            {isRightPanel && floorLatchRight && (
              <rect x={iX + iW - 16} y={iY + iH - 2} width={8} height={8} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />
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
            <text x={cx} y={dy + 12} textAnchor="middle" fontSize="9" fill="var(--theme-accent)" fillOpacity="0.45">{panelWmm}</text>
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
