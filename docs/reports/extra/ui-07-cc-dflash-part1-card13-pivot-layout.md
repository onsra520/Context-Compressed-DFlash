# CC-DFlash Part 1 Card 1.3 Pivot Layout Report

Báo cáo tiến độ tái cấu trúc hiển thị cho thẻ **1.3 Từ blocker sang CC-DFlash** trong phần **Part 1 — Lý do chuyển hướng** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Cấu trúc lại Card 1.3 và đổi tiêu đề

* Đổi mã số thẻ từ `1.3–1.4` thành `1.3` duy nhất theo yêu cầu tối ưu nhãn.
* Cập nhật tiêu đề chính của card thành **"Từ blocker sang CC-DFlash"**.

### 2. Thiết kế Lưới Đối xứng 2 Cột (Pivot Layout) cho nội dung

* Thay vì hiển thị văn bản dạng đoạn văn dài (paragraph), nội dung so sánh đối chiếu đã được tách thành lưới 2 cột đối xứng trực quan thông qua class `.pivot-container` và các cột `.pivot-column`:
  * **Cột trái (HTFSD blocker):** Giải thích lý do dừng hướng HTFSD (phức tạp, overhead cao, acceptance thấp, khó benchmark).
  * **Cột phải (CC-DFlash pivot):** Giải thích lý do chuyển hướng sang CC-DFlash (giữ DFlash core, nén phía trước, giả thuyết dễ đo, dễ audit).
* Ở giữa hai cột có một ký tự mũi tên chuyển tiếp `→` (`.pivot-arrow`) để thể hiện rõ ràng luồng tư duy chuyển đổi (flow pivot).
* Đã bổ sung các CSS classes cần thiết:

  ```css
  .pivot-container {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
      align-items: center;
      gap: 24px;
      margin-top: 20px;
  }

  .pivot-column {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 20px;
      padding: 20px;
      text-align: left;
  }

  .pivot-column h4 {
      margin: 0 0 10px 0;
      color: #ffffff;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
  }

  .pivot-column p {
      margin: 0 0 14px 0;
      font-size: 14px;
      line-height: 1.55;
      color: rgba(255, 255, 255, 0.7);
  }

  .pivot-column ul {
      margin: 0;
      padding-left: 1.2rem;
      display: grid;
      gap: 6px;
  }

  .pivot-column li {
      font-size: 13.5px;
      color: rgba(255, 255, 255, 0.86);
  }

  .pivot-arrow {
      font-size: 28px;
      color: rgba(255, 255, 255, 0.32);
      user-select: none;
  }
  ```

### 3. Đồng bộ hóa Responsive cho các màn hình di động

* Đã tinh chỉnh trong media query `@media (max-width: 760px)` để đảm bảo khi xem trên màn hình nhỏ:
  * Lưới `.pivot-container` chuyển về dạng 1 cột dọc (`grid-template-columns: 1fr`).
  * Mũi tên chuyển hướng `.pivot-arrow` xoay dọc thành hướng xuống dưới (`transform: rotate(90deg)`) để giữ đúng luồng thị giác.
* Thao tác này giúp giao diện responsive tốt, không gây tràn màn hình (horizontal overflow).

### 4. Tối ưu vùng Research Question và Badge

* Vùng câu hỏi nghiên cứu tiếp tục sử dụng style `.claim-line` để làm nổi bật câu hỏi chính, nhưng được đặt gọn gàng ở phần dưới của card để giữ tỷ lệ chiều cao hợp lý.
* Giữ nguyên 3 badge nhãn tag dưới cùng (`Giả thuyết rõ hơn`, `Benchmark được`, `Audit được`).

## Tình trạng và Giới hạn (Scope)

* Giữ nguyên nội dung card `1.1` và `1.2`.
* Giữ nguyên Part 2–6, canvas, shader nền, và ranh giới claim an toàn.
