# Báo cáo tinh chỉnh dữ liệu bảng QMSum và nội dung diễn giải (UI-23)

Báo cáo tiến độ cập nhật dữ liệu bảng số liệu QMSum (5.3) và hoàn thiện nội dung phần QMSum Interpretation (5.4) trong tệp `frontend/pages/cc-dflash/cc-dflash.html`.

## Chi tiết các công việc đã thực hiện

### 1. Cập nhật bảng dữ liệu QMSum Results Table (Section 5.3)

* Đổi tên tiêu đề thành: **QMSum Diagnostic Results — Long-context Full Matrix**.
* Cập nhật đoạn mở đầu:
  > Khác với GSM8K, QMSum không dùng numeric exact-match. QMSum được dùng để quan sát long-context diagnostic behavior: input length, prefill, compression overhead, end-to-end latency, compression ratio và lexical overlap proxy. Vì rerun cuối của QMSum không hoàn chỉnh, bảng này dùng full diagnostic matrix làm nguồn metric chính.
* Cập nhật phần lưu ý về nguồn metric:
  > Lưu ý về nguồn metric: Bảng dưới dùng full diagnostic matrix làm reference vì đây là lần chạy duy nhất có đủ bốn conditions ở n=30. Rerun cuối không dùng để so sánh hoặc xếp hạng condition vì Baseline-AR có đủ 30 rows, DFlash-R1 chỉ có 2 rows, còn LLMLingua-AR-R2 và CC-DFlash-R2 không có rows hoàn chỉnh.
* Bổ sung các cột dữ liệu đầy đủ:
  * **Condition**, **Overlap proxy**, **Cap hits**, **Input tokens**, **Compression ratio**, **T_prefill**, **T_compress**, **Avg e2e**, **E2E tok/s**, **Kết luận an toàn**.
* Cập nhật dữ liệu chính xác cho 4 conditions:
  * **Baseline-AR**: Overlap proxy: `0.233`, Cap hits: `0`, Input tokens: `1999`, Compression ratio: `—`, T_prefill: `687ms`, T_compress: `0ms`, Avg e2e: `4.264s`, E2E tok/s: `14.45`.
  * **DFlash-R1**: Overlap proxy: `0.234`, Cap hits: `0`, Input tokens: `1999`, Compression ratio: `—`, T_prefill: `656ms`, T_compress: `0ms`, Avg e2e: `3.097s`, E2E tok/s: `19.54`.
  * **LLMLingua-AR-R2**: Overlap proxy: `0.359`, Cap hits: `22`, Input tokens: `979`, Compression ratio: `2.07×`, T_prefill: `375ms`, T_compress: `5576ms`, Avg e2e: `26.378s`, E2E tok/s: `13.21`.
  * **CC-DFlash-R2**: Overlap proxy: `0.357`, Cap hits: `21`, Input tokens: `979`, Compression ratio: `2.07×`, T_prefill: `388ms`, T_compress: `5928ms`, Avg e2e: `19.056s`, E2E tok/s: `18.12`.
* Cập nhật footer caveat của Section 5.3:
  > QMSum chỉ dùng để chẩn đoán long-context behavior: input length, prefill, compression overhead, compression ratio, cap pressure, latency và lexical/normalized proxy. Không dùng QMSum để claim semantic correctness hoặc final quality.

### 2. Cập nhật QMSum Interpretation (Section 5.4)

* Đổi tên tiêu đề thành: **QMSum Interpretation — Diagnostic Timing và Proxy**.
* Cấu trúc lại nội dung diễn giải với 5 mục so sánh:
  1. **Baseline-AR vs DFlash-R1**: DFlash-R1 có local e2e timing tốt hơn Baseline-AR trên QMSum diagnostic reference. Tuy nhiên, đây chỉ là long-context diagnostic behavior, không phải final speedup claim hay production speedup.
  2. **LLMLingua-AR-R2 vs Baseline-AR**: LLMLingua-AR-R2 có overlap proxy cao hơn Baseline-AR và giảm input tokens từ khoảng 1999 xuống 979, nhưng avg e2e latency cao hơn nhiều vì phải trả thêm chi phí nén và bị cap pressure. Vì vậy compression-only không được claim là luôn hữu ích end-to-end.
  3. **CC-DFlash-R2 vs LLMLingua-AR-R2**: Đây là cặp quan trọng nhất cho compressed path trên QMSum. CC-DFlash-R2 nhanh hơn LLMLingua-AR-R2 và có overlap proxy gần tương đương, nên có thể nói DFlash giúp cải thiện compressed path trong diagnostic reference. Nhưng vì QMSum dùng lexical proxy, không được claim semantic correctness.
  4. **CC-DFlash-R2 vs DFlash-R1**: Không dùng QMSum để nói CC-DFlash-R2 thắng DFlash-R1 toàn diện. DFlash-R1 vẫn nhanh hơn vì không phải trả chi phí nén. CC-DFlash-R2 chỉ nên được đọc như compressed-DFlash path tốt hơn compression-only path, không phải universal speedup so với DFlash-R1.
  5. **QMSum rerun caveat**: Rerun cuối không được dùng để so sánh QMSum vì dữ liệu không hoàn chỉnh: Baseline-AR có đủ 30 rows, DFlash-R1 chỉ có 2 rows, còn LLMLingua-AR-R2 và CC-DFlash-R2 không có rows hoàn chỉnh. Vì vậy, các so sánh trong phần QMSum phải dựa trên full diagnostic matrix, còn rerun cuối chỉ cho thấy caveat về local runtime/rerun stability.
* Cập nhật kết luận an toàn ở cuối Section 5.4:
  > Kết luận an toàn: QMSum chỉ hỗ trợ đọc long-context diagnostic behavior như latency, prefill, overhead, compression ratio, cap pressure và lexical proxy. QMSum không chứng minh semantic correctness, final correctness, universal speedup hoặc deployment readiness.

### 3. Chuẩn hóa thuật ngữ & Tránh các từ khóa nội bộ

* Đã lọc sạch và không để hiển thị các từ `Task69`, `Task71`, `Task80A`, `Task80B`, `Task81` trong bất kỳ nội dung nào người đọc nhìn thấy.
* Sử dụng chính xác và thống nhất các từ ngữ theo chỉ thị: `"full diagnostic matrix"`, `"rerun cuối"`, `"rerun caveat"`, `"diagnostic reference"`, `"local runtime evidence"`, `"lexical proxy"`, và `"semantic correctness"`.

## Kết quả Verification

1. **HTML Validation**: Chạy công cụ kiểm tra thẻ đóng-mở HTML `validate_html.py` thành công không phát hiện lỗi cấu trúc.
2. **Pytest Regression**: Toàn bộ 179 ca kiểm thử Pytest chạy thành công 100%.
