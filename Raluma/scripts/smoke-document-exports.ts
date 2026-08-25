import assert from 'node:assert/strict';

import type { ProjectDocumentType } from '../src/api/projects';
import {
  commercialDocumentNumber,
  filenameFromContentDisposition,
  productionProjectNumber,
  projectDocumentNumber,
} from '../src/utils/documentExports';

const project = {
  number: 'B26-7-4225',
  orderNumber: 'B26-7-4225',
  invoiceNumber: '00000004',
};

assert.equal(productionProjectNumber(project), 'B26-7-4225');
assert.equal(commercialDocumentNumber(project), '00000004');

const productionDocuments: ProjectDocumentType[] = [
  'sketch',
  'glass',
  'paint',
  'delivery',
  'hardware_order',
];
for (const docType of productionDocuments) {
  assert.equal(projectDocumentNumber(project, docType), 'B26-7-4225', docType);
}
for (const docType of ['commercial', 'contract_appendix'] as ProjectDocumentType[]) {
  assert.equal(projectDocumentNumber(project, docType), '00000004', docType);
}

const serverFilename = 'Заказ стекла_B26-7-4225.docx';
const contentDisposition = `attachment; filename*=UTF-8''${encodeURIComponent(serverFilename)}`;
assert.equal(filenameFromContentDisposition(contentDisposition), serverFilename);
assert.equal(
  filenameFromContentDisposition('attachment; filename="ПЛ_B26-7-4225_сек1.xlsx"'),
  'ПЛ_B26-7-4225_сек1.xlsx',
);

console.log('Document export filename smoke test passed');
