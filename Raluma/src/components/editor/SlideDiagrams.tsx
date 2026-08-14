import React from 'react';
import { SlideCalcPreview } from '../../api/projects';
import { diagramGlassFillColor, isMatteGlass } from '../../constants/glass';
import { Section } from './types';

// ── SVG Схема сверху (СЛАЙД) ──────────────────────────────────────────────────

function roundGlassMm(value: number) {
  return Math.floor(Math.max(0, value) + 0.5);
}

function expandGlassWidths(calc: SlideCalcPreview | null | undefined, panels: number, fallbackWidth: number) {
  if (calc?.panel_glass?.length && panels > 0) {
    const physicalPanels = [...calc.panel_glass]
      .sort((left, right) => left.panel - right.panel)
      .slice(0, panels);
    if (physicalPanels.length === panels) {
      return physicalPanels.map(panel => roundGlassMm(panel.width_mm));
    }
  }

  if (!calc?.glass?.length || panels <= 0) {
    return Array.from({ length: Math.max(panels, 1) }, () => roundGlassMm(fallbackWidth / Math.max(panels, 1)));
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

  if (panels === 1) return [roundGlassMm(middle)];
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
    return widths.slice(0, panels).map(roundGlassMm);
  }

  const widths = Array.from({ length: panels }, (_, index) => {
    if (index === 0) return left ?? edge ?? middle;
    if (index === panels - 1) return right ?? edge ?? middle;
    return middle;
  });

  return widths.map(roundGlassMm);
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

function panelNumber(
  section: Section,
  calc: SlideCalcPreview | null | undefined,
  index: number,
) {
  const calculated = calc?.panel_numbers?.[index];
  if (typeof calculated === 'number') return calculated;
  const panels = Math.max(section.panels, 1);
  if ((section.slideRows ?? 1) !== 2) {
    return (section.firstPanelInside ?? 'Справа') === 'Справа'
      ? panels - index
      : index + 1;
  }
  const half = Math.floor(panels / 2);
  return (section.unusedTrack ?? 'Внешний') === 'Внешний'
    ? (index < half ? half - index : index - half + 1)
    : (index < half ? index + 1 : panels - index);
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

type SideAssemblyVariant = 'lock-handle' | 'p-handle' | 'p-bubble' | 'bubble';

const SIDE_ASSEMBLY_IMAGES: Record<SideAssemblyVariant, {
  filename: string;
  sourceWidth: number;
  sourceHeight: number;
  visibleBounds: [number, number, number, number];
  displayHeight: number;
  widthScale: number;
}> = {
  'lock-handle': {
    filename: 'SIDE_RS2081_RS112.png',
    sourceWidth: 584,
    sourceHeight: 383,
    visibleBounds: [33, 0, 583, 364],
    displayHeight: 60,
    widthScale: 1.16,
  },
  'p-handle': {
    filename: 'SIDE_RS1082_RS112.png',
    sourceWidth: 389,
    sourceHeight: 401,
    visibleBounds: [36, 14, 357, 379],
    displayHeight: 60,
    widthScale: 1.16,
  },
  'p-bubble': {
    filename: 'SIDE_RS1082_RS1002.png',
    sourceWidth: 249,
    sourceHeight: 245,
    visibleBounds: [42, 38, 220, 215],
    displayHeight: 44,
    widthScale: 1,
  },
  bubble: {
    filename: 'SIDE_RS1002.png',
    sourceWidth: 177,
    sourceHeight: 133,
    visibleBounds: [17, 21, 149, 108],
    displayHeight: 32,
    widthScale: 1,
  },
};

function profileAssetUrl(filename: string) {
  return `/api/catalog/profile-assets/${encodeURIComponent(filename)}`;
}

function sideAssemblyImageLayout(variant: SideAssemblyVariant) {
  const image = SIDE_ASSEMBLY_IMAGES[variant];
  const [minX, minY, maxX, maxY] = image.visibleBounds;
  const scaleY = image.displayHeight / (maxY - minY + 1);
  const scaleX = scaleY * image.widthScale;

  return {
    ...image,
    imageWidth: image.sourceWidth * scaleX,
    imageHeight: image.sourceHeight * scaleY,
    imageX: -maxX * scaleX,
    imageY: -((minY + maxY) / 2) * scaleY,
    visibleWidth: (maxX - minX + 1) * scaleX,
  };
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
  if (bubble) return 'bubble';
  return null;
}

export function SlideSchemeSVG({ section, calc }: { section: Section; calc?: SlideCalcPreview | null }) {
  const sideAssemblyFilterPrefix = React.useId().replace(/:/g, '');
  const glassFill = diagramGlassFillColor(section.glassType);
  const matteGlass = isMatteGlass(section.glassType);
  const mattePatternId = `${sideAssemblyFilterPrefix}-matte-glass-top`;
  const {
    panels, rails = 3, firstPanelInside = 'Справа', unusedTrack,
    width: sectionWidth,
  } = section;
  const is2row = (section.slideRows ?? 1) === 2;
  const railCount = rails as number;

  const rowH   = 34;
  const topPad = 28;
  const botPad = 42;
  const leftW  = 130;
  const rightW = 130;
  const railAreaW = 500;
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
  const centerIsRs112 = is2row && (section.centerHandle ?? '').toLowerCase().includes('rs112');
  const centerLeftIndex = Math.max(0, Math.floor(panels / 2) - 1);
  const centerRightIndex = Math.min(panels - 1, Math.floor(panels / 2));

  const scaleBaseMm = Math.max(sectionWidth || panelWidthsMm.reduce((sum, width) => sum + width, 0), 1);
  const mmToPx = (mm: number, minPx = 0) => Math.max(minPx, (mm / scaleBaseMm) * railAreaW);
  const centerGapPx = is2row ? Math.max(1, mmToPx(3)) : 0;
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
  const sideAssemblyOverlap = 16;
  const sideAssemblySocketDepth = (variant: SideAssemblyVariant | null) => {
    if (variant === 'lock-handle') return 30;
    if (variant === 'p-handle') return 28;
    if (variant === 'p-bubble') return 32;
    return 28;
  };
  const leftAssemblyVisualWidth = leftSideVariant ? sideAssemblyImageLayout(leftSideVariant).visibleWidth : 0;
  const rightAssemblyVisualWidth = rightSideVariant ? sideAssemblyImageLayout(rightSideVariant).visibleWidth : 0;
  const schemeLeftX = leftSideVariant ? leftW - leftAssemblyVisualWidth + sideAssemblyOverlap - 4 : leftW;
  const schemeRightX = rightSideVariant ? leftW + railAreaW + rightAssemblyVisualWidth - sideAssemblyOverlap + 4 : leftW + railAreaW;
  const wallArticle = railCount === 5 ? 'RS2335' : 'RS2333';
  const wallImageWidth = 34;
  // PNG profiles contain transparent end margins. A small bleed keeps the
  // visible profile joined to both opening boundaries after rotation.
  const wallImageHeight = railCount * rowH + 16;
  const wallImageY = topPad - 8;
  const wallAttachOverlap = railCount === 5 ? 11 : 8;
  const diagramOuterLeft = section.profileLeftWall
    ? schemeLeftX - wallImageWidth + wallAttachOverlap
    : schemeLeftX;
  const diagramOuterRight = section.profileRightWall
    ? schemeRightX + wallImageWidth - wallAttachOverlap
    : schemeRightX;
  const diagramOffsetX = svgW / 2 - (diagramOuterLeft + diagramOuterRight) / 2;

  const panelGlassBounds = (panelIndex: number) => {
    const layout = panelLayout[panelIndex];
    let left = layout.x + (panelIndex === 0 ? 5 : -6);
    let right = layout.x + layout.width + (panelIndex === panels - 1 ? -5 : 6);
    if (panelIndex === 0 && leftSideVariant) {
      left = leftW + sideAssemblyOverlap - sideAssemblySocketDepth(leftSideVariant);
    }
    if (panelIndex === panels - 1 && rightSideVariant) {
      right = leftW + railAreaW - sideAssemblyOverlap + sideAssemblySocketDepth(rightSideVariant);
    }
    if (is2row && panelIndex === centerLeftIndex) {
      right = layout.x + layout.width - centerGapPx / 2;
    } else if (is2row && panelIndex === centerRightIndex) {
      left = layout.x + centerGapPx / 2;
    }
    return { left, right };
  };

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
    railIndex: number,
  ) => {
    if (!variant) return null;

    const cy = topPad + railIndex * rowH + rowH / 2;
    const image = sideAssemblyImageLayout(variant);
    const x = side === 'left' ? leftW + sideAssemblyOverlap : leftW + railAreaW - sideAssemblyOverlap;
    const transform = side === 'right'
      ? `translate(${x} ${cy}) scale(-1 1)`
      : `translate(${x} ${cy})`;
    const filterId = `${sideAssemblyFilterPrefix}-side-assembly-${side}`;

    return (
      <g key={`${side}-side-assembly`} transform={transform} data-side-assembly={variant}>
        <defs>
          <filter id={filterId} x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
            <feFlood floodColor="var(--theme-accent)" floodOpacity="0.82" result="profile-color" />
            <feComposite in="profile-color" in2="SourceAlpha" operator="in" />
          </filter>
        </defs>
        <image
          data-side-assembly-image={image.filename}
          href={profileAssetUrl(image.filename)}
          x={image.imageX}
          y={image.imageY}
          width={image.imageWidth}
          height={image.imageHeight}
          preserveAspectRatio="none"
          filter={`url(#${filterId})`}
        />
      </g>
    );
  };

  const renderWallProfile = (side: 'left' | 'right') => {
    const enabled = side === 'left' ? section.profileLeftWall : section.profileRightWall;
    if (!enabled) return null;
    const filterId = `${sideAssemblyFilterPrefix}-wall-profile-${side}`;
    const wallX = side === 'left'
      ? schemeLeftX - wallImageWidth + wallAttachOverlap
      : schemeRightX - wallAttachOverlap;
    const transform = side === 'left'
      ? `translate(${wallX} ${wallImageY + wallImageHeight}) rotate(-90)`
      : `translate(${wallX + wallImageWidth} ${wallImageY}) rotate(90)`;

    return (
      <g
        key={`${side}-wall-profile`}
        data-profile-image={`${wallArticle}-${side}`}
        transform={transform}
      >
        <defs>
          <filter id={filterId} x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
            <feFlood floodColor="var(--theme-accent)" floodOpacity="0.72" result="profile-color" />
            <feComposite in="profile-color" in2="SourceAlpha" operator="in" />
          </filter>
        </defs>
        <image
          href={profileAssetUrl(`${wallArticle}.png`)}
          x="0"
          y="0"
          width={wallImageHeight}
          height={wallImageWidth}
          preserveAspectRatio="none"
          filter={`url(#${filterId})`}
        />
      </g>
    );
  };

  return (
    <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} className="block w-full drop-shadow-[0_0_15px_rgba(79,209,197,0.08)]" style={{ maxWidth: svgW, margin: '0 auto' }}>
      <defs>
        <pattern id={mattePatternId} data-glass-pattern="matte" width="5" height="5" patternUnits="userSpaceOnUse">
          <rect width="5" height="5" fill={glassFill} />
          <circle cx="1.25" cy="1.25" r="0.65" fill="var(--theme-accent)" fillOpacity="0.48" />
        </pattern>
      </defs>
      <g
        transform={`translate(${diagramOffsetX} 0)`}
        data-diagram-outer-left={diagramOuterLeft + diagramOffsetX}
        data-diagram-outer-right={diagramOuterRight + diagramOffsetX}
      >
        {/* Labels: УЛИЦА (top) / ПОМЕЩЕНИЕ (bottom) */}
        <text x={leftW + railAreaW / 2} y={12} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.45" fontWeight="bold" letterSpacing="1.5">УЛИЦА</text>
        <text x={leftW + railAreaW / 2} y={topPad + railCount * rowH + 14} textAnchor="middle" fontSize="8" fill="var(--theme-accent)" fillOpacity="0.45" fontWeight="bold" letterSpacing="1.5">ПОМЕЩЕНИЕ</text>

      {/* Boundary lines (top + bottom of opening) */}
      <line x1={schemeLeftX} y1={topPad - 2} x2={schemeRightX} y2={topPad - 2} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />
      <line x1={schemeLeftX} y1={topPad + railCount * rowH + 2} x2={schemeRightX} y2={topPad + railCount * rowH + 2} stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />

      {/* Vertical boundary lines */}
      <line x1={schemeLeftX} y1={topPad - 4} x2={schemeLeftX} y2={topPad + railCount * rowH + 4} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.5" />
      <line x1={schemeRightX} y1={topPad - 4} x2={schemeRightX} y2={topPad + railCount * rowH + 4} stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.5" />

      {renderWallProfile('left')}
      {renderWallProfile('right')}

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
        const panelNum = panelNumber(section, calc, pi);
        const bounds = panelGlassBounds(pi);
        const rx = bounds.left;
        const rRight = bounds.right;
        const rw = Math.max(1, rRight - rx);
        const cx = px + panelW / 2;
        return (
          <g key={pi}>
            <rect data-scheme-panel={pi + 1} x={rx} y={cy - 6} width={rw} height={12} data-glass-fill={glassFill} data-glass-pattern={matteGlass ? 'matte' : undefined} rx="2"
              fill={matteGlass ? `url(#${mattePatternId})` : glassFill} fillOpacity="0.52" stroke="var(--diagram-line)" strokeWidth="1.4" strokeOpacity="0.9" />
            {layout.widthMm ? (
              <text x={cx} y={cy + 5} textAnchor="middle" fontSize="8" fill="var(--diagram-symbol)" fillOpacity="1" fontWeight="bold">{layout.widthMm} · №{panelNum}</text>
            ) : (
              <text x={cx} y={cy + 5} textAnchor="middle" fontSize="9" fill="var(--diagram-symbol)" fillOpacity="1" fontWeight="bold">{panelNum}</text>
            )}
          </g>
        );
      })}

      {centerIsRs112 && ([
        { side: 'left', panelIndex: centerLeftIndex },
        { side: 'right', panelIndex: centerRightIndex },
      ] as const).map(({ side, panelIndex }) => {
        const layout = panelLayout[panelIndex];
        const railIndex = panelRailMap[panelIndex] ?? 0;
        const cy = topPad + railIndex * rowH + rowH / 2;
        const profileX = side === 'left'
          ? layout.x + layout.width - centerGapPx / 2 - 4
          : layout.x + centerGapPx / 2 + 4;
        const glassEndX = profileX + (side === 'left' ? -9 : 9);
        return (
          <g key={`center-rs112-${side}`} data-center-rs112-top={side} data-profile-width-mm="40">
            <line x1={profileX} y1={cy - 14} x2={profileX} y2={cy + 14}
              stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.82" />
            <line x1={profileX - 5} y1={cy - 14} x2={profileX + 5} y2={cy - 14}
              stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.82" strokeLinecap="round" />
            <line x1={profileX - 5} y1={cy + 14} x2={profileX + 5} y2={cy + 14}
              stroke="var(--theme-accent)" strokeWidth="2" strokeOpacity="0.82" strokeLinecap="round" />
            <line x1={profileX} y1={cy - 3} x2={glassEndX} y2={cy - 3}
              stroke="var(--theme-accent)" strokeWidth="1.4" strokeOpacity="0.68" />
            <line x1={profileX} y1={cy + 3} x2={glassEndX} y2={cy + 3}
              stroke="var(--theme-accent)" strokeWidth="1.4" strokeOpacity="0.68" />
          </g>
        );
      })}

      {hasInterGlassProfile && panelLayout.slice(0, -1).map((_, pi) => {
        if (is2row && pi === panels / 2 - 1) return null;
        const attachesToNextPanel = is2row
          ? pi < panels / 2
          : firstPanelInside === 'Справа';
        const ownerIndex = attachesToNextPanel ? pi + 1 : pi;
        const ri = panelRailMap[ownerIndex] ?? panelRailMap[pi];
        const cy = topPad + ri * rowH + rowH / 2;
        const ownerBounds = panelGlassBounds(ownerIndex);
        const edgeX = attachesToNextPanel ? ownerBounds.left : ownerBounds.right;
        const inwardDirection = attachesToNextPanel ? 1 : -1;
        return renderInterGlassProfile(edgeX, cy, pi, inwardDirection);
      })}

      {renderSideAssembly('left', leftSideVariant, panelRailMap[0] ?? 0)}
      {renderSideAssembly('right', rightSideVariant, panelRailMap[panels - 1] ?? railCount - 1)}

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
      </g>
    </svg>
  );
}

