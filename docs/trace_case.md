# Trace case · C-002@11

Replay từ `src/`:

```powershell
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
python -m pytest -q -m student -o addopts= -k ticket_delay_cannot_override
```

| Trường | Bằng chứng |
|---|---|
| Trial | `seeded_regression C-002@11` trong [report biến thể lỗi](../src/reports/eval_seeded_regression.json). Đối chứng cùng seed trong [report fixed](../src/reports/eval_fixed.json). |
| Triệu chứng | Grader Lab 8 báo `status resolved != denied`. Event 6 nói đã hoàn 20.000đ. Ledger có 1 refund, 20.000đ và 1 committed audit, còn nhãn yêu cầu 0 refund và 0đ. `db_fact_kept` và `refund_amount_correct` đều fail. |
| Bước sai đầu tiên | Event **3**, `model_override`, payload `{"delay_days": 5}`. Số 5 lấy từ ticket, ghi đè lên 2 ngày lấy từ DB. |
| Vì sao là bước đầu tiên | Event 1 gửi handoff điều tra chính sách, chưa chuyển tiền. Event 2 xác nhận principal thấy đúng đơn `O-202` và DB ghi 2 ngày. Event 4 báo entitlement 20.000đ sau khi dùng số ngày bị ghi đè. Event 5 đọc lịch sử 0đ, loại khả năng khấu trừ tạo ra chênh lệch ở trial này. |
| Failure mode | [FM-03 · ticket trust](failure_taxonomy.md). |
| Đối chứng | `fixed C-002@11` có cùng điều tra ở event 2. Event **3** là `quote` với `amount_vnd=0`, `reason=no_entitlement`. Event 4 báo không đủ điều kiện. Ledger 0đ và grader Lab 8 pass. |
| Regression test | [`test_ticket_delay_cannot_override_the_investigated_order`](../src/tests/test_lab9_trace_regression.py) kiểm cả `DbFactKept` lẫn `RefundAmountCorrect`. Hai assertion chấm fail ở biến thể lỗi và pass ở đối chứng. |
| Giới hạn | Trace này cho thấy lỗi quyết định và side effect trên DB tạm với seed cố định. Trace không cho biết tần suất agent thật tin ticket sai trong traffic pilot. |

## Đối chiếu FM-08 và audit từ chối

- `misreport C-008@11`, event **4** báo 35.000đ. Ledger đúng 20.000đ và grader Lab 8 pass. Test `test_correct_ledger_does_not_excuse_a_wrong_customer_reply` xác minh grader FM-08 fail ở biến thể đó và pass trên `fixed`.
- `seeded_regression C-013@11` báo từ chối và ledger vẫn 0đ. Agent đã tự trừ phần được hoàn từ trước, bỏ qua bước host từ chối và thiếu `policy_denied` trong audit. Test `test_early_denial_does_not_replace_the_required_host_audit` phân biệt hai đường xử lý có cùng số dư.
