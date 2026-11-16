# Day 7 · Agentic RAG trên Quy chế 3626

**Vũ Xuân Hiếu · MSSV 2A202603860 · Lớp L3B**  
Thực nghiệm phần cơ bản ngày 16/11/2026, giờ Việt Nam.

## Dữ liệu và benchmark

Dùng bản có lớp chữ của Quy chế đào tạo đại học ĐHQGHN ban hành kèm Quyết định 3626/QĐ-ĐHQGHN ngày 21/10/2022. Corpus có 52 trang. Collection `structured` có 180 chunk từ cấu hình B Day 6. Từng chunk giữ nguyên ID, nguồn, trang, chương, điều và offsets. Trang 1–52 của bản chữ tương ứng trang PDF 2–53 của bản scan. Manifest Day 6 ghi phiên bản nguồn, checksum, căn cứ sử dụng và cách tái tạo. [Nguồn công bố](https://fos.ussh.vnu.edu.vn/vi/laws/detail/Quy-che-dao-tao-dai-hoc-tai-Dai-hoc-Quoc-gia-Ha-Noi-Ap-dung-tu-khoa-QH-2022-X-5/) · [Manifest và pipeline Day 6](https://github.com/vuhieuvh/K5-L3B-DAY06-VuXuanHieu-2A202603860-DataIngestion)

Embedding `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 384 chiều, ONNX INT8. Query dùng tiền tố `query: ` và tìm cosine exact trong Qdrant local. TF-IDF dùng token Unicode, chuẩn hóa NFC và chữ thường. Hybrid hợp nhất top 10 của mỗi nhánh bằng RRF với hằng số 60. Không dùng filter ở lượt đo chính. Agent Qwen2.5 3B Instruct Q4_K_M chạy bằng llama.cpp b8259 trên Intel Iris Xe, endpoint localhost. [Hướng dẫn chạy và trọng số](../../docs/RUN_DAY7.md)

Dev có 15 câu có đáp án được dùng lại từ dev Day 6 và hai câu thiếu bằng chứng mới. Test có năm câu có đáp án mới và hai câu thiếu bằng chứng mới, được soạn trước khi chạy agent và giữ riêng cho đến khi chốt. Các câu thiếu bằng chứng được xác định bằng cách đọc các điều liên quan và dò toàn văn. Agent chỉ nhận câu hỏi và context do công cụ tìm được. [Dev](../../data/benchmark_dev.json) · [Test](../../data/benchmark_test.json)

## Cách đo

Hit@1 và Evidence Hit@3 đo query gốc trên 15 câu dev hoặc 5 câu test có đáp án. Một hit cần thấy span evidence hợp lệ, đúng nguồn, trang, điều và offsets. Với T04, một hit ở ranking có thể chỉ có một trong hai phần evidence. Context Evidence Rate tính đủ các phần trên context cuối, kể cả các đoạn đến từ query viết lại. Context review chấm 0 khi thiếu đoạn trả lời, 1 khi có bằng chứng nhưng thiếu điều kiện hoặc nguồn, 2 khi đủ và kiểm chứng được. Đối chiếu câu trả lời và từng citation theo thang trong đề. Lỗi model/store báo riêng. [Định nghĩa chấm](../../BENCHMARK.md)

Các cấu hình dùng tối đa hai lần tìm. Lần đầu dùng câu hỏi gốc. Agent có thể viết lại query, gộp theo ID và chọn các đoạn nguyên vẹn đủ chỗ trong ngân sách ký tự JSON. Model sinh hành động theo schema có ràng buộc. Mức 0 USD là phí dịch vụ suy luận của lần chạy cục bộ và chưa tính máy hay điện. Mỗi cấu hình chạy tuần tự, thứ tự cố định và server có cache prompt. Các số độ trễ mô tả lần chạy này.

## Kết quả

Cấu hình **dense** được chọn lúc `2026-11-16T10:03:04.093441+07:00` theo tiêu chí đã công bố. Đã khóa hash code, benchmark, index và trọng số trước lượt test. [Biên bản chốt](../../results/selection.json)

| Split | Cấu hình | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Retrieval trung vị | Agent trung vị | Phí dịch vụ |
|---|---|---:|---:|---:|---:|---:|---:|
| dev | `dense` | 11/15 (73.3%) | 13/15 (86.7%) | 13/15 (86.7%) | 21.9 ms | 6.82 s | 0 USD |
| dev | `lexical` | 7/15 (46.7%) | 11/15 (73.3%) | 11/15 (73.3%) | 1.6 ms | 5.18 s | 0 USD |
| dev | `hybrid` | 10/15 (66.7%) | 12/15 (80.0%) | 11/15 (73.3%) | 21.0 ms | 4.82 s | 0 USD |
| dev | `hybrid_context` | 10/15 (66.7%) | 12/15 (80.0%) | 12/15 (80.0%) | 19.6 ms | 5.56 s | 0 USD |
| test | `dense` | 5/5 (100.0%) | 5/5 (100.0%) | 4/5 (80.0%) | 10.5 ms | 7.03 s | 0 USD |

Baseline và cấu hình được chọn là cùng một cấu hình, nên một lượt test đại diện cho cả hai vai trò.

Chỉ số bổ sung cho câu nhiều đoạn, **đủ tất cả nhóm evidence trong top 3**, đạt **4/5 (80%)** trên test. Riêng T04, có ít nhất một nhóm ở top 3 là **1/1**, đủ cả hai nhóm là **0/1**. Khi chấm T04, “hội đồng chấm khóa luận” chỉ hội đồng nêu tại khoản 5 Điều 39, áp dụng cho chương trình tài năng và chất lượng cao. Đoạn trang 40 quy định về hội đồng bảo vệ và đánh giá trong trường hợp được nêu ở khoản 1. Hai đoạn có phạm vi khác nhau.

| Split / Cấu hình | Context 0/1/2 | Grounded 0/1/2 | Điểm /2 | Citation hợp lệ | Câu trả lời có citation | Từ chối đúng | Từ chối nhầm | Lỗi |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dev / `dense` | 2/0/13 | 3/0/12 | 1.60 | 12/14 | 14/14 | 2/2 | 1/15 | 0 |
| dev / `lexical` | 4/0/11 | 4/1/10 | 1.40 | 11/13 | 13/13 | 1/2 | 3/15 | 0 |
| dev / `hybrid` | 3/1/11 | 5/0/10 | 1.33 | 10/12 | 12/12 | 2/2 | 3/15 | 0 |
| dev / `hybrid_context` | 2/1/12 | 5/0/10 | 1.33 | 10/13 | 13/13 | 1/2 | 3/15 | 0 |
| test / `dense` | 0/1/4 | 1/0/4 | 1.60 | 4/5 | 5/5 | 1/2 | 1/5 | 0 |

| Split / Cấu hình | Tool use | Số câu theo số lượt tìm | Token prompt / sinh |
|---|---:|---|---:|
| dev / `dense` | 17/17 | 1 lượt × 17 câu | 12767 / 873 |
| dev / `lexical` | 17/17 | 1 lượt × 17 câu | 12611 / 699 |
| dev / `hybrid` | 17/17 | 1 lượt × 17 câu | 12601 / 658 |
| dev / `hybrid_context` | 17/17 | 1 lượt × 17 câu | 19215 / 729 |
| test / `dense` | 7/7 | 1 lượt × 7 câu | 5339 / 262 |

[Kết quả dev](../../results/dev/review_summary.json) · [Kết quả test](../../results/test/review_summary.json) · [Phiếu chấm](../../reviews)

Thử nghiệm 1 dùng RRF thay dense, giữ top-k 3 và ngân sách 1.800 ký tự. Evidence Hit@3 giảm từ 13/15 xuống 12/15 và context đủ giảm từ 13/15 xuống 11/15. Thử nghiệm 2 tăng hybrid lên top-k 5 và 3.100 ký tự. Context đủ tăng từ 11/15 lên 12/15 trên hybrid, còn điểm grounded trung bình giữ ở 1,33/2. Dense đạt 1,60/2, cao nhất theo tiêu chí chọn trên dev.

## Phân tích lỗi dev

- **D03 — thiếu bằng chứng ngay từ retrieval.** Dense xếp đoạn về bồi hoàn kinh phí và đăng ký tín chỉ trong top 3, nên agent từ chối dù Điều 8 tr. 6 có đáp án. TF-IDF đưa Điều 8 vào context. Agent lexical trả được phương án theo số tín chỉ, bỏ sót phương án theo kỳ và được chấm 1/2. Trong phép dò dev riêng, viết lại từ câu hỏi thành “quy định nộp học phí theo số tín chỉ từng học kỳ” đưa đúng đoạn vào hạng 3 của RRF, từ ngoài top 5. Dense vẫn ngoài top 5.
- **D12 — con số đúng với nguồn sai.** Dense trả 2,5 và trích Điều 26 về học chương trình thứ hai. Đáp án cần Điều 28 tr. 28 về chuyển ngành. Câu trả lời và citation đều chấm 0. Phép dò dev đổi query thành “điều kiện chuyển ngành sau năm học thứ nhất điểm trung bình tối thiểu” đưa Điều 28 lên hạng 1 ở cả dense và hybrid. Với query gốc, đoạn nằm ngoài top 5 dense và ở hạng 5 hybrid. Đây là phép dò thủ công để kiểm tra nguyên nhân, chưa tính như kết quả viết lại tự động của agent.
- **D05 — bằng chứng đủ nhưng model chọn sai đối tượng.** Context của dense có Điều 13 tr. 11 với bậc 3 cho chương trình chuẩn và bậc 4 cho chương trình tài năng, chất lượng cao. Model chọn bậc 4. Trên lexical, context có thứ tự và đoạn đi kèm khác, câu trả lời là bậc 3 và citation đúng. Kết quả ủng hộ việc kiểm tra điều kiện áp dụng ở bước tổng hợp.
- **D08 — lỗi định dạng đầu ra model.** Lượt thử ban đầu có evidence đầy đủ về 15 giờ/tuần và 4 giờ/ngày, nhưng lớp xử lý chat trả chuỗi JSON không phân tích được. Chuyển sang endpoint gốc `/completion` với schema hành động, rồi chạy lại cả dev. Dense trả đúng hai giới hạn, citation về Điều 20 tr. 17 và điểm 2/2. Lượt thử cũ không đưa vào bảng chính thức.

- **D04 và D11 — chi phí của context lớn hơn.** Với D04, Điều 11 tr. 10 đứng hạng 3 trong cả hai cấu hình hybrid. Giới hạn 1.800 ký tự bỏ đoạn sau hai chunk dài, khiến agent từ chối. Cấu hình 3.100 ký tự giữ đoạn và trả đúng đủ năm khối. Với D11, cả hai context đã có Điều 23 tr. 21. Hybrid gọn trả đúng điểm F và việc không hoàn học phí, còn bản mở rộng từ chối. Thí nghiệm thay đổi cùng lúc top-k và ngân sách, nên chỉ quy kết kết quả cho toàn cấu hình.

[Trace dense dev](../../results/dev/dense.json) · [Trace lexical dev](../../results/dev/lexical.json) · [Trace hybrid dev](../../results/dev/hybrid.json) · [Trace hybrid mở rộng dev](../../results/dev/hybrid_context.json)

## Ví dụ kiểm chứng trên test

- **T01 — trả lời có căn cứ.** Agent nêu ngày 01/03 hằng năm và trích Điều 9 tr. 8 về hạn phân bổ chỉ tiêu tuyển sinh của Giám đốc ĐHQGHN. Chunk `90b13a12-dd78-5559-9713-f05db7d960af` hỗ trợ trực tiếp mốc được hỏi.
- **T06 — từ chối đúng.** Agent trả “Không đủ bằng chứng trong quy chế để trả lời.” Đối chiếu toàn văn và các điều liên quan đến thi, chấm thi không thấy mức lệ phí phúc khảo.
- **T04 — hit ở hạng 1, context vẫn thiếu.** Hạng 1 giữ đoạn xác định Hội đồng chấm khóa luận ở tr. 41. Câu tiếp theo bị cắt tại ranh giới chunk. Đoạn chứa “tối thiểu gồm 5 người, trong đó có 2 phản biện” nằm ngoài top 3. Context nhận 1/2 và agent từ chối nhầm.
- **T07 — trả lời khi thiếu bằng chứng.** Câu hỏi hỏi số tiền của giải nhất cấp ĐHQGHN. Agent trả 0,10 điểm kèm đoạn về giải cấp đơn vị. Sai đơn vị và sai cấp giải. Trường hợp này làm tỷ lệ từ chối đúng trên test còn 1/2.

[Trace test](../../results/test/dense.json) · [Nhãn từng câu test](../../reviews/test_dense.json)

## Tái lập và giới hạn

Bảng điểm định lượng được tổng hợp từ trace và nhãn do Codex đọc, đối chiếu với câu hỏi, evidence từ PDF và các đoạn agent thật sự nhận. Nhãn và lý do cho từng câu nằm trong thư mục `reviews/`. ID chunk, nguồn, trang, offsets, query, candidate, context, hành động, token, thời gian và câu trả lời có trong trace. Trace công khai dùng các tham chiếu để tái dựng nội dung đoạn. Bản đầy đủ sinh tại `.local/traces/` theo lệnh chạy, dữ liệu gốc và model đều có đường dẫn tái tạo. [Hướng dẫn chạy](../../docs/RUN_DAY7.md)

Script kiểm chứng đã khôi phục và đối chiếu **75 trace, 83 chunk nguồn** từ PDF Day 6. Kết quả khôi phục khớp toàn bộ năm tệp JSON trace đầy đủ của lần chạy. [Script kiểm chứng](../../scripts/verify_submission.py) · [Cách kiểm tra](../../docs/RUN_DAY7.md#kiểm-tra-minh-chứng)

Tập test nhỏ, cùng một quy chế và phần lớn hỏi dữ kiện trong văn bản. Ranh giới chunk có thể bẻ đôi câu, như T04. Trong các lượt đo chính thức, model chọn kết luận sau một lần tìm trên mọi câu. Vòng lặp hỗ trợ lượt tìm thứ hai đã được kiểm tra bằng unit test. Hai phép viết lại ở trên chỉ đo retrieval riêng trên dev. Kết quả trên máy khác có thể đổi do backend và cache. Nhãn chấm nên được người nộp hoặc người chấm đối chiếu lại qua trace và bản PDF.

Sau khi nhận nhận xét, đã sửa luồng benchmark để ghi lỗi query gốc theo từng câu, chặn ghi đè test và gắn phiếu chấm với SHA-256 của trace. Bảng điểm phía trên đến từ lần chạy gốc. Phiên bản runner gốc đã được lưu và đối chiếu với hash trong biên bản chốt. [Phản hồi nhận xét](../../docs/PHAN_HOI_CHAM_BAI.md)

## Đánh giá lại phạm vi Điều 39 và đơn vị tại Điều 32

D18 làm rõ phạm vi khoản 5 Điều 39 đối với chương trình tài năng và chất lượng cao. Gold gồm đoạn mở đầu khoản và đoạn nối ghi 5 người, 2 phản biện tại trang 41. Khoản 1 Điều 39 ở trang 40 quy định ít nhất 3 thành viên. D19 đưa lại câu hỏi tiền thưởng của T07 vào dev. Điều 32 trang 31 ghi 0,20 **điểm** cho giải nhất cấp ĐHQGHN/cấp Bộ và 0,10 **điểm** cho giải nhất cấp đơn vị đào tạo. Đáp án cho câu hỏi về mức tiền là từ chối vì thiếu bằng chứng. [Dev sửa đổi](../../data/benchmark_revised_dev.json) · [Test mới](../../data/benchmark_revised_test.json)

Hai cấu hình agent chạy cùng Qwen3-4B-Instruct-2507 Q4_K_M, cùng 180 chunk Day 6 và cùng ranking dense. `clause_grounded` dùng mã điều và khoản trong câu hỏi để chọn ngữ cảnh, giữ ID và offset gốc. Ngân sách context tăng từ 1.800 lên 2.500 ký tự. Mô hình nêu phần trích cần kiểm chứng. Agent đối chiếu các trị số trong phần trích và yêu cầu nguồn ghi mức tiền khi câu hỏi hỏi bằng đồng. Khi trích sai chữ trong một khoản được nêu rõ, agent có thể tìm lại đoạn liên tục chứa tất cả trị số mà câu trả lời sử dụng. Lượt thử đầu đã lấy được hai chunk của D18 nhưng từ chối vì câu trích bị diễn đạt lại. [Trace lượt thử](../../results/basic_revised/pilot-dev/clause_grounded.json) · [Mã xử lý bằng chứng](../../src/grounding.py)

| Phương pháp trên query gốc của dev sửa đổi | Hit@1 | Evidence Hit@3 |
|---|---:|---:|
| Dense E5/Qdrant | 11/16 | 14/16 |
| Lexical TF-IDF | 8/16 | 12/16 |
| Hybrid RRF | 11/16 | 13/16 |

Ba câu thiếu bằng chứng nằm ngoài mẫu số retrieval. `clause_grounded` giữ cùng ranking query gốc với `dense`. Việc gom các chunk theo khoản thuộc bước dựng context ở lượt agent. [So sánh retrieval trên dev](../../results/basic_revised/retrieval_dev/summary.json)

| Cấu hình trên 19 câu dev | Grounded answer | Citation hợp lệ | Từ chối đúng | Trung vị |
|---|---:|---:|---:|---:|
| `dense` | 1,56/2 | 13/14 | 3/3 | 10,23 s |
| `clause_grounded` | 1,69/2 | 15/15 | 3/3 | 16,25 s |

Chọn `clause_grounded` sau khi chấm dev. D18 cả hai cấu hình trả đúng số lượng. `dense` chỉ dẫn phần số lượng nên chưa chứng minh phạm vi chương trình. `clause_grounded` dẫn cả phần xác định đối tượng và phần số lượng. D19 cả hai cấu hình từ chối đúng ở lượt dev này. Kiểm thử hồi quy riêng xác nhận guard loại trích dẫn 0,10 điểm khi câu hỏi yêu cầu số tiền. D03 và D12 vẫn thiếu đoạn đúng trong context của cả hai cấu hình. [Phiếu dev](../../results/basic_revised/dev/review_summary.json) · [Biên bản chốt](../../results/basic_revised/selection.json)

Trên R01–R07 độc lập, cả hai cấu hình có ngữ cảnh đủ và trả lời đạt 2/2 cho **5/5 câu có đáp án**, trích dẫn hợp lệ **5/5**, từ chối đúng **2/2** và có 0 lỗi hệ thống. Trung vị là **8,12 giây/câu** cho `dense` và **10,35 giây/câu** cho `clause_grounded`. Phí dịch vụ của cả hai là 0 USD. Bộ test này phân biệt khoản 1 Điều 39 với khoản 5 đã kiểm tra trên dev, và phân biệt điểm thưởng có căn cứ với câu hỏi tiền không có trong nguồn. Điểm test bằng nhau trong lượt đo này. Khác biệt quan sát được ở D18 là phạm vi được chứng minh bằng hai trích dẫn. [Tổng hợp test](../../results/basic_revised/test/review_summary.json) · [Biên bản chấm](../../reviews/basic_revised)
