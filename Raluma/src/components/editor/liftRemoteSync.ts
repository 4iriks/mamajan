import type { Section } from './types';

export type LiftRemoteCounts = Pick<
  Section,
  'liftRemote1chQty' | 'liftRemote6chQty'
>;

export function isLiftRemoteSection(section: Section): boolean {
  return (
    section.system === 'ЛИФТ' &&
    (section.liftControlType || 'Пульт ДУ') === 'Пульт ДУ'
  );
}

export function sharedLiftRemoteCounts(sections: Section[]): LiftRemoteCounts {
  const remoteSections = sections.filter(isLiftRemoteSection);
  const source = remoteSections.find(
    section =>
      (section.liftRemote1chQty ?? 0) > 0 ||
      (section.liftRemote6chQty ?? 0) > 0,
  ) ?? remoteSections[0];

  return {
    liftRemote1chQty: source?.liftRemote1chQty ?? 0,
    liftRemote6chQty: source?.liftRemote6chQty ?? 0,
  };
}

export function synchronizeLiftRemoteCounts(sections: Section[]): Section[] {
  const counts = sharedLiftRemoteCounts(sections);
  return sections.map(section =>
    isLiftRemoteSection(section) ? { ...section, ...counts } : section,
  );
}

export function updateLiftRemoteSections(
  sections: Section[],
  activeSectionId: string,
  updates: Partial<Section>,
): Section[] {
  const current = sections.find(section => section.id === activeSectionId);
  if (!current) return sections;

  let nextUpdates = updates;
  const nextControl =
    updates.liftControlType ?? current.liftControlType ?? 'Пульт ДУ';

  if (
    current.system === 'ЛИФТ' &&
    nextControl === 'Пульт ДУ' &&
    updates.liftControlType === 'Пульт ДУ'
  ) {
    const otherRemoteSections = sections.filter(
      section => section.id !== current.id && isLiftRemoteSection(section),
    );
    nextUpdates = {
      ...updates,
      ...(otherRemoteSections.length > 0
        ? sharedLiftRemoteCounts(otherRemoteSections)
        : {
            liftRemote1chQty: current.liftRemote1chQty ?? 0,
            liftRemote6chQty: current.liftRemote6chQty ?? 0,
          }),
    };
  }

  const changesSharedCounts =
    current.system === 'ЛИФТ' &&
    nextControl === 'Пульт ДУ' &&
    (
      Object.prototype.hasOwnProperty.call(nextUpdates, 'liftRemote1chQty') ||
      Object.prototype.hasOwnProperty.call(nextUpdates, 'liftRemote6chQty')
    );

  if (!changesSharedCounts) {
    return sections.map(section =>
      section.id === activeSectionId
        ? { ...section, ...nextUpdates }
        : section,
    );
  }

  const counts: LiftRemoteCounts = {
    liftRemote1chQty:
      nextUpdates.liftRemote1chQty ?? current.liftRemote1chQty ?? 0,
    liftRemote6chQty:
      nextUpdates.liftRemote6chQty ?? current.liftRemote6chQty ?? 0,
  };

  return sections.map(section => {
    if (section.id === activeSectionId) {
      return { ...section, ...nextUpdates, ...counts };
    }
    return isLiftRemoteSection(section) ? { ...section, ...counts } : section;
  });
}
