import type { ProjectDocumentType } from '../api/projects';

interface ProjectNumbers {
  number: string;
  invoiceNumber?: string | null;
  orderNumber?: string | null;
}

export function productionProjectNumber(project: ProjectNumbers): string {
  return project.orderNumber?.trim() || project.number.trim() || 'project';
}

export function commercialDocumentNumber(project: ProjectNumbers): string {
  return project.invoiceNumber?.trim() || productionProjectNumber(project);
}

export function isCommercialProjectDocument(docType: ProjectDocumentType): boolean {
  return docType === 'commercial' || docType === 'contract_appendix';
}

export function projectDocumentNumber(
  project: ProjectNumbers,
  docType: ProjectDocumentType,
): string {
  return isCommercialProjectDocument(docType)
    ? commercialDocumentNumber(project)
    : productionProjectNumber(project);
}

export function filenameFromContentDisposition(header?: string): string | null {
  if (!header) return null;

  const extended = header.match(/filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i)?.[1];
  if (extended) {
    const encoded = extended.trim().replace(/^"|"$/g, '');
    try {
      return decodeURIComponent(encoded);
    } catch {
      return encoded;
    }
  }

  const plain = header.match(/filename\s*=\s*(?:"([^"]+)"|([^;]+))/i);
  return (plain?.[1] || plain?.[2])?.trim() || null;
}
