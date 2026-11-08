import React, { useEffect, useState } from 'react';
import client, { projectVersion } from '../api/client';
import { getProject, ProjectFull, ProjectWorkflow, REVIEW_LABELS } from '../api/projects';
import { getInternalQuote } from '../api/quotes';
import { toast } from '../store/toastStore';


const ACTIONS: Record<string, string> = {
  submit: 'Отправить на согласование', claim: 'Взять в работу', return: 'Вернуть на доработку',
  approve: 'Одобрить проект', reopen: 'Изменить проект', renew: 'Отправить на повторное согласование',
  reassign: 'Переназначить менеджера',
};

export function ProjectReviewBar({ projectId, workflow, prepare, onChanged }: {
  projectId: number; workflow?: ProjectWorkflow;
  prepare: (action: string) => Promise<boolean>; onChanged: (project: ProjectFull) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<{ action: string; version: number; token?: string; total?: string } | null>(null);
  const [comment, setComment] = useState('');
  const [manager, setManager] = useState('');
  const [reviewers, setReviewers] = useState<Array<{ id: number; name: string }>>([]);
  useEffect(() => { setDialog(null); }, [projectId]);
  if (!workflow || workflow.status === 'internal') return null;
  const report = (error: unknown) => {
    const detail = (error as { response?: { data?: { detail?: string | { message?: string } } } }).response?.data?.detail;
    toast.error(typeof detail === 'string' ? detail : detail?.message || 'Не удалось выполнить действие');
  };
  const send = async (action: string, version: number, token?: string) => {
    const result = await client.post<ProjectFull>(`/api/projects/${projectId}/review`, {
      action, expected_version: version, comment, manager_id: manager ? Number(manager) : undefined,
      expected_preview_token: token,
    });
    onChanged(result.data); setDialog(null); setComment('');
    toast.success('Состояние проекта обновлено');
  };
  const start = async (action: string) => {
    setBusy(true);
    try {
      if (!await prepare(action)) return;
      let version = projectVersion(projectId) ?? workflow.version;
      if (action === 'approve') {
        const [pricing, project] = await Promise.all([getInternalQuote(projectId), getProject(projectId)]);
        version = project.workflow?.version ?? version;
        if (!pricing.pending_quote?.export_allowed) {
          toast.error('КП не готово: исправьте ошибки расчёта в блоке стоимости'); return;
        }
        setDialog({ action, version, token: pricing.preview_token,
          total: pricing.pending_quote.totals.document_grand_total ?? pricing.pending_quote.totals.grand_total });
      } else if (['return', 'reopen', 'reassign'].includes(action)) {
        setComment(''); setManager('');
        if (action === 'reassign') setReviewers((await client.get('/api/projects/reviewers')).data);
        setDialog({ action, version });
      } else await send(action, version);
    } catch (error) { report(error); } finally { setBusy(false); }
  };
  return <section className="flex-shrink-0 border-b border-tint/30 bg-accent/5 px-4 py-3 sm:px-8" aria-label="Согласование проекта">
    <div className="flex flex-wrap items-center gap-3">
      <strong>{REVIEW_LABELS[workflow.status]}</strong>
      {workflow.manager_name && <span className="text-sm text-fg/60">Менеджер: {workflow.manager_name}</span>}
      {workflow.status === 'approved' && <span className="text-sm">КП действует до {workflow.valid_until}</span>}
      {workflow.actions.map(action => <button key={action} disabled={busy} onClick={() => void start(action)}
        className="rounded-xl border border-accent/30 px-3 py-2 text-sm font-semibold disabled:opacity-50">{ACTIONS[action]}</button>)}
      <button disabled={busy} className="text-sm underline" onClick={async () => { if (await prepare('refresh')) await getProject(projectId).then(onChanged).catch(report); }}>Обновить статус</button>
    </div>
    {workflow.comment && <p className="mt-2 text-sm">Причина возврата: {workflow.comment}</p>}
    {workflow.status === 'expired' && <p className="mt-2 text-sm">КП недоступно. Отправьте проект на повторное согласование.</p>}
    {!workflow.can_edit && <p className="mt-1 text-xs text-fg/60">Состав и размеры проекта заблокированы для изменений.</p>}
    {dialog && <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4">
      <div role="dialog" aria-modal="true" aria-label={ACTIONS[dialog.action]} className="w-full max-w-lg rounded-2xl border border-tint/30 bg-modal p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{ACTIONS[dialog.action]}</h2>
        {dialog.action === 'reopen' && <p>Текущее КП и цены станут недоступны. После изменений потребуется новое согласование.</p>}
        {dialog.action === 'approve' && <p>Утвердить проверенную редакцию КП на сумму <strong>{Number(dialog.total).toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽</strong>? После одобрения она станет доступна владельцу проекта.</p>}
        {dialog.action === 'return' && <label className="block">Причина возврата<textarea autoFocus className="mt-2 w-full rounded-lg border border-tint/40 bg-hi/5 p-3" maxLength={5000} rows={4} value={comment} onChange={e => setComment(e.target.value)} /></label>}
        {dialog.action === 'reassign' && <label>Ответственный менеджер<select value={manager} onChange={e => setManager(e.target.value)} className="my-3 w-full rounded-lg bg-surface p-3"><option value="">Выберите менеджера</option>{reviewers.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>}
        <div className="mt-6 flex justify-end gap-3"><button disabled={busy} onClick={() => setDialog(null)}>Отмена</button>
          <button className="rounded-xl bg-accent px-4 py-2 text-white disabled:opacity-40" disabled={busy || (dialog.action === 'return' && !comment.trim()) || (dialog.action === 'reassign' && !manager)} onClick={async () => {
            setBusy(true); try { await send(dialog.action, dialog.version, dialog.token); } catch (error) { report(error); } finally { setBusy(false); }
          }}>Подтвердить</button></div>
      </div>
    </div>}
  </section>;
}
