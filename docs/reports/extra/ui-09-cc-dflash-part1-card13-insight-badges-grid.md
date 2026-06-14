# CC-DFlash Part 1 Card 1.3 Insight Badges Grid Report

Báo cáo tiến độ hoàn thành tối ưu hóa layout hiển thị cho 3 chip/tag nhãn của Research Question bên trong thẻ **1.3 Từ blocker sang CC-DFlash** của phần **Part 1 — Lý do chuyển hướng** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Đồng bộ chiều rộng bằng 3-column CSS Grid (Desktop)

* Thay đổi thuộc tính layout của container `.insight-badges` từ `display: flex` sang `display: grid; grid-template-columns: repeat(3, minmax(0, 1fr))` trên môi trường máy tính (desktop).
* Thao tác này đảm bảo 3 chip/tag có chiều rộng giống hệt nhau (`1fr`), nằm thẳng hàng, và có khoảng cách giãn cách đồng đều (`gap: 12px`).
* Khắc phục hoàn toàn hiện trạng chip cuối dài hơn gây lệch bố cục.

### 2. Căn giữa văn bản của các chip

* Cập nhật kiểu hiển thị của `.insight-badge` thành `display: flex; justify-content: center; text-align: center;`.
* Định nghĩa thêm `box-sizing: border-box` và padding hợp lý (`6px 12px`, border-radius `8px`) để văn bản hiển thị gọn gàng, căn giữa tuyệt đối trong từng cột.

### 3. Hỗ trợ hiển thị trên thiết bị di động (Mobile Responsive)

* Thêm CSS quy định trong media query `@media (max-width: 760px)` của `.insight-badges`:
  ```css
  .insight-badges {
      grid-template-columns: 1fr;
      gap: 8px;
  }
  ```
* Trên màn hình di động, 3 chip sẽ tự động xếp chồng (stack) theo chiều dọc, giữ nguyên chiều rộng bằng nhau và không bị tràn hay lỗi bố cục (overflow-safe).

## Tình trạng và Giới hạn (Scope)

* **Giữ nguyên nội dung và tiêu đề**: Không sửa đổi nội dung text của câu hỏi nghiên cứu, text của 3 chip nhãn, hay title của Card 1.3.
* **Giữ nguyên Part 1.1, 1.2 & Part 2-6**: Các cấu trúc và nội dung khác hoàn toàn được bảo vệ.
* **Canvas / Shaders / Backend / Claims**: Không có bất kỳ thay đổi nào liên quan đến logic kỹ thuật chính của dự án.
