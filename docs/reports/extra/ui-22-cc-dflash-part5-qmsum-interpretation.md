# Báo cáo tinh chỉnh Bố cục QMSum Interpretation (UI-22)

Báo cáo tiến độ cấu trúc lại bố cục Phần 5, phân tách QMSum Results Table và QMSum Interpretation, đồng thời chuyển dịch các section sau đó trong tệp `frontend/pages/cc-dflash/cc-dflash.html`.

## Chi tiết các công việc đã thực hiện

### 1. Cấu trúc lại bố cục Phần 5 thành các Section từ 5.1 đến 5.7

* **Section 5.1**: GSM8K Results Table (giữ nguyên).
* **Section 5.2**: GSM8K Interpretation (giữ nguyên).
* **Section 5.3**: QMSum Results Table (chỉ chứa tiêu đề, đoạn mở đầu, lưu ý nguồn metric, bảng số liệu 4 conditions và footer caveat. Loại bỏ các so sánh chi tiết sang 5.4).
* **Section 5.4 (Mới)**: Tiêu đề **QMSum Interpretation — Diagnostic Timing và Proxy**. Diễn giải trực tiếp từ bảng 5.3 với:
  * Một đoạn `<p>` mở đầu.
  * Một danh sách so sánh (`comparison-list`) chứa 5 mục:
    1. **Baseline-AR vs DFlash-R1**: Đối chiếu timing trong diagnostic reference, nhấn mạnh tính chất long-context diagnostic behavior, không claim final/production speedup.
    2. **LLMLingua-AR-R2 vs Baseline-AR**: Đối chiếu timing nén và cap pressure ảnh hưởng đến latency e2e.
    3. **CC-DFlash-R2 vs LLMLingua-AR-R2**: Điểm mấu chốt chứng minh tích hợp DFlash giúp cải thiện tốc độ của compressed path nhưng không claim semantic correctness.
    4. **CC-DFlash-R2 vs DFlash-R1**: Làm rõ DFlash-R1 vẫn nhanh hơn do không tốn chi phí nén, không claim universal speedup so với DFlash-R1.
    5. **QMSum rerun caveat**: Giải thích lý do vì sao bảng 5.3 lấy full diagnostic matrix làm nguồn metric chính thay vì rerun cuối.
  * Một `reading-note-strip` kết luận an toàn ở cuối:
    `Kết luận an toàn: QMSum chỉ hỗ trợ đọc long-context diagnostic behavior như latency, overhead, compression ratio, cap pressure và lexical proxy. QMSum không chứng minh semantic correctness, final correctness, universal speedup hoặc deployment readiness.`
* **Section 5.5**: Cross-dataset Interpretation (chuyển dịch từ 5.4 cũ).
* **Section 5.6**: Claim-safety boundary (chuyển dịch từ 5.5 cũ).
* **Section 5.7**: Những claim không được dùng (chuyển dịch từ 5.6 cũ).

### 2. Chuẩn hóa thuật ngữ & Tránh từ khóa nội bộ

* **Loại bỏ hoàn toàn từ khóa nội bộ**: Đảm bảo không chứa `Task69`, `Task71`, `Task80A`, `Task81`, `T80B`. Riêng `Task80B` cũ trong bảng Claim-safety boundary đã được chuyển thành cụm từ trung tính `"trong các lần chạy"`.
* **Sử dụng các thuật ngữ trình bày trực quan**:
  * "rerun xác nhận cuối"
  * "speed reference"
  * "full diagnostic matrix"
  * "rerun caveat"
  * "runtime/timing watch"
  * "diagnostic reference"
* Đảm bảo không sử dụng cụm từ "Cách đọc" trong Part 5 (sử dụng "Diễn giải", "Kết luận an toàn", hoặc "Phạm vi diễn giải").

### 3. Cập nhật tiến độ & Roadmap

* Cập nhật thông tin task `UI-22` vào bảng theo dõi [task.md](file:///home/quyseggs/CCDF/docs/plans/task.md) và dòng thời gian của dự án tại [Roadmap.html](file:///home/quyseggs/CCDF/docs/Roadmap.html).

## Kết quả Verification

1. **HTML Validation**: Tập lệnh `validate_html.py` xác nhận cấu trúc tài liệu HTML chuẩn, không lỗi tag.
2. **Backend Regression**: Toàn bộ 179 ca kiểm thử `pytest` chạy thành công 100% không gặp lỗi hồi quy.
