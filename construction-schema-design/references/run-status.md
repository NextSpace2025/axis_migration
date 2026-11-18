# Persistent task state and final notice

Use this for design, conversion, matching and viewer delivery in Axis Migration.
The helper persists state; the active skill writes and reads it. This is not an
OS shutdown hook, background worker or proof of document-reading accuracy.

## Write the actual stage

Keep `status.json` in the private run directory defined by `output/agents.md`.
Create that directory for a selected-folder task, including an inline proposal
that needs a saved handoff. Never use the package/cwd as an implicit result path.
Read the folder record and relevant previous `status.json` on resume, checking
scope and artifact existence; create a new run for new conversion. Before a
lengthy stage, write `running`. Link the status from the folder record.

From the package, using the host's available Python executable:

```sh
python scripts/run_status.py write --run "/absolute/private/run" --state running --stage "모델 검토" --summary "요청한 자료의 포함 여부를 검토합니다." --checks not_run
```

At checkpoints and before the final response, write the actual state:

| State | Use when |
|---|---|
| `completed` | The requested stage is finished, required checks passed or genuinely do not apply, and delivery files exist. Design completion is not conversion completion. |
| `waiting` | A decision, missing input/access or unperformed required check prevents the requested stage from finishing. Record what is needed and the next action. |
| `error` | Execution or a blocking required check failed. Record the cause and remedy. |
| `running` | Work is in progress; an abrupt exit leaves it incomplete, never automatically completed. |

Use `--checks passed|not_required|not_run|failed` honestly. Blocking verification
failure requires `error`. Source discrepancies copied faithfully, representable
unknowns and ordinary unbilled items are findings, not automatically failures.
Use repeated `--issue` for nonblocking findings and `--pending` only for blockers.
A completed stage may retain findings. Do not invent an approval gate or stop
authorized work merely to emit a waiting notice.

```sh
python scripts/run_status.py write --run "/absolute/private/run" --state waiting --stage "모델 확인" --summary "요청한 헤더 제안을 저장했습니다. 사용자 확인 후 변환합니다." --checks passed --result structure.md --pending "제안한 헤더 확인" --next "사용자가 헤더를 확인하면 요청된 다음 단계를 진행합니다."
python scripts/run_status.py write --run "/absolute/private/run" --state completed --stage "모델 검토" --summary "요청된 설계와 자료 포함 여부 검토를 마쳤습니다. 변환은 하지 않았습니다." --checks passed --result structure.md --result validation.md
python scripts/run_status.py write --run "/absolute/private/run" --state error --stage "정합성 검증" --summary "필수 검증에 실패했습니다." --checks failed --result validation.md --error "외래키 검증 실패" --next "검증 보고서의 연결 오류를 확인한 뒤 새 결과에서 재검증합니다."
python scripts/run_status.py show --run "/absolute/private/run"
```

Repeated `--result` values are paths relative to the run or absolute paths; only
existing files are accepted. `--json` reads the same state as JSON. Writes append
a UTC event to private `run.jsonl`, retaining prior events. Use one writer per
run; concurrent jobs use separate runs. The helper never edits a DB.

When reopening previous work, keep its original status unchanged. Record the
new viewing task in a separate run with links to the existing result and verified
reopen artifacts; do not replace a conversion's state with viewer completion.

## Read before reporting

After the final write, actually run `show` and use the saved state in the user's
language. End with a short **Axis · 완료 / 확인 대기 / 오류 · 단계** notice, actual
result links, remaining findings, and the next action if needed. Link `status.json`
from the folder record together with the result/reopen links. Verify viewer and
launcher behavior using the reopening workflow before claiming viewer delivery.
A live URL can be described in the summary; retain reopening files as results.
When delivery to a designated graph viewer was requested, apply
[the graph delivery checks](../../output/agents.md#deliver-to-a-designated-graph-viewer)
before marking that delivery complete. Put the verified graph link immediately
below the other result links.

If write/show fails, report **상태 기록 오류** and its cause; never claim the new
state was saved or fall back to a global/package file. Missing/malformed prior
state is unverified, not completed. No selected input/result folder means no
persisted run yet: give an honest chat notice without inventing paths. Existing
historical runs without a status file are not automatically backfilled as complete.
Standalone skill copies without this helper use available file tools to write/read
the same fields and private event log, or report inability to save.
