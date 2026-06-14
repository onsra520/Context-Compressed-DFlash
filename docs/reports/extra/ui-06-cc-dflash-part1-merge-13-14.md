# CC-DFlash Part 1 Card Merge Report

Báo cáo tiến độ gộp nội dung các thẻ `1.3` và `1.4` của phần **Part 1 — Lý do chuyển hướng** trên trang thuyết trình CC-DFlash thành một thẻ duy nhất.

## Chi tiết công việc đã thực hiện

### 1. Gộp nội dung 1.3 và 1.4 thành Card 1.3–1.4

* Đã xóa 2 card riêng lẻ cũ:
  * `1.3 Vì sao cần chuyển hướng`
  * `1.4 Ý nghĩa của việc chuyển sang CC-DFlash`
* Thay bằng một card mới duy nhất có label `1.3–1.4` và tiêu đề `Vì sao chuyển sang CC-DFlash?`.
* Nội dung của card gộp đã được tinh lọc và viết gọn gàng, súc tích hơn:
  * Phần đầu giải thích vì sao HTFSD quá phức tạp (overhead cao, acceptance thấp) và lý do chuyển sang hướng CC-DFlash độc lập hơn.
  * Phần Research Question được đóng khung làm nổi bật bằng container `.claim-line` (callout box dạng glassmorphism).

### 2. Thiết kế Badges/Chips hàng cuối

* Đã bổ sung CSS rules phục vụ hiển thị các nhãn tag ở cuối card:

  ```css
  .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 18px;
  }

  .badge-tag {
      display: inline-flex;
      align-items: center;
      padding: 6px 14px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.16);
      background: rgba(255, 255, 255, 0.08);
      color: rgba(255, 255, 255, 0.86);
      font-size: 13px;
      font-weight: 600;
      letter-spacing: 0.02em;
  }
  ```

* Sử dụng cấu trúc này để render 3 nhãn tag nhỏ xếp cạnh nhau trên cùng một dòng:
  * `Giả thuyết rõ hơn`
  * `Benchmark được`
  * `Audit được`

### 3. Layout Bố cục và Cân chỉnh Spacing

* Thiết lập class `wide` trên card gộp mới (`<article class="section-card wide">`) giúp nó tự động chiếm full width (trải rộng cả 2 cột trên desktop), xếp chồng thẳng hàng hoàn hảo dưới hai card `1.1` và `1.2`.
* Toàn bộ bố cục hiển thị của Part 1 hiện tại đạt cấu trúc hàng dọc 3 phần đều tăm tắp:
  * `1.1` (Full-width)
  * `1.2` (Full-width)
  * `1.3–1.4` (Full-width)
* Trên mobile, cả 3 card vẫn xếp chồng 1 cột mượt mà theo đúng thứ tự mà không bị tràn màn hình.

## Tình trạng và Giới hạn (Scope)

* Giữ nguyên nội dung của card `1.1` và `1.2`.
* Các phần Part 2–6, canvas, shader nền, và claim boundary được giữ nguyên hoàn toàn.
