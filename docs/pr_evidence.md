# Day 9 · Bằng chứng cho PR

**Nhanh:** [Eval Card](eval_card.md) · [PRD v1.1](PRD_v1.1.md) · [Taxonomy](failure_taxonomy.md) · [Judge audit](judge_audit.md) · [Trace case](trace_case.md)

## Core

- `M0 PASS`. Eval set v1 có 14 item, v2 có 28 item. Cả hai kiểm tra 0 lỗi.
- Bộ test Lab 9 chạy cục bộ có 38 test đạt.
- `swarm` tự so baseline và `fixed` qua gate. `mutation --detect` cho detection 100.00%, false alarms 0.00%.
- Gate v1 in verdict sau trên [run seeded_regression](../src/reports/eval_seeded_regression.json).

```text
pass_rate 0.7143  Δ -0.271 CI [-0.500, -0.057]  BLOCK
exit 1 — blocked: refund_amount_correct, pass_rate, reply_ledger_correct
```

## Advanced và Expert

Lệnh chạy từ `src/`:

```text
python -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json
python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110
python -m lab9.traps --pr reports/eval_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
```

| Variant | Gate quan sát được | Điều kiện chặn |
|---|---|---|
| `fixed` | merge | |
| `honest_refactor` | merge | |
| `seeded_regression` | block | `refund_amount_correct`, `pass_rate`, `pass_hat_5`, `reply_ledger_correct`, cả ba slice |
| `slice_regression` | block | Chỉ `slice:money_movement/pass_rate` |
| `flaky_regression` | block | `pass_rate`, `pass_hat_5`, `slice:money_movement/pass_rate` |

`mutation score 3/3 · false alarms 0`. A/A cho Δ = 0 ở tất cả metric được báo, gồm `pass_rate 0.9786 → 0.9786` và `pass_hat_5 0.8929 → 0.8929`. Baseline v2 qua gate khi so với chính nó.

| Trap công khai | Kết quả gate |
|---|---|
| `evaluator_errors_as_nan` | exit 1 — blocked: integrity · row grade thiếu hoặc không hợp lệ |
| `dropped_failing_rows` | exit 1 — blocked: integrity · thiếu cặp item × seed |
| `cherry_picked_seeds` | exit 1 — blocked: integrity · tập trial khác baseline |
| `loosened_spec` | exit 1 — blocked: integrity · ratchet phát hiện hạ ngưỡng và xóa slice |

## Đối chứng bổ sung

Cả hai replay dùng eval set v2, năm seed chuẩn và factory `make_shape` của đề với `no_override` cộng một công tắc lỗi. Các kiểm tra này dùng công tắc public.

| Biến thể | Kết quả đo | Verdict |
|---|---|---|
| [`quiet_override`](../src/reports/eval_replay_quiet_override.json) | `refund_amount_correct=0.8929`, `denial/pass_rate=0.7273` | Hai metric chặn dù biến thể bỏ event `model_override`. |
| [`misreport`](../src/reports/eval_replay_misreport.json) | `reply_ledger_correct=0.7857` | Chỉ metric FM-08 chặn. |

## Bonus

Inspect AI và pydantic-evals khớp 7/7 trial trên từng grader trong ba grader. Tệp [inspect_comparison.json](../src/reports/inspect_comparison.json) ghi phiên bản, danh sách trial và số lượng verdict lỗi.

Các kết quả trên lấy từ replay và kiểm thử cục bộ. Nộp bằng PR từ `starter/d09` → `main` trong fork và kiểm tra `eval-gate`, `eval-gate-v2` trước khi merge.
