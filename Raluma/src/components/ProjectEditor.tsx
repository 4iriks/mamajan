/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, Save, Plus, Trash2, FileText,
  ClipboardList, Square as WindowIcon, Palette,
  Loader2, X, ArrowRight, Map,
} from 'lucide-react';
import { getProject, updateProject, createSection, updateSection, deleteSection } from '../api/projects';
import ProductionSheetModal from './ProductionSheetModal';
import { toast } from '../store/toastStore';

import { Section, OrderItem, ProjectEditorProps, SystemType, LBL, INP, SEL } from './editor/types';
import { apiToLocal, localToApi } from './editor/converters';
import { EditorSidebar } from './editor/EditorSidebar';
import { SectionFormWrapper } from './editor/SectionFormWrapper';

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
  const [unsavedModalOpen, setUnsavedModalOpen] = useState(false);
  const [pendingNavTarget, setPendingNavTarget] = useState<string | null>(null);

  const activeSection = useMemo(() =>
    sections.find(s => s.id === activeSectionId) || null,
    [sections, activeSectionId]
  );

  useEffect(() => {
    setIsDirty(false);
    if (activeSectionId) setMobileSidebarOpen(false);
  }, [activeSectionId]);


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
      threshold: 'Стандартный анод',
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

  if (loadingProject) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-page">
        <Loader2 className="w-10 h-10 text-accent animate-spin" />
      </div>
    );
  }

  if (!project) return null;

  return (
    <div className="min-h-screen flex flex-col bg-page">

      {/* Header */}
      <div className="bg-surface/40 border-b border-tint/30 px-4 sm:px-8 py-3 sm:py-4 flex items-center justify-between z-20 flex-shrink-0 gap-3">
        <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
          <button onClick={onBack} className="flex items-center gap-2 text-fg/40 hover:text-accent transition-colors group flex-shrink-0">
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span className="hidden sm:inline text-sm font-bold uppercase tracking-wider">Проекты</span>
          </button>
          <div className="hidden sm:block h-6 w-px bg-tint/20 flex-shrink-0" />
          <div className="flex items-center gap-2 min-w-0 overflow-hidden">
            <span className="text-sm sm:text-xl font-bold whitespace-nowrap">№ {project.number}</span>
            <div className="hidden lg:flex items-center gap-2 flex-shrink-0">
              <span className="text-fg/20">·</span>
              <span className="text-fg/60 truncate max-w-[200px]">{project.customer}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            className="sm:hidden p-2.5 rounded-xl bg-tint/15 border border-tint/30 text-accent hover:bg-tint/30 transition-colors"
            onClick={() => setMobileSidebarOpen(v => !v)}
            aria-label="Секции"
          >
            <ClipboardList className="w-4 h-4" />
          </button>
          <button onClick={async () => { await handleSaveSection(); onBack(); }}
            className={`flex items-center gap-2 px-3 sm:px-6 py-2 sm:py-2.5 text-white font-bold rounded-xl transition-all shadow-lg ${
              isDirty
                ? 'bg-amber-500 hover:bg-amber-400 shadow-amber-500/20'
                : 'bg-primary hover:bg-primary-h shadow-primary/20'
            }`}>
            {isSaving ? (
              <div className="w-4 h-4 border-2 border-hi/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">{isDirty ? 'Сохранить и выйти' : 'Выйти'}</span>
          </button>
        </div>
      </div>

      {/* Document buttons sub-bar — only visible at project level (no active section) */}
      {!activeSectionId && (
        <div className="hidden sm:flex items-center gap-1 px-4 sm:px-8 py-2 border-b border-tint/20 bg-surface/20 flex-shrink-0">
          {[
            { name: 'Спецификация', icon: FileText },
            { name: 'Накладная', icon: ClipboardList },
            { name: 'Заказ стекла', icon: WindowIcon },
            { name: 'Заявка покр.', icon: Palette },
            { name: 'Производственный лист', icon: ClipboardList },
            { name: 'Схема', icon: Map },
          ].map(doc => (
            <button key={doc.name} onClick={() => openPreview(doc.name)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-hi/[0.03] border border-hi/[0.06] hover:bg-tint/20 hover:border-tint/40 transition-all group">
              <doc.icon className="w-3 h-3 text-accent/50 group-hover:text-accent transition-colors flex-shrink-0" />
              <span className="text-[10px] font-bold text-fg/40 group-hover:text-fg transition-colors whitespace-nowrap">{doc.name}</span>
            </button>
          ))}
        </div>
      )}

      {/* Body */}
      <div className="flex-1 flex flex-col sm:flex-row min-h-0 overflow-hidden">

        <EditorSidebar
          sections={sections}
          activeSectionId={activeSectionId}
          onSelectSection={requestNavigate}
          onAddSection={handleAddSection}
          onDeleteSection={section => { setSectionToDelete(section); setIsDeleteModalOpen(true); }}
          mobileSidebarOpen={mobileSidebarOpen}
          setMobileSidebarOpen={setMobileSidebarOpen}
          projectExtraParts={projectExtraParts}
          setProjectExtraParts={setProjectExtraParts}
          projectComments={projectComments}
          setProjectComments={setProjectComments}
          onSaveProjectNotes={handleSaveProjectNotes}
        />

        {/* Right: editor */}
        <main className={`flex-1 overflow-y-auto bg-page/50 ${mobileSidebarOpen ? 'hidden sm:block' : 'block'}`}>
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
                              ? 'bg-accent/15 border-accent/40 text-accent'
                              : 'bg-black/10 border-tint/20 text-fg/70 hover:border-tint/40'
                          }`}>
                          Этап {n}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Status */}
                <div className="bg-surface/40 border border-tint/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40">Статус</span>
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
                  <div className="bg-surface/40 border border-tint/30 rounded-2xl p-5 sm:p-6 mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40 block mb-4">Стекла</span>
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
                <div className="bg-surface/40 border border-tint/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40 block mb-4">Покраска</span>
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
                <div className="bg-surface/40 border border-tint/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40">Заказ доп. комплектующих</span>
                    <button onClick={addOrderItem}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-tint/20 border border-tint/40 text-accent text-xs font-bold hover:bg-tint/40 transition-colors">
                      <Plus className="w-3.5 h-3.5" /> Добавить
                    </button>
                  </div>
                  {orderItems.length > 0 && (
                    <div className="space-y-2">
                      <div className="hidden sm:grid grid-cols-[1fr_1fr_120px_120px_32px] gap-2 mb-1">
                        {['Название','Счёт','Оплачен','Доставлен в цех',''].map((h, i) => (
                          <span key={i} className="text-[9px] font-bold uppercase tracking-widest text-fg/25">{h}</span>
                        ))}
                      </div>
                      {orderItems.map(item => (
                        <div key={item.id} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_120px_120px_32px] gap-2 items-center">
                          <input value={item.name} onChange={e => updateOrderItem(item.id,'name',e.target.value)}
                            onBlur={saveOrderItems} placeholder="Название"
                            className="bg-hi/[0.04] border border-tint/20 rounded-xl px-3 py-2 text-xs text-fg/70 outline-none focus:border-accent/40 transition-colors" />
                          <input value={item.invoice} onChange={e => updateOrderItem(item.id,'invoice',e.target.value)}
                            onBlur={saveOrderItems} placeholder="Счёт"
                            className="bg-hi/[0.04] border border-tint/20 rounded-xl px-3 py-2 text-xs text-fg/70 outline-none focus:border-accent/40 transition-colors" />
                          <input type="date" value={item.paidDate} onChange={e => { updateOrderItem(item.id,'paidDate',e.target.value); saveOrderItems(); }}
                            className="bg-hi/[0.04] border border-tint/20 rounded-xl px-3 py-2 text-xs text-fg/70 outline-none focus:border-accent/40 transition-colors" />
                          <input type="date" value={item.deliveredDate} onChange={e => { updateOrderItem(item.id,'deliveredDate',e.target.value); saveOrderItems(); }}
                            className="bg-hi/[0.04] border border-tint/20 rounded-xl px-3 py-2 text-xs text-fg/70 outline-none focus:border-accent/40 transition-colors" />
                          <button onClick={() => removeOrderItem(item.id)}
                            className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-red-500/20 text-red-400/60 hover:text-red-400 transition-colors">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {orderItems.length === 0 && (
                    <p className="text-xs text-fg/20 text-center py-4">Нажмите «Добавить» для добавления позиции</p>
                  )}
                </div>

                {/* Notes */}
                <div className="bg-surface/40 border border-tint/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40 mb-5">Примечания к проекту</p>
                  <div className="space-y-4">
                    <div>
                      <label className="text-[11px] text-fg/35 uppercase tracking-wider block mb-2">Доп. комплектующие</label>
                      <textarea value={projectExtraParts} onChange={e => setProjectExtraParts(e.target.value)}
                        onBlur={handleSaveProjectNotes} rows={3} placeholder="Перечислите дополнительные комплектующие..."
                        className="w-full bg-hi/[0.03] border border-tint/25 rounded-2xl px-4 py-3 text-sm text-fg/70 placeholder-fg/20 resize-none focus:outline-none focus:border-accent/40 transition-colors" />
                    </div>
                    <div>
                      <label className="text-[11px] text-fg/35 uppercase tracking-wider block mb-2">Комментарии</label>
                      <textarea value={projectComments} onChange={e => setProjectComments(e.target.value)}
                        onBlur={handleSaveProjectNotes} rows={3} placeholder="Любые дополнительные комментарии..."
                        className="w-full bg-hi/[0.03] border border-tint/25 rounded-2xl px-4 py-3 text-sm text-fg/70 placeholder-fg/20 resize-none focus:outline-none focus:border-accent/40 transition-colors" />
                    </div>
                  </div>
                </div>

                <button onClick={() => setMobileSidebarOpen(true)}
                  className="sm:hidden mt-4 w-full flex items-center justify-center gap-2 px-6 py-3 bg-hi/[0.03] border border-tint/20 hover:bg-tint/20 text-fg/40 hover:text-accent text-sm font-bold rounded-xl transition-all">
                  <ClipboardList className="w-4 h-4" /> Список секций
                </button>
              </motion.div>
            ) : (
              <motion.div key={activeSection.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                className="p-4 sm:p-6 w-full max-w-4xl xl:max-w-[1380px] mx-auto">
                <SectionFormWrapper
                  section={activeSection}
                  onUpdate={updateActiveSection}
                  onSave={handleSaveSection}
                  onBack={() => requestNavigate(null)}
                  isSaving={isSaving}
                  isDirty={isDirty}
                  onOpenDoc={openPreview}
                />
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
              className="relative w-full max-w-md bg-modal border border-red-500/30 rounded-[2rem] p-6 sm:p-8 shadow-2xl z-10">
              <button onClick={() => setIsDeleteModalOpen(false)} className="absolute right-6 top-6 text-fg/20 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>
              <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-6">
                <Trash2 className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Удалить секцию?</h2>
              <p className="text-fg/60 leading-relaxed mb-8">
                Секция <span className="text-fg font-bold">{sectionToDelete?.name}</span> будет удалена безвозвратно.
              </p>
              <div className="flex gap-4">
                <button onClick={() => setIsDeleteModalOpen(false)} className="flex-1 py-4 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all">Отмена</button>
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
              className="relative w-full max-w-md bg-modal border border-amber-500/30 rounded-[2rem] p-6 sm:p-8 shadow-2xl z-10">
              <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-6">
                <Save className="w-8 h-8 text-amber-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Несохранённые изменения</h2>
              <p className="text-fg/60 leading-relaxed mb-8">
                Секция <span className="text-fg font-bold">{activeSection?.name}</span> содержит несохранённые изменения.
              </p>
              <div className="flex gap-3 flex-col sm:flex-row">
                <button onClick={() => { setUnsavedModalOpen(false); setPendingNavTarget(null); }}
                  className="flex-1 py-3 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all text-sm">
                  Остаться
                </button>
                <button onClick={confirmUnsavedDiscard}
                  className="flex-1 py-3 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all text-sm text-fg/50">
                  Не сохранять
                </button>
                <button onClick={confirmUnsavedSave} disabled={isSaving}
                  className="flex-1 py-3 rounded-2xl bg-amber-500 hover:bg-amber-400 text-white font-bold transition-all text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {isSaving
                    ? <div className="w-4 h-4 border-2 border-hi/30 border-t-white rounded-full animate-spin" />
                    : <><Save className="w-4 h-4" /> Сохранить</>
                  }
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Производственный лист — полноценная модалка с iframe */}
      {previewDocName === 'Производственный лист' && activeSection && (
        <ProductionSheetModal
          isOpen={isPreviewModalOpen}
          onClose={() => setIsPreviewModalOpen(false)}
          projectId={projectId}
          sectionId={Number(activeSection.id)}
          projectNumber={project.number}
          sectionOrder={activeSection.id ? sections.findIndex(s => s.id === activeSection.id) + 1 : 1}
        />
      )}

      {/* Плейсхолдер для остальных документов */}
      <AnimatePresence>
        {isPreviewModalOpen && previewDocName !== 'Производственный лист' && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsPreviewModalOpen(false)} className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-4xl bg-surface border border-tint/30 rounded-2xl sm:rounded-[2.5rem] shadow-2xl overflow-hidden flex flex-col max-h-[95vh] z-10">
              <div className="px-5 py-5 sm:px-10 sm:py-7 border-b border-tint/20 flex items-center justify-between flex-shrink-0">
                <h2 className="text-2xl font-bold">{previewDocName}</h2>
                <button onClick={() => setIsPreviewModalOpen(false)} className="text-fg/20 hover:text-fg transition-colors">
                  <X className="w-6 h-6" />
                </button>
              </div>
              <div className="flex-1 p-4 sm:p-10 overflow-y-auto bg-black/20">
                <div className="aspect-[1/1.414] w-full bg-hi rounded-lg shadow-inner p-5 sm:p-12 text-black flex flex-col">
                  <div className="flex-1 border-2 border-dashed border-black/10 rounded-xl flex items-center justify-center">
                    <div className="text-center">
                      <FileText className="w-16 h-16 text-black/10 mx-auto mb-4" />
                      <p className="text-sm font-medium text-black/40">Визуализация в разработке</p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="px-5 py-4 sm:px-10 sm:py-6 bg-black/40 border-t border-tint/20 flex justify-end flex-shrink-0">
                <button onClick={() => setIsPreviewModalOpen(false)} className="px-8 py-3 rounded-xl bg-hi/5 hover:bg-hi/10 font-bold transition-all">Закрыть</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
