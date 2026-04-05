BASE_PROMPT = """Hãy tưởng tượng bạn VỪA ĐỌC XONG đoạn văn bên dưới, rồi GẤP SÁCH LẠI. Bây giờ bạn đang KỂ LẠI nội dung đó cho bạn bè nghe bằng giọng {style} của chính mình, HOÀN TOÀN TỪ TRÍ NHỚ — không nhìn lại bài gốc.

QUY TẮC KỂ LẠI:

1. KHÔNG BAO GIỜ viết theo thứ tự ý giống bài gốc. Kể theo dòng suy nghĩ tự nhiên: nhớ gì nói đó, đôi khi nhảy ý rồi quay lại.
2. KHÔNG dùng bất kỳ cụm từ nào dài hơn 3 từ liên tiếp giống bài gốc. Phải dùng từ ngữ hoàn toàn khác.
3. Câu cú phải THẬT BẤT QUY TẮC:
   - Xen kẽ câu cực ngắn (2-5 từ: "Hay thật.", "Vậy đó.", "Nói thẳng nhé.") với câu dài lan man.
   - Thỉnh thoảng bắt đầu câu bằng "Và", "Nhưng", "Ờ thì", "Nói chung là".
   - Được phép 1-2 câu hỏi tu từ ("...đúng không?", "...ai mà biết?").
   - Được phép 1 lần ngắt ý giữa chừng rồi nối lại ("...à mà quên, ý mình là...").
4. TUYỆT ĐỐI CẤM sử dụng các mẫu câu sau (đây là dấu hiệu AI):
   - "không chỉ... mà còn..."
   - "bên cạnh đó" / "ngoài ra" / "hơn nữa" / "hơn thế nữa"
   - "đóng vai trò" / "góp phần" / "nhằm mục đích"
   - "sự phát triển vượt bậc" / "chuyển mình mạnh mẽ"
   - "ngày càng" / "không ngừng"
   - "trong bối cảnh" / "xét cho cùng" / "nói cách khác"
   - "có thể thấy rằng" / "có thể nói rằng" / "điều này cho thấy"
   - "một cách + tính từ" (VD: "một cách hiệu quả", "một cách rõ ràng")
5. Giữ nguyên 100% số liệu, tên riêng, dữ kiện. Chỉ thay cách diễn đạt.
6. Mức chỉnh: {intensity_level}
   - light: giữ gần ý gốc, chỉ đổi từ và xen câu ngắn
   - medium: kể lại tự do hơn, gộp tách câu, đảo thứ tự ý
   - heavy: kể chuyện hoàn toàn tự do, như đang nói chuyện với bạn bè
7. Ngôn ngữ: {language}
8. KHÔNG dùng Markdown. Chỉ xuất plain text.
9. {student_directive}

NỘI DUNG CẦN KỂ LẠI:
{text}"""
