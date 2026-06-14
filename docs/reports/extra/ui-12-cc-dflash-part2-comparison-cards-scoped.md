# CC-DFlash Part 2 Comparison Cards Scoped Layout Report

Báo cáo tiến độ sửa lỗi hiển thị và scope lại style của **Card 2.2 Vì sao compression có thể hữu ích?** và **Card 2.3 Không phải lossless end-to-end** trong phần **Part 2 — Method & Conditions** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Khôi phục label/part number về dạng pill nhỏ

* Lỗi phát sinh: Khi đặt `.section-card` là vertical flex container, thuộc tính mặc định `align-items: stretch` khiến thẻ con `.section-num` bị kéo giãn full width.
* Giải pháp: Thêm `align-self: flex-start;` trực tiếp vào định nghĩa lớp `.section-num` trong CSS. Điều này đảm bảo toàn bộ label số card (`2.1`, `2.2`, `2.3`, v.v.) co lại về kích thước pill nhỏ đúng chuẩn ban đầu, không bị kéo dài theo chiều ngang dù ở bất kỳ layout flexbox nào.

### 2. Scope lại layout flex của Card 2.2 và 2.3

* Trước đó, selector `@media (min-width: 761px) { .part-2 .section-grid .section-card }` đã áp dụng `display: flex; flex-direction: column;` lên toàn bộ các card của Part 2 (gồm cả 2.1, 2.4, 2.5), gây side effect không mong muốn.
* Giải pháp:
  * Tạo class chuyên biệt `.part2-comparison` trong HTML cho riêng hai card 2.2 và 2.3.
  * Chuyển đổi selector CSS trong media query desktop thành `.part2-comparison` và `.part2-comparison .insight-strip`.
  * Cách này giúp scope toàn bộ layout flex và căn gióng bottom callout vào đúng phạm vi của 2.2 và 2.3, bảo vệ hoàn toàn bố cục của các card 2.1, 2.4, 2.5 và các Part khác (Part 1, Part 3–6).

### 3. Đồng bộ hóa vị trí Callout và triệt tiêu overlap

* Layout desktop của cặp card `2.2` và `2.3` sử dụng vertical flexbox cục bộ (`.part2-comparison`), đẩy callout dưới cùng `.insight-strip` xuống đáy qua `margin-top: auto`.
* Nhờ cấu trúc HTML chuẩn và không dùng absolute positioning, nội dung tự động wrap tự nhiên mà không xảy ra hiện tượng đè chữ (overlap) hay tràn khung (overflow) ngay cả khi kích thước màn hình thay đổi.
* Trên các thiết bị di động, media query tự động chuyển lưới về 1 cột dọc và trả khoảng cách về mốc mặc định an toàn.

## Tình trạng và Giới hạn (Scope)

* **Không đổi nội dung kỹ thuật**: Giữ nguyên toàn bộ tiêu đề, danh sách bullet points và văn bản callout theo đúng yêu cầu đặc tả.
* **Không ảnh hưởng các thành phần khác**: Các Part 1 và Part 3–6 không bị sửa đổi ngoài ý muốn. Hệ thống canvas background và shader animation được bảo toàn nguyên vẹn.
