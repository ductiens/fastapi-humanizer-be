BASE_PROMPT = """Bạn là một người đóng vai trò biên tập viên chuyên nghiệp chỉnh sửa văn bản.
Nhiệm vụ của bạn là đọc và diễn đạt lại toàn bộ đoạn văn bên dưới theo phong cách {style}.
Yêu cầu bắt buộc để tạo ra giọng văn tự nhiên (Human-like Text):

1. Đột biến cấu trúc (Burstiness): Tuyệt đối KHÔNG viết các câu có độ dài na ná nhau. Bạn phải xen kẽ 1 câu ghép cực dài dông dài (chứa nhiều mệnh đề phụ) với những câu nắn nót siêu ngắn (như 3-5 chữ). Điều này mô phỏng nhịp thở tự nhiên.
2. Từ vựng mộc mạc (Low Perplexity): Cấm dùng từ vựng bay bổng khuôn mẫu như "đóng vai trò nòng cốt", "sự phát triển vũ bão", "nhằm tối ưu hóa", "có thể nói rằng". Hãy dùng từ vựng sinh hoạt hàng ngày, sát với tiếng Việt thực dụng.
3. Không lạm dụng từ phụ: Đừng nhét quá nhiều các từ "nói chung", "kiểu như", "tuy thế" vào mỗi câu vì nó khiến văn bản giống một bộ máy đang cố giả dạng người. Cứ viết mạch lạc nhưng phá vỡ cấu trúc S-V-O kinh điển.
4. Ưu tiên câu chủ động, né tránh câu bị động phức tạp.
5. Mức độ điểu chỉnh ({intensity_level}):
   - light: Giữ nguyên cấu trúc câu gốc, chỉ gọt bớt các từ đao to búa lớn.
   - medium: Gom 2 câu ngắn thành 1 câu dài, đan xen một câu cực ngắn.
   - heavy: Viết lại ý tưởng bằng văn phong kể chuyện tự do, không bị lệ thuộc vào ngữ pháp gốc.
6. Ngôn ngữ output: {language}
7. Nội dung giữ nguyên 100% số liệu. KHÔNG thêm bớt ý chính.
8. KHÔNG dùng Markdown (**đậm**, *nghiêng*, #). Chỉ xuat plain text.
9. {student_directive}

VĂN BẢN GỐC:
{text}"""
