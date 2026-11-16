# Đối chiếu nhận xét chấm bài Day 7

Mức **75/85** là điểm dự kiến của người chấm. Kiểm chứng lại xác nhận các số của lần chạy gốc, gồm **4/5** câu có đáp án được trả lời đầy đủ, **4/5** citation có căn cứ và **1/2** câu thiếu evidence được từ chối đúng. Kết quả này thuộc đúng phiên bản đã chạy. [Tổng hợp test](../results/test/review_summary.json) · [Biên bản chốt](../results/selection.json)

| Nhận xét | Đối chiếu và xử lý |
|---|---|
| Truy xuất query gốc lỗi có thể dừng cả benchmark | **Đúng.** Lần gọi trước agent chưa được xử lý theo từng câu. Runner mới lưu lỗi, giữ câu trong mẫu số retrieval nếu có đáp án, ghi lỗi hệ thống riêng và tiếp tục câu sau. |
| Nhãn cũ có thể được áp cho câu trả lời mới | **Đúng.** Trùng ID và số citation chưa đủ để xác định cùng output. Phiếu mới gắn SHA-256 của trace. Tổng hợp lưu hash của cả hai và pha test kiểm tra lại trace, phiếu dev theo biên bản chốt. |
| Có thể ghi đè test và tài liệu tái lập trỏ nhầm phiếu cũ | **Đúng.** Runner từ chối ghi vào thư mục test đã có. Hướng dẫn dùng thư mục mới cho kết quả, trace đầy đủ và nhãn ở mỗi lần chạy. |
| T04 mơ hồ và thiếu số lượng trong context | **Đúng.** Câu hỏi nên nêu chương trình tài năng, chất lượng cao và khoản 5 Điều 39. Chỗ khoản 1 có phạm vi khác và nói ít nhất 3 thành viên. Theo câu hỏi và gold đã khóa, pipeline bị tính từ chối nhầm. Với context thực nhận, từ chối là hành vi hợp lý. |
| Citation ID không bảo đảm câu trả lời có căn cứ | **Đúng.** T07 nhầm cả đơn vị và cấp giải. Điều 32 nêu 0,20 **điểm** cho giải nhất cấp ĐHQGHN, còn 0,10 điểm trong đoạn được dẫn thuộc giải nhất cấp đơn vị. D05 chọn bậc ngoại ngữ của nhóm khác. D12 nêu con số trùng đáp án nhưng dựa vào quy định về học chương trình thứ hai. Giữ nhãn trượt cho cả ba. |
| Link nộp bài phải có code, báo cáo và trace | **Đúng.** Bản làm đang nằm ở checkout cục bộ. Việc đưa lên fork và kiểm tra quyền của người chấm thuộc bước bàn giao. |

[Runner mới](../src/benchmark.py) · [Kiểm thử hồi quy](../tests/test_benchmark_protocol.py) · [Hướng dẫn tái lập](RUN_DAY7.md) · [Nhãn test gốc](../reviews/test_dense.json)

## Bản chấm lại và xử lý lỗi ONNX

Người chấm cập nhật mức dự kiến lên **79/85** và phát hiện ba lỗi của ONNX Runtime thoát khỏi khối xử lý theo câu. Bản cục bộ đã chuyển `Fail`, `RuntimeException` và `InvalidArgument` tại bước embedding query thành `EmbeddingError`, ghi nguyên loại lỗi ONNX trong trace. Hai kiểm thử hồi quy dùng đúng các lớp lỗi của ONNX Runtime để kiểm tra đường benchmark và đường gọi từ agent. Toàn bộ **24/24 unit test** qua. Phép đo retrieval trên dev vẫn khớp kết quả gốc ở cả bốn cấu hình. Các chỉ số chất lượng agent tiếp tục lấy từ lượt test đã khóa. [Bộ điều hợp retrieval](../src/retrieval.py) · [Kiểm thử ONNX](../tests/test_embedding_errors.py)

## Phạm vi của bản sửa

Các lần sửa xử lý ghi lỗi, lưu minh chứng và tái lập. Câu hỏi, cấu hình agent, trace, phiếu chấm và số liệu của lượt gốc được giữ nguyên. Runner và mã retrieval gốc có SHA-256 khớp biên bản chốt. Hash ghép phiếu với trace gốc được ghi bổ sung khi kiểm toán, sau thời điểm benchmark. [Hồ sơ phiên bản gốc](../results/frozen_protocol) · [Script kiểm chứng](../scripts/verify_submission.py)

Một điểm có thể làm rõ với người chấm là rubric không ấn định ngưỡng benchmark cho phần cơ bản. Bài đã có model thật, điều kiện dừng, cơ chế từ chối và trace. Các lỗi D05, D12 và T07 vẫn là bằng chứng trực tiếp về giới hạn của kiểm tra citation theo ID. Cách chấm hợp lý có thể ghi nhận phần triển khai vòng lặp agent và đánh giá riêng chất lượng đối chiếu bằng chứng. [Rubric](../RUBRIC.md) · [Báo cáo](../report/individual/2A202603860_VuXuanHieu.md)

Nếu đo phiên bản agent cải tiến, có thể thử kiểm tra đối tượng, điều kiện và đơn vị trên D05/D12, rồi đo việc lấy chunk liền kề bằng ca dev. Một thay đổi thiết kế dựa vào T04 hoặc T07 cần được đánh giá bằng tập test độc lập mới. [Quy tắc benchmark](../BENCHMARK.md)

## Bản nháp trao đổi với người chấm

