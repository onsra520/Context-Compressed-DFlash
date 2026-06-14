# CC-DFlash Part 1 Card 1.3 Insight Strip Report

Báo cáo tiến độ tinh chỉnh vùng câu hỏi nghiên cứu (Research Question) và tích hợp thẻ nhãn (badges) cho thẻ **1.3 Từ blocker sang CC-DFlash** trong phần **Part 1 — Lý do chuyển hướng** trên trang thuyết trình CC-DFlash.

## Chi tiết công việc đã thực hiện

### 1. Thu gọn visual weight của Research Question

* Chuyển đổi container `.claim-line` (vốn có font-size khá lớn và padding dày) thành một callout strip mới gọn hơn với tên class `.insight-strip`.
* Thiết lập font-size cho câu hỏi nhỏ hơn (`font-size: clamp(14px, 1.15vw, 16px)` so với mức cũ `clamp(17px, 1.55vw, 23px)`), giúp visual flow không bị lấn át bởi hai panel so sánh phía trên.
* Đặt nhãn nhỏ `Research question` bằng chữ in hoa tinh tế phía trên text câu hỏi thay vì đặt text bold inline như trước.

### 2. Tích hợp trực tiếp 3 chip/tag vào bên trong Callout Box

* Đưa 3 chip/tag vào nằm gọn bên dưới câu hỏi nghiên cứu trong cùng một container `.insight-strip` để tạo sự liên kết chặt chẽ về mặt logic và thị giác.
* Thay đổi nội dung của 3 chip/tag mới theo yêu cầu:
  * `Giả thuyết dễ đo hơn`
  * `Benchmark 4 condition`
  * `Tách speed / quality / overhead`
* Thiết kế lại styles của các chip này (`.insight-badge`) nhỏ hơn, tinh gọn hơn (padding `4px 10px`, font-size `12px`, border-radius `6px`, màu sắc dịu hơn) để tránh cảm giác giống các button lớn rời rạc.

### 3. CSS Classes mới được thêm vào

```css
.insight-strip {
    margin-top: 20px;
    padding: 16px 20px;
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.01));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(8px);
}

.insight-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(255, 255, 255, 0.4);
    margin-bottom: 6px;
}

.insight-text {
    font-size: clamp(14px, 1.15vw, 16px);
    line-height: 1.5;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.9);
    margin-bottom: 12px;
}

.insight-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.insight-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.04);
    color: rgba(255, 255, 255, 0.75);
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.01em;
}
```

## Tình trạng và Giới hạn (Scope)

* **Giữ nguyên cấu trúc Part 1**: Card `1.1 Mục tiêu ban đầu` và `1.2 Blocker của HTFSD` được giữ nguyên vẹn.
* **Giữ nguyên Part 2-6**: Không chỉnh sửa bất kỳ phần nào khác ngoài nội dung và layout cuối card 1.3 của Part 1.
* **Canvas / Shaders**: Giữ nguyên toàn bộ mã nguồn liên quan đến animation, canvas, shader của background.
