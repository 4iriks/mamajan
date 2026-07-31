import { AlertTriangle, CheckCircle2, LockKeyhole } from 'lucide-react';

import type { BookCalcPreview } from '../../api/projects';


const roleLabels = {
  standard: 'Подвижная панель',
  door: 'Крайняя дверь',
  fixed: 'Глухая панель',
  moving_door: 'Доп. дверь',
};

const movementLabels = {
  left: 'Влево',
  right: 'Вправо',
  none: 'Неподвижна',
};

export function BookCalcResults({
  calc,
  error,
}: {
  calc?: BookCalcPreview | null;
  error?: string | null;
}) {
  if (error) {
    return (
      <div className="rounded-2xl border border-red-400/40 bg-red-500/10 p-4 text-sm font-bold text-red-200" data-book-calc-error>
        <div className="flex gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      </div>
    );
  }
  if (!calc) {
    return (
      <div className="rounded-2xl border border-tint/25 bg-black/5 p-4 text-sm text-fg/40" data-book-calc-loading>
        Расчёт физических панелей…
      </div>
    );
  }

  const includedHardware = calc.hardware.filter(item => item.included);
  const bookSystem = String(calc.normalized_config.book_system || 'B25');
  return (
    <div className="space-y-4" data-book-calc-results data-book-configuration-status={calc.configuration_status}>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-tint/25 bg-black/5 p-3">
          <div className="text-[9px] font-bold uppercase tracking-widest text-fg/35">Физические панели</div>
          <div className="mt-1 font-mono text-xl font-bold text-fg">{calc.panels.length}</div>
        </div>
        <div className="rounded-xl border border-tint/25 bg-black/5 p-3">
          <div className="text-[9px] font-bold uppercase tracking-widest text-fg/35">Конфигурация</div>
          <div className={`mt-1 text-sm font-bold ${
            calc.configuration_status === 'confirmed' ? 'text-emerald-300' : 'text-amber-300'
          }`}>
            {calc.configuration_status === 'confirmed' ? 'Подтверждена' : 'Предварительная'}
          </div>
          <div
            className="mt-1 font-mono text-[10px] font-bold text-fg/55"
            data-book-calculated-system={bookSystem}
          >
            Система {bookSystem}
          </div>
        </div>
        <div className="rounded-xl border border-tint/25 bg-black/5 p-3">
          <div className="text-[9px] font-bold uppercase tracking-widest text-fg/35">Приоритет источников</div>
          <div className="mt-1 text-xs font-bold uppercase text-fg/70">{calc.source_priority.join(' → ')}</div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-tint/25">
        <table className="w-full min-w-[650px] border-collapse text-left text-xs" data-book-panels-table>
          <thead className="bg-tint/10 text-[9px] uppercase tracking-wider text-fg/45">
            <tr>
              <th className="px-3 py-2">№</th>
              <th className="px-3 py-2">Роль</th>
              <th className="px-3 py-2">Движение</th>
              <th className="px-3 py-2">Стекло, мм</th>
              <th className="px-3 py-2">Профиль, мм</th>
              <th className="px-3 py-2">Источник</th>
            </tr>
          </thead>
          <tbody>
            {calc.panels.map(panel => (
              <tr
                key={panel.number}
                className="border-t border-tint/15 text-fg/75"
                data-book-result-panel={panel.number}
              >
                <td className="px-3 py-2 font-mono font-bold text-accent">{panel.number}</td>
                <td className="px-3 py-2">
                  {roleLabels[panel.role]}
                  {panel.door_opening_label && (
                    <span className="block text-[9px] text-fg/40">{panel.door_opening_label}</span>
                  )}
                </td>
                <td className="px-3 py-2">{movementLabels[panel.movement_direction]}</td>
                <td className="px-3 py-2 font-mono">
                  {panel.glass_width_mm.toFixed(1)} × {panel.glass_height_mm.toFixed(1)}
                </td>
                <td className="px-3 py-2 font-mono">{panel.glass_profile_width_mm.toFixed(1)}</td>
                <td className="px-3 py-2">
                  <span className={`rounded-full px-2 py-1 text-[9px] font-bold uppercase ${
                    panel.status === 'confirmed'
                      ? 'bg-emerald-500/12 text-emerald-300'
                      : 'bg-amber-500/12 text-amber-300'
                  }`}>
                    {panel.source} · {panel.status === 'confirmed' ? 'подт.' : 'предв.'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <details className="rounded-xl border border-tint/25 bg-black/5 p-3" data-book-profiles>
          <summary className="cursor-pointer text-xs font-bold text-fg/70">
            Профили · {calc.profiles.length} поз.
          </summary>
          <div className="mt-3 space-y-2">
            {calc.profiles.map((item, index) => (
              <div key={`${item.article}-${item.panel_number ?? index}`} className="flex justify-between gap-3 border-t border-tint/15 pt-2 text-[10px]">
                <span className="text-fg/60">{item.article} · {item.position}</span>
                <span className="whitespace-nowrap font-mono text-fg/80">{item.length_mm.toFixed(1)} мм × {item.qty}</span>
              </div>
            ))}
          </div>
        </details>
        <details className="rounded-xl border border-tint/25 bg-black/5 p-3" data-book-hardware>
          <summary className="cursor-pointer text-xs font-bold text-fg/70">
            Фурнитура · {includedHardware.length} поз.
          </summary>
          <div className="mt-3 space-y-2">
            {includedHardware.map((item, index) => (
              <div key={`${item.article}-${index}`} className="flex justify-between gap-3 border-t border-tint/15 pt-2 text-[10px]">
                <span className="text-fg/60">
                  {item.article} · этап {item.shipment_stage}
                  {item.status === 'preliminary' ? ' · предв.' : ''}
                </span>
                <span className="whitespace-nowrap font-mono text-fg/80">{item.qty} {item.unit}</span>
              </div>
            ))}
          </div>
        </details>
      </div>

      {calc.warnings.map((warning, index) => (
        <div
          key={`${warning}-${index}`}
          className="flex gap-2 rounded-xl border border-amber-400/25 bg-amber-500/8 px-3 py-2 text-xs text-amber-200"
          data-book-calc-warning
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
          <span>{warning}</span>
        </div>
      ))}

      <div className="flex gap-2 rounded-xl border border-tint/30 bg-black/8 px-3 py-2 text-xs text-fg/55" data-book-documents-state>
        {calc.documents_implemented ? (
          <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-300" />
        ) : (
          <LockKeyhole className="h-4 w-4 flex-shrink-0 text-amber-300" />
        )}
        <span>
          Производственные документы КНИЖКИ появятся следующим пакетом после согласования калькулятора.
        </span>
      </div>
    </div>
  );
}
