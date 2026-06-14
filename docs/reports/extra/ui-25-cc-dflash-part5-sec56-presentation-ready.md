# Báo cáo tinh chỉnh trình bày Section 5.6 (UI-25)

Báo cáo tiến độ cấu trúc lại Section 5.6 từ hướng ranh giới kiểm duyệt nội bộ thành một phiên bản trình bày thân thiện hơn với người nghe thuyết trình (`Kết luận đúng phạm vi`).

## Chi tiết các công việc đã thực hiện

### 1. Thay đổi tiêu đề và đoạn mở đầu của Section 5.6

* **Tiêu đề mới**: `Kết luận đúng phạm vi`

* **Đoạn mở đầu mới**:
  > Bảng này tóm tắt cách nên hiểu kết quả của project. Mỗi kết luận chỉ có giá trị trong phạm vi dataset, metric và môi trường chạy đã kiểm chứng. Vì vậy, thay vì kết luận quá rộng, report chỉ trình bày những gì evidence hiện tại thật sự hỗ trợ.

### 2. Định dạng lại Bảng 5.6 thành 3 cột

* **Các cột mới**: `Phạm vi evidence`, `Kết luận nên trình bày`, `Giới hạn cần nhắc`

* **Nội dung các hàng**:
  1. **GSM8K**:
     * Kết luận nên trình bày: `Numeric-quality proxy tương đối ổn định trong n=30: Baseline-AR đạt 25/30, ba condition còn lại đạt 24/30.`
     * Giới hạn cần nhắc: `Đây là short-context numeric proxy, không phải semantic correctness tổng quát.`
  2. **QMSum**:
     * Kết luận nên trình bày: `QMSum cho thấy long-context diagnostic behavior: latency, prefill, compression overhead, compression ratio và lexical proxy.`
     * Giới hạn cần nhắc: `QMSum không được dùng để chứng minh semantic correctness hoặc final quality.`
  3. **Timing**:
     * Kết luận nên trình bày: `Một số cặp so sánh cho thấy lợi ích timing trong local runtime, đặc biệt CC-DFlash-R2 so với LLMLingua-AR-R2.`
     * Giới hạn cần nhắc: `Không kết luận universal speedup hoặc production speedup.`
  4. **Compression**:
     * Kết luận nên trình bày: `Compression giúp giảm input tokens và prefill, nhưng phải trả thêm chi phí nén.`
     * Giới hạn cần nhắc: `Compression chỉ có lợi khi phần tiết kiệm được lớn hơn chi phí nén.`
  5. **DFlash-R1**:
     * Kết luận nên trình bày: `DFlash-R1 vẫn là baseline mạnh trong cả GSM8K và QMSum diagnostic reference.`
     * Giới hạn cần nhắc: `Không dùng runtime caveat để kết luận DFlash-R1 bị lỗi hoặc bị regression.`
  6. **Deployment**:
     * Kết luận nên trình bày: `Project hiện là MVP/evidence package cho đánh giá giả thuyết.`
     * Giới hạn cần nhắc: `Chưa claim deploy-ready hoặc confirmed 8GB deployment.`

### 3. Cập nhật Note tóm tắt an toàn

* Đổi nội dung thành:
  > **Thông điệp an toàn khi thuyết trình:** CC-DFlash có evidence có điều kiện. Trên GSM8K, numeric-quality proxy tương đối ổn định. Trên QMSum, kết quả chỉ dùng để chẩn đoán long-context behavior. CC-DFlash-R2 có lợi rõ nhất khi so với compression-only path, nhưng chưa chứng minh universal speedup, final correctness, QMSum semantic correctness hoặc deployment readiness.

## Kết quả Verification

1. **HTML Validation**: Cú pháp HTML hoàn toàn chính xác, không có tag mở/đóng sai lệch (`HTML Validation Passed`).
2. **Backend Regression**: Toàn bộ 179 ca kiểm thử backend Pytest đều chạy thành công 100%.
