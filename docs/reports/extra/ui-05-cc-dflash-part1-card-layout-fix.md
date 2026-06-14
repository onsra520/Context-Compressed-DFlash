# CC-DFlash Part 1 Card Layout Fix Report

Báo cáo tiến độ cập nhật bố cục hiển thị các thẻ nội dung của **Part 1 — Lý do chuyển hướng** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Cập nhật CSS Grid cho Part 1

* Đã thay đổi số lượng cột hiển thị của lưới nội dung trong Part 1 từ dạng tỷ lệ lệch (`0.9fr 1.1fr`) sang dạng 2 cột bằng nhau:

  ```css
  .part-1 .section-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      align-items: stretch;
  }
  ```

* Cách cấu hình này đảm bảo khi hai card nằm cùng hàng, chúng sẽ chia sẻ chiều rộng đều nhau (`50% / 50%`) và tự động kéo giãn chiều cao để cân bằng nhau.

### 2. Thiết lập hiển thị hàng dọc cho các card 1.1 và 1.2

* Đã thêm class `wide` vào thẻ `<article>` của hai card:
  * Card 1.1: **Mục tiêu ban đầu**
  * Card 1.2: **Blocker của HTFSD**
* Class `wide` kế thừa thuộc tính `grid-column: 1 / -1;` có sẵn, giúp hai card này trải rộng chiếm toàn bộ chiều ngang của grid (full width), mỗi card chiếm riêng một hàng độc lập từ trên xuống.
* Kết quả là sơ đồ hiển thị đạt đúng mong muốn:

  ```txt
  1.1 (Mục tiêu ban đầu - Full width)
  1.2 (Blocker của HTFSD - Full width)
  1.3 (Vì sao cần chuyển hướng) | 1.4 (Ý nghĩa của việc chuyển sang CC-DFlash)
  ```

### 3. Đồng bộ hóa Responsive cho Mobile / Tablet

* Để tránh việc grid có độ ưu tiên CSS cao hơn đè lên thiết lập mobile, đã đồng bộ hóa trong media query `@media (max-width: 760px)`:

  ```css
  .section-grid,
  .part-1 .section-grid {
      grid-template-columns: 1fr;
  }
  ```

* Cấu hình này giúp trên màn hình nhỏ, cả 4 card tự động chuyển về xếp chồng 1 cột theo đúng thứ tự từ 1.1 đến 1.4 mà không bị tràn màn hình hoặc lệch chiều rộng.

## Tình trạng và Giới hạn (Scope)

* Giữ nguyên toàn bộ nội dung văn bản của Part 1.
* Không thay đổi các phần Part 2–6.
* Không ảnh hưởng tới canvas, shader nền, hoặc claim boundary.
