# Đối chiếu rubric Day 7

Phạm vi là phần cơ bản, tối đa **85 điểm**. Các mục dưới đây có minh chứng trong bản làm cục bộ. Điểm do giảng viên quyết định. Phần nâng cao có thang và benchmark riêng. [Rubric](../RUBRIC.md) · [Đề bài](../README.md)

| Hạng mục | Điểm tối đa | Đối chiếu bài làm |
|---|---:|---|
| Dữ liệu và benchmark | 13 | Dùng lại 180 chunk, nguồn PDF 52 trang, Qdrant và E5 384 chiều của Day 6. Dev có 15 câu có đáp án và 2 thiếu evidence. Test có 5 câu có đáp án và 2 thiếu evidence, soạn mới trước lần đo. Có evidence theo nguồn, trang, điều và offsets, cùng lý do thiếu evidence. [Dev](../data/benchmark_dev.json) · [Test](../data/benchmark_test.json) |
| Retrieval | 17 | Dense cosine, TF-IDF và Hybrid RRF chạy cùng corpus và split dev. Trace giữ rank theo thứ tự, score, nguồn, metadata và filter. Hybrid mở rộng vẫn xuất top 3 cùng chuẩn so sánh. [Retrieval](../src/retrieval.py) · [Kết quả dev](../results/dev/summary.json) |
| Agent và context | 17 | Qwen2.5 thật gọi truy xuất, chọn trả lời hoặc từ chối. Trace ghi hành động, query, context và điều kiện dừng. Các lượt đo chính thức dùng một search mỗi câu. Unit test kiểm tra tìm lần hai, citation ngoài context, query lặp và lỗi kết nối. [Agent](../src/agent.py) · [Unit test](../tests/test_day7_agent.py) |
| Đánh giá | 17 | Có Hit@1, Evidence Hit@3, Context Evidence Rate, nhãn context 0–2 và nhãn câu trả lời, citation, tool use, abstention. Cả 7 câu test có lý do chấm. T04 được báo thêm theo tiêu chí đủ cả hai nhóm evidence. [Phiếu chấm](../reviews) · [Tổng hợp test](../results/test/review_summary.json) |
| Thử nghiệm và cải thiện | 13 | Thử đổi dense sang hybrid, rồi mở rộng candidate và ngân sách context của hybrid. Báo cả cấu hình giảm điểm, lỗi dev và đánh đổi thời gian, token, chi phí. Dense thắng theo tiêu chí dev và đồng thời là baseline, nên hai vai trò dùng cùng một lượt test đã khóa. [Biên bản chốt](../results/selection.json) · [Phân tích lỗi](../report/individual/2A202603860_VuXuanHieu.md#phân-tích-lỗi-dev) |
| Tái lập và báo cáo | 8 | Có báo cáo tên MSSV, phiên bản Day 6 đã ghim, lệnh chạy, nguồn và hướng dẫn tái dựng. Đã khôi phục đủ 75 trace và đối chiếu 83 chunk với PDF. [Hướng dẫn](RUN_DAY7.md) · [Báo cáo](../report/individual/2A202603860_VuXuanHieu.md) |

## Việc cần kiểm tra trước khi nộp

- **Đọc lại phiếu chấm.** Codex đã đọc trace và đối chiếu nguồn. Theo quy tắc của đề, người nộp chịu trách nhiệm kiểm tra code, kết quả và nguồn. Có thể dùng lệnh khôi phục context để đối chiếu cả bảy câu test với PDF. [Quy tắc](../RULES.md) · [Nhãn test](../reviews/test_dense.json)
- **Cập nhật fork và kiểm tra quyền truy cập.** Khi đối chiếu, nhánh `main` trên GitHub vẫn ở commit starter `c67ec62`. Bài làm và minh chứng nằm ở bản clone cục bộ. Người chấm cần mở được repo chứa bản làm sau khi nộp. [Danh sách nộp bài](../SUBMISSION.md)
- **Giữ nguyên đợt test đã khóa.** Kết quả test có hai lỗi nội dung đã ghi rõ. Nếu dùng chúng để chỉnh pipeline cho một lượt đánh giá mới, cần tạo bộ test mới theo quy định. [Quy tắc dev/test](../BENCHMARK.md#1-bộ-câu-hỏi) 
