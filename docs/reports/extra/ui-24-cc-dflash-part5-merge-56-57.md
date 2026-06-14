# Báo cáo gộp các mục Claim-safety boundary và Những claim không được dùng (UI-24)

Báo cáo tiến độ cấu trúc lại Phần 5, gộp hai Section 5.6 (Claim-safety boundary) và 5.7 (Những claim không được dùng) thành một mục duy nhất.

## Chi tiết các công việc đã thực hiện

### 1. Gộp Section 5.6 và 5.7 thành Section 5.6 mới

* **Tiêu đề mới**: `Claim-safety boundary — Những câu không được nói`

* **Đoạn mở đầu mới**:
  > Bảng này xác định ranh giới kết luận của project: kết quả hiện tại cho phép nói gì, và chưa đủ cơ sở để nói gì. Khi thuyết trình, mọi kết luận cần gắn với phạm vi “trong setting đã test”, “theo proxy”, hoặc “trong diagnostic reference”, thay vì nói như một kết luận tổng quát.

* **Cấu trúc Bảng 5.6 mới**: Đổi sang bảng có 4 cột:
  * **Evidence area**, **Có thể nói**, **Không được nói**, **Cách nói an toàn**.

* **Nội dung các hàng trong bảng**:
  1. **GSM8K**:
     * Có thể nói: `Numeric-quality proxy tương đối ổn định trong n=30.`
     * Không được nói: `CC-DFlash có semantic correctness tổng quát hoặc final correctness.`
     * Cách nói an toàn: `Trên GSM8K, các condition cho thấy numeric-quality pattern tương đối ổn định trong setting đã test.`
  2. **QMSum**:
     * Có thể nói: `QMSum hỗ trợ quan sát long-context diagnostic behavior: latency, prefill, overhead, compression ratio và lexical proxy.`
     * Không được nói: `QMSum chứng minh semantic correctness hoặc final quality.`
     * Cách nói an toàn: `Trên QMSum, kết quả chỉ dùng để chẩn đoán behavior của pipeline trên long-context.`
  3. **Timing**:
     * Có thể nói: `Các số timing là local runtime observation trong môi trường đã audit.`
     * Không được nói: `Universal speedup hoặc production speedup.`
     * Cách nói an toàn: `CC-DFlash-R2 có lợi về timing trong một số cặp so sánh local, đặc biệt so với compression-only path.`
  4. **Compression**:
     * Có thể nói: `Compression giảm input tokens và prefill, nhưng phải trả thêm chi phí nén.`
     * Không được nói: `Compression luôn hữu ích end-to-end trong mọi trường hợp.`
     * Cách nói an toàn: `Compression chỉ có lợi khi input/prefill saving và DFlash gain vượt được chi phí nén.`
  5. **DFlash-R1**:
     * Có thể nói: `DFlash-R1 vẫn là baseline mạnh; timing shift trong rerun chỉ là runtime/timing watch.`
     * Không được nói: `DFlash-R1 bị broken hoặc bị chứng minh là regression.`
     * Cách nói an toàn: `Không dùng rerun chưa ổn định để kết luận DFlash-R1 bị lỗi.`
  6. **Deployment**:
     * Có thể nói: `Project chưa claim deployment.`
     * Không được nói: `Deploy-ready hoặc confirmed 8GB deployment.`
     * Cách nói an toàn: `Hiện tại project là MVP/evidence package, chưa phải deployment proof.`

### 2. Bổ sung dải note tổng kết an toàn sau bảng

* Thêm một `reading-note-strip`:
  > **Cách nói tổng kết an toàn:** CC-DFlash có evidence có điều kiện. Trên GSM8K, numeric-quality proxy tương đối ổn định. Trên QMSum, kết quả chỉ dùng để chẩn đoán long-context behavior. CC-DFlash-R2 có lợi nhất khi so với compression-only path, nhưng chưa chứng minh universal speedup, final correctness, QMSum semantic correctness, deployment readiness hoặc confirmed 8GB deployment.

### 3. Xóa hoàn toàn Section 5.7 cũ

* Đã gỡ bỏ toàn bộ tệp thẻ `<article>` chứa Section 5.7 cũ (`Những claim không được dùng`), bảo đảm không để lại khoảng trống hay article rỗng, đồng thời không còn số thứ tự 5.7 nào xuất hiện trong Part 5.

## Kết quả Verification

1. **HTML Validation**: Tập lệnh `validate_html.py` trả về kết quả đạt yêu cầu (`HTML Validation Passed: No syntax errors or unclosed tags`).
2. **Backend Regression**: Toàn bộ 179 ca kiểm thử Pytest chạy thành công 100%.
