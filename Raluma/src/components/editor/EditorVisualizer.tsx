/**
 * EditorVisualizer — SVG-схемы секции (вид из помещения + вид сверху).
 * Извлечено из ProjectEditor.tsx (строки 636–653, 671–688).
 *
 * variant="mobile"  → показывается на <xl (под формой)
 * variant="desktop" → sticky-панель справа на xl+
 */

import React from 'react';
import type { BookCalcPreview, SectionCalcPreview } from '../../api/projects';
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
  return Boolean(calc && 'normalized_config' in calc && 'panels' in calc);
}

export const EditorVisualizer: React.FC<EditorVisualizerProps> = ({ section, variant, calc }) => {
  const bookCalc = isBookCalcPreview(calc) ? calc : null;
  const slideCalc = calc && !isBookCalcPreview(calc) ? calc : null;

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
      <div className="hidden xl:sticky xl:top-4 xl:flex xl:w-[500px] xl:flex-shrink-0 xl:flex-col xl:gap-3" data-book-visualizer="desktop">
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
      <div className="hidden xl:sticky xl:top-4 xl:flex xl:w-[500px] xl:flex-shrink-0 xl:flex-col">
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

  if (section.system !== 'СЛАЙД') return null;

  if (variant === 'mobile') {
    return (
      <div className="xl:hidden space-y-4 mb-4">
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
    <div className="hidden xl:flex xl:flex-col xl:gap-3 xl:w-[500px] xl:flex-shrink-0 xl:sticky xl:top-4">
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
