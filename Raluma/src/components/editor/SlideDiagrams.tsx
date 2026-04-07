import React from 'react';
import { Section } from './types';

// ── SVG Схема сверху (СЛАЙД) ──────────────────────────────────────────────────

export function SlideSchemeSVG({ section }: { section: Section }) {
  const {
    panels, rails = 3, firstPanelInside = 'Справа', unusedTrack, interGlassProfile,
    profileLeftWall, profileLeftLockBar, profileLeftPBar, profileLeftHandleBar, profileLeftBubble,
    profileRightWall, profileRightLockBar, profileRightPBar, profileRightHandleBar, profileRightBubble,
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

  const panelW = railAreaW / panels;
  const slideLeft = firstPanelInside === 'Справа';
  const glassW = sectionWidth ? Math.round(sectionWidth / panels) : null;

  // Simple vertical lines for left/right profiles (no detailed cross-section symbols)
  const drawLeftProfiles = () => {
    const y1 = topPad;
    const h = railCount * rowH;
    const shapes: React.ReactElement[] = [];
    let x = leftW - 4;
    const profiles = [profileLeftWall, profileLeftLockBar, profileLeftPBar, profileLeftHandleBar, profileLeftBubble];
    profiles.forEach((p, i) => {
      if (p) {
        shapes.push(<line key={`lp${i}`} x1={x - 3} y1={y1} x2={x - 3} y2={y1 + h} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.6" />);
        x -= 8;
      }
    });
    return shapes;
  };

  const drawRightProfiles = () => {
    const y1 = topPad;
    const h = railCount * rowH;
    const shapes: React.ReactElement[] = [];
    let x = leftW + railAreaW + 4;
    const profiles = [profileRightWall, profileRightLockBar, profileRightPBar, profileRightHandleBar, profileRightBubble];
    profiles.forEach((p, i) => {
      if (p) {
        shapes.push(<line key={`rp${i}`} x1={x + 3} y1={y1} x2={x + 3} y2={y1 + h} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.6" />);
        x += 8;
      }
    });
    return shapes;
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
        const px = leftW + pi * panelW;
        const panelNum = firstPanelInside === 'Справа' ? panels - pi : pi + 1;
        const rx = px + (pi === 0 ? 5 : -6);
        const rRight = px + panelW + (pi === panels - 1 ? -5 : 6);
        const rw = rRight - rx;
        const cx = px + panelW / 2;
        return (
          <g key={pi}>
            <rect x={rx} y={cy - 9} width={rw} height={18} rx="2"
              fill="var(--theme-accent)" fillOpacity="0.13" stroke="var(--theme-accent)" strokeWidth="1.4" strokeOpacity="0.75" />
            {glassW ? (
              <text x={cx} y={cy + 5} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.9" fontWeight="bold">{glassW} · №{panelNum}</text>
            ) : (
              <text x={cx} y={cy + 5} textAnchor="middle" fontSize="9" fill="var(--theme-accent)" fillOpacity="0.9" fontWeight="bold">{panelNum}</text>
            )}
          </g>
        );
      })}

      {/* Inter-glass profile */}
      {interGlassProfile && Array.from({ length: panels - 1 }, (_, pi) => (
        <rect key={pi}
          x={leftW + (pi + 1) * panelW - 2} y={topPad}
          width={4} height={railCount * rowH}
          fill="var(--theme-accent)" fillOpacity="0.15" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.55" />
      ))}

      <g>{drawLeftProfiles()}</g>
      <g>{drawRightProfiles()}</g>

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

export function SlideRoomViewSVG({ section }: { section: Section }) {
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
  const pW = iW / panels;

  const panelWmm = Math.round(W / panels);
  const arrowLeft = firstRight;

  // Determine which panel index is leftmost/rightmost
  const leftPanelIdx = firstRight ? panels - 1 : 0;
  const rightPanelIdx = firstRight ? 0 : panels - 1;

  const renderHandleSymbol = (handle: string, side: 'left' | 'right', px: number) => {
    const symX = side === 'left' ? px - 10 : px + pW + 10;
    const symY = iY + iH / 2;
    const h = handle.toLowerCase();

    if (h.includes('кноб') || h.includes('rs3014')) {
      // Circle for knob
      return <circle cx={symX} cy={symY} r={6} fill="var(--theme-accent)" fillOpacity="0.6" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />;
    }
    if (h.includes('скоба')) {
      // Vertical line for bracket handle
      return <line x1={symX} y1={symY - 18} x2={symX} y2={symY + 18} stroke="var(--theme-accent)" strokeWidth="3" strokeOpacity="0.7" />;
    }
    if (h.includes('стеклян') || h.includes('rs3017')) {
      // Square for glass handle
      return <rect x={symX - 5} y={symY - 5} width={10} height={10} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />;
    }
    return null;
  };

  const renderLockSymbol = (lock: string, side: 'left' | 'right', px: number) => {
    const symX = side === 'left' ? px - 10 : px + pW + 10;
    const symY = iY + iH / 2;
    const l = lock.toLowerCase();

    if (l.includes('1стор') || l.includes('1-сторон')) {
      // Small bar for 1-sided lock
      return <line x1={symX} y1={symY - 12} x2={symX} y2={symY + 12} stroke="var(--theme-accent)" strokeWidth="2.5" strokeOpacity="0.7" />;
    }
    if (l.includes('2стор') || l.includes('2-сторон') || l.includes('ключ')) {
      // Bar + key symbol for 2-sided lock
      return (
        <g>
          <line x1={symX} y1={symY - 12} x2={symX} y2={symY + 12} stroke="var(--theme-accent)" strokeWidth="2.5" strokeOpacity="0.7" />
          <circle cx={symX} cy={symY - 16} r={3} fill="none" stroke="var(--theme-accent)" strokeWidth="1.2" strokeOpacity="0.7" />
          <line x1={symX} y1={symY - 13} x2={symX} y2={symY - 6} stroke="var(--theme-accent)" strokeWidth="1.2" strokeOpacity="0.7" />
          <line x1={symX} y1={symY - 8} x2={symX + 2} y2={symY - 8} stroke="var(--theme-accent)" strokeWidth="1.2" strokeOpacity="0.7" />
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
        const px = iX + i * pW;
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
                <line x1={px + 8} y1={iY + 8} x2={px + pW - 8} y2={iY + iH - 8} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.4" />
                <line x1={px + pW - 8} y1={iY + 8} x2={px + 8} y2={iY + iH - 8} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.4" />
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

            {/* Handle symbols on left panel */}
            {isLeftPanel && renderHandleSymbol(handleLeft, 'left', px)}
            {isLeftPanel && renderLockSymbol(lockLeft, 'left', px)}

            {/* Handle symbols on right panel */}
            {isRightPanel && renderHandleSymbol(handleRight, 'right', px)}
            {isRightPanel && renderLockSymbol(lockRight, 'right', px)}

            {/* Floor latches — small squares at bottom */}
            {isLeftPanel && floorLatchLeft && (
              <rect x={px + 4} y={iY + iH - 8} width={8} height={8} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />
            )}
            {isRightPanel && floorLatchRight && (
              <rect x={px + pW - 12} y={iY + iH - 8} width={8} height={8} fill="var(--theme-accent)" fillOpacity="0.5" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />
            )}
          </g>
        );
      })}

      {Array.from({ length: panels }).map((_, i) => {
        const dx1 = iX + i * pW;
        const dx2 = iX + (i + 1) * pW;
        const dy  = fY + fH + 18;
        const cx  = (dx1 + dx2) / 2;
        return (
          <g key={i}>
            <line x1={dx1 + 3} y1={dy} x2={dx2 - 3} y2={dy} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.35" />
            <line x1={dx1 + 3} y1={dy - 4} x2={dx1 + 3} y2={dy + 4} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.35" />
            <line x1={dx2 - 3} y1={dy - 4} x2={dx2 - 3} y2={dy + 4} stroke="var(--theme-accent)" strokeWidth="0.8" strokeOpacity="0.35" />
            <text x={cx} y={dy + 12} textAnchor="middle" fontSize="9" fill="var(--theme-accent)" fillOpacity="0.45">{panelWmm}</text>
          </g>
        );
      })}

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
