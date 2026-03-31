/**
 * EditorSidebar — левая панель: список секций, системпикер, примечания проекта.
 * Извлечено из ProjectEditor.tsx (строки 438–663).
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Trash2, ChevronRight, ClipboardList } from 'lucide-react';
import { Section, SystemType, SYSTEM_COLORS, SYSTEM_ACCENT_BG, SYSTEM_PICKER_COLORS } from './types';
import { getSectionTypeLabel, getSectionColorLabel } from './FormInputs';

export interface EditorSidebarProps {
  sections: Section[];
  activeSectionId: string | null;
  onSelectSection: (id: string | null) => void;
  onAddSection: (system: SystemType, opts?: {
    slideRails?: 3 | 5;
    bookSubtype?: string;
    liftPanels?: number;
    csShape?: string;
  }) => void;
  onDeleteSection: (section: Section) => void;
  mobileSidebarOpen: boolean;
  setMobileSidebarOpen: (v: boolean | ((prev: boolean) => boolean)) => void;
  projectExtraParts: string;
  setProjectExtraParts: (v: string) => void;
  projectComments: string;
  setProjectComments: (v: string) => void;
  onSaveProjectNotes: () => void;
}

export const EditorSidebar: React.FC<EditorSidebarProps> = ({
  sections,
  activeSectionId,
  onSelectSection,
  onAddSection,
  onDeleteSection,
  mobileSidebarOpen,
  setMobileSidebarOpen,
  projectExtraParts,
  setProjectExtraParts,
  projectComments,
  setProjectComments,
  onSaveProjectNotes,
}) => {
  const [showSystemPicker, setShowSystemPicker] = useState(false);
  const [slideSubVisible, setSlideSubVisible] = useState(false);
  const [bookSubVisible, setBookSubVisible] = useState(false);
  const [liftSubVisible, setLiftSubVisible] = useState(false);
  const [csSubVisible, setCsSubVisible] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);

  // Reset picker when active section changes
  useEffect(() => { setShowSystemPicker(false); }, [activeSectionId]);

  const handleAdd = (system: SystemType, opts?: Parameters<typeof onAddSection>[1]) => {
    setShowSystemPicker(false);
    setSlideSubVisible(false);
    setBookSubVisible(false);
    setLiftSubVisible(false);
    setCsSubVisible(false);
    onAddSection(system, opts);
  };

  return (
    <aside className={`border-r border-tint/30 flex-col bg-page/80 backdrop-blur-sm z-10 flex-shrink-0 w-full sm:w-[260px] ${mobileSidebarOpen ? 'flex' : 'hidden sm:flex'}`}>
      <div className="p-5 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40">Секции</h3>
          <button
            onClick={() => setShowSystemPicker(v => !v)}
            className={`p-1.5 rounded-lg border transition-colors ${
              showSystemPicker
                ? 'bg-accent/20 border-accent/40 text-accent'
                : 'bg-tint/20 border-tint/30 text-accent hover:bg-tint/40'
            }`}
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* System picker */}
        <AnimatePresence>
          {showSystemPicker && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden mb-4"
            >
              <div className="flex flex-col gap-1.5 pt-1 pb-3">
                {/* СЛАЙД */}
                <div className={`rounded-xl border overflow-hidden transition-all ${slideSubVisible ? 'border-tint/50' : 'border-tint/25'}`}>
                  <button onClick={() => setSlideSubVisible(v => !v)}
                    className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['СЛАЙД']}`}>
                    <span>СЛАЙД</span>
                    <ChevronRight className={`w-3.5 h-3.5 transition-transform ${slideSubVisible ? 'rotate-90' : ''}`} />
                  </button>
                  {slideSubVisible && (
                    <div className="grid grid-cols-2 border-t border-tint/25">
                      <button onClick={() => handleAdd('СЛАЙД', { slideRails: 3 })}
                        className={`py-2 font-bold text-[11px] transition-all border-r border-tint/25 ${SYSTEM_PICKER_COLORS['СЛАЙД']}`}>
                        Стандарт 1 ряд
                      </button>
                      <button onClick={() => handleAdd('СЛАЙД', { slideRails: 5 })}
                        className={`py-2 font-bold text-[11px] transition-all ${SYSTEM_PICKER_COLORS['СЛАЙД']}`}>
                        2 ряда от центра
                      </button>
                    </div>
                  )}
                </div>
                {/* КНИЖКА */}
                <div className={`rounded-xl border overflow-hidden transition-all ${bookSubVisible ? 'border-[#7a4a2a]/50' : 'border-[#7a4a2a]/25'}`}>
                  <button onClick={() => setBookSubVisible(v => !v)}
                    className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                    <span>КНИЖКА</span>
                    <ChevronRight className={`w-3.5 h-3.5 transition-transform ${bookSubVisible ? 'rotate-90' : ''}`} />
                  </button>
                  {bookSubVisible && (
                    <div className="border-t border-[#7a4a2a]/25">
                      <div className="grid grid-cols-2">
                        <button onClick={() => handleAdd('КНИЖКА', { bookSubtype: 'doors' })}
                          className={`py-2 font-bold text-[11px] transition-all border-r border-b border-[#7a4a2a]/25 ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                          С дверями
                        </button>
                        <button onClick={() => handleAdd('КНИЖКА', { bookSubtype: 'angle' })}
                          className={`py-2 font-bold text-[11px] transition-all border-b border-[#7a4a2a]/25 ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                          С углом
                        </button>
                      </div>
                      <button onClick={() => handleAdd('КНИЖКА', { bookSubtype: 'doors_and_angle' })}
                        className={`w-full py-2 font-bold text-[11px] transition-all ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                        С дверями и углом
                      </button>
                    </div>
                  )}
                </div>
                {/* ЛИФТ */}
                <div className={`rounded-xl border overflow-hidden transition-all ${liftSubVisible ? 'border-[#4a2a7a]/50' : 'border-[#4a2a7a]/25'}`}>
                  <button onClick={() => setLiftSubVisible(v => !v)}
                    className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['ЛИФТ']}`}>
                    <span>ЛИФТ</span>
                    <ChevronRight className={`w-3.5 h-3.5 transition-transform ${liftSubVisible ? 'rotate-90' : ''}`} />
                  </button>
                  {liftSubVisible && (
                    <div className="grid grid-cols-3 border-t border-[#4a2a7a]/25">
                      {[2, 3, 4].map((n, i) => (
                        <button key={n} onClick={() => handleAdd('ЛИФТ', { liftPanels: n })}
                          className={`py-2 font-bold text-[11px] transition-all ${i < 2 ? 'border-r border-[#4a2a7a]/25' : ''} ${SYSTEM_PICKER_COLORS['ЛИФТ']}`}>
                          {n} пан.
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {/* ЦС */}
                <div className={`rounded-xl border overflow-hidden transition-all ${csSubVisible ? 'border-[#2a4a7a]/50' : 'border-[#2a4a7a]/25'}`}>
                  <button onClick={() => setCsSubVisible(v => !v)}
                    className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['ЦС']}`}>
                    <span>ЦС</span>
                    <ChevronRight className={`w-3.5 h-3.5 transition-transform ${csSubVisible ? 'rotate-90' : ''}`} />
                  </button>
                  {csSubVisible && (
                    <div className="grid grid-cols-2 border-t border-[#2a4a7a]/25">
                      {['Треугольник', 'Прямоугольник', 'Трапеция', 'Сложная форма'].map((shape, i) => (
                        <button key={shape} onClick={() => handleAdd('ЦС', { csShape: shape })}
                          className={`py-2 font-bold text-[11px] transition-all
                            ${i % 2 === 0 ? 'border-r border-[#2a4a7a]/25' : ''}
                            ${i < 2 ? 'border-b border-[#2a4a7a]/25' : ''}
                            ${SYSTEM_PICKER_COLORS['ЦС']}`}>
                          {shape}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {/* КОМПЛЕКТАЦИЯ */}
                <button onClick={() => handleAdd('КОМПЛЕКТАЦИЯ')}
                  className={`py-2.5 rounded-xl border font-bold text-[11px] transition-all ${SYSTEM_PICKER_COLORS['КОМПЛЕКТАЦИЯ']}`}>
                  КОМПЛЕКТАЦИЯ
                </button>
              </div>
              <div className="h-px bg-tint/20" />
            </motion.div>
          )}
        </AnimatePresence>

        <div className="space-y-2">
          {sections.map(section => (
            <motion.div key={section.id} layoutId={section.id}
              onClick={() => onSelectSection(section.id)}
              className={`relative group p-4 rounded-2xl border transition-all cursor-pointer overflow-hidden ${
                activeSectionId === section.id
                  ? 'bg-tint/20 border-accent/50 shadow-lg shadow-accent/5'
                  : 'bg-surface/60 border-tint/20 hover:border-tint/40'
              }`}
            >
              <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${SYSTEM_ACCENT_BG[section.system]} transition-opacity ${
                activeSectionId === section.id ? 'opacity-80' : 'opacity-30 group-hover:opacity-60'
              }`} />
              <div className="flex justify-between items-start mb-2">
                <span className={`text-sm font-bold leading-snug ${activeSectionId === section.id ? 'text-accent' : 'text-fg'}`}>
                  {section.name}
                </span>
                <button onClick={e => { e.stopPropagation(); onDeleteSection(section); }}
                  className="p-1 rounded-lg hover:bg-red-500/20 text-red-400 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0 ml-1">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${SYSTEM_COLORS[section.system]}`}>
                  {section.system}
                </span>
                {getSectionTypeLabel(section) && (
                  <span className="text-[11px] text-fg/60 font-medium">{getSectionTypeLabel(section)}</span>
                )}
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-mono text-fg/55">{section.width} × {section.height} мм</span>
                {getSectionColorLabel(section) && (
                  <span className="text-[11px] text-fg/55">{getSectionColorLabel(section)}</span>
                )}
              </div>
            </motion.div>
          ))}
          {sections.length === 0 && !showSystemPicker && (
            <div className="text-center py-8 text-fg/20 text-xs">Нажмите + чтобы добавить секцию</div>
          )}
        </div>

        {/* Sidebar project notes */}
        <div className="mt-5 pt-4 border-t border-tint/20">
          <button
            onClick={() => setNotesOpen(v => !v)}
            className="flex items-center justify-between w-full group mb-0"
          >
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40 group-hover:text-accent/70 transition-colors">
              Примечания
            </span>
            <span className={`text-accent/30 group-hover:text-accent/60 transition-all ${notesOpen ? 'rotate-180' : ''} duration-200`}>
              <ChevronRight className="w-3.5 h-3.5 rotate-90" />
            </span>
          </button>
          <AnimatePresence initial={false}>
            {notesOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2, ease: 'easeInOut' }}
                className="overflow-hidden"
              >
                <div className="space-y-2.5 pt-3">
                  <div>
                    <label className="text-[10px] text-fg/25 uppercase tracking-wider block mb-1.5">Доп. комплектующие</label>
                    <textarea
                      value={projectExtraParts}
                      onChange={e => setProjectExtraParts(e.target.value)}
                      onBlur={onSaveProjectNotes}
                      rows={2}
                      placeholder="..."
                      className="w-full bg-hi/[0.02] border border-tint/20 rounded-xl px-3 py-2 text-[11px] text-fg/60 placeholder-fg/15 resize-none focus:outline-none focus:border-accent/40 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-fg/25 uppercase tracking-wider block mb-1.5">Комментарии</label>
                    <textarea
                      value={projectComments}
                      onChange={e => setProjectComments(e.target.value)}
                      onBlur={onSaveProjectNotes}
                      rows={2}
                      placeholder="..."
                      className="w-full bg-hi/[0.02] border border-tint/20 rounded-xl px-3 py-2 text-[11px] text-fg/60 placeholder-fg/15 resize-none focus:outline-none focus:border-accent/40 transition-colors"
                    />
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {activeSectionId && (
        <div className="sm:hidden p-3 border-t border-tint/20 flex-shrink-0">
          <button onClick={() => setMobileSidebarOpen(false)}
            className="w-full py-3 rounded-xl bg-tint/20 border border-tint/40 text-accent font-bold text-sm flex items-center justify-center gap-2">
            <ChevronRight className="w-4 h-4" /> Редактировать
          </button>
        </div>
      )}
    </aside>
  );
};
