# CC-DFlash Part 3 Layout Refinement Report

Báo cáo tiến độ tái cấu trúc giao diện và tối ưu hóa hiển thị cho **Part 3 — Benchmark & Evaluation** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Đồng bộ chiều cao Card 3.1 và Card 3.2

* Thêm lớp `.part3-comparison` vào hai card 3.1 và 3.2.
* Đồng bộ hóa chúng bằng vertical flexbox (`display: flex; flex-direction: column; gap: 20px;`) trong media query desktop. Điều này giúp hai card có chiều cao bằng nhau tuyệt đối, tạo bố cục song song cân đối.

### 2. Tách bullet của Card 3.3 thành 2 cột theo Dataset

* Loại bỏ danh sách bullet đơn 4 hàng ban đầu của Card 3.3.
* Thay thế bằng một hệ thống lưới `.dataset-roles-grid` gồm 2 cột tương ứng với hai dataset chính:
  * **Cột GSM8K**: Nêu rõ vai trò (không chứng minh long-context speedup, dùng cho numeric-quality proxy).
  * **Cột QMSum**: Nêu rõ vai trò (không chứng minh semantic correctness, dùng cho long-context diagnostic behavior).
* Thiết kế responsive tự động stack thành 1 cột trên màn hình nhỏ.

### 3. Gộp Card 3.4 và Card 3.5 thành Card 3.4 song song

* Gộp hai card riêng biệt cho GSM8K (cũ là 3.4) và QMSum (cũ là 3.5) thành một card chung duy nhất: **3.4 GSM8K và QMSum: hai vai trò đánh giá**.
* Thiết lập card này hiển thị full width (`class="section-card wide"`) và tổ chức nội dung bên trong thành lưới so sánh song song (`.dataset-comparison-grid`) gồm 2 cột.
* Mỗi cột hiển thị thông tin rõ ràng về mục đích "Dùng để" và "Không dùng để" của từng dataset, loại bỏ sự rườm rà và giúp người đọc dễ so sánh vai trò của chúng.

### 4. Đổi Card Metric scope thành dạng bảng chi tiết (Card 3.5)

* Đổi mã hiệu của card từ `3.6` thành `3.5`.
* Thay thế danh sách badge/chip list đơn thuần bằng một bảng dữ liệu chi tiết `.report-table`.
* Bảng bao gồm 10 metrics thực nghiệm được chia cột rõ ràng: **Metric**, **Dùng để đọc gì**, **Caveat / phạm vi**.
* Bảng được bọc lớp responsive tự động kích hoạt thanh cuộn ngang trên mobile, đảm bảo không bị vỡ bố cục.
* Giữ nguyên câu nhận định thận trọng ở dưới cùng bảng về end-to-end latency.

## Tình trạng và Giới hạn (Scope)

* **Hoàn tất renumbering**: Đã đánh số thứ tự chuẩn từ `3.1` đến `3.5`, không còn card `3.6`.
* **Không đổi nội dung kỹ thuật**: Giữ nguyên toàn bộ số liệu, claim boundary, tên metric và ý nghĩa đánh giá.
* **Không ảnh hưởng các thành phần khác**: Các Part 1, 2 và 4–6 không bị thay đổi. Nền canvas và shader animation được bảo toàn nguyên vẹn.
