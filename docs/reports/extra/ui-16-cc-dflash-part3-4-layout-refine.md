# CC-DFlash Part 3 & 4 Layout Refinement Report (UI-16)

Báo cáo chi tiết các điều chỉnh giao diện (UI/Layout) cho **Part 3 — Benchmark & Evaluation** và **Part 4 — Experiment Journey** trên trang thuyết trình CC-DFlash.

## Chi tiết các thay đổi đã thực hiện

### A. Căn gióng và đồng đều chiều cao Card 3.1 & 3.2 (Part 3)

* **Vấn đề**: Trên desktop, Card 3.1 và Card 3.2 đứng cạnh nhau nhưng có sự chênh lệch về chiều cao nội dung, làm cho giao diện không cân đối ở phần đáy.
* **Giải pháp**:
  * Đặt `height: 100%` cho lớp `.part3-comparison` khi ở màn hình lớn (desktop) để đảm bảo hai hộp thẻ card co dãn hoàn toàn theo chiều dọc của hàng lưới (`align-items: stretch` hoạt động triệt để).
  * Thêm thuộc tính `margin-top: auto` cho phần tử con cuối cùng của thẻ card (`.part3-comparison > *:last-child`).
  * **Hiển thị**: Giúp đẩy danh sách có thứ tự ở Card 3.1 và đoạn văn giải thích ở Card 3.2 xuống sát đáy, tạo sự căn gióng song song cân đối tuyệt đối ở cả cạnh trên và cạnh dưới.

### B. Tái cấu trúc và tối ưu hóa Part 4 — Experiment Journey

#### 1. Định dạng Badge Flow cho Card 4.1

* **Vấn đề**: Dòng flow cũ sử dụng style thô của `.pipe-node` với chiều cao lớn (44px) và các góc bo tròn nhỏ, làm cho flow trông nặng nề.
* **Giải pháp**:
  * Định nghĩa lớp CSS riêng biệt `.audit-flow-strip .pipe-node` để biến các nút flow thành dạng badge/chip bo tròn hoàn toàn (`border-radius: 999px`), bỏ chiều cao tối thiểu (`min-height: unset`) và điều chỉnh độ cao chỉ còn `32px` với padding gọn (`0 16px`).
  * **Hiển thị**: Tạo ra một pipeline/chip flow cực kỳ thanh mảnh, hiện đại, dễ đọc và tự động stack dọc/xoay mũi tên khi thu nhỏ màn hình (mobile responsive).

#### 2. Đồng bộ kích thước và căn chỉnh 4 Blocker Cards (4.2 – 4.5)

* **Vấn đề**: Các blocker cards có lượng thông tin lệch nhau, khi xếp thành lưới 2x2 trên desktop tạo cảm giác không đồng đều về nhịp điệu nội dung.
* **Giải pháp**:
  * Chuẩn hóa cấu trúc nội dung của cả 4 card: mỗi card có chính xác 2 đoạn văn (Đoạn 1 mô tả blocker & cách sửa; Đoạn 2 ghi nhận evidence/limitation còn lại).
  * Gắn lớp `.blocker-evidence` cho đoạn văn thứ hai của mỗi card.
  * Cấu hình CSS cho `.part4-blocker` trên desktop sử dụng `display: flex; flex-direction: column; height: 100%;` kết hợp `margin-top: auto;` cho `.blocker-evidence`.
  * **Hiển thị**: Khi co dãn theo grid stretch, phần thông tin evidence/limitation của Card 4.2 & 4.3 (hàng 1) và Card 4.4 & 4.5 (hàng 2) được đẩy xuống sát đáy card một cách đồng bộ và đối xứng.

#### 3. Thiết lập Card 4.6 (Runtime caveat) chiếm Full Width

* Đảm bảo Card 4.6 có lớp `.section-card.wide` để tự động trải rộng hết 2 cột của lưới grid (`grid-column: 1 / -1`), loại bỏ khoảng trống thừa ở bên phải và nằm gọn gàng bên dưới lưới 2x2.

#### 4. Đổi tiêu đề Card 4.7

* Tiêu đề Card 4.7 được đổi thành: **Bảng tổng hợp audit evidence** giúp tinh gọn và làm nổi bật vai trò tổng hợp của bảng dữ liệu so với tiêu đề cũ quá dài dòng.

## Đánh giá và Verification

1. **HTML Validation**: Đã chạy bộ phân tích cú pháp HTML tĩnh, xác nhận không có thẻ nào bị đóng sai hoặc bị thiếu.
2. **Backend Regression**: Đã chạy toàn bộ 179 backend test cases và đều vượt qua 100%.
3. **Phạm vi bảo toàn**:
   * Không sửa đổi nội dung và claim kỹ thuật của nghiên cứu.
   * Không ảnh hưởng tới Part 1, Part 2, Part 5, Part 6 và các shader/canvas background.
