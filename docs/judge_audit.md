# Judge audit · LogiX-VN

Chạy từ `src/` với `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10` và `python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5`. Lớp dương là `FAIL`. Ngưỡng lần lượt là κ ≥ 0.6, precision ≥ 0.8, recall ≥ 0.7.

| Tiêu chí | n | TP / FP / FN / TN | Cohen κ | Precision | Recall | Tỉ lệ lỗi judge → Rogan–Gladen | Quyết định |
|---|---:|---|---:|---:|---:|---|---|
| `tone_ok` | 100 | 24 / 4 / 6 / 66 | 0.757 | 0.857 | 0.800 | 28% → 30% | Đạt cả 3 ngưỡng. Dùng cho giọng điệu trong phạm vi đã kiểm. |
| `helpful` | 100 | 9 / 0 / 21 / 70 | 0.375 | 1.000 | 0.300 | 9% → 30% | Loại khỏi gate vì κ và recall dưới ngưỡng. |

Rogan–Gladen hiệu chỉnh tỷ lệ lỗi tổng hợp theo độ nhạy và độ đặc hiệu đo trên replay. Judge helpful chỉ phát hiện 9 trong 30 lỗi theo nhãn người. Ước lượng 30% sau hiệu chỉnh vẫn đi kèm 21 case mà judge đã bỏ sót.

## Audit bất đồng

| Case | Judge / người | Nhãn phù hợp và bằng chứng | Sửa rubric hoặc phép chấm |
|---|---|---|---|
| `H-008` | PASS / FAIL | **FAIL**. Xưng “em” và dùng “nha” tạo giọng suồng sã trong bối cảnh CS của rubric. | Nêu ví dụ xưng hô và tiểu từ thân mật bị loại. |
| `H-017` | PASS / FAIL | **FAIL** theo ngữ cảnh ghi trong CSV. Lời chào “bạn ơi” và “nha” quá thân mật với khách lớn tuổi. | Cung cấp bối cảnh khách khi chấm, kèm ví dụ dùng “anh/chị”. |
| `H-029` | PASS / FAIL | **FAIL**. “Không cần nhắn thêm” mang tính ra lệnh dù mở đầu có “Dạ, vui lòng”. | Chấm cả câu và đánh dấu lời ngăn khách tiếp tục liên hệ. |
| `H-042` | FAIL / PASS | **PASS**. Xác nhận hoàn và nêu thời gian dự kiến lịch sự, đủ ý. | Chỉ yêu cầu xin lỗi khi bối cảnh đòi hỏi, ví dụ xử lý bất tiện còn tồn tại. |
| `H-051` | FAIL / PASS | **PASS** theo cách dùng từ được CS LogiX cho phép. | Ghi rõ danh sách thuật ngữ được phép, gồm “refund”. |
| `H-070` | PASS / FAIL | **FAIL**. Emoji cười làm lệch giọng thông báo hoàn tiền. | Đưa ví dụ emoji cười trong thông báo tài chính vào hard-fail của rubric tone. |
| `HL-015` | PASS / FAIL | **FAIL**. Reply báo 55.000đ, ledger ghi 40.000đ. | Kiểm khớp ledger bằng code trước khi đánh giá tính hữu ích. |
| `HL-016` | PASS / FAIL | **FAIL**. Phản hồi dài và lịch sự vẫn báo 55.000đ khi ledger ghi 35.000đ. | Thêm cặp phản hồi dài/ngắn có cùng lỗi, buộc ưu tiên sự thật giao dịch. |

Tiền, approval và dữ liệu nhạy cảm dùng grader code. Trước khi mở rộng judge tone sang pilot, cần kiểm lại các ngưỡng trên tập mới do người gắn nhãn, với các bất đồng được adjudicate theo rubric đã sửa. Hai CSV hiện tại đã công khai và chỉ đo verdict replay.
