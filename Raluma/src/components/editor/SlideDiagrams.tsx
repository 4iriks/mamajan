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

  const drawLeftProfiles = () => {
    const y1 = topPad;
    const h = railCount * rowH;
    const shapes: React.ReactElement[] = [];
    let x = leftW - 4;

    if (profileLeftWall) {
      shapes.push(<rect key="lw1" x={x - 14} y={y1} width={7} height={h} rx="1" fill="var(--theme-accent)" fillOpacity="0.45" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />);
      shapes.push(<rect key="lw2" x={x - 7}  y={y1} width={7} height={h} rx="1" fill="var(--theme-accent)" fillOpacity="0.22" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />);
      x -= 16;
    }
    if (profileLeftLockBar) {
      shapes.push(<rect key="ll1" x={x - 12} y={y1} width={4} height={h} rx="1" fill="var(--theme-accent)" fillOpacity="0.40" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />);
      shapes.push(<rect key="ll2" x={x - 5}  y={y1} width={4} height={h} rx="1" fill="var(--theme-accent)" fillOpacity="0.40" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />);
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<line key={`llb${ri}`} x1={x - 10} y1={cy} x2={x - 3} y2={cy} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.7" />);
      });
      x -= 14;
    }
    if (profileLeftPBar) {
      shapes.push(<path key="lp" d={`M${x-12},${y1} L${x-2},${y1} L${x-2},${y1+h} L${x-12},${y1+h}`} fill="none" stroke="var(--theme-accent)" strokeWidth="2.5" strokeOpacity="0.85" />);
      x -= 14;
    }
    if (profileLeftHandleBar) {
      shapes.push(<line key="lhv" x1={x-8} y1={y1} x2={x-8} y2={y1+h} stroke="var(--theme-accent)" strokeWidth="2.5" strokeOpacity="0.85" />);
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<line key={`lhh${ri}`} x1={x-14} y1={cy} x2={x-2} y2={cy} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.65" />);
      });
      x -= 16;
    }
    if (profileLeftBubble) {
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<circle key={`lb${ri}`} cx={x-7} cy={cy} r={5} fill="var(--theme-accent)" fillOpacity="0.25" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.85" />);
      });
    }
    return shapes;
  };

  const drawRightProfiles = () => {
    const y1 = topPad;
    const h = railCount * rowH;
    const shapes: React.ReactElement[] = [];
    let x = leftW + railAreaW + 4;

    if (profileRightWall) {
      shapes.push(<rect key="rw1" x={x}     y={y1} width={7} height={h} rx="1" fill="var(--theme-accent)" fillOpacity="0.45" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />);
      shapes.push(<rect key="rw2" x={x + 7} y={y1} width={7} height={h} rx="1" fill="var(--theme-accent)" fillOpacity="0.22" stroke="var(--theme-accent)" strokeWidth="1" strokeOpacity="0.8" />);
      x += 16;
    }
    if (profileRightLockBar) {
      shapes.push(<rect key="rl1" x={x}     y={y1} width={4} height={h} rx="1" fill="var(--theme-accent)" fillOpacity="0.40" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />);
      shapes.push(<rect key="rl2" x={x + 8} y={y1} width={4} height={h} rx="1" fill="var(--theme-accent)" fillOpacity="0.40" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.9" />);
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<line key={`rlb${ri}`} x1={x+2} y1={cy} x2={x+10} y2={cy} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.7" />);
      });
      x += 14;
    }
    if (profileRightPBar) {
      shapes.push(<path key="rp" d={`M${x+12},${y1} L${x+2},${y1} L${x+2},${y1+h} L${x+12},${y1+h}`} fill="none" stroke="var(--theme-accent)" strokeWidth="2.5" strokeOpacity="0.85" />);
      x += 14;
    }
    if (profileRightHandleBar) {
      shapes.push(<line key="rhv" x1={x+8} y1={y1} x2={x+8} y2={y1+h} stroke="var(--theme-accent)" strokeWidth="2.5" strokeOpacity="0.85" />);
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<line key={`rhh${ri}`} x1={x+2} y1={cy} x2={x+14} y2={cy} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.65" />);
      });
      x += 16;
    }
    if (profileRightBubble) {
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<circle key={`rb${ri}`} cx={x+7} cy={cy} r={5} fill="var(--theme-accent)" fillOpacity="0.25" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.85" />);
      });
    }
    return shapes;
  };

  return (
    <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} className="w-full drop-shadow-[0_0_15px_rgba(79,209,197,0.08)]" style={{ maxWidth: svgW }}>

      {/* Labels: ПОМЕЩЕНИЕ / УЛИЦА */}
      <text x={leftW + railAreaW / 2} y={12} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.45" fontWeight="bold" letterSpacing="1.5">ПОМЕЩЕНИЕ</text>
      <text x={leftW + railAreaW / 2} y={topPad + railCount * rowH + 14} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.45" fontWeight="bold" letterSpacing="1.5">УЛИЦА</text>

      {/* Red boundary lines (top + bottom of opening) */}
      <line x1={leftW - 8} y1={topPad - 2} x2={leftW + railAreaW + 8} y2={topPad - 2} stroke="#ef4444" strokeWidth="1.5" strokeOpacity="0.7" />
      <line x1={leftW - 8} y1={topPad + railCount * rowH + 2} x2={leftW + railAreaW + 8} y2={topPad + railCount * rowH + 2} stroke="#ef4444" strokeWidth="1.5" strokeOpacity="0.7" />

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

  const vbW = 540, vbH = 330;
  const fX = 50, fY = 35, fW = 400, fH = 210;
  const pt = 10;

  const iX = fX + pt, iY = fY + pt;
  const iW = fW - 2 * pt, iH = fH - 2 * pt;
  const pW = iW / panels;

  const panelWmm = Math.round(W / panels);
  const arrowLeft = firstRight;

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

        return (
          <g key={i}>
            <rect x={px} y={iY} width={pW} height={iH} fill="var(--theme-accent)" fillOpacity="0.07" />
            <rect x={px + 3} y={iY + 3} width={pW * 0.28} height={iH - 6} fill="var(--theme-fg)" fillOpacity="0.025" rx="1" />

            {i < panels - 1 && (
              <rect x={px + pW - 2} y={iY} width={4} height={iH}
                fill="var(--theme-page)" stroke="var(--theme-accent)" strokeWidth="0.4" strokeOpacity="0.25" />
            )}

            <text x={cx} y={cy - 12} textAnchor="middle" fontSize="14"
              fill="var(--theme-accent)" fillOpacity="0.85" fontWeight="bold" fontFamily="monospace">
              {num}
            </text>

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
