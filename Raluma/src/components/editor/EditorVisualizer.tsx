/**
 * EditorVisualizer — SVG-схемы секции (вид из помещения + вид сверху).
 * Извлечено из ProjectEditor.tsx (строки 636–653, 671–688).
 *
 * variant="mobile"  → показывается на <xl (под формой)
 * variant="desktop" → sticky-панель справа на xl+
 */

import React from 'react';
import { isCsCalcPreview, type BookCalcPreview, type CsCalcPreview, type SectionCalcPreview } from '../../api/projects';
import { Section } from './types';
import { BookRoomViewSVG, BookTopViewSVG } from './BookDiagrams';
import { SlideSchemeSVG, SlideRoomViewSVG } from './SlideDiagrams';
import { LiftKinematicSVG, LiftRoomViewSVG } from './LiftDiagrams';

export interface EditorVisualizerProps {
  section: Section;
  variant: 'desktop' | 'mobile';
  calc?: SectionCalcPreview | null;
}

function isBookCalcPreview(
  calc?: SectionCalcPreview | null,
): calc is BookCalcPreview {
  return Boolean(calc && 'normalized_config' in calc && 'panels' in calc && 'source_priority' in calc);
}

function CsRoomView({ section, calc }: { section: Section; calc: CsCalcPreview }) {
  const width = Math.max(1, section.width || 1);
  const height = Math.max(1, section.height || 1);
  return <svg viewBox={`-120 -120 ${width + 240} ${height + 240}`} className="h-auto w-full" role="img" aria-label="Схема ЦС">
    {calc.panes.map(pane => <g key={pane.number}>
      <polygon points={pane.polygon.map(point => `${point.x},${height - point.y}`).join(' ')} fill="#dff3f7" stroke="#66858c" strokeWidth={Math.max(width, height) / 350} />
      {(() => {
        const x = pane.polygon.reduce((sum, point) => sum + point.x, 0) / pane.polygon.length;
        const y = pane.polygon.reduce((sum, point) => sum + point.y, 0) / pane.polygon.length;
        return <g><text x={x} y={height - y - 18} textAnchor="middle" fontSize={Math.max(width, height) / 30} fontWeight="700" fill="#102f35">{pane.number}</text><text x={x} y={height - y + 34} textAnchor="middle" fontSize={Math.max(width, height) / 48} fill="#102f35">{pane.width_mm}×{pane.height_mm}</text></g>;
      })()}
    </g>)}
    <text x={width / 2} y={height + 90} textAnchor="middle" fontSize={Math.max(width, height) / 35} fontWeight="700" fill="currentColor">{section.width} мм</text>
    <text x={width + 75} y={height / 2} textAnchor="middle" fontSize={Math.max(width, height) / 35} fontWeight="700" fill="currentColor" transform={`rotate(-90 ${width + 75} ${height / 2})`}>{section.height} мм</text>
  </svg>;
}