Em cảm ơn thầy/cô đã đối chiếu trace và chỉ ra các điểm yếu. Em đồng ý với nhận xét về T04 và T07, đồng thời giữ điểm của lần chạy gốc. Em đã sửa runner để lưu lỗi truy xuất query gốc theo từng câu, bảo vệ thư mục test và ràng buộc phiếu chấm với đúng trace. Em cũng cập nhật hướng dẫn để dùng phiếu mới cho mỗi lần chạy. Khi xem lại mục Agent và context, em mong thầy/cô cân nhắc phần triển khai và minh chứng đã có theo rubric, cùng các lỗi về phạm vi và đơn vị đã được ghi rõ trong báo cáo.

## Bản chấm 80/100 và hai điều kiện bonus

Người chấm xác nhận **80/85 phần cơ bản** và **30/30 câu P01–P30 đúng về câu trả lời và trích dẫn**. Việc chấm 0/15 bonus ở phiên bản đó có căn cứ. P17–P20 gồm các ý độc lập, còn biên bản chốt chỉ ràng buộc trace dev. Khi kiểm tra giao thức, việc chương trình đọc và xác thực phiếu dev quan trọng hơn thời gian sửa của tệp trên máy. [Phiếu P01–P30](../results/bonus_passages/test/passages.review.json) · [Quy tắc bonus](../ADVANCED.md)

- J17–J20 yêu cầu đọc một nhãn trong hình rồi dùng tên vừa đọc để tìm hàng và cột của bảng ở trang khác. Gold ghi `bridge` cùng hai vùng bằng chứng. Trace ghi nhãn do bước đầu sinh và truy vấn bảng thực tế. [Bộ J01–J30](../data/bonus_joined_test.json)
- Runner so sánh truy xuất song song với truy xuất phụ thuộc trên cùng dev. Bước chốt tính lại kết quả từ phiếu, kiểm hash và lưu điểm hai cấu hình. Bước test xác minh lại toàn bộ hồ sơ dev trước khi tạo thư mục chạy test. [Mã kiểm chứng](../scripts/bonus_joined.py) · [Cách tái lập](RUN_BONUS_DAY7.md)

`dependent` đạt 21/22 trên dev với 4/4 chuỗi phụ thuộc, so với 18/22 của `parallel`. Sau khi chốt, J01–J30 đạt 30/30 với 4/4 chuỗi được kiểm tra từ trace và PDF. Theo mức 80/85 đã được người chấm xác nhận, tổng điểm dự kiến là 95/100 nếu bản cập nhật được duyệt đủ 15 điểm bonus. [Biên bản chốt](../results/bonus_joined/selection.json) · [Tổng hợp test](../results/bonus_joined/test/summary.json) · [Phiếu chấm từng câu](../results/bonus_joined/test/dependent.review.json)

## Hai khoản trừ phần cơ bản liên quan T04 và T07

- **T04.** Khoản 1 Điều 39 ở trang 40 quy định hội đồng ít nhất 3 thành viên. Khoản 5 áp dụng cho chương trình tài năng và chất lượng cao ở trang 41, quy định tối thiểu 5 người gồm 2 phản biện. Trace cũ có đoạn mở đầu khoản 5 nhưng thiếu chunk kế tiếp chứa số lượng. D18 làm rõ chương trình và khoản trong câu hỏi, đồng thời ghi hai nhóm evidence bắt buộc. Agent mới lấy cả đoạn mở đầu và đoạn nối theo khoản, giữ trang và offset của từng chunk. [T04 lịch sử](../data/benchmark_test.json) · [Dev D18](../data/benchmark_revised_dev.json)
- **T07.** Điều 32 quy định **0,20 điểm** cho giải nhất cấp ĐHQGHN/cấp Bộ và **0,10 điểm** cho giải nhất cấp đơn vị đào tạo. Trace cũ lấy số thứ hai và trả điểm khi đề hỏi tiền bằng đồng. Điều 32 không quy định khoản tiền đó. D19 dùng lại câu hỏi để chẩn đoán. Nhánh xác thực kiểm tra trích dẫn có số tiền đúng đơn vị trước khi chấp nhận câu trả lời về tiền. [Phiếu chấm test lịch sử](../reviews/test_dense.json) · [Mã kiểm tra trích dẫn](../src/grounding.py)

Bộ R01–R07 được tạo trước khi chạy lại dev. Hai ca đã biết T04/T07 thuộc dev sửa đổi. Bộ chẩn đoán và bộ độc lập dùng cùng nguồn Day 6. Kết quả thiếu ngữ cảnh và citation sai của lần đầu tiếp tục nằm trong hồ sơ gốc. [Test mới](../data/benchmark_revised_test.json) · [Cách tái lập](RUN_DAY7.md)

D18 đạt context 2/2, câu trả lời 2/2 và cả hai trích dẫn hợp lệ trên `clause_grounded`. D19 từ chối đúng. Chọn cấu hình trên dev trước khi chạy test. Cả hai cấu hình đạt 5/5 câu có đáp án và 2/2 ca từ chối trên bộ test mới. Với `clause_grounded`, điểm grounded trên dev là 1,69/2 so với 1,56/2 của `dense`; độ trễ trung vị trên test tăng từ 8,12 lên 10,35 giây/câu. [Phiếu chẩn đoán](../reviews/basic_revised/dev_clause_grounded.json) · [Biên bản chốt](../results/basic_revised/selection.json) · [Kết quả test mới](../results/basic_revised/test/review_summary.json)