// ── SVG: Вид из помещения ─────────────────────────────────────────────────────

export function SlideRoomViewSVG({
  section,
  calc,
  compact = false,
}: {
  section: Section;
  calc?: SlideCalcPreview | null;
  compact?: boolean;
}) {
  const diagramId = React.useId().replace(/:/g, '');
  const panels  = section.panels;
  const is2row = (section.slideRows ?? 1) === 2;
  const glassFill = diagramGlassFillColor(section.glassType);
  const matteGlass = isMatteGlass(section.glassType);
  const mattePatternId = `${diagramId}-matte-glass-room`;
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
  const firstPanelsInCenter = (section.unusedTrack ?? 'Внешний') === 'Внешний';
  const centerIsDeaf = centerHandle === 'Без ручки (глухие)' || centerHandle === '';
  const centerIsRs112 = is2row && centerHandle.toLowerCase().includes('rs112');
  const centerLeftIdx = Math.max(0, Math.floor(panels / 2) - 1);
  const centerRightIdx = Math.min(panels - 1, Math.floor(panels / 2));

  const leftIsDeaf = (handleLeft === 'Без' || handleLeft.toLowerCase().includes('глухая'))
    && lockLeft === 'Без' && !section.profileLeftHandleBar;
  const rightIsDeaf = (handleRight === 'Без' || handleRight.toLowerCase().includes('глухая'))
    && lockRight === 'Без' && !section.profileRightHandleBar;

  const vbW = 600, vbH = 360;
  const maxDrawingW = 500;
  const maxDrawingH = 245;
  const drawingOriginX = 35;
  const drawingOriginY = 28;
  const safeW = Math.max(W, 1);
  const safeH = Math.max(Hh, 1);
  const drawingScale = Math.min(maxDrawingW / safeW, maxDrawingH / safeH);
  const fW = safeW * drawingScale;
  const fH = safeH * drawingScale;
  const fX = drawingOriginX + (maxDrawingW - fW) / 2;
  const fY = drawingOriginY + (maxDrawingH - fH) / 2;
  const compactPadding = 10;
  const roomViewBox = compact
    ? `${fX - compactPadding} ${fY - compactPadding} ${fW + compactPadding * 2} ${fH + compactPadding * 2}`
    : `0 0 ${vbW} ${vbH}`;

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
  const arrowsBothDirections = !is2row && !leftIsDeaf && !rightIsDeaf;

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

  const renderHandleSymbol = (handle: string, x: number, sizeScale = 1) => {
    const h = handle.toLowerCase();
    if (h.includes('кноб') || h.includes('rs3014')) {
      return <circle cx={x} cy={symY} r={6 * sizeScale} fill="var(--diagram-symbol)" fillOpacity="0.85" stroke="var(--diagram-symbol)" strokeWidth={1.5 * sizeScale} strokeOpacity="1" />;
    }
    if (h.includes('скоба')) {
      return <line x1={x} y1={symY - 26 * sizeScale} x2={x} y2={symY + 26 * sizeScale} stroke="var(--diagram-symbol)" strokeWidth={3 * sizeScale} strokeOpacity="1" />;
    }
    if (h.includes('стеклян') || h.includes('rs3017')) {
      const size = 10 * sizeScale;
      return <rect x={x - size / 2} y={symY - size / 2} width={size} height={size} fill="var(--diagram-symbol)" fillOpacity="0.75" stroke="var(--diagram-symbol)" strokeWidth={1.5 * sizeScale} strokeOpacity="1" />;
    }
    return null;
  };

  const renderLockSymbol = (lock: string, x: number) => {
    const l = lock.toLowerCase();
    if (l.includes('1стор') || l.includes('1-сторон')) {
      return <line x1={x} y1={symY - 12} x2={x} y2={symY + 12} stroke="var(--diagram-symbol)" strokeWidth="2.5" strokeOpacity="1" />;
    }
    if (l.includes('2стор') || l.includes('2-сторон') || l.includes('ключ')) {
      const kx = x + 12;
      return (
        <g>
          <line x1={x} y1={symY - 12} x2={x} y2={symY + 12} stroke="var(--diagram-symbol)" strokeWidth="2.5" strokeOpacity="1" />
          <circle cx={kx} cy={symY - 5} r={5} fill="none" stroke="var(--diagram-symbol)" strokeWidth="1.5" strokeOpacity="1" />
          <line x1={kx} y1={symY} x2={kx} y2={symY + 12} stroke="var(--diagram-symbol)" strokeWidth="1.5" strokeOpacity="1" />
          <line x1={kx} y1={symY + 6} x2={kx + 4} y2={symY + 6} stroke="var(--diagram-symbol)" strokeWidth="1.5" strokeOpacity="1" />
          <line x1={kx} y1={symY + 9} x2={kx + 3} y2={symY + 9} stroke="var(--diagram-symbol)" strokeWidth="1.5" strokeOpacity="1" />
        </g>
      );
    }
    return null;
  };

  return (
    <svg
      data-room-view-mode={compact ? 'compact' : 'full'}
      viewBox={roomViewBox}
      className="block w-full"
      style={{ maxWidth: 600, maxHeight: 360, margin: '0 auto' }}
    >
      <defs>
        <pattern id={mattePatternId} data-glass-pattern="matte" width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill={glassFill} />
          <circle cx="1.5" cy="1.5" r="0.75" fill="var(--theme-accent)" fillOpacity="0.48" />
        </pattern>
      </defs>

      <rect x={fX} y={fY} width={fW} height={topPx} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX} y={fY + fH - bottomPx} width={fW} height={bottomPx} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX} y={fY} width={sidePx} height={fH} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect x={fX + fW - sidePx} y={fY} width={sidePx} height={fH} fill="var(--theme-surface)" stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.4" />
      <rect data-room-frame x={fX} y={fY} width={fW} height={fH} fill="none" stroke="var(--theme-accent)" strokeWidth="1.5" strokeOpacity="0.5" />
      {Array.from({ length: panels }).map((_, i) => {
        const layout = panelLayout[i];
        const px = layout.x;
        const pW = layout.width;
        const cx = px + pW / 2;
        const cy = iY + iH / 2;
        const num = panelNumber(section, calc, i);
        const aLen = Math.min(22, pW * 0.45);
        const isLeftPanel = i === leftPanelIdx;
        const isRightPanel = i === rightPanelIdx;
        const isCenterPanel = is2row && (i === centerLeftIdx || i === centerRightIdx);
        const isDeaf = (isLeftPanel && leftIsDeaf) || (isRightPanel && rightIsDeaf) || (isCenterPanel && centerIsDeaf);
        const panelArrowLeft = is2row ? i < panels / 2 : arrowLeft;
        const panelBidirectional = is2row
          ? (i < panels / 2 ? !leftIsDeaf : !rightIsDeaf)
          : arrowsBothDirections;
        const centerRs112Width = Math.min(pW * 0.25, Math.max(4, 40 * drawingScale));
        const centerRs112X = i === centerLeftIdx ? px + pW - centerRs112Width : px;

        return (
          <g key={i}>
            <rect data-glass-panel={i + 1} data-glass-fill={glassFill} data-glass-pattern={matteGlass ? 'matte' : undefined} x={px} y={iY} width={pW} height={iH} fill={matteGlass ? `url(#${mattePatternId})` : glassFill} fillOpacity="0.52" />

            {isCenterPanel && centerIsRs112 && (
              <rect
                data-center-rs112-room={i === centerLeftIdx ? 'left' : 'right'}
                data-profile-width-mm="40"
                x={centerRs112X}
                y={iY + 1}
                width={centerRs112Width}
                height={Math.max(1, iH - 2)}
                fill="none"
                stroke="var(--theme-accent)"
                strokeWidth="0.8"
                strokeOpacity="0.8"
              />
            )}

            {i < panels - 1 && (is2row && i === centerLeftIdx ? (
              <line x1={px + pW} y1={iY} x2={px + pW} y2={iY + iH}
                stroke="var(--theme-accent)" strokeWidth="0.6" strokeOpacity="0.25" />
            ) : (
              <rect x={px + pW - 2} y={iY} width={4} height={iH}
                fill="var(--theme-page)" stroke="var(--theme-accent)" strokeWidth="0.4" strokeOpacity="0.25" />
            ))}

            {/* Deaf panel — big X */}
            {isDeaf && (
              <g>
                <line x1={px + pW * 0.24} y1={iY + iH * 0.22} x2={px + pW * 0.76} y2={iY + iH * 0.78} stroke="var(--theme-accent)" strokeWidth="1.2" strokeOpacity="0.35" />
                <line x1={px + pW * 0.76} y1={iY + iH * 0.22} x2={px + pW * 0.24} y2={iY + iH * 0.78} stroke="var(--theme-accent)" strokeWidth="1.2" strokeOpacity="0.35" />
              </g>
            )}

            <text x={cx} y={cy - 12} textAnchor="middle" fontSize="14"
              fill="var(--diagram-symbol)" fillOpacity="1" fontWeight="bold" fontFamily="monospace">
              {num}
            </text>

            {!isDeaf && (
              <>
                <line
                  data-panel-direction={panelBidirectional ? 'both' : (panelArrowLeft ? 'left' : 'right')}
                  x1={panelArrowLeft ? cx + aLen / 2 : cx - aLen / 2}
                  y1={cy + 5}
                  x2={panelArrowLeft ? cx - aLen / 2 : cx + aLen / 2}
                  y2={cy + 5}
                  stroke="var(--diagram-symbol)" strokeWidth="1.5" strokeOpacity="0.9"
                />
                {(panelArrowLeft || panelBidirectional) && (
                  <polyline
                    points={`${cx - aLen / 2 + 6},${cy + 1} ${cx - aLen / 2},${cy + 5} ${cx - aLen / 2 + 6},${cy + 9}`}
                    stroke="var(--diagram-symbol)" strokeWidth="1.5" fill="none" strokeOpacity="0.9"
                  />
                )}
                {(!panelArrowLeft || panelBidirectional) && (
                  <polyline
                    points={`${cx + aLen / 2 - 6},${cy + 1} ${cx + aLen / 2},${cy + 5} ${cx + aLen / 2 - 6},${cy + 9}`}
                    stroke="var(--diagram-symbol)" strokeWidth="1.5" fill="none" strokeOpacity="0.9"
                  />
                )}
              </>
            )}
            {isCenterPanel && !centerIsDeaf && !centerIsRs112 && (() => {
              const inset = Math.min(pW * 0.35, Math.max(9, 130 * drawingScale));
              const anchorX = firstPanelsInCenter
                ? (i === centerLeftIdx ? px + pW - inset : px + inset)
                : cx;
              return (
                <g data-center-handle={i === centerLeftIdx ? 'left' : 'right'} data-anchor-x={anchorX}>
                  {renderHandleSymbol(centerHandle, anchorX, 0.84)}
                </g>
              );
            })()}

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

      {is2row && centerLock && centerLock !== 'Без' && (() => {
        const centerBoundaryX = panelLayout[centerLeftIdx].x + panelLayout[centerLeftIdx].width;
        const isOverheadLatch = centerLock.toLowerCase().includes('rs206')
          || centerLock.toLowerCase().includes('накидн');
        // Для RS112 допустима только нижняя накидная защёлка. Старые секции
        // могли сохранить замок стекло-стекло и рисовали лишнее пятно по центру.
        if (centerIsRs112 && !isOverheadLatch) return null;
        const centerHandleText = centerHandle.toLowerCase();
        const centerHandleHalfHeight = centerIsRs112
          ? 10
          : centerHandleText.includes('скоба')
            ? 26
            : centerHandleText.includes('кноб') || centerHandleText.includes('rs3014')
              ? 6
              : 5;
        const handleGap = Math.max(4, 100 * drawingScale);
        const lockBelowHandlesY = Math.min(
          iY + iH - 10,
          symY + centerHandleHalfHeight + handleGap,
        );
        const lockY = isOverheadLatch ? iY + iH - 9 : lockBelowHandlesY;
        return (
          <rect
            data-center-lock={isOverheadLatch ? 'RS206' : 'center'}
            data-center-lock-position={isOverheadLatch ? 'bottom' : 'below-handles'}
            x={centerBoundaryX - 5}
            y={lockY}
            width={10}
            height={7}
            rx={1.5}
            fill="var(--diagram-symbol)"
            fillOpacity="0.75"
            stroke="var(--diagram-symbol)"
            strokeWidth="1"
            strokeOpacity="0.75"
          />
        );
      })()}

      {!compact && Array.from({ length: panels }).map((_, i) => {
        const layout = panelLayout[i];
        const dx1 = layout.x;
        const dx2 = layout.x + layout.width;
        const dy  = fY + fH + 18;
        const cx  = (dx1 + dx2) / 2;
        const panelWmm = layout.widthMm;
        return (
          <g key={i} data-room-panel-dimension={i + 1}>
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

      {!compact && (
        <g data-room-overall-dimensions>
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
        </g>
      )}
    </svg>
  );
}
