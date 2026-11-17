# Counterparty classification by construction trade

## Required output

Present classification proposals and classification views with these leading
columns, in this order:

| 회사명 | 대분류(공종) | 중분류 | 소분류 | 분류기준 | 원문 근거 |
|---|---|---|---|---|---|
| Example Counterparty A | 금속공사 | 가공 | V컷 | Metal processing context and an explicit V컷/V-CUT charge | Example source, page/sheet/cell, exact text |

The English contract fields are `company_name`, `major_category`,
`middle_category`, `minor_category`, `classification_basis`, `source_reference`.
Company means the counterparty, not `reference_company_name` (the buyer).
Major category means the construction trade; middle means the activity; minor
means the specific operation. Do not use 자재비, 노무비 or 장비비 as trade names.
Keep direct/indirect cost as a separate attribute when established, not a fourth
hierarchy level. Append classification status or other metadata after the six
leading columns. Other business tables keep their own contract column order.

Keep exactly these three classification levels; company, classification basis
and source evidence are not additional levels. Document type, floor, zone,
material, specification and pricing basis belong in independent business fields
when supported by source content, not deeper trade categories. Use the
[document-type-specific header rules](intent-to-table.md#document-type-specific-headers)
to design those fields. Unestablished classification levels remain null; three
levels does not require inventing three populated values for every record.

## Map source text before proposing the hierarchy

1. After identifying the reference company, read the requested statement/order
   contents. Map raw labels and text to candidate meanings, keeping exact source
   locations. For example, 품명/제품명/적요 may describe an item or operation;
   공급자/납품업체 and 공급받는자/발주처 identify different party roles. Inspect
   actual values and context rather than equating labels mechanically.
2. Resolve counterparties from those roles. Do not classify the reference buyer,
   project owners, staff or every company name appearing in a logo. Keep source
   names; apply aliases only with evidence or a supplied map.
3. Group observed item, operation, specification and pricing text by counterparty.
   Show recurrent terms and the files/locations supporting them. A company may
   supply several trades or operations; frequency suggests candidates, not a
   permanent single category for that company.
4. Use the starter table below to propose the three levels for the observed
   work. Attach the actual matching text, context and location to each proposal.
   Represent multiple company/trade/activity/operation combinations as separate
   classification rows and link their source occurrences without merging real
   transactions. Review the remaining material and extend the proposal where
   the starter table does not fit.

## Starter classification table

These are configurable design candidates, not a statutory trade/licence list
or a company's approved cost master. Reuse supplied project/company trade names
when established. The trade requires source/project context as well as task
words: V컷 alone does not establish 금속공사. A table entry is not evidence
that the user's company performs that work.

| 대분류(공종) | 중분류 | 소분류 | Candidate text and required context |
|---|---|---|---|
| 금속공사 | 가공 | V컷 | V컷, V-CUT, 브이컷 in metal processing work |
| 금속공사 | 가공 | 용접 | 용접, 용접비 in a metal work/charge description |
| 금속공사 | 가공 | 절곡 | 절곡, 벤딩 in metal forming work |
| 금속공사 | 가공 | 절단 | 절단, 컷팅 in metal cutting work |
| 금속공사 | 가공 | 타공 | 타공, 천공 in metal processing work |
| 금속공사 | 단열 | 단열재 부착 | Explicit insulation attachment work associated with the metal trade |
| 금속공사 | 표면처리 | 분체도장 | 분체도장, 분체도장비 on metal components |
| 금속공사 | 표면처리 | 불소도장 | 불소도장, 불소도장비 on metal components |
| 창호공사 | 제작 | 창호 조립 | 창호 조립/제작 work, not merely an accessory item |
| 창호공사 | 설치 | 창호 설치 | Explicit 창호 installation work |
| 유리공사 | 시공 | 유리 설치 | Explicit 유리 installation work |
| 실링공사 | 시공 | 코킹 | 코킹/실링 application work, not silicone supply alone |
| 비계공사 | 설치 | 시스템비계 설치 | Explicit system-scaffold installation work |
| 비계공사 | 해체 | 시스템비계 해체 | Explicit system-scaffold dismantling work |
| 방수공사 | 시공 | 도막방수 | Explicit liquid-applied waterproofing work |

## Decisions and exceptions

- Classification proposals are required even without an existing company map.
  Keep proposed values and their basis distinct from confirmed company fields;
  a supplied/defined classification mapping takes precedence over starter rows.
- A term such as 용접봉 describes a consumable, not proof of welding work.
  Likewise, 단열재 or 실리콘 supply does not establish attachment or 코킹.
  Generic 가공 without further evidence does not establish V컷 or 용접.
- Use null for an unestablished level, display 확인 필요, and record the issue
  beside the evidence. Propose a new category with reasons instead of forcing
  a match. Do not turn unrelated records, payments or tax into trade operations.
- Document classification mapping/version and state (proposed, defined or
  unresolved) separately from coverage/validation status. A plausible proposal
  is not an approved company policy or a validated transaction.

Company-specific names, accepted mappings and actual business records stay
outside this public package. All company names in this guide are fictional.
