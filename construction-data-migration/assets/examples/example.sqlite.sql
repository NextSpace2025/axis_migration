-- Synthetic SQLite export. Run in an empty disposable database.
-- Exact decimals are canonical TEXT; calculations use decimal arithmetic.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

CREATE TABLE documents (
    document_id TEXT PRIMARY KEY NOT NULL,
    document_type TEXT NOT NULL,
    document_number TEXT,
    document_date TEXT,
    supplier_name TEXT,
    buyer_name TEXT,
    project_name TEXT,
    currency TEXT,
    supply_amount TEXT,
    tax_amount TEXT,
    total_amount TEXT
);

CREATE TABLE document_lines (
    line_id TEXT PRIMARY KEY NOT NULL,
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    row_type TEXT NOT NULL CHECK (row_type IN (
        'detail', 'charge', 'deduction', 'subtotal', 'carry_forward', 'tax', 'total', 'note'
    )),
    item_name TEXT,
    specification TEXT,
    work_area TEXT,
    billed_quantity TEXT,
    billed_unit TEXT,
    unit_price TEXT,
    amount TEXT,
    source_category TEXT,
    company_category TEXT,
    raw_record TEXT NOT NULL,
    UNIQUE (document_id, line_number),
    UNIQUE (document_id, line_id)
);

CREATE TABLE source_references (
    reference_id TEXT PRIMARY KEY NOT NULL,
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    line_id TEXT,
    source_file TEXT NOT NULL,
    source_location TEXT NOT NULL,
    connection_evidence TEXT,
    FOREIGN KEY (document_id, line_id) REFERENCES document_lines(document_id, line_id)
);

CREATE TABLE validation_issues (
    issue_id TEXT PRIMARY KEY NOT NULL,
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    line_id TEXT,
    code TEXT NOT NULL,
    cause TEXT NOT NULL,
    resolution TEXT NOT NULL,
    FOREIGN KEY (document_id, line_id) REFERENCES document_lines(document_id, line_id)
);

INSERT INTO documents (
    document_id, document_type, document_number, document_date, supplier_name,
    buyer_name, project_name, currency, supply_amount, tax_amount, total_amount
) VALUES
    ('D-PO-1', 'purchase_order', 'EX-PO-001', '2030-04-14', 'Example Metal Works',
     'Example Contractor', 'Example Site A', 'KRW', '1200', '120', '1320'),
    ('D-ST-1', 'transaction_statement', 'EX-ST-001', '2030-04-15', 'Example Metal Works',
     'Example Contractor', 'Example Site A', 'KRW', '650', '65', '715');

INSERT INTO document_lines (
    line_id, document_id, line_number, row_type, item_name, specification,
    work_area, billed_quantity, billed_unit, unit_price, amount,
    source_category, company_category, raw_record
) VALUES
    ('L-PO-1', 'D-PO-1', 1, 'detail', 'AL sheet', '2T', NULL, '2', 'SHEET', '300', '600',
     NULL, NULL, '{"품명":"AL sheet","규격":"2T","청구수량":"2","청구단위":"SHEET","단가":"300","금액":"600"}'),
    ('L-PO-2', 'D-PO-1', 2, 'detail', 'AL sheet', '2T', NULL, '2', 'SHEET', '300', '600',
     NULL, NULL, '{"품명":"AL sheet","규격":"2T","청구수량":"2","청구단위":"SHEET","단가":"300","금액":"600"}'),
    ('L-ST-1', 'D-ST-1', 1, 'detail', 'Panel processing', 'O''Brien finish', '4.5', '6', 'EA', '100', '600',
     NULL, NULL, '{"품명":"Panel processing","규격":"O''Brien finish","면적(㎡)":"4.5","청구수량":"6","청구단위":"EA","단가":"100","금액":"600"}'),
    ('L-ST-2', 'D-ST-1', 2, 'charge', 'Delivery charge', NULL, NULL, NULL, NULL, NULL, '50',
     NULL, NULL, '{"품명":"Delivery charge","규격":"","면적(㎡)":"","청구수량":"","청구단위":"","단가":"","금액":"50"}');

INSERT INTO source_references (
    reference_id, document_id, line_id, source_file, source_location, connection_evidence
) VALUES
    ('R-PO-H', 'D-PO-1', NULL, 'example-order.txt', 'Document header and totals', NULL),
    ('R-PO-1', 'D-PO-1', 'L-PO-1', 'example-order.txt', 'Table row 1', NULL),
    ('R-PO-2', 'D-PO-1', 'L-PO-2', 'example-order.txt', 'Table row 2', NULL),
    ('R-ST-H', 'D-ST-1', NULL, 'example-statement.txt', 'Document header and totals', NULL),
    ('R-ST-1', 'D-ST-1', 'L-ST-1', 'example-statement.txt', 'Table row 1', NULL),
    ('R-ST-2', 'D-ST-1', 'L-ST-2', 'example-statement.txt', 'Table row 2', NULL);

INSERT INTO validation_issues (
    issue_id, document_id, line_id, code, cause, resolution
) VALUES (
    'I-ST-2', 'D-ST-1', 'L-ST-2', 'amount_not_checkable',
    'The source charge has an amount but no quantity or unit price.',
    'Retain the source amount; obtain a pricing basis if multiplication must be checked.'
);

COMMIT;

-- 동작 설명: 가상 문서와 상세행을 만들고 원본 위치와 확인 사항을 연결합니다.
-- 실제 회사 데이터나 연결된 운영 데이터베이스는 사용하지 않습니다.
