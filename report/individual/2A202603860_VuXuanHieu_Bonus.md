# Day 7 · Báo cáo phần nâng cao

**Vũ Xuân Hiếu · 2A202603860 · Lớp L3B**

Lượt J01–J30 đạt **30/30 (100,00%)**, với **4/4 câu multi-hop có trace truy xuất phụ thuộc**. Hai cấu hình đã được chấm dev trước khi chọn và khóa. Lượt lịch sử P01–P30 tiếp tục là hồ sơ đối chiếu chất lượng câu trả lời và citation. [Tổng hợp J01–J30](../../results/bonus_joined/test/summary.json) · [Đối chiếu nhận xét](../../docs/PHAN_HOI_CHAM_BAI.md#bản-chấm-80100-và-hai-điều-kiện-bonus)

## Tài liệu và phạm vi

Dùng bản thuyết minh tổng hợp Quy hoạch phân khu đô thị phía Tây Vành đai 4, phân đoạn 2, tỷ lệ 1/2.000, bản tháng 10/2025. Tệp có 327 trang vật lý. Bản người học đưa và bản tải lại công khai khớp SHA-256. Hồ sơ được công bố lấy ý kiến. Bài sử dụng hồ sơ cho thực nghiệm cục bộ và chỉ dẫn lại đường tải, phiên bản, hash và vùng nguồn để tái lập. [Nguồn và hướng dẫn](../../docs/RUN_BONUS_DAY7.md#nguồn)

Chỉ mục bao phủ **327/327 trang** với **1.316 đoạn** gồm 440 đoạn văn bản gốc, 545 đoạn OCR, 315 đoạn bảng, 15 thẻ ảnh hoặc sơ đồ và 1 thẻ biểu đồ. Có 153 trang OCR không có lớp chữ và ba trang có cả lớp chữ lẫn OCR. Ranh giới vùng lưu theo tọa độ PDF. Bảng giữ vùng bảng, số dòng và nội dung từ lưới cột nhận diện được. Các hình được mô tả từ ảnh gốc, còn số liệu biểu đồ được chép từ nhãn in trong vùng biểu đồ. [Hồ sơ chỉ mục](../../results/bonus/index_profile.json) · [Thẻ trực quan](../../data/bonus_visuals.json)

OCR tiếng Việt và trích bảng có thể nhầm chữ nhỏ hoặc tách một hàng nhiều dòng thành các hàng con. Bảng trong phụ lục scan được truy xuất bằng lớp OCR, độ tin cậy của các ô riêng lẻ cần đối chiếu ảnh. Chỉ mục dùng thẻ ảnh và OCR như đại diện truy xuất cho nội dung trực quan. Tệp gốc vẫn là nguồn kiểm chứng cho các vùng nhỏ, màu chú giải và số liệu.

## Thiết kế và đánh giá

Dense dùng multilingual E5 384 chiều. Lexical dùng TF-IDF trên token, cặp và nhóm ba từ tiếng Việt đã chuẩn hóa phục vụ tìm kiếm; bản gốc giữ nguyên dấu. Hai thứ hạng hợp nhất bằng RRF. Lượt đo chính thức dùng Qwen3-4B-Instruct-2507 Q4_K_M thông qua llama.cpp b8259 Vulkan, suy luận tại localhost. Cấu hình hybrid tìm toàn corpus. Cấu hình routed nhận diện phạm vi bảng/hình/biểu đồ trong câu hỏi, ưu tiên phần thuyết minh khi không gọi tên phụ lục, tách yêu cầu nhiều ý và kiểm lại kết luận lấy từ biểu đồ. [Mã index](../../bonus/index.py) · [Mã agent](../../bonus/benchmark.py)

Bộ dev/test được lập trước khi so sánh model. Dev có 15 câu có đáp án và 3 câu thiếu bằng chứng. Test có 30 câu mới theo năm nhóm có đáp án và nhóm thiếu bằng chứng. Năm câu biểu đồ kiểm tra các đặc điểm khác nhau của biểu đồ dân số trang 18, gồm đọc chú giải/trục, so ngưỡng, đọc nhãn cột và tính tổng. Với câu thiếu evidence, phạm vi được ghi rõ trong câu hỏi và được rà trên hình, bảng hoặc biểu đồ tương ứng. Khi chạy, agent nhận câu hỏi và kết quả truy xuất. Gold chỉ dùng để đối chiếu kết quả. [Dev](../../data/bonus_dev.json) · [Test](../../data/bonus_test.json)

Câu có đáp án phải có đủ nội dung, số, đơn vị và trích đúng vùng chứng minh. Khi chính câu hỏi chỉ định duy nhất đơn vị cần trả về, một số đứng riêng được hiểu theo đơn vị đó nếu vùng dẫn nguồn xác nhận cùng đơn vị. Câu thiếu bằng chứng cần từ chối rõ ràng. Các lỗi kết nối hoặc model nằm trong mẫu số. Nhãn được lập bằng cách đọc trace và đối chiếu ảnh/PDF nguồn. Ngưỡng đề yêu cầu ít nhất 27/30 trên bộ test này. [Quy tắc bonus](../../ADVANCED.md)

## Kết quả và phân tích

### Chọn trên dev

| Lượt | Model | Cấu hình | Số câu đạt | Độ trễ trung vị |
|---|---|---|---:|---:|
| Thử ban đầu | Qwen2.5 3B | Hybrid | 12/18 | 8,78 s |
| Thử ban đầu | Qwen2.5 3B | Routed | 11/18 | 5,63 s |
| Sau sửa định tuyến | Qwen3 4B | Hybrid | 15/18 | 9,84 s |
| Sau sửa định tuyến | Qwen3 4B | Routed | 14/18 | 6,68 s |
| Lượt chốt | Qwen3 4B | Routed, lọc số hiệu bảng và yêu cầu citation gọn cho mỗi ý | 15/18 | 9,45 s |

Chọn routed lượt chốt vì bằng số câu đạt và số lỗi hệ thống với hybrid Qwen3, còn độ trễ trung vị trong lần đo thấp hơn. Đây là thống kê trên 18 câu của một tài liệu. Các bản ghi dev, phiếu chấm và hash có trong hồ sơ từng lượt. [Thử ban đầu](../../results/bonus/pilot/dev/summary.json) · [Lượt thứ hai](../../results/bonus/round2/dev/summary.json) · [Biên bản chốt](../../results/bonus/selection.json)

- **D12:** Chuẩn hóa bỏ dấu từng làm “bằng đường sắt” kích hoạt bộ lọc bảng. Dùng chữ “bảng” có dấu ở bước nhận diện phạm vi khắc phục lỗi. Agent tìm được đoạn về tiếp cận nội đô trong 15 phút.
- **D16:** Qwen2.5 gán nhầm dân số của một xã cho một nhóm tuổi. Các lượt Qwen3 từ chối đúng khi nhóm tuổi vắng mặt trong biểu đồ. Model và một số chi tiết prompt khác cùng thay đổi giữa hai lượt.
- **D18:** Routed lượt hai dùng số ở bảng 7.6-3 để trả lời về bảng 7.6-4. Lọc theo số hiệu bảng thu hẹp vùng tìm đúng bảng và agent từ chối ở lượt chốt.
- **D03 và D15:** Lượt chốt vẫn có thể lấy dòng tổng thay dòng con hoặc thêm citation về đối tượng khác dù đã yêu cầu một đoạn sát nhất. Hai câu này được chấm trượt y nguyên theo quy tắc evidence.

### Test độc lập

Chốt cấu hình `routed` lúc `2026-11-16T11:17:19.583995+07:00`; sau đó chạy đủ 30 câu test. **Dưới ngưỡng 90% với 25/30 (83.33%)**.

| Nhóm | Đạt / tổng | Tỷ lệ |
|---|---:|---:|
| Bảng | 5/6 | 83.33% |
| Ảnh / sơ đồ | 5/5 | 100.00% |
| Biểu đồ | 5/5 | 100.00% |
| Multi-hop | 4/4 | 100.00% |
| Văn bản | 3/4 | 75.00% |
| Thiếu bằng chứng | 3/6 | 50.00% |
| **Toàn bộ** | **25/30** | **83.33%** |

Có 0 lỗi hệ thống. Độ trễ trung vị 9.45 giây/câu, tổng thời gian xử lý 314.48 giây, phí dịch vụ 0 USD.

Các câu trượt điểm

- **T02** · Bảng hiện trạng tiếp sang tr. 19 và ghi 50,89%. Agent dẫn bảng theo ô đất tr. 84 và lấy nhầm 1,11%.
- **T24** · 6 làn là trị số cần tìm ở hiện trạng Đại lộ Thăng Long tr. 25. Citation tr. 113 nói về 6 làn chính của trục Tây Thăng Long.
- **T27** · Hình 6 tr. 55 chỉ đánh dấu Khu A đến D. Màu tím thuộc Khu B, không có Khu E.
- **T29** · Hình 13 tr. 144 chỉ có hai lưu vực. Vị trí dưới và trái thuộc Lưu vực 2.
- **T30** · Bảng phụ tải điện tr. 134 có kW và kVA cho A2, không có đồng/kWh. Số 150 ở phần nội dung đứng trước bảng không phải giá điện.

[Trace test lần đầu](../../results/bonus/test/routed.json) · [Nhãn và lý do từng câu](../../results/bonus/test/routed.review.json) · [Tổng hợp](../../results/bonus/test/summary.json)

### Đợt đánh giá độc lập sau cải tiến

Giữ trọn kết quả 25/30 của lần đầu. Chuyển năm câu lỗi thành bài chẩn đoán `R02`, `R24`, `R27`, `R29`, `R30` trên dev. Phiên bản cải tiến bổ sung đoạn bảng ở trang liền kề khi tiêu đề và hàng cần tìm nằm ở hai trang. Kiểm tra định danh khu/vùng và đơn vị tiền trên đoạn được trích, rồi dùng Qwen3 đối chiếu mệnh đề với chính các đoạn đó. Bước đối chiếu có thể bỏ các citation dư. [Mã lần hai](../../scripts/bonus_refined.py)

Dev cải tiến đạt **16/18** trên câu dev gốc và **4/5** trên ca chẩn đoán. R02 lấy được hàng đúng ở trang 19. R27, R29 và R30 được từ chối đúng. R24 vẫn nhầm Đại lộ Thăng Long với trục Tây Thăng Long dù đã qua bước kiểm chứng. Bộ test lần hai có 30 câu ID `Nxx` khác các câu đã dùng để tinh chỉnh. [Phiếu dev](../../results/bonus_refined/dev/refined.review.json) · [Bộ test mới](../../data/bonus_refined_test.json) · [Biên bản chốt](../../results/bonus_refined/selection.json)

Chốt lúc `2026-11-16T11:32:04.895689+07:00`. Test mới đạt **22/30 (73.33%)**, dưới ngưỡng 90%. Hai lượt test dùng câu hỏi khác nhau.

| Nhóm | Đạt / tổng | Tỷ lệ |
|---|---:|---:|
| Bảng | 4/6 | 66.67% |
| Ảnh / sơ đồ | 2/5 | 40.00% |
| Biểu đồ | 4/5 | 80.00% |
| Multi-hop | 3/4 | 75.00% |
| Văn bản | 4/4 | 100.00% |
| Thiếu bằng chứng | 5/6 | 83.33% |
| **Toàn bộ** | **22/30** | **73.33%** |

Có 0 lỗi hệ thống. Độ trễ trung vị 12.90 giây/câu. Tổng 415.87 giây. Phí dịch vụ 0 USD.

Các câu trượt điểm

- **N02** · Bảng hiện trạng tiếp ở tr. 19 ghi Hồ, ao, đầm 79,40 ha. Agent lấy 0,51 ở bảng quy hoạch theo ô đất tr. 82.
- **N04** · Ô A3 tr. 134 ghi 5.553 kW và 6.170 kVA. Agent đọc nhầm cột kW.
- **N07** · Hình 3 tr. 14 cho thấy ảnh vệ tinh còn nhìn thấy trong đường viền. Chỉ trả lời 'Không' cho câu hỏi hai lựa chọn chưa xác định được phương án.
- **N09** · Hiện trạng và Quy hoạch là hai nhóm chính. Hai cột dưới Quy hoạch là Đợt đầu và Dài hạn.
- **N11** · Hai hình phía dưới tr. 103 mô tả dãy kho xưởng. Agent lặp nhóm tiêu đề chung của toàn bộ Hình 11, gồm cả bến và dịch vụ cảng.
- **N15** · Cột Sơn Đồng ở tr. 18 ghi 9.490 người, nằm trong khoảng cần tìm. Agent từ chối.
- **N20** · Màu đỏ đúng ở Hình 13. Agent dẫn thoát nước mưa tr. 108 cho ý 2, trong khi mục Lựa chọn hệ thống thoát nước thải tr. 143 nêu hệ thống riêng hoàn toàn.
- **N25** · Biểu đồ tr. 18 chỉ có dân số chung từng xã. 39,9% dân số nam ở Đan Phượng không có căn cứ.

[Trace test lần hai](../../results/bonus_refined/test/refined.json) · [Phiếu chấm từng câu](../../results/bonus_refined/test/refined.review.json) · [Tổng hợp](../../results/bonus_refined/test/summary.json)

Hai đợt đều dùng đúng 30 câu đã chốt cho từng đợt và đều dưới ngưỡng 27/30. Ở đợt hai, kiểm chứng phát hiện một số câu thiếu bằng chứng nhưng vẫn bỏ lọt lỗi phân biệt cột, cấp chú giải và phạm vi nguồn. Chênh lệch tỷ lệ giữa hai tập test cần được đọc cùng lưu ý rằng chúng gồm các câu hỏi khác nhau.

### Đợt đánh giá với đối chiếu hàng và cột

Hai tập test trước được giữ nguyên. Chênh lệch từ 25 xuống 22 câu gồm giảm 3 câu ảnh/sơ đồ và giảm 1 câu ở mỗi nhóm bảng, biểu đồ, đa nguồn. Văn bản tăng 1 câu và từ chối đúng tăng 2 câu. Các nhóm đo trên hai tập câu hỏi khác nhau. Trên cùng 18 câu dev ban đầu, hai phiên bản cũ đạt lần lượt 15/18 và 16/18.

Phiên bản này đọc lại lưới bảng từ PDF theo hàng và cột, gắn tên bảng cho trang tiếp nối, và giữ vị trí thực của hàng. Bảng phụ tải có ô gộp làm lệch chỉ số vật lý, nên mã dùng thứ tự bốn ô có dữ liệu để phân biệt Ptt (kW) và Stt (kVA). Bước đọc ô xét cả định danh, nhóm, cột và kỳ nếu được nêu. Khi cần thông tin bên trong hình, agent đọc chú giải nội vùng. Với câu biểu đồ có phép tính, chương trình thực hiện phép tính từ dãy số đã kiểm tra trong biểu đồ và ghi lựa chọn công cụ vào trace. Với câu hỏi chữ, mô hình chỉ định một nguồn cùng đoạn trích liên tục. Chương trình kiểm tra đoạn trích và định danh hiện diện trong nguồn. Câu đa nguồn được kiểm tra theo từng ý và giữ đủ các vùng hỗ trợ. [Mã chạy](../../scripts/bonus_verified.py)

Lượt dev gồm 18 câu gốc và 13 ca chẩn đoán lấy từ các lỗi của hai lần trước. Bộ V01–V30 bao phủ 6 câu bảng, 5 câu ảnh/sơ đồ, 5 câu biểu đồ, 4 câu nhiều nguồn, 4 câu văn bản và 6 câu thiếu bằng chứng. Đáp án và vùng chuẩn chỉ dùng khi chấm. Mọi câu biểu đồ dùng một biểu đồ dân số ở trang 18. Bản sửa chỉ gia cố cấu trúc bảy bảng, với chỉ mục đầy đủ 327 trang tiếp tục phục vụ tìm kiếm văn bản, OCR và bảng khác. Phương pháp đọc hình dựa vào mô tả đã đối chiếu PDF nên độ bao phủ phụ thuộc chi tiết có trong mô tả. [Bộ test V01–V30](../../data/bonus_verified_test.json)

Trước khi chốt, bản này đạt **18/18 trên dev gốc** và **11/13 trên ca chẩn đoán**. R24 vẫn lấy đúng trị số nhưng dẫn nhầm tuyến Tây Thăng Long. RN20 chọn đúng nguồn thoát nước thải và đúng loại hệ thống riêng, nhưng thiếu từ “hoàn toàn” khi chấm nghiêm theo đáp án. Hai ca được giữ là lỗi dev. [Tổng hợp dev](../../results/bonus_verified/dev/summary.json) · [Phiếu chấm dev](../../results/bonus_verified/dev/verified.review.json)

Test độc lập V01–V30 đạt **23/30 (76,67%)**. Bảng 6/6, ảnh/sơ đồ 4/5, biểu đồ 5/5, đa nguồn 3/4, văn bản 2/4, thiếu bằng chứng 3/6. Có 0 lỗi hệ thống. Độ trễ trung vị 4,35 giây, tổng 200,59 giây và phí dịch vụ 0 USD. V09 và V23 truy xuất đúng vùng nhưng chọn sai vị trí trong một dãy. V17 dẫn phụ lục thay cho mục được hỏi. V24 bỏ sót đoạn có đáp án. V25, V26 và V29 lấy số có thật để trả lời cho một đại lượng khác, lần lượt là mật độ dân số, sức chứa và điện áp. [Trace](../../results/bonus_verified/test/verified.json) · [Phiếu chấm](../../results/bonus_verified/test/verified.review.json) · [Tổng hợp](../../results/bonus_verified/test/summary.json)

### Đợt đánh giá với ràng buộc phạm vi, đại lượng và thứ tự

Bản tiếp theo ưu tiên đoạn chứa tên mục được chỉ định rõ, kiểm tra đại lượng yêu cầu có mặt trong các vùng nguồn và xác định vị trí giữa các mốc bằng chính thứ tự từ PDF. Nếu chỉ có kW hoặc kVA, agent từ chối câu hỏi kV. Tương tự, tổng dân số không đáp ứng câu hỏi mật độ dân số. Với dãy có dấu mũi tên hoặc danh sách ghi rõ thứ tự trái sang phải, agent có thể lấy phần tử giữa hai mốc bằng chương trình. Quote và phạm vi được ghi lại để chấm. [Mã lần bốn](../../scripts/bonus_scoped.py)

Bộ S01–S30 dùng các câu hỏi khác, với cùng phân bổ theo nhóm và các đáp án xác định từ cùng PDF. Phiên bản này dùng ba lượt test cũ làm hồ sơ lỗi, còn các câu đưa lại vào dev được đánh dấu riêng. [Bộ test S01–S30](../../data/bonus_scoped_test.json)

Dev đạt **18/18 câu gốc** và **9/11 ca chẩn đoán**, trong đó cả **7/7 lỗi V01–V30** được xử lý đúng khi chạy lại. R24 vẫn dẫn nhầm tuyến đường, còn RN20 từ chối ý thứ hai sau khi không xác thực được đúng mục thoát nước thải. Các ca chẩn đoán chỉ dùng để chốt cấu hình. [Tổng hợp dev](../../results/bonus_scoped/dev/summary.json) · [Phiếu chấm dev](../../results/bonus_scoped/dev/scoped.review.json) · [Biên bản chốt](../../results/bonus_scoped/selection.json)

Test S01–S30 đạt **27/30 (90,00%)**, đúng ngưỡng tối thiểu của rubric. Bảng 6/6, ảnh/sơ đồ 4/5, biểu đồ 5/5, đa nguồn 2/4, văn bản 4/4 và thiếu bằng chứng 6/6. Có 0 lỗi hệ thống. Độ trễ trung vị 2,72 giây, tổng 187,67 giây, phí dịch vụ 0 USD. S07 từ chối dù bản đồ có nhãn Thái Nguyên. S19 ghép đúng sơ đồ nhưng không tìm được đoạn riêng về nước thải công nghiệp. S20 dùng khoảng 3.100 ha của quyết định trong phụ lục, trong khi mục được hỏi ghi khoảng 3.086 ha. [Trace](../../results/bonus_scoped/test/scoped.json) · [Phiếu chấm](../../results/bonus_scoped/test/scoped.review.json) · [Tổng hợp](../../results/bonus_scoped/test/summary.json)

### Đợt đánh giá với truy xuất theo đoạn và phần hồ sơ

Phiên bản này giữ chỉ mục toàn tài liệu và các công cụ của đợt trước. Với câu hỏi văn bản, agent ưu tiên đoạn có cụm từ trùng dài và sát chủ đề, đồng thời dùng phạm vi thuyết minh hoặc phụ lục theo nội dung câu hỏi. Khi bộ tìm kiếm theo đoạn thiếu kết quả đủ liên quan, agent dùng lại kết quả truy xuất lai. Với câu nhận diện nhãn có hai lựa chọn rõ, agent chọn khi chỉ một nhãn xuất hiện trong nội dung vùng hình. Mục tiêu của các thay đổi là giảm khả năng lấy nhầm trị số từ phần khác của PDF và tăng tính nhất quán của câu đa nguồn. [Mã chạy](../../scripts/bonus_passages.py) · [Bộ test P01–P30](../../data/bonus_passages_test.json)

Dev đạt **17/18 câu gốc** và **5/6 ca chẩn đoán**, gồm cả **3/3 lỗi S01–S30**. Hai lỗi còn lại trong dev là dẫn mô tả sông Đáy khi được hỏi đầy đủ về ranh phía Tây và lấy nội dung thoát nước mưa khi được hỏi về hệ thống thoát nước thải. Các bộ test đã chấm giữ nguyên câu, nhãn và trace. [Tổng hợp dev](../../results/bonus_passages/dev/summary.json) · [Phiếu chấm dev](../../results/bonus_passages/dev/passages.review.json) · [Biên bản chốt](../../results/bonus_passages/selection.json)

| Nhóm | Đạt / tổng |
|---|---:|
| Bảng | 6/6 |
| Ảnh / sơ đồ | 5/5 |
| Biểu đồ | 5/5 |
| Đa nguồn | 4/4 |
| Văn bản | 4/4 |
| Thiếu bằng chứng | 6/6 |
| **Toàn bộ** | **30/30** |

Có 0 lỗi hệ thống. Thời gian trung vị 3,32 giây/câu, tổng thời gian xử lý 127,95 giây và phí dịch vụ 0 USD. Phiếu chấm ghi đối chiếu vùng PDF cho từng câu. Bộ test dùng một tài liệu và một biểu đồ dân số; các lỗi dev vẫn cho thấy rủi ro khi câu hỏi chỉ định phạm vi bằng những cụm từ chung. [Trace](../../results/bonus_passages/test/passages.json) · [Phiếu chấm](../../results/bonus_passages/test/passages.review.json) · [Tổng hợp](../../results/bonus_passages/test/summary.json)

### Đợt đánh giá truy xuất multi-hop phụ thuộc

J17–J20 đều có một kết luận cần nhãn từ hình để chọn hàng của bảng ở trang khác. Tên đối tượng không xuất hiện trong câu hỏi. Agent chọn nhãn dựa trên thẻ hình đối chiếu từ PDF, đưa nhãn đó vào truy vấn bảng, rồi đọc đúng ô theo dòng, nhóm và đơn vị. Gold ghi hai vùng và trường `bridge` cho người chấm. Trace ghi `hop_bind` cùng tên lấy từ hình và `hop_search_2` với truy vấn kế tiếp. Bước tổng hợp kiểm khớp nhãn, thứ tự truy vấn, ID trích dẫn và đoạn truy xuất trước khi tính một chuỗi đạt. [Bộ câu hỏi](../../data/bonus_joined_test.json) · [Mã truy xuất](../../scripts/bonus_joined.py)

Chạy `parallel` và `dependent` trên cùng bộ dev 22 câu. `parallel` lấy hình và bảng song song từ câu hỏi ban đầu. `dependent` lấy nhãn hình trước khi truy xuất hàng bảng. Chấm cả hai cấu hình trước khi khóa. Cấu hình hợp lệ phải có đủ bốn chuỗi dev đạt với trace phụ thuộc. Sau đó ưu tiên số câu dev đạt, số câu đa nguồn đạt, số lỗi hệ thống thấp hơn và độ trễ trung vị thấp hơn. Biên bản chốt lưu SHA-256 của hai trace, hai phiếu, hai bảng tổng hợp và danh tính mã/đầu vào. Chương trình xác minh lại các tệp này trước khi chạy test độc lập. [Dev](../../data/bonus_joined_dev.json) · [Cách tái lập](../../docs/RUN_BONUS_DAY7.md)

| Cấu hình dev | Đạt / tổng | Chuỗi phụ thuộc có trace | Lỗi hệ thống | Trung vị |
|---|---:|---:|---:|---:|
| `parallel` | 18/22 | 0/4 | 2 | 6,96 s |
| `dependent` | 21/22 | 4/4 | 0 | 4,55 s |

Chọn `dependent` sau khi ghi phiếu và tổng hợp dev. `parallel` trả đúng kết luận JD03 từ ngữ cảnh lấy song song, nhưng trace thiếu truy vấn bảng sử dụng nhãn vừa đọc. `dependent` xử lý đủ bốn chuỗi đạt. Cả hai cấu hình còn sai D13 vì dùng mô tả sông Đáy thay cho đoạn xác định ranh giới phía Tây. Nhánh truy xuất phụ thuộc hiện hỗ trợ câu hỏi hình → bảng nêu rõ hình, chỉ tiêu và tên bảng. [Tổng hợp parallel](../../results/bonus_joined/dev/parallel.summary.json) · [Tổng hợp dependent](../../results/bonus_joined/dev/dependent.summary.json) · [Biên bản chốt](../../results/bonus_joined/selection.json)

| Câu | Nhãn đọc trước | Hàng được tra sau |
|---|---|---|
| J17 | Ô tím sáng tr. 20 → Đất sản xuất công nghiệp, kho bãi | Bảng hiện trạng tr. 19 → 76,27 ha |
| J18 | Ô xanh lam cuối chú giải tr. 20 → Sông, suối, kênh, rạch | Bảng hiện trạng tr. 19 → 108,06 ha |
| J19 | Vùng vàng nâu tr. 55 → Khu C | Ô Stt của Khu C tr. 135 → 135.931 kVA |
| J20 | Vùng xanh lam sáng tr. 55 → Khu D | Dòng CTR xây dựng thuộc Khu D tr. 147 → 8,0 tấn/ngày |

Test đạt **30/30**. Bảng 6/6, ảnh/sơ đồ 5/5, biểu đồ 5/5, đa nguồn 4/4, văn bản 4/4 và thiếu bằng chứng 6/6. Có 0 lỗi hệ thống. Thời gian trung vị 2,62 giây/câu, tổng 84,27 giây, phí dịch vụ 0 USD. [Trace](../../results/bonus_joined/test/dependent.json) · [Phiếu chấm](../../results/bonus_joined/test/dependent.review.json) · [Tổng hợp](../../results/bonus_joined/test/summary.json)

## Tái lập

Dùng [hướng dẫn Day 7 bonus](../../docs/RUN_BONUS_DAY7.md) để tải đúng PDF và trọng số, tạo lại chỉ mục và chạy từng giai đoạn. Bộ test có thể kiểm chứng bằng ảnh crop theo ID hoặc khôi phục nguyên văn từ cùng chỉ mục. PDF, trọng số, dữ liệu index và trace có nội dung đầy đủ được xử lý cục bộ. Trace chia sẻ giữ các tham chiếu để kiểm lại vùng gốc.

Chi phí dịch vụ của OCR, index và suy luận bằng 0 USD trong lần chạy cục bộ. Điện và thiết bị chưa được đo. Các giới hạn chính gồm một tài liệu duy nhất, một biểu đồ được kiểm thử sâu, chất lượng OCR không đồng đều trong phụ lục và phụ thuộc vào độ chính xác của khâu chọn vùng bằng chứng.
