import { Section, LBL, INP, SEL } from './types';
import { Checkbox, ToggleGroup, RadioList, ProfileCheckbox } from './FormInputs';

// ── Tab: Основное (общая для всех систем) ─────────────────────────────────────

export function MainTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className={LBL}>Секция №</label>
            <input
              type="number" min="1"
              value={s.name.replace(/\D/g, '')}
              onChange={e => update({ name: `Секция ${e.target.value}` })}
              className={INP}
            />
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>Кол-во, шт</label>
            <input type="number" min="1" value={s.quantity || ''} onChange={e => update({ quantity: parseInt(e.target.value) || 0 })} className={INP} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className={LBL}>Ширина, мм</label>
            <input type="number" value={s.width || ''} onChange={e => update({ width: parseInt(e.target.value) || 0 })} className={INP} />
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>Высота, мм</label>
            <input type="number" value={s.height || ''} onChange={e => update({ height: parseInt(e.target.value) || 0 })} className={INP} />
          </div>
        </div>
        <div className="space-y-1.5">
          <label className={LBL}>Стекло</label>
          <select value={s.glassType} onChange={e => update({ glassType: e.target.value })} className={SEL}>
            <option>10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ</option>
            <option>10ММ ЗАКАЛЕННОЕ МАТОВОЕ</option>
            <option>8ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ</option>
            <option>8ММ ЗАКАЛЕННОЕ МАТОВОЕ</option>
            <option>6ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ</option>
            <option>6ММ ЗАКАЛЕННОЕ МАТОВОЕ</option>
          </select>
        </div>
      </div>
      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className={LBL}>Окрашивание</label>
          <div className="space-y-1.5">
            {(['RAL стандарт', 'RAL нестандарт', 'Анодированный'] as const).map(type => (
              <button key={type} onClick={() => update({ paintingType: type })}
                className={`flex items-center gap-3 w-full px-3 py-2 rounded-xl border transition-all text-left ${
                  s.paintingType === type ? 'bg-accent/10 border-accent/50 text-accent' : 'bg-black/10 border-tint/20 text-fg/70 hover:border-tint/50'
                }`}
              >
                <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 ${s.paintingType === type ? 'border-accent' : 'border-hi/10'}`}>
                  {s.paintingType === type && <div className="w-2 h-2 rounded-full bg-accent" />}
                </div>
                <span className="text-xs font-medium">{type}</span>
              </button>
            ))}
          </div>
          {s.paintingType.includes('RAL') && (
            <div className="mt-2 space-y-1.5">
              <label className={LBL}>Цвет RAL</label>
              <input type="text" value={s.ralColor || ''} onChange={e => update({ ralColor: e.target.value })} className={INP} placeholder="Напр. 9016" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Tab: СЛАЙД — Система + Профили + Фурнитура ────────────────────────────────

export function SlideSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  const showLockLeft  = (s.profileLeftLockBar  || s.profileLeftHandleBar)  && !(s.profileLeftPBar  && s.profileLeftHandleBar);
  const showNoLockLeft  = s.profileLeftPBar  && s.profileLeftHandleBar;
  const showHandleLeft  = (s.profileLeftPBar  && s.profileLeftBubble)  || (s.profileLeftBubble  && !s.profileLeftLockBar  && !s.profileLeftPBar  && !s.profileLeftHandleBar);
  const showLockRight = (s.profileRightLockBar || s.profileRightHandleBar) && !(s.profileRightPBar && s.profileRightHandleBar);
  const showNoLockRight = s.profileRightPBar && s.profileRightHandleBar;
  const showHandleRight = (s.profileRightPBar && s.profileRightBubble) || (s.profileRightBubble && !s.profileRightLockBar && !s.profileRightPBar && !s.profileRightHandleBar);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6">
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className={LBL}>Рельсы</label>
            <ToggleGroup
              value={s.rails === 5 ? '5ти рельсовая' : '3х рельсовая'}
              options={['3х рельсовая', '5ти рельсовая']}
              onChange={v => {
                const newRails = v.startsWith('3') ? 3 : 5;
                const maxPanels = newRails;
                update({ rails: newRails, panels: Math.min(s.panels ?? 3, maxPanels) });
              }}
            />
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>Кол-во панелей</label>
            <ToggleGroup value={String(s.panels)}
              options={s.rails === 5 ? ['1', '2', '3', '4', '5'] : ['1', '2', '3']}
              onChange={v => update({ panels: parseInt(v) })} />
          </div>
          {((s.rails !== 5 && (s.panels ?? 3) < 3) || (s.rails === 5 && (s.panels ?? 3) < 5)) && (
            <div className="space-y-1.5">
              <label className={LBL}>Неиспользуемый рельс</label>
              <ToggleGroup value={s.unusedTrack ?? 'Внутренний'} options={['Внутренний', 'Внешний']}
                onChange={v => update({ unusedTrack: v })} />
            </div>
          )}
          <div className="space-y-1.5">
            <label className={LBL}>1-я панель внутри помещения</label>
            <ToggleGroup value={s.firstPanelInside} options={['Слева', 'Справа']}
              onChange={v => update({ firstPanelInside: v })} />
          </div>
        </div>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className={LBL}>Порог</label>
            <select value={s.threshold || ''} onChange={e => update({ threshold: e.target.value || undefined })} className={SEL}>
              <option value="">— Без порога —</option>
              <option>Стандартный анод</option>
              <option>Стандартный окраш</option>
              <option>Накладной анод</option>
              <option>Накладной окраш</option>
            </select>
            {!s.threshold && (
              <p className="text-[10px] text-amber-400/70 font-bold uppercase tracking-wider pl-1">⚠ Без порога система быть не может</p>
            )}
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>Межстекольный профиль</label>
            <select value={s.interGlassProfile || ''} onChange={e => update({ interGlassProfile: e.target.value || undefined })} className={SEL}>
              <option value="">— Без межстекольного профиля —</option>
              <option>Алюминиевый RS2061</option>
              <option>Прозрачный с фетром RS1006</option>
              <option>h-профиль RS1004</option>
            </select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Профили слева */}
        <div className="space-y-2">
          <label className={LBL}>Профили слева</label>
          <div className="space-y-0.5">
            <ProfileCheckbox checked={s.profileLeftWall} onChange={() => update({ profileLeftWall: !s.profileLeftWall })} label="Пристеночный RS2333/2335" />
            <ProfileCheckbox checked={s.profileLeftLockBar} onChange={() => { if (!s.profileLeftLockBar) update({ profileLeftLockBar: true, profileLeftPBar: false, profileLeftHandleBar: true, profileLeftBubble: false }); else update({ profileLeftLockBar: false }); }} label="Боковой профиль-замок RS2081" indent />
            <ProfileCheckbox checked={s.profileLeftPBar} onChange={() => { if (!s.profileLeftPBar) update({ profileLeftPBar: true, profileLeftLockBar: false }); else update({ profileLeftPBar: false }); }} label="Боковой П-профиль RS1082" indent />
            <ProfileCheckbox checked={s.profileLeftHandleBar} onChange={() => { if (!s.profileLeftHandleBar) update({ profileLeftHandleBar: true, profileLeftBubble: false }); else update({ profileLeftHandleBar: false }); }} label="Ручка-профиль RS112" />
            <ProfileCheckbox checked={s.profileLeftBubble} onChange={() => { if (!s.profileLeftBubble) update({ profileLeftBubble: true, profileLeftHandleBar: false }); else update({ profileLeftBubble: false }); }} label="Пузырьковый уплотнитель RS1002" disabled={s.profileLeftLockBar} />
          </div>
          {showLockLeft && (
            <div className="mt-2 space-y-1">
              <label className={LBL}>Замок слева</label>
              <RadioList value={s.lockLeft} noneLabel="Без замка"
                options={['ЗАМОК-ЗАЩЕЛКА 1стор', 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом']}
                onChange={v => update({ lockLeft: v })} />
            </div>
          )}
          {showNoLockLeft && (
            <div className="mt-2 px-4 py-2 bg-black/10 border border-tint/20 rounded-xl">
              <span className="text-xs text-fg/40 font-bold">Без замков</span>
            </div>
          )}
          {showHandleLeft && (
            <div className="mt-2 space-y-1">
              <label className={LBL}>Ручка слева</label>
              <RadioList value={s.handleLeft} noneLabel="Без ручки (глухая)"
                options={['Без ручки (подвижная)', 'Ручка-кноб RS3014', 'Стеклянная ручка RS3017', 'Ручка-скоба']}
                onChange={v => update({ handleLeft: v })} />
            </div>
          )}
        </div>

        {/* Профили справа */}
        <div className="space-y-2">
          <label className={LBL}>Профили справа</label>
          <div className="space-y-0.5">
            <ProfileCheckbox checked={s.profileRightWall} onChange={() => update({ profileRightWall: !s.profileRightWall })} label="Пристеночный RS2333/2335" />
            <ProfileCheckbox checked={s.profileRightLockBar} onChange={() => { if (!s.profileRightLockBar) update({ profileRightLockBar: true, profileRightPBar: false, profileRightHandleBar: true, profileRightBubble: false }); else update({ profileRightLockBar: false }); }} label="Боковой профиль-замок RS2081" indent />
            <ProfileCheckbox checked={s.profileRightPBar} onChange={() => { if (!s.profileRightPBar) update({ profileRightPBar: true, profileRightLockBar: false }); else update({ profileRightPBar: false }); }} label="Боковой П-профиль RS1082" indent />
            <ProfileCheckbox checked={s.profileRightHandleBar} onChange={() => { if (!s.profileRightHandleBar) update({ profileRightHandleBar: true, profileRightBubble: false }); else update({ profileRightHandleBar: false }); }} label="Ручка-профиль RS112" />
            <ProfileCheckbox checked={s.profileRightBubble} onChange={() => { if (!s.profileRightBubble) update({ profileRightBubble: true, profileRightHandleBar: false }); else update({ profileRightBubble: false }); }} label="Пузырьковый уплотнитель RS1002" disabled={s.profileRightLockBar} />
          </div>
          {showLockRight && (
            <div className="mt-2 space-y-1">
              <label className={LBL}>Замок справа</label>
              <RadioList value={s.lockRight} noneLabel="Без замка"
                options={['ЗАМОК-ЗАЩЕЛКА 1стор', 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом']}
                onChange={v => update({ lockRight: v })} />
            </div>
          )}
          {showNoLockRight && (
            <div className="mt-2 px-4 py-2 bg-black/10 border border-tint/20 rounded-xl">
              <span className="text-xs text-fg/40 font-bold">Без замков</span>
            </div>
          )}
          {showHandleRight && (
            <div className="mt-2 space-y-1">
              <label className={LBL}>Ручка справа</label>
              <RadioList value={s.handleRight} noneLabel="Без ручки (глухая)"
                options={['Без ручки (подвижная)', 'Ручка-кноб RS3014', 'Стеклянная ручка RS3017', 'Ручка-скоба']}
                onChange={v => update({ handleRight: v })} />
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <label className={LBL}>Защёлки в пол</label>
        <div className="flex gap-6">
          <Checkbox checked={s.floorLatchesLeft} onChange={() => update({ floorLatchesLeft: !s.floorLatchesLeft })} label="Слева" />
          <Checkbox checked={s.floorLatchesRight} onChange={() => update({ floorLatchesRight: !s.floorLatchesRight })} label="Справа" />
        </div>
      </div>

      {(s.handleLeft === 'Стеклянная ручка RS3017' || s.handleLeft === 'Ручка-скоба' || s.handleRight === 'Стеклянная ручка RS3017' || s.handleRight === 'Ручка-скоба') && (
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <label className={LBL}>Отступ A (левое), мм</label>
            <input
              type="number"
              value={s.handleOffsetLeft ?? (s.handleLeft === 'Ручка-скоба' ? '' : '')}
              onChange={e => update({ handleOffsetLeft: parseFloat(e.target.value) || undefined })}
              className={INP}
              placeholder={s.handleLeft === 'Ручка-скоба' ? '100' : '0'}
            />
          </div>
          <div className="space-y-2">
            <label className={LBL}>Отступ B (правое), мм</label>
            <input
              type="number"
              value={s.handleOffsetRight ?? ''}
              onChange={e => update({ handleOffsetRight: parseFloat(e.target.value) || undefined })}
              className={INP}
              placeholder={s.handleRight === 'Ручка-скоба' ? '100' : '0'}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tab: КНИЖКА — Система ─────────────────────────────────────────────────────

export function BookSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  const hasDoors = !s.bookSubtype || s.bookSubtype === 'doors' || s.bookSubtype === 'doors_and_angle';
  const hasAngle = s.bookSubtype === 'angle' || s.bookSubtype === 'doors_and_angle';
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        {hasDoors && (
          <>
            <div className="space-y-2">
              <label className={LBL}>Кол-во дверей</label>
              <ToggleGroup value={s.doors?.toString()} options={['1', '2']}
                onChange={v => update({ doors: parseInt(v) })} />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Сторона двери</label>
              <ToggleGroup value={s.doorSide} options={['Левая', 'Правая']}
                onChange={v => update({ doorSide: v })} />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Тип двери</label>
              <RadioList value={s.doorType}
                options={['Тип 1', 'Тип 4']}
                onChange={v => update({ doorType: v })} />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Открывание</label>
              <ToggleGroup value={s.doorOpening} options={['Внутрь', 'Наружу']}
                onChange={v => update({ doorOpening: v })} />
            </div>
          </>
        )}
        <div className="space-y-2">
          <label className={LBL}>Кол-во панелей</label>
          <select value={s.panels} onChange={e => update({ panels: parseInt(e.target.value) })} className={SEL}>
            {[2, 3, 4, 5, 6].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </div>
      <div className="space-y-5">
        {hasDoors && (
          <>
            <div className="space-y-2">
              <label className={LBL}>Система книжки</label>
              <RadioList value={s.bookSystem} noneLabel="— Стандарт —"
                options={['С кареткой', 'Без каретки']}
                onChange={v => update({ bookSystem: v })} />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Компенсатор</label>
              <RadioList value={s.compensator} noneLabel="— Нет —"
                options={['Левый', 'Правый', 'Оба']}
                onChange={v => update({ compensator: v })} />
            </div>
          </>
        )}
        {(hasDoors || hasAngle) && (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className={LBL}>Угол лев., °</label>
              <input type="number" value={s.angleLeft || ''} onChange={e => update({ angleLeft: parseFloat(e.target.value) || undefined })} className={INP} placeholder="0" />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Угол пр., °</label>
              <input type="number" value={s.angleRight || ''} onChange={e => update({ angleRight: parseFloat(e.target.value) || undefined })} className={INP} placeholder="0" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: ЛИФТ — Система ───────────────────────────────────────────────────────

export function LiftSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Кол-во панелей</label>
          <ToggleGroup value={s.panels?.toString()} options={['2', '3', '4']}
            onChange={v => update({ panels: parseInt(v) })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>1-я панель</label>
          <ToggleGroup value={s.firstPanelInside} options={['Слева', 'Справа']}
            onChange={v => update({ firstPanelInside: v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Замок</label>
          <RadioList value={s.lock} noneLabel="Без замка"
            options={['RS3018 Замок-защёлка', 'С ключом']}
            onChange={v => update({ lock: v })} />
        </div>
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Профиль левый</label>
          <select value={s.profileLeft || ''} onChange={e => update({ profileLeft: e.target.value || undefined })} className={SEL}>
            <option value="">— Нет —</option>
            <option>Стойка</option>
            <option>Угол</option>
            <option>Торец</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className={LBL}>Профиль правый</label>
          <select value={s.profileRight || ''} onChange={e => update({ profileRight: e.target.value || undefined })} className={SEL}>
            <option value="">— Нет —</option>
            <option>Стойка</option>
            <option>Угол</option>
            <option>Торец</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className={LBL}>Ручка</label>
          <RadioList value={s.handle} noneLabel="Без ручки"
            options={['RS3014 Ручка-кноб', 'RS3017 Стеклянная ручка']}
            onChange={v => update({ handle: v })} />
        </div>
      </div>
    </div>
  );
}

// ── Tab: ЦС — Форма ───────────────────────────────────────────────────────────

export function CsShapeTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <label className={LBL}>Форма секции</label>
        <div className="grid grid-cols-2 gap-3">
          {['Треугольник', 'Прямоугольник', 'Трапеция', 'Сложная форма'].map(shape => (
            <button key={shape} onClick={() => update({ csShape: shape })}
              className={`py-4 rounded-xl border font-bold text-xs transition-all ${
                s.csShape === shape ? 'bg-accent/10 border-accent/50 text-accent' : 'bg-black/10 border-tint/20 text-fg/70 hover:border-tint/50'
              }`}
            >{shape}</button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className={LBL}>Ширина (осн.), мм</label>
          <input type="number" value={s.width || ''} onChange={e => update({ width: parseInt(e.target.value) || 0 })} className={INP} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Высота, мм</label>
          <input type="number" value={s.height || ''} onChange={e => update({ height: parseInt(e.target.value) || 0 })} className={INP} />
        </div>
        {s.csShape === 'Трапеция' && (
          <div className="space-y-2">
            <label className={LBL}>Ширина 2, мм</label>
            <input type="number" value={s.csWidth2 || ''} onChange={e => update({ csWidth2: parseFloat(e.target.value) || undefined })} className={INP} placeholder="мм" />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: КОМПЛЕКТАЦИЯ — Система ───────────────────────────────────────────────

export function DoorSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Тип системы</label>
          <RadioList value={s.doorSystem}
            options={['Одностворчатая', 'Двустворчатая', 'Маятниковая']}
            onChange={v => update({ doorSystem: v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Открывание</label>
          <ToggleGroup value={s.doorOpening} options={['Внутрь', 'Наружу']}
            onChange={v => update({ doorOpening: v })} />
        </div>
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Замок</label>
          <RadioList value={s.lock} noneLabel="Без замка"
            options={['RS3018 Защёлка', 'RS3019 С ключом', 'Магнитный']}
            onChange={v => update({ lock: v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Ручка</label>
          <RadioList value={s.handle} noneLabel="Без ручки"
            options={['RS3014 Ручка-кноб', 'RS3017 Стеклянная ручка', 'Ручка-скоба', 'Ручка-раковина']}
            onChange={v => update({ handle: v })} />
        </div>
      </div>
    </div>
  );
}
