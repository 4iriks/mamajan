import React from 'react';
import { Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react';
import type { SectionTemplate } from '../../api/sectionTemplates';
import { applyTemplateDataToSection } from './converters';
import { SlideRoomViewSVG } from './SlideDiagrams';
import { LiftRoomViewSVG } from './LiftDiagrams';
import { Section, SYSTEM_COLORS } from './types';

const MAX_TEMPLATES = 10;

function sectionLabel(section: Section) {
  if (section.system === 'СЛАЙД') {
    const rows = section.slideRows === 2 ? '2 ряда' : '1 ряд';
    return `${rows} · ${section.panels} пан.`;
  }
  if (section.system === 'КНИЖКА') return `${section.doors || section.panels || 1} ств.`;
  if (section.system === 'ЛИФТ') return `${section.panels || 2} пан.`;
  if (section.system === 'ЦС') return section.csShape || 'форма';
  return section.doorSystem || 'комплект';
}

function templateSystemLabel(section: Section) {
  if (section.system !== 'СЛАЙД') return section.system;
  return section.slideRows === 2 ? 'СЛАЙД 2 ряда' : 'СЛАЙД 1 ряд';
}

function GenericTemplatePreview({ section }: { section: Section }) {
  const panels = Math.max(1, Math.min(section.panels || 1, 8));
  const width = 220;
  const height = 110;
  const innerX = 22;
  const innerY = 20;
  const innerW = 176;
  const innerH = 68;
  const panelW = innerW / panels;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
      <rect x={innerX} y={innerY} width={innerW} height={innerH} fill="var(--theme-accent)" fillOpacity="0.06" stroke="var(--theme-accent)" strokeOpacity="0.55" strokeWidth="2" />
      {Array.from({ length: panels - 1 }).map((_, index) => (
        <line
          key={index}
          x1={innerX + panelW * (index + 1)}
          y1={innerY}
          x2={innerX + panelW * (index + 1)}
          y2={innerY + innerH}
          stroke="var(--theme-accent)"
          strokeOpacity="0.35"
          strokeWidth="1.5"
        />
      ))}
      <text x={width / 2} y={innerY + innerH / 2 + 4} textAnchor="middle" fontSize="16" fill="var(--theme-accent)" fillOpacity="0.75" fontWeight="bold">
        {section.system}
      </text>
      <text x={width / 2} y={innerY + innerH + 16} textAnchor="middle" fontSize="10" fill="var(--theme-accent)" fillOpacity="0.45">
        {Math.round(section.width)}×{Math.round(section.height)}
      </text>
    </svg>
  );
}

function TemplatePreview({ section }: { section: Section }) {
  if (section.system === 'СЛАЙД') {
    return (
      <div className="h-full w-full overflow-hidden [&_svg]:h-full [&_svg]:max-w-none">
        <SlideRoomViewSVG section={section} />
      </div>
    );
  }
  if (section.system === 'ЛИФТ') {
    return (
      <div className="h-full w-full overflow-hidden [&_svg]:h-full [&_svg]:max-w-none">
        <LiftRoomViewSVG section={section} />
      </div>
    );
  }
  return <GenericTemplatePreview section={section} />;
}

interface SectionTemplatesPanelProps {
  section: Section;
  templates: SectionTemplate[];
  isAdmin: boolean;
  isLoading?: boolean;
  onApply: (template: SectionTemplate) => void;
  onCreate: () => void;
  onRename: (template: SectionTemplate) => void;
  onRefresh: (template: SectionTemplate) => void;
  onDelete: (template: SectionTemplate) => void;
}

export const SectionTemplatesPanel: React.FC<SectionTemplatesPanelProps> = ({
  section,
  templates,
  isAdmin,
  isLoading,
  onApply,
  onCreate,
  onRename,
  onRefresh,
  onDelete,
}) => {
  if (!isAdmin && templates.length === 0) return null;

  const slots = Array.from({ length: MAX_TEMPLATES }, (_, index) => templates[index] || null);
  const systemLabel = templateSystemLabel(section);

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-accent/45">Шаблоны</span>
          <span className={`px-2 py-0.5 rounded-md text-[9px] font-bold border ${SYSTEM_COLORS[section.system]}`}>
            {systemLabel}
          </span>
        </div>
        <span className="text-[10px] font-bold text-fg/25">{templates.length}/{MAX_TEMPLATES}</span>
      </div>

      <div className="grid grid-cols-10 gap-1.5">
        {slots.map((template, index) => {
          if (!template) {
            if (!isAdmin) return null;
            return (
              <button
                key={`empty-${index}`}
                onClick={onCreate}
                disabled={isLoading}
                className="h-24 rounded-lg border border-dashed border-tint/30 bg-hi/[0.025] hover:bg-tint/10 hover:border-accent/35 transition-all flex flex-col items-center justify-center gap-1.5 text-accent/60 disabled:opacity-50"
                title="Добавить шаблон"
              >
                <Plus className="w-4 h-4" />
                <span className="text-[8px] font-bold uppercase tracking-wide">Добавить</span>
              </button>
            );
          }

          const previewSection = applyTemplateDataToSection(section, template.template_data);
          return (
            <div
              key={template.id}
              className="relative h-24 rounded-lg border border-tint/25 bg-surface/45 hover:bg-tint/10 hover:border-accent/45 overflow-hidden transition-all text-left group"
            >
              <button
                type="button"
                onClick={() => onApply(template)}
                disabled={isLoading}
                className="absolute inset-0 text-left disabled:opacity-60"
                title="Применить шаблон"
              >
                <span className="absolute inset-x-1 top-1 h-[66px] rounded-md bg-page/70 border border-tint/15 overflow-hidden">
                  <TemplatePreview section={previewSection} />
                </span>
                <span className="absolute left-2 right-2 bottom-1.5">
                  <span className="block text-[8px] leading-tight font-bold text-fg/80 truncate">{template.name}</span>
                  <span className="block text-[7px] leading-tight font-bold text-fg/35 truncate">{sectionLabel(previewSection)}</span>
                </span>
              </button>

              {isAdmin && (
                <div className="absolute right-1.5 top-1.5 z-10 flex gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100 transition-opacity">
                  <button
                    type="button"
                    onClick={event => { event.stopPropagation(); onRefresh(template); }}
                    className="w-5 h-5 rounded-md bg-page/90 border border-tint/30 text-fg/45 hover:text-accent hover:border-accent/40 flex items-center justify-center"
                    title="Обновить из текущей секции"
                  >
                    <RefreshCw className="w-3 h-3" />
                  </button>
                  <button
                    type="button"
                    onClick={event => { event.stopPropagation(); onRename(template); }}
                    className="w-5 h-5 rounded-md bg-page/90 border border-tint/30 text-fg/45 hover:text-accent hover:border-accent/40 flex items-center justify-center"
                    title="Переименовать"
                  >
                    <Pencil className="w-3 h-3" />
                  </button>
                  <button
                    type="button"
                    onClick={event => { event.stopPropagation(); onDelete(template); }}
                    className="w-5 h-5 rounded-md bg-page/90 border border-red-500/25 text-red-400/60 hover:text-red-300 hover:border-red-400/50 flex items-center justify-center"
                    title="Удалить"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
