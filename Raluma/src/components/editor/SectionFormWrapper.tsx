/**
 * SectionFormWrapper — редактор активной секции: хлебные крошки, форма, визуализатор, сохранение.
 * Извлечено из ProjectEditor.tsx (строки 274–347, 604–657).
 */

import React, { useEffect, useRef } from 'react';
import { ArrowLeft, Save, FileText, ClipboardList, Map } from 'lucide-react';
import { Section, LBL, SYSTEM_COLORS } from './types';
import { SectionDivider } from './FormInputs';
import { MainTab, SlideSystemTab, BookSystemTab, LiftSystemTab, CsShapeTab, DoorSystemTab } from './FormTabs';
import { EditorVisualizer } from './EditorVisualizer';

export interface SectionFormWrapperProps {
  section: Section;
  onUpdate: (updates: Partial<Section>) => void;
  onSave: () => Promise<void>;
  onBack: () => void;
  isSaving: boolean;
  isDirty: boolean;
  onOpenDoc?: (docName: string) => void;
}

export const SectionFormWrapper: React.FC<SectionFormWrapperProps> = ({
  section, onUpdate, onSave, onBack, isSaving, isDirty, onOpenDoc,
}) => {
  // Ctrl+S → сохранить секцию
  const onSaveRef = useRef(onSave);
  onSaveRef.current = onSave;

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        onSaveRef.current();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // beforeunload guard
  useEffect(() => {
    if (!isDirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [isDirty]);

  // Метка системы для заголовка
  const systemLabel = (() => {
    switch (section.system) {
      case 'СЛАЙД':
        return 'СЛАЙД стандарт 1 ряд';
      case 'КНИЖКА':
        return section.bookSubtype
          ? `КНИЖКА ${section.bookSubtype === 'doors' ? 'с дверями' : section.bookSubtype === 'angle' ? 'с углом' : 'с дверями и углом'}`
          : 'КНИЖКА';
      case 'ЛИФТ':
        return `ЛИФТ · ${section.panels ?? 2} пан.`;
      case 'ЦС':
        return section.csShape ? `ЦС · ${section.csShape}` : 'ЦС';
      default:
        return section.system;
    }
  })();

  return (
    <>
      {/* Хлебные крошки + заголовок */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 sm:mb-5 gap-3">
        <div>
          <button onClick={onBack}
            className="flex items-center gap-1.5 text-fg/30 hover:text-accent transition-colors group mb-3 text-xs font-bold uppercase tracking-wider">
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
            К проекту
          </button>
          <h2 className="text-xl sm:text-2xl font-bold mb-1.5">{section.name}</h2>
          <span className={`px-3 py-1 rounded-lg text-[11px] font-bold border ${SYSTEM_COLORS[section.system]}`}>
            {systemLabel}
          </span>
        </div>
      </div>

      {/* Flex-контейнер: форма слева, схема справа (на xl) */}
      <div className={section.system === 'СЛАЙД' ? 'xl:flex xl:gap-5 xl:items-start' : ''}>

        <div className={section.system === 'СЛАЙД' ? 'xl:flex-1 xl:min-w-0' : ''}>
          {/* Карточка формы */}
          <div className="bg-surface/40 border border-tint/35 rounded-2xl sm:rounded-[2rem] p-4 sm:p-6 mb-4">
            <div className="space-y-5">
              <div>
                <SectionDivider label="Основное" />
                <div className="mt-3">
                  <MainTab s={section} update={onUpdate} />
                </div>
              </div>

              {section.system === 'СЛАЙД' && (
                <div>
                  <SectionDivider label="Система · Профили · Фурнитура" />
                  <div className="mt-3">
                    <SlideSystemTab s={section} update={onUpdate} />
                  </div>
                </div>
              )}

              {section.system === 'КНИЖКА' && (
                <div>
                  <SectionDivider label="Система" />
                  <div className="mt-3">
                    <BookSystemTab s={section} update={onUpdate} />
                  </div>
                </div>
              )}

              {section.system === 'ЛИФТ' && (
                <div>
                  <SectionDivider label="Система" />
                  <div className="mt-3">
                    <LiftSystemTab s={section} update={onUpdate} />
                  </div>
                </div>
              )}

              {section.system === 'ЦС' && (
                <div>
                  <SectionDivider label="Форма" />
                  <div className="mt-3">
                    <CsShapeTab s={section} update={onUpdate} />
                  </div>
                </div>
              )}

              {section.system === 'КОМПЛЕКТАЦИЯ' && (
                <div>
                  <SectionDivider label="Система" />
                  <div className="mt-3">
                    <DoorSystemTab s={section} update={onUpdate} />
                  </div>
                </div>
              )}

              <div>
                <SectionDivider label="Примечания к секции" />
                <div className="mt-3">
                  <div className="space-y-1.5">
                    <label className={LBL}>Комментарии</label>
                    <textarea
                      value={section.comments || ''}
                      onChange={e => onUpdate({ comments: e.target.value || undefined })}
                      rows={2}
                      placeholder="Дополнительные комментарии..."
                      className="w-full bg-hi/8 border border-tint/30 rounded-xl px-3 py-2 outline-none focus:border-accent/50 transition-all text-fg resize-y placeholder-fg/20 text-sm"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Мобильный визуализатор */}
          <EditorVisualizer section={section} variant="mobile" />

          {/* Нижняя панель: сохранить + кнопки документов */}
          <div className="flex flex-wrap gap-2 sm:gap-3 items-stretch">
            <button onClick={onSave} disabled={isSaving}
              className={`flex-1 min-w-[180px] py-3 rounded-2xl text-white font-bold transition-all flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed ${
                isDirty
                  ? 'bg-amber-500 hover:bg-amber-400 shadow-lg shadow-amber-500/20'
                  : 'bg-primary hover:bg-primary-h shadow-lg shadow-primary/20'
              }`}>
              {isSaving ? (
                <div className="w-5 h-5 border-2 border-hi/30 border-t-white rounded-full animate-spin" />
              ) : isDirty ? (
                <><Save className="w-4 h-4" /> Сохранить изменения</>
              ) : 'Сохранить секцию'}
            </button>
            {[
              { name: 'Спецификация', icon: FileText },
              { name: 'Производственный лист', icon: ClipboardList },
              { name: 'Схема', icon: Map },
            ].map(doc => (
              <button key={doc.name} onClick={() => onOpenDoc?.(doc.name)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface/60 border border-tint/30 hover:bg-tint/30 hover:border-accent/40 transition-all group">
                <doc.icon className="w-3.5 h-3.5 text-accent/50 group-hover:text-accent transition-colors flex-shrink-0" />
                <span className="text-[10px] font-bold text-fg/50 group-hover:text-fg transition-colors whitespace-nowrap uppercase tracking-wider">{doc.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Десктопный визуализатор (sticky) */}
        <EditorVisualizer section={section} variant="desktop" />

      </div>
    </>
  );
};
