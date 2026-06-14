# CC-DFlash Part 2 Layout Refinement Report

Báo cáo tiến độ tái cấu trúc giao diện và tối ưu hóa hiển thị cho **Part 2 — Method & Conditions** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Đồng bộ hóa và tạo sự đối xứng cho Card 2.2 và Card 2.3

* Áp dụng luật CSS Grid đồng bộ `.part-2 .section-grid` tương tự như Part 1, thiết lập tỷ lệ chiều rộng 2 cột bằng nhau (`1fr`) và căn gióng chiều cao tự động co dãn (`align-items: stretch`). Thao tác này giúp Card 2.2 và Card 2.3 hiển thị song song cân đối và có cùng chiều cao chính xác trên giao diện desktop.
* Tách biệt các luận điểm và viết lại dưới dạng danh sách `compact-list` rõ ràng, tránh để các khối chữ (paragraphs) quá nặng nề:
  * **Card 2.2**: Lần lượt chỉ ra vai trò của `Prefill cost`, `Giảm input tokens`, `DFlash hỗ trợ decoding`, và mốc so sánh `Savings vs T_compress`.
  * **Card 2.3**: Chỉ ra các giới hạn bao gồm `Verify trên context nén`, `Nén mất mát (Lossy)`, `Rủi ro sai lệch output`, và `Evaluation toàn diện`.
* Tối ưu hóa visual weight của các callout chốt bằng cách thay thế khối `.claim-line` (vốn to và thô) bằng container `.insight-strip` gọn gàng và tinh tế hơn:
  * **Card 2.2**: Đặt label `Core Question` cùng câu hỏi: *"Sau khi tính cả T_compress, pipeline có nhanh hơn và quality proxy có còn ổn định hay không?"*
  * **Card 2.3**: Đặt label `Claim Boundary` cùng câu khẳng định: *"Lossy input compression + DFlash trên compressed context ≠ lossless full pipeline."*

### 2. Thiết kế lại Pipeline Flow Badges trong Card 2.1 thành Grid đồng đều

* Thay đổi thuộc tính hiển thị của `.pipeline-strip` từ Flexbox dòng cuốn (`display: flex; flex-wrap: wrap`) sang dạng lưới cố định Grid gồm 9 cột:
  ```css
  grid-template-columns: 1fr auto 1fr auto 1.2fr auto 1fr auto 1fr;
  align-items: stretch;
  ```
* Thiết lập `.pipe-node` thành dạng hình hộp bo góc nhẹ (`border-radius: 12px`, padding `8px 10px`, min-height `44px`) với căn giữa văn bản qua flexbox. Điều này giúp các badge (Original context, Context compression, Compressed natural text, DFlash, Output) có kích thước đồng đều và chiều cao bằng nhau, không bị lệch thị giác.
* Thêm responsive rule trong media query di động `@media (max-width: 760px)` để tự động chuyển grid thành 1 cột dọc và xoay dọc các mũi tên chuyển tiếp `→` thành hướng đi xuống `↓` (`transform: rotate(90deg)`), loại bỏ hoàn toàn nguy cơ tràn màn hình (horizontal overflow).

### 3. Xóa bỏ hoàn toàn các container Speaker Box (Ý chính khi nói)

* Đã xóa bỏ triệt để các khối ghi chú `Ý chính khi nói` (`<div class="speaker-box">`) ở tất cả các phần:
  * **Part 2** (Dòng 1556)
  * **Part 3** (Dòng 1732)
  * **Part 4** (Dòng 1898)
  * **Part 5** (Dòng 2063)
  * **Part 6** (Dòng 2226)
* Sự cải tiến này giúp giao diện public của slide thuyết trình sạch sẽ, hiện đại và tập trung hoàn toàn vào nội dung kỹ thuật.

## Tình trạng và Giới hạn (Scope)

* **Giữ nguyên nội dung kỹ thuật cốt lõi**: Không thay đổi bất kỳ claim, benchmark results, dataset, model, hay logic CUDA/decoding nào.
* **Giữ nguyên Animation & Canvas background**: Mã nguồn điều khiển canvas, shader nền không bị tác động.
