/**
 * EditorVisualizer — SVG-схемы секции (вид из помещения + вид сверху).
 * Извлечено из ProjectEditor.tsx (строки 636–653, 671–688).
 *
 * variant="mobile"  → показывается на <xl (под формой)
 * variant="desktop" → sticky-панель справа на xl+
 */

import React from 'react';
import { Section } from './types';
import { SlideSchemeSVG, SlideRoomViewSVG } from './SlideDiagrams';

export interface EditorVisualizerProps {
  section: Section;
  variant: 'desktop' | 'mobile';
}

export const EditorVisualizer: React.FC<EditorVisualizerProps> = ({ section, variant }) => {
  // Пока визуализация только для СЛАЙД
  if (section.system !== 'СЛАЙД') return null;

  if (variant === 'mobile') {
    return (
      <div className="xl:hidden space-y-4 mb-4">
        <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 overflow-x-auto">
          <div className="flex items-center justify-between mb-4 min-w-[360px]">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Вид из помещения</h4>
            <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">{section.panels} пан. · {section.width}×{section.height}</span>
          </div>
          <div className="flex justify-center py-2"><SlideRoomViewSVG section={section} /></div>
        </div>
        <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 overflow-x-auto">
          <div className="flex items-center justify-between mb-5 min-w-[360px]">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Схема · Вид сверху</h4>
            <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">{section.rails ?? 3}-рельс · {section.panels} пан.</span>
          </div>
          <div className="flex justify-center py-4"><SlideSchemeSVG section={section} /></div>
        </div>
      </div>
    );
  }

  // variant === 'desktop'
  return (
    <div className="hidden xl:flex xl:flex-col xl:gap-3 xl:w-[420px] xl:flex-shrink-0 xl:sticky xl:top-4">
      <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Вид из помещения</span>
          <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">{section.panels} пан. · {section.width}×{section.height}</span>
        </div>
        <SlideRoomViewSVG section={section} />
      </div>
      <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Схема · Вид сверху</span>
          <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">{section.rails ?? 3}-рельс · {section.panels} пан.</span>
        </div>
        <SlideSchemeSVG section={section} />
      </div>
    </div>
  );
};
