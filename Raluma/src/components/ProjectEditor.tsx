/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, Save, Plus, Trash2, FileText,
  ClipboardList, Square as WindowIcon, Palette,
  ChevronRight, Loader2, X, ArrowRight, Map,
} from 'lucide-react';
import { getProject, updateProject, createSection, updateSection, deleteSection } from '../api/projects';
import { toast } from '../store/toastStore';

import { Section, OrderItem, ProjectEditorProps, SystemType, LBL, INP, SEL, SYSTEM_COLORS, SYSTEM_ACCENT_BG, SYSTEM_PICKER_COLORS } from './editor/types';
import { apiToLocal, localToApi } from './editor/converters';
import { getSectionTypeLabel, getSectionColorLabel, SectionDivider } from './editor/FormInputs';
import { MainTab, SlideSystemTab, BookSystemTab, LiftSystemTab, CsShapeTab, DoorSystemTab } from './editor/FormTabs';
import { SlideSchemeSVG, SlideRoomViewSVG } from './editor/SlideDiagrams';

export type { SystemType };
export type { Section };

export const ProjectEditor: React.FC<ProjectEditorProps> = ({ projectId, onBack }) => {
  const [project, setProject] = useState<{ id: number; number: string; customer: string } | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [loadingProject, setLoadingProject] = useState(true);

  useEffect(() => {
    getProject(projectId).then(p => {
      setProject({ id: p.id, number: p.number, customer: p.customer });
      setProjectExtraParts(p.extra_parts || '');
      setProjectComments(p.comments || '');
      setProductionStages((p.production_stages as 1 | 2) || 1);
      setCurrentStage((p.current_stage as 1 | 2) || 1);
      setProjectStatus(p.status || '');
      setGlassStatus(p.glass_status || '');
      setGlassInvoice(p.glass_invoice || '');
      setGlassReadyDate(p.glass_ready_date || '');
      setPaintStatus(p.paint_status || '');
      setPaintShipDate(p.paint_ship_date || '');
      setPaintReceivedDate(p.paint_received_date || '');
      try { setOrderItems(p.order_items ? JSON.parse(p.order_items) : []); } catch { setOrderItems([]); }
      setSections(p.sections.map(s => apiToLocal(s)));
      setLoadingProject(false);
    }).catch(() => { setLoadingProject(false); onBack(); });
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [sectionToDelete, setSectionToDelete] = useState<Section | null>(null);
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [previewDocName, setPreviewDocName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(true);
  const [projectExtraParts, setProjectExtraParts] = useState('');
  const [projectComments, setProjectComments] = useState('');
  const [productionStages, setProductionStages] = useState<1 | 2>(1);
  const [currentStage, setCurrentStage] = useState<1 | 2>(1);
  const [projectStatus, setProjectStatus] = useState('');
  const [glassStatus, setGlassStatus] = useState('');
  const [glassInvoice, setGlassInvoice] = useState('');
  const [glassReadyDate, setGlassReadyDate] = useState('');
  const [paintStatus, setPaintStatus] = useState('');
  const [paintShipDate, setPaintShipDate] = useState('');
  const [paintReceivedDate, setPaintReceivedDate] = useState('');
  const [orderItems, setOrderItems] = useState<OrderItem[]>([]);
  const [notesOpen, setNotesOpen] = useState(false);
  const [showSystemPicker, setShowSystemPicker] = useState(false);
  const [slideSubVisible, setSlideSubVisible] = useState(false);
  const [bookSubVisible, setBookSubVisible] = useState(false);
  const [liftSubVisible, setLiftSubVisible] = useState(false);
  const [csSubVisible, setCsSubVisible] = useState(false);
  const [unsavedModalOpen, setUnsavedModalOpen] = useState(false);
  const [pendingNavTarget, setPendingNavTarget] = useState<string | null>(null);
  const handleSaveSectionRef = useRef<() => Promise<void>>(async () => {});

  const activeSection = useMemo(() =>
    sections.find(s => s.id === activeSectionId) || null,
    [sections, activeSectionId]
  );

  useEffect(() => {
    setIsDirty(false);
    setShowSystemPicker(false);
    if (activeSectionId) setMobileSidebarOpen(false);
  }, [activeSectionId]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSaveSectionRef.current();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    if (!isDirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [isDirty]);

  const defaultsForSystem = (system: SystemType, opts?: { bookSubtype?: string; liftPanels?: number; csShape?: string }): Partial<Section> => {
    switch (system) {
      case 'СЛАЙД':  return { rails: 3, firstPanelInside: 'Справа', panels: 3 };
      case 'КНИЖКА': {
        const sub = opts?.bookSubtype || 'doors';
        const hasDoors = sub === 'doors' || sub === 'doors_and_angle';
        return {
          bookSubtype: sub,
          doors: hasDoors ? 1 : undefined,
          doorSide: hasDoors ? 'Правая' : undefined,
          panels: 3,
        };
      }
      case 'ЛИФТ':   return { panels: opts?.liftPanels || 2 };
      case 'ЦС':     return { csShape: opts?.csShape || 'Прямоугольник', panels: 1 };
      case 'КОМПЛЕКТАЦИЯ': return { panels: 1, doorSystem: 'Одностворчатая', doorOpening: 'Внутрь' };
    }
  };

  const handleAddSection = async (system: SystemType, opts?: { slideRails?: 3 | 5; bookSubtype?: string; liftPanels?: number; csShape?: string }) => {
    if (!project) return;
    setShowSystemPicker(false);
    setSlideSubVisible(false);
    setBookSubVisible(false);
    setLiftSubVisible(false);
    setCsSubVisible(false);
    const extra: Partial<Section> = {};
    if (system === 'СЛАЙД' && opts?.slideRails) extra.rails = opts.slideRails;
    if (system === 'КНИЖКА' && opts?.bookSubtype) extra.bookSubtype = opts.bookSubtype;
    if (system === 'ЛИФТ' && opts?.liftPanels) extra.panels = opts.liftPanels;
    if (system === 'ЦС' && opts?.csShape) extra.csShape = opts.csShape;
    const maxNum = sections.reduce((m, sec) => Math.max(m, parseInt(sec.name.replace(/\D/g, '')) || 0), 0);
    const newSection: Section = {
      id: `tmp-${Date.now()}`,
      name: `Секция ${maxNum + 1}`,
      system,
      width: 2000, height: 2400, panels: 3, quantity: 1,
      glassType: '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
      paintingType: 'RAL стандарт', ralColor: '9016',
      cornerLeft: false, cornerRight: false,
      floorLatchesLeft: false, floorLatchesRight: false,
      profileLeftWall: false, profileLeftLockBar: false, profileLeftPBar: false,
      profileLeftHandleBar: false, profileLeftBubble: false,
      profileRightWall: false, profileRightLockBar: false, profileRightPBar: false,
      profileRightHandleBar: false, profileRightBubble: false,
      ...defaultsForSystem(system, opts),
      ...extra,
    };
    try {
      const created = await createSection(project.id, localToApi(newSection, sections.length));
      const local = apiToLocal(created);
      setSections(prev => [...prev, local]);
      setActiveSectionId(local.id);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err.response?.data?.detail || 'Не удалось создать секцию');
    }
  };

  const updateActiveSection = (updates: Partial<Section>) => {
    if (!activeSectionId) return;
    setIsDirty(true);
    setSections(sections.map(s => s.id === activeSectionId ? { ...s, ...updates } : s));
  };

  const handleSaveSection = async () => {
    if (!activeSection || !project || isSaving) return;
    const sectionId = parseInt(activeSection.id);
    if (isNaN(sectionId)) return;
    setIsSaving(true);
    const idx = sections.findIndex(s => s.id === activeSectionId);
    try {
      await updateSection(project.id, sectionId, localToApi(activeSection, idx));
      setIsDirty(false);
      toast.success('Секция сохранена');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err.response?.data?.detail || 'Не удалось сохранить секцию');
    } finally {
      setIsSaving(false);
    }
  };

  handleSaveSectionRef.current = handleSaveSection;

  const requestNavigate = (targetId: string | null) => {
    if (isDirty) {
      setPendingNavTarget(targetId);
      setUnsavedModalOpen(true);
    } else {
      setActiveSectionId(targetId);
    }
  };

  const confirmUnsavedSave = async () => {
    await handleSaveSection();
    setUnsavedModalOpen(false);
    setActiveSectionId(pendingNavTarget);
    setPendingNavTarget(null);
  };

  const confirmUnsavedDiscard = () => {
    setIsDirty(false);
    setUnsavedModalOpen(false);
    setActiveSectionId(pendingNavTarget);
    setPendingNavTarget(null);
  };

  const handleDeleteSection = async () => {
    if (!sectionToDelete || !project) return;
    try {
      const sectionId = parseInt(sectionToDelete.id);
      if (!isNaN(sectionId)) await deleteSection(project.id, sectionId);
      setSections(sections.filter(s => s.id !== sectionToDelete.id));
      if (activeSectionId === sectionToDelete.id) setActiveSectionId(null);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err.response?.data?.detail || 'Не удалось удалить секцию');
    } finally {
      setIsDeleteModalOpen(false);
      setSectionToDelete(null);
    }
  };

  const openPreview = (name: string) => { setPreviewDocName(name); setIsPreviewModalOpen(true); };

  const handleSaveProjectNotes = async () => {
    if (!project) return;
    try {
      await updateProject(project.id, {
        extra_parts: projectExtraParts,
        comments: projectComments,
        production_stages: productionStages,
        current_stage: currentStage,
        status: projectStatus || undefined,
        glass_status: glassStatus || undefined,
        glass_invoice: glassInvoice || undefined,
        glass_ready_date: glassReadyDate || undefined,
        paint_status: paintStatus || undefined,
        paint_ship_date: paintShipDate || undefined,
        paint_received_date: paintReceivedDate || undefined,
        order_items: orderItems.length ? JSON.stringify(orderItems) : undefined,
      });
    } catch {
      toast.error('Не удалось сохранить данные проекта');
    }
  };

  const saveStatus = async (updates: Partial<{ status: string; glass_status: string; glass_invoice: string; glass_ready_date: string; paint_status: string; paint_ship_date: string; paint_received_date: string; current_stage: number; order_items: string; production_stages: number; }>) => {
    if (!project) return;
    try { await updateProject(project.id, updates); }
    catch { toast.error('Не удалось сохранить'); }
  };

  const addOrderItem = () => {
    const newItem: OrderItem = { id: `oi-${Date.now()}`, name: '', invoice: '', paidDate: '', deliveredDate: '' };
    const next = [...orderItems, newItem];
    setOrderItems(next);
    saveStatus({ order_items: JSON.stringify(next) });
  };

  const removeOrderItem = (id: string) => {
    const next = orderItems.filter(oi => oi.id !== id);
    setOrderItems(next);
    saveStatus({ order_items: next.length > 0 ? JSON.stringify(next) : undefined });
  };

  const updateOrderItem = (id: string, field: keyof OrderItem, value: string) => {
    const next = orderItems.map(oi => oi.id === id ? { ...oi, [field]: value } : oi);
    setOrderItems(next);
  };

  const saveOrderItems = () => {
    saveStatus({ order_items: orderItems.length > 0 ? JSON.stringify(orderItems) : undefined });
  };

  const renderSectionContent = () => {
    if (!activeSection) return null;
    return (
      <div className="space-y-5">
        <div>
          <SectionDivider label="Основное" />
          <div className="mt-3">
            <MainTab s={activeSection} update={updateActiveSection} />
          </div>
        </div>

        {activeSection.system === 'СЛАЙД' && (
          <div>
            <SectionDivider label="Система · Профили · Фурнитура" />
            <div className="mt-3">
              <SlideSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'КНИЖКА' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-3">
              <BookSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'ЛИФТ' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-3">
              <LiftSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'ЦС' && (
          <div>
            <SectionDivider label="Форма" />
            <div className="mt-3">
              <CsShapeTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'КОМПЛЕКТАЦИЯ' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-3">
              <DoorSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        <div>
          <SectionDivider label="Примечания к секции" />
          <div className="mt-3">
            <div className="space-y-1.5">
              <label className={LBL}>Комментарии</label>
              <textarea
                value={activeSection.comments || ''}
                onChange={e => updateActiveSection({ comments: e.target.value || undefined })}
                rows={2}
                placeholder="Дополнительные комментарии..."
                className="w-full bg-white/8 border border-[#2a7a8a]/30 rounded-xl px-3 py-2 outline-none focus:border-[#4fd1c5]/50 transition-all text-white resize-y placeholder-white/20 text-sm"
              />
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loadingProject) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0c1d2d]">
        <Loader2 className="w-10 h-10 text-[#4fd1c5] animate-spin" />
      </div>
    );
  }

  if (!project) return null;

  return (
    <div className="min-h-screen flex flex-col bg-[#0c1d2d]">

      {/* Header */}
      <div className="bg-[#1a4b54]/40 border-b border-[#2a7a8a]/30 px-4 sm:px-8 py-3 sm:py-4 flex items-center justify-between z-20 flex-shrink-0 gap-3">
        <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
          <button onClick={onBack} className="flex items-center gap-2 text-white/40 hover:text-[#4fd1c5] transition-colors group flex-shrink-0">
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span className="hidden sm:inline text-sm font-bold uppercase tracking-wider">Проекты</span>
          </button>
          <div className="hidden sm:block h-6 w-px bg-[#2a7a8a]/20 flex-shrink-0" />
          <div className="flex items-center gap-2 min-w-0 overflow-hidden">
            <span className="text-sm sm:text-xl font-bold whitespace-nowrap">№ {project.number}</span>
            <div className="hidden lg:flex items-center gap-2 flex-shrink-0">
              <span className="text-white/20">·</span>
              <span className="text-white/60 truncate max-w-[200px]">{project.customer}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            className="sm:hidden p-2.5 rounded-xl bg-[#2a7a8a]/15 border border-[#2a7a8a]/30 text-[#4fd1c5] hover:bg-[#2a7a8a]/30 transition-colors"
            onClick={() => setMobileSidebarOpen(v => !v)}
            aria-label="Секции"
          >
            <ClipboardList className="w-4 h-4" />
          </button>
          <button onClick={async () => { await handleSaveSection(); onBack(); }}
            className={`flex items-center gap-2 px-3 sm:px-6 py-2 sm:py-2.5 text-white font-bold rounded-xl transition-all shadow-lg ${
              isDirty
                ? 'bg-amber-500 hover:bg-amber-400 shadow-amber-500/20'
                : 'bg-[#00b894] hover:bg-[#00d1a7] shadow-[#00b894]/20'
            }`}>
            {isSaving ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">{isDirty ? 'Сохранить и выйти' : 'Выйти'}</span>
          </button>
        </div>
      </div>

      {/* Document buttons sub-bar — only visible at project level (no active section) */}
      {!activeSectionId && (
        <div className="hidden sm:flex items-center gap-1 px-4 sm:px-8 py-2 border-b border-[#2a7a8a]/20 bg-[#1a4b54]/20 flex-shrink-0">
          {[
            { name: 'Спецификация', icon: FileText },
            { name: 'Накладная', icon: ClipboardList },
            { name: 'Заказ стекла', icon: WindowIcon },
            { name: 'Заявка покр.', icon: Palette },
            { name: 'Производственный лист', icon: ClipboardList },
            { name: 'Схема', icon: Map },
          ].map(doc => (
            <button key={doc.name} onClick={() => openPreview(doc.name)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:bg-[#2a7a8a]/20 hover:border-[#2a7a8a]/40 transition-all group">
              <doc.icon className="w-3 h-3 text-[#4fd1c5]/50 group-hover:text-[#4fd1c5] transition-colors flex-shrink-0" />
              <span className="text-[10px] font-bold text-white/40 group-hover:text-white transition-colors whitespace-nowrap">{doc.name}</span>
            </button>
          ))}
        </div>
      )}

      {/* Body */}
      <div className="flex-1 flex flex-col sm:flex-row min-h-0 overflow-hidden">

        {/* Left: sections list */}
        <aside className={`border-r border-[#2a7a8a]/30 flex-col bg-[#0c1d2d]/80 backdrop-blur-sm z-10 flex-shrink-0 w-full sm:w-[260px] ${mobileSidebarOpen ? 'flex' : 'hidden sm:flex'}`}>
          <div className="p-5 flex-1 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40">Секции</h3>
              <button
                onClick={() => setShowSystemPicker(v => !v)}
                className={`p-1.5 rounded-lg border transition-colors ${
                  showSystemPicker
                    ? 'bg-[#4fd1c5]/20 border-[#4fd1c5]/40 text-[#4fd1c5]'
                    : 'bg-[#2a7a8a]/20 border-[#2a7a8a]/30 text-[#4fd1c5] hover:bg-[#2a7a8a]/40'
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
                    <div className={`rounded-xl border overflow-hidden transition-all ${slideSubVisible ? 'border-[#2a7a8a]/50' : 'border-[#2a7a8a]/25'}`}>
                      <button onClick={() => setSlideSubVisible(v => !v)}
                        className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['СЛАЙД']}`}>
                        <span>СЛАЙД</span>
                        <ChevronRight className={`w-3.5 h-3.5 transition-transform ${slideSubVisible ? 'rotate-90' : ''}`} />
                      </button>
                      {slideSubVisible && (
                        <div className="grid grid-cols-2 border-t border-[#2a7a8a]/25">
                          <button onClick={() => handleAddSection('СЛАЙД', { slideRails: 3 })}
                            className={`py-2 font-bold text-[11px] transition-all border-r border-[#2a7a8a]/25 ${SYSTEM_PICKER_COLORS['СЛАЙД']}`}>
                            Стандарт 1 ряд
                          </button>
                          <button onClick={() => handleAddSection('СЛАЙД', { slideRails: 5 })}
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
                            <button onClick={() => handleAddSection('КНИЖКА', { bookSubtype: 'doors' })}
                              className={`py-2 font-bold text-[11px] transition-all border-r border-b border-[#7a4a2a]/25 ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                              С дверями
                            </button>
                            <button onClick={() => handleAddSection('КНИЖКА', { bookSubtype: 'angle' })}
                              className={`py-2 font-bold text-[11px] transition-all border-b border-[#7a4a2a]/25 ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                              С углом
                            </button>
                          </div>
                          <button onClick={() => handleAddSection('КНИЖКА', { bookSubtype: 'doors_and_angle' })}
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
                            <button key={n} onClick={() => handleAddSection('ЛИФТ', { liftPanels: n })}
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
                            <button key={shape} onClick={() => handleAddSection('ЦС', { csShape: shape })}
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
                    <button onClick={() => handleAddSection('КОМПЛЕКТАЦИЯ')}
                      className={`py-2.5 rounded-xl border font-bold text-[11px] transition-all ${SYSTEM_PICKER_COLORS['КОМПЛЕКТАЦИЯ']}`}>
                      КОМПЛЕКТАЦИЯ
                    </button>
                  </div>
                  <div className="h-px bg-[#2a7a8a]/20" />
                </motion.div>
              )}
            </AnimatePresence>

            <div className="space-y-2">
              {sections.map(section => (
                <motion.div key={section.id} layoutId={section.id}
                  onClick={() => requestNavigate(section.id)}
                  className={`relative group p-4 rounded-2xl border transition-all cursor-pointer overflow-hidden ${
                    activeSectionId === section.id
                      ? 'bg-[#2a7a8a]/20 border-[#4fd1c5]/50 shadow-lg shadow-[#4fd1c5]/5'
                      : 'bg-white/[0.02] border-[#2a7a8a]/10 hover:border-[#2a7a8a]/40'
                  }`}
                >
                  <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${SYSTEM_ACCENT_BG[section.system]} transition-opacity ${
                    activeSectionId === section.id ? 'opacity-80' : 'opacity-30 group-hover:opacity-60'
                  }`} />
                  <div className="flex justify-between items-start mb-2">
                    <span className={`text-sm font-bold leading-snug ${activeSectionId === section.id ? 'text-[#4fd1c5]' : 'text-white/80'}`}>
                      {section.name}
                    </span>
                    <button onClick={e => { e.stopPropagation(); setSectionToDelete(section); setIsDeleteModalOpen(true); }}
                      className="p-1 rounded-lg hover:bg-red-500/20 text-red-400 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0 ml-1">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${SYSTEM_COLORS[section.system]}`}>
                      {section.system}
                    </span>
                    {getSectionTypeLabel(section) && (
                      <span className="text-[11px] text-white/40 font-medium">{getSectionTypeLabel(section)}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[11px] font-mono text-white/35">{section.width} × {section.height} мм</span>
                    {getSectionColorLabel(section) && (
                      <span className="text-[11px] text-white/35">{getSectionColorLabel(section)}</span>
                    )}
                  </div>
                </motion.div>
              ))}
              {sections.length === 0 && !showSystemPicker && (
                <div className="text-center py-8 text-white/20 text-xs">Нажмите + чтобы добавить секцию</div>
              )}
            </div>

            {/* Sidebar project notes */}
            <div className="mt-5 pt-4 border-t border-[#2a7a8a]/20">
              <button
                onClick={() => setNotesOpen(v => !v)}
                className="flex items-center justify-between w-full group mb-0"
              >
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 group-hover:text-[#4fd1c5]/70 transition-colors">
                  Примечания
                </span>
                <span className={`text-[#4fd1c5]/30 group-hover:text-[#4fd1c5]/60 transition-all ${notesOpen ? 'rotate-180' : ''} duration-200`}>
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
                        <label className="text-[10px] text-white/25 uppercase tracking-wider block mb-1.5">Доп. комплектующие</label>
                        <textarea
                          value={projectExtraParts}
                          onChange={e => setProjectExtraParts(e.target.value)}
                          onBlur={handleSaveProjectNotes}
                          rows={2}
                          placeholder="..."
                          className="w-full bg-white/[0.02] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-[11px] text-white/60 placeholder-white/15 resize-none focus:outline-none focus:border-[#4fd1c5]/40 transition-colors"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-white/25 uppercase tracking-wider block mb-1.5">Комментарии</label>
                        <textarea
                          value={projectComments}
                          onChange={e => setProjectComments(e.target.value)}
                          onBlur={handleSaveProjectNotes}
                          rows={2}
                          placeholder="..."
                          className="w-full bg-white/[0.02] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-[11px] text-white/60 placeholder-white/15 resize-none focus:outline-none focus:border-[#4fd1c5]/40 transition-colors"
                        />
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {activeSectionId && (
            <div className="sm:hidden p-3 border-t border-[#2a7a8a]/20 flex-shrink-0">
              <button onClick={() => setMobileSidebarOpen(false)}
                className="w-full py-3 rounded-xl bg-[#2a7a8a]/20 border border-[#2a7a8a]/40 text-[#4fd1c5] font-bold text-sm flex items-center justify-center gap-2">
                <ChevronRight className="w-4 h-4" /> Редактировать
              </button>
            </div>
          )}
        </aside>

        {/* Right: editor */}
        <main className={`flex-1 overflow-y-auto bg-[#0c1d2d]/50 ${mobileSidebarOpen ? 'hidden sm:block' : 'block'}`}>
          <AnimatePresence mode="wait">
            {!activeSection ? (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="p-4 sm:p-8 max-w-3xl mx-auto w-full">

                {productionStages === 2 && (
                  <div className="flex items-center gap-3 mb-6">
                    <span className="text-xs font-bold text-amber-300/70 border border-amber-500/20 bg-amber-500/5 rounded-xl px-3 py-1.5">
                      Производство в 2 этапа
                    </span>
                    <div className="flex gap-2">
                      {([1, 2] as const).map(n => (
                        <button key={n} onClick={() => { setCurrentStage(n); saveStatus({ current_stage: n }); }}
                          className={`px-4 py-1.5 rounded-xl border font-bold text-sm transition-all ${
                            currentStage === n
                              ? 'bg-[#4fd1c5]/15 border-[#4fd1c5]/40 text-[#4fd1c5]'
                              : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/40'
                          }`}>
                          Этап {n}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Status */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40">Статус</span>
                  </div>
                  <select value={projectStatus} onChange={e => { setProjectStatus(e.target.value); saveStatus({ status: e.target.value }); }} className={SEL}>
                    <option>РАСЧЕТ</option>
                    <option>В работе</option>
                    <option>Запущен в производство</option>
                    <option>Готов</option>
                    <option>Отгружен полностью</option>
                    <option>Отгружен частично</option>
                    <option>Отгружен 1 этап</option>
                    <option>Рекламация</option>
                    <option>Архив</option>
                  </select>
                </div>

                {/* Glass */}
                {!(productionStages === 2 && currentStage === 1) && (
                  <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 block mb-4">Стекла</span>
                    <div className="mb-4">
                      <select value={glassStatus} onChange={e => { setGlassStatus(e.target.value); saveStatus({ glass_status: e.target.value }); }} className={SEL}>
                        <option>Без стекла</option>
                        <option>Стекла заказаны</option>
                        <option>Стекла в цеху</option>
                      </select>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <label className={LBL}>Счёт №</label>
                        <input value={glassInvoice} onChange={e => setGlassInvoice(e.target.value)}
                          onBlur={() => saveStatus({ glass_invoice: glassInvoice || undefined })}
                          className={INP} placeholder="Номер счёта" />
                      </div>
                      <div className="space-y-1">
                        <label className={LBL}>Ориентир готовности</label>
                        <input type="date" value={glassReadyDate} onChange={e => { setGlassReadyDate(e.target.value); saveStatus({ glass_ready_date: e.target.value || undefined }); }}
                          className={INP} />
                      </div>
                    </div>
                  </div>
                )}

                {/* Paint */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 block mb-4">Покраска</span>
                  <div className="mb-4">
                    <select value={paintStatus} onChange={e => { setPaintStatus(e.target.value); saveStatus({ paint_status: e.target.value }); }} className={SEL}>
                      <option>Без покраски</option>
                      <option>Задание на покраску в цеху</option>
                      <option>Отгружен на покраску</option>
                      <option>Получен с покраски</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className={LBL}>Отгружен на покраску</label>
                      <input type="date" value={paintShipDate} onChange={e => { setPaintShipDate(e.target.value); saveStatus({ paint_ship_date: e.target.value || undefined }); }}
                        className={INP} />
                    </div>
                    <div className="space-y-1">
                      <label className={LBL}>Получен с покраски</label>
                      <input type="date" value={paintReceivedDate} onChange={e => { setPaintReceivedDate(e.target.value); saveStatus({ paint_received_date: e.target.value || undefined }); }}
                        className={INP} />
                    </div>
                  </div>
                </div>

                {/* Order items */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40">Заказ доп. комплектующих</span>
                    <button onClick={addOrderItem}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#2a7a8a]/20 border border-[#2a7a8a]/40 text-[#4fd1c5] text-xs font-bold hover:bg-[#2a7a8a]/40 transition-colors">
                      <Plus className="w-3.5 h-3.5" /> Добавить
                    </button>
                  </div>
                  {orderItems.length > 0 && (
                    <div className="space-y-2">
                      <div className="hidden sm:grid grid-cols-[1fr_1fr_120px_120px_32px] gap-2 mb-1">
                        {['Название','Счёт','Оплачен','Доставлен в цех',''].map((h, i) => (
                          <span key={i} className="text-[9px] font-bold uppercase tracking-widest text-white/25">{h}</span>
                        ))}
                      </div>
                      {orderItems.map(item => (
                        <div key={item.id} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_120px_120px_32px] gap-2 items-center">
                          <input value={item.name} onChange={e => updateOrderItem(item.id,'name',e.target.value)}
                            onBlur={saveOrderItems} placeholder="Название"
                            className="bg-white/[0.04] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-xs text-white/70 outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                          <input value={item.invoice} onChange={e => updateOrderItem(item.id,'invoice',e.target.value)}
                            onBlur={saveOrderItems} placeholder="Счёт"
                            className="bg-white/[0.04] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-xs text-white/70 outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                          <input type="date" value={item.paidDate} onChange={e => { updateOrderItem(item.id,'paidDate',e.target.value); saveOrderItems(); }}
                            className="bg-white/[0.04] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-xs text-white/70 outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                          <input type="date" value={item.deliveredDate} onChange={e => { updateOrderItem(item.id,'deliveredDate',e.target.value); saveOrderItems(); }}
                            className="bg-white/[0.04] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-xs text-white/70 outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                          <button onClick={() => removeOrderItem(item.id)}
                            className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-red-500/20 text-red-400/60 hover:text-red-400 transition-colors">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {orderItems.length === 0 && (
                    <p className="text-xs text-white/20 text-center py-4">Нажмите «Добавить» для добавления позиции</p>
                  )}
                </div>

                {/* Notes */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 mb-5">Примечания к проекту</p>
                  <div className="space-y-4">
                    <div>
                      <label className="text-[11px] text-white/35 uppercase tracking-wider block mb-2">Доп. комплектующие</label>
                      <textarea value={projectExtraParts} onChange={e => setProjectExtraParts(e.target.value)}
                        onBlur={handleSaveProjectNotes} rows={3} placeholder="Перечислите дополнительные комплектующие..."
                        className="w-full bg-white/[0.03] border border-[#2a7a8a]/25 rounded-2xl px-4 py-3 text-sm text-white/70 placeholder-white/20 resize-none focus:outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                    </div>
                    <div>
                      <label className="text-[11px] text-white/35 uppercase tracking-wider block mb-2">Комментарии</label>
                      <textarea value={projectComments} onChange={e => setProjectComments(e.target.value)}
                        onBlur={handleSaveProjectNotes} rows={3} placeholder="Любые дополнительные комментарии..."
                        className="w-full bg-white/[0.03] border border-[#2a7a8a]/25 rounded-2xl px-4 py-3 text-sm text-white/70 placeholder-white/20 resize-none focus:outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                    </div>
                  </div>
                </div>

                <button onClick={() => setMobileSidebarOpen(true)}
                  className="sm:hidden mt-4 w-full flex items-center justify-center gap-2 px-6 py-3 bg-white/[0.03] border border-[#2a7a8a]/20 hover:bg-[#2a7a8a]/20 text-white/40 hover:text-[#4fd1c5] text-sm font-bold rounded-xl transition-all">
                  <ClipboardList className="w-4 h-4" /> Список секций
                </button>
              </motion.div>
            ) : (
              <motion.div key={activeSection.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                className="p-4 sm:p-6 w-full max-w-4xl xl:max-w-[1380px] mx-auto">

                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 sm:mb-5 gap-3">
                  <div>
                    <button onClick={() => requestNavigate(null)}
                      className="flex items-center gap-1.5 text-white/30 hover:text-[#4fd1c5] transition-colors group mb-3 text-xs font-bold uppercase tracking-wider">
                      <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
                      К проекту
                    </button>
                    <h2 className="text-xl sm:text-2xl font-bold mb-1.5">{activeSection.name}</h2>
                    <span className={`px-3 py-1 rounded-lg text-[11px] font-bold border ${SYSTEM_COLORS[activeSection.system]}`}>
                      {activeSection.system === 'СЛАЙД'
                        ? `СЛАЙД стандарт ${activeSection.rails === 5 ? '2 ряда от центра' : '1 ряд'}`
                        : activeSection.system === 'КНИЖКА' && activeSection.bookSubtype
                          ? `КНИЖКА ${activeSection.bookSubtype === 'doors' ? 'с дверями' : activeSection.bookSubtype === 'angle' ? 'с углом' : 'с дверями и углом'}`
                          : activeSection.system === 'ЛИФТ'
                            ? `ЛИФТ · ${activeSection.panels ?? 2} пан.`
                            : activeSection.system === 'ЦС' && activeSection.csShape
                              ? `ЦС · ${activeSection.csShape}`
                              : activeSection.system}
                    </span>
                  </div>
                </div>

                <div className={activeSection.system === 'СЛАЙД' ? 'xl:flex xl:gap-5 xl:items-start' : ''}>

                  <div className={activeSection.system === 'СЛАЙД' ? 'xl:flex-1 xl:min-w-0' : ''}>
                    <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/35 rounded-2xl sm:rounded-[2rem] p-4 sm:p-6 mb-4">
                      {renderSectionContent()}
                    </div>

                    {activeSection.system === 'СЛАЙД' && (
                      <div className="xl:hidden space-y-4 mb-4">
                        <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 overflow-x-auto">
                          <div className="flex items-center justify-between mb-4 min-w-[360px]">
                            <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Вид из помещения</h4>
                            <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">{activeSection.panels} пан. · {activeSection.width}×{activeSection.height}</span>
                          </div>
                          <div className="flex justify-center py-2"><SlideRoomViewSVG section={activeSection} /></div>
                        </div>
                        <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 overflow-x-auto">
                          <div className="flex items-center justify-between mb-5 min-w-[360px]">
                            <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Схема · Вид сверху</h4>
                            <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">{activeSection.rails ?? 3}-рельс · {activeSection.panels} пан.</span>
                          </div>
                          <div className="flex justify-center py-4"><SlideSchemeSVG section={activeSection} /></div>
                        </div>
                      </div>
                    )}

                    <div className="flex gap-4">
                      <button onClick={handleSaveSection} disabled={isSaving}
                        className={`flex-1 py-4 rounded-2xl text-white font-bold transition-all flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed ${
                          isDirty
                            ? 'bg-amber-500 hover:bg-amber-400 shadow-lg shadow-amber-500/20'
                            : 'bg-[#00b894] hover:bg-[#00d1a7] shadow-lg shadow-[#00b894]/20'
                        }`}>
                        {isSaving ? (
                          <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : isDirty ? (
                          <><Save className="w-4 h-4" /> Сохранить изменения</>
                        ) : 'Сохранить секцию'}
                      </button>
                    </div>
                  </div>

                  {activeSection.system === 'СЛАЙД' && (
                    <div className="hidden xl:flex xl:flex-col xl:gap-3 xl:w-[420px] xl:flex-shrink-0 xl:sticky xl:top-4">
                      <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl p-4">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Вид из помещения</span>
                          <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">{activeSection.panels} пан. · {activeSection.width}×{activeSection.height}</span>
                        </div>
                        <SlideRoomViewSVG section={activeSection} />
                      </div>
                      <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl p-4">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Схема · Вид сверху</span>
                          <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">{activeSection.rails ?? 3}-рельс · {activeSection.panels} пан.</span>
                        </div>
                        <SlideSchemeSVG section={activeSection} />
                      </div>
                    </div>
                  )}

                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>

      {/* Delete Section Modal */}
      <AnimatePresence>
        {isDeleteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsDeleteModalOpen(false)} className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-[#122433] border border-red-500/30 rounded-[2rem] p-6 sm:p-8 shadow-2xl z-10">
              <button onClick={() => setIsDeleteModalOpen(false)} className="absolute right-6 top-6 text-white/20 hover:text-white transition-colors">
                <X className="w-6 h-6" />
              </button>
              <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-6">
                <Trash2 className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Удалить секцию?</h2>
              <p className="text-white/60 leading-relaxed mb-8">
                Секция <span className="text-white font-bold">{sectionToDelete?.name}</span> будет удалена безвозвратно.
              </p>
              <div className="flex gap-4">
                <button onClick={() => setIsDeleteModalOpen(false)} className="flex-1 py-4 rounded-2xl bg-white/5 hover:bg-white/10 font-bold transition-all">Отмена</button>
                <button onClick={handleDeleteSection} className="flex-1 py-4 rounded-2xl bg-red-500 hover:bg-red-400 text-white font-bold transition-all">Удалить</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Unsaved Changes Modal */}
      <AnimatePresence>
        {unsavedModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => { setUnsavedModalOpen(false); setPendingNavTarget(null); }}
              className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-[#122433] border border-amber-500/30 rounded-[2rem] p-6 sm:p-8 shadow-2xl z-10">
              <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-6">
                <Save className="w-8 h-8 text-amber-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Несохранённые изменения</h2>
              <p className="text-white/60 leading-relaxed mb-8">
                Секция <span className="text-white font-bold">{activeSection?.name}</span> содержит несохранённые изменения.
              </p>
              <div className="flex gap-3 flex-col sm:flex-row">
                <button onClick={() => { setUnsavedModalOpen(false); setPendingNavTarget(null); }}
                  className="flex-1 py-3 rounded-2xl bg-white/5 hover:bg-white/10 font-bold transition-all text-sm">
                  Остаться
                </button>
                <button onClick={confirmUnsavedDiscard}
                  className="flex-1 py-3 rounded-2xl bg-white/5 hover:bg-white/10 font-bold transition-all text-sm text-white/50">
                  Не сохранять
                </button>
                <button onClick={confirmUnsavedSave} disabled={isSaving}
                  className="flex-1 py-3 rounded-2xl bg-amber-500 hover:bg-amber-400 text-white font-bold transition-all text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {isSaving
                    ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    : <><Save className="w-4 h-4" /> Сохранить</>
                  }
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Document Preview Modal */}
      <AnimatePresence>
        {isPreviewModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsPreviewModalOpen(false)} className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-4xl bg-[#1a4b54] border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2.5rem] shadow-2xl overflow-hidden flex flex-col max-h-[95vh] z-10">
              <div className="px-5 py-5 sm:px-10 sm:py-7 border-b border-[#2a7a8a]/20 flex items-center justify-between flex-shrink-0">
                <h2 className="text-2xl font-bold">{previewDocName}</h2>
                <button onClick={() => setIsPreviewModalOpen(false)} className="text-white/20 hover:text-white transition-colors">
                  <X className="w-6 h-6" />
                </button>
              </div>
              <div className="flex-1 p-4 sm:p-10 overflow-y-auto bg-black/20">
                <div className="aspect-[1/1.414] w-full bg-white rounded-lg shadow-inner p-5 sm:p-12 text-black flex flex-col">
                  <div className="flex justify-between items-start border-b-2 border-black pb-8 mb-8">
                    <div>
                      <h1 className="text-4xl font-black uppercase tracking-tighter">Ралюма</h1>
                      <p className="text-xs font-bold uppercase tracking-widest text-black/40">
                        {previewDocName} · {activeSection?.system ?? '—'}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold">Проект № {project.number}</p>
                      <p className="text-xs text-black/60">{project.customer}</p>
                      <p className="text-xs text-black/40">{new Date().toLocaleDateString('ru-RU')}</p>
                    </div>
                  </div>
                  <div className="flex-1 border-2 border-dashed border-black/10 rounded-xl flex items-center justify-center">
                    <div className="text-center">
                      <FileText className="w-16 h-16 text-black/10 mx-auto mb-4" />
                      <p className="text-sm font-medium text-black/40">Визуализация в разработке</p>
                      <p className="text-xs text-black/20 mt-1">{sections.length} секц. · {activeSection ? activeSection.name : '—'}</p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="px-5 py-4 sm:px-10 sm:py-6 bg-black/40 border-t border-[#2a7a8a]/20 flex justify-end gap-4 flex-shrink-0">
                <button onClick={() => setIsPreviewModalOpen(false)} className="px-8 py-3 rounded-xl bg-white/5 hover:bg-white/10 font-bold transition-all">Закрыть</button>
                <button className="px-8 py-3 rounded-xl bg-[#00b894] hover:bg-[#00d1a7] text-white font-bold transition-all">
                  <ArrowRight className="w-4 h-4 inline mr-2" />Скачать PDF
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
