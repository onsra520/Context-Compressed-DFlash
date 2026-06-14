# CC-DFlash Part 5 Layout Refinement Report (UI-17)

Báo cáo tiến độ hoàn thiện căn gióng giao diện (UI/Layout) cho **Part 5 — Results & Claim Safety** trên trang thuyết trình CC-DFlash.

## Chi tiết các công việc đã thực hiện

### 1. Loại bỏ và Gộp nội dung Card 5.1 cũ

* **Vấn đề**: Card `Cách đọc phần kết quả` (5.1 cũ) có kích thước quá nhỏ, gây manh mún bố cục và nội dung của nó thực chất chỉ là một note hướng dẫn đọc kết quả.
* **Giải pháp**:
  * Xóa hoàn toàn card `Cách đọc phần kết quả` riêng biệt.
  * Tích hợp nội dung note đọc kết quả vào card **GSM8K Results Summary** (5.1 mới) ngay bên dưới câu giới thiệu mở đầu.
  * Định nghĩa lớp CSS `.reading-note-strip` cho note này với thiết kế tinh gọn, độ tương phản vừa phải để hoạt động như một “reading note” nhẹ nhàng mà không làm phân tán sự chú ý khỏi bảng kết quả chính.

### 2. Tinh gọn Card GSM8K Results Summary (5.1 mới)

* Cập nhật số thứ tự thẻ thành `5.1`.
* Loại bỏ khối `.claim-line` cũ có kích thước chữ quá lớn và nặng nề, thay bằng lớp `.claim-line-small` với font chữ nhỏ hơn và padding gọn gàng hơn.
* Rút gọn câu ghi nhận kết quả:
  > **GSM8K**: compressed DFlash path giữ numeric-quality proxy ngang compression-only trong setting đã test.
* Đảm bảo bảng số kết quả GSM8K vẫn được giữ nguyên vẹn.

### 3. Tái cấu trúc Card QMSum Diagnostic Summary (5.2 mới)

* **Vấn đề**: Card này trước đây chỉ rộng 1 cột trên desktop, tạo ra khoảng trống lớn bên phải và chứa khối callout `.claim-line` quá nặng nề.
* **Giải pháp**:
  * Cho phép Card QMSum chiếm full width (`wide`) trên desktop để cân bằng bố cục.
  * Thiết kế lại cấu trúc bên trong card thành 2 cột đều nhau trên desktop thông qua `.qmsum-columns` (tự động stack dọc trên mobile):
    * **Cột trái (Diagnostic Signal)**: Mô tả vai trò quan sát hành vi của pipeline trong long-context.
    * **Cột phải (Claim Boundary)**: Nêu rõ các giới hạn chất lượng phát hiện qua triage (cap-hit, proxy degradation...).
  * Thay thế callout cồng kềnh cũ bằng một `.compact-caveat-strip` mảnh, gọn nằm ở cuối card:
    > QMSum chỉ là long-context diagnostic evidence, không phải semantic correctness benchmark.

### 4. Đánh số lại toàn bộ Part 5 (Renumbering)

Để đảm bảo cấu trúc liền mạch sau khi loại bỏ card 5.1 cũ, các thẻ card đã được đánh số lại như sau:

* **5.1** GSM8K Results Summary (formerly 5.2)
* **5.2** QMSum Diagnostic Summary (formerly 5.3)
* **5.3** Claim-safety boundary (formerly 5.4)
* **5.4** Những claim không được dùng (formerly 5.5)

## Kết quả Verification

1. **HTML Validation**: Chạy công cụ kiểm tra thẻ HTML, không phát hiện lỗi cú pháp hay thẻ chưa đóng.
2. **Backend Regression**: Toàn bộ 179 ca kiểm thử `pytest` vượt qua 100% thành công.
3. **Phạm vi bảo toàn**:
   * Không sửa đổi nội dung của bảng Claim-safety boundary.
   * Không sửa đổi danh sách các claims không được dùng.
   * Giữ nguyên các Part 1-4, Part 6 và hệ thống canvas/background.