export const EditorVisualizer: React.FC<EditorVisualizerProps> = ({ section, variant, calc }) => {
  const bookCalc = isBookCalcPreview(calc) ? calc : null;
  const csCalc = isCsCalcPreview(calc) ? calc : null;
  const slideCalc = calc && !isBookCalcPreview(calc) && !isCsCalcPreview(calc) ? calc : null;

  if (section.system === 'КНИЖКА') {
    if (!bookCalc) return null;
    const diagrams = (
      <>
        <div className="rounded-2xl border border-tint/30 bg-surface/25 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-widest text-accent/50">Вид из помещения</span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-fg/25">
              {bookCalc.panels.length} физ. пан. · {section.width}×{section.height}
            </span>
          </div>
          <BookRoomViewSVG section={section} calc={bookCalc} />
        </div>
        <div className="rounded-2xl border border-tint/30 bg-surface/25 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-widest text-accent/50">Вид сверху</span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-fg/25">
              Панели и направления движения
            </span>
          </div>
          <BookTopViewSVG section={section} calc={bookCalc} />
        </div>
      </>
    );
    if (variant === 'mobile') {
      return <div className="mb-4 space-y-4 xl:hidden" data-book-visualizer="mobile">{diagrams}</div>;
    }
    return (
      <div className="hidden xl:sticky xl:top-4 xl:flex xl:max-h-[calc(100dvh-2rem)] xl:w-[500px] xl:flex-shrink-0 xl:self-start xl:flex-col xl:gap-3 xl:overflow-y-auto xl:overscroll-contain xl:pr-1" data-book-visualizer="desktop">
        {diagrams}
      </div>
    );
  }

  if (section.system === 'ЛИФТ') {
    const diagrams = (
      <div className="flex min-w-[360px] flex-col gap-4">
        <figure className="m-0">
          <LiftRoomViewSVG section={section} />
          <figcaption
            data-lift-view-caption
            className="mt-1 text-center text-[10px] font-bold uppercase tracking-widest text-accent/50"
          >
            Вид из помещения
          </figcaption>
        </figure>
        <figure className="m-0 border-t border-tint/20 pt-3">
          <LiftKinematicSVG section={section} />
          <figcaption
            data-lift-kinematic-caption
            className="mt-1 text-center text-[10px] font-bold uppercase tracking-widest text-accent/50"
          >
            Кинематическая схема
          </figcaption>
        </figure>
      </div>
    );
    if (variant === 'mobile') {
      return (
        <div className="mb-4 xl:hidden">
          <div className="overflow-x-auto rounded-2xl border border-tint/30 bg-surface/25 p-4 sm:rounded-[2rem] sm:p-7">
            <div className="mb-4 flex min-w-[360px] items-center justify-between">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-accent/40">Схема ЛИФТ</h4>
              <span className="text-[10px] font-bold uppercase tracking-widest text-fg/20">
                {section.panels} пан. · {section.width}×{section.height}
              </span>
            </div>
            <div className="flex justify-center py-2">{diagrams}</div>
          </div>
        </div>
      );
    }
    return (
      <div className="hidden xl:sticky xl:top-4 xl:flex xl:max-h-[calc(100dvh-2rem)] xl:w-[500px] xl:flex-shrink-0 xl:self-start xl:flex-col xl:overflow-y-auto xl:overscroll-contain xl:pr-1">
        <div className="rounded-2xl border border-tint/30 bg-surface/25 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-widest text-accent/40">Схема ЛИФТ</span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-fg/20">
              {section.panels} пан. · {section.width}×{section.height}
            </span>
          </div>
          {diagrams}
        </div>
      </div>
    );
  }

  if (section.system === 'ЦС') {
    if (!csCalc) return null;
    const diagram = <div className="rounded-2xl border border-tint/30 bg-surface/25 p-4">
      <div className="mb-3 flex items-center justify-between"><span className="text-[10px] font-bold uppercase tracking-widest text-accent/50">Вид из помещения · ЦС</span><span className="text-[10px] text-fg/30">предварительно</span></div>
      <CsRoomView section={section} calc={csCalc} />
      <div className="mt-3 text-xs text-fg/45">{csCalc.system.name} · {csCalc.panes.length} стекол · {csCalc.glass_area_m2.toFixed(2)} м²</div>
    </div>;
    return variant === 'mobile'
      ? <div className="mb-4 xl:hidden">{diagram}</div>
      : <div className="hidden xl:sticky xl:top-4 xl:block xl:w-[500px] xl:flex-shrink-0">{diagram}</div>;
  }

  if (section.system !== 'СЛАЙД') return null;

  if (variant === 'mobile') {
    return (
      <div className="xl:hidden space-y-4 mb-4" data-slide-visualizer="mobile">
        <div className="bg-surface/25 border border-tint/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 overflow-x-auto">
          <div className="flex items-center justify-between mb-4 min-w-[360px]">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-accent/40">Вид из помещения</h4>
            <span className="text-[10px] text-fg/20 font-bold uppercase tracking-widest">{section.panels} пан. · {section.width}×{section.height}</span>
          </div>
          <div className="flex justify-center py-2"><SlideRoomViewSVG section={section} calc={slideCalc} /></div>
        </div>
        <div className="bg-surface/25 border border-tint/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 overflow-x-auto">
          <div className="flex items-center justify-between mb-5 min-w-[360px]">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-accent/40">Схема · Вид сверху</h4>
            <span className="text-[10px] text-fg/20 font-bold uppercase tracking-widest">{section.rails ?? 3}-рельс · {section.panels} пан.</span>
          </div>
          <div className="flex justify-center py-4"><SlideSchemeSVG section={section} calc={slideCalc} /></div>
        </div>
      </div>
    );
  }

  // variant === 'desktop'
  return (
    <div className="hidden xl:sticky xl:top-4 xl:flex xl:max-h-[calc(100dvh-2rem)] xl:w-[500px] xl:flex-shrink-0 xl:self-start xl:flex-col xl:gap-3 xl:overflow-y-auto xl:overscroll-contain xl:pr-1" data-slide-visualizer="desktop">
      <div className="bg-surface/25 border border-tint/30 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-bold uppercase tracking-widest text-accent/40">Вид из помещения</span>
          <span className="text-[10px] text-fg/20 font-bold uppercase tracking-widest">{section.panels} пан. · {section.width}×{section.height}</span>
        </div>
        <SlideRoomViewSVG section={section} calc={slideCalc} />
      </div>
      <div className="bg-surface/25 border border-tint/30 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-bold uppercase tracking-widest text-accent/40">Схема · Вид сверху</span>
          <span className="text-[10px] text-fg/20 font-bold uppercase tracking-widest">{section.rails ?? 3}-рельс · {section.panels} пан.</span>
        </div>
        <SlideSchemeSVG section={section} calc={slideCalc} />
      </div>
    </div>
  );
};
