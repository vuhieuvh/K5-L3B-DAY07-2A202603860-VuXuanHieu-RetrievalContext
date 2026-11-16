# Tái lập phần nâng cao Day 7

**Vũ Xuân Hiếu · 2A202603860 · L3B**

## Nguồn

Bản thuyết minh tổng hợp Quy hoạch phân khu đô thị phía Tây Vành đai 4, phân đoạn 2, tỷ lệ 1/2.000, bìa ghi Hà Nội 10.2025. Tệp 327 trang gồm phần thuyết minh, phụ lục và tài liệu pháp lý kèm hồ sơ. Số trang trong benchmark là vị trí vật lý tính từ trang đầu. SHA-256 của bản người học cung cấp và bản tải từ nguồn dẫn dưới đều là `3f34ce114dd553421e4a5c9d44c8baa39a8608afd2067c79dcb731a8f8c459fe`. Công bố chính thức là thông báo lấy ý kiến. Bài dùng đúng phiên bản đó làm corpus. [Trang công bố của Đan Phượng](https://danphuong.hanoi.gov.vn/kinh-te-tai-chinh/ve-viec-to-chuc-lay-y-kien-co-quan-quan-ly-nha-nuoc-to-chuc-chuyen-gia-va-cong-dong-dan-cu-co-lien-quan-doi-voi-quy-hoach-phan-khu-do-thi-phia-tay-vanh-dai-4-2845251030201537833.htm) · [Bản PDF tải lại có cùng hash](https://cdn.thuviennhadat.vn/upload/hinh-anh-bai-viet/TTR/thang-12-2025/01/phan-doan-2.pdf)

PDF, trọng số và các bản trích nguyên văn đầy đủ lưu cục bộ. Repo chứa đường dẫn tải lại, hash, mã tái tạo, các vùng dẫn nguồn và chú giải trực quan đã kiểm tra. Suy luận và OCR chạy tại máy người học.

## Tái dựng chỉ mục

Cài môi trường theo [phần cơ bản](RUN_DAY7.md) và khai báo `$py`, `$day6`. PDF có thể đặt tại vị trí bất kỳ và truyền qua `--pdf`. Dùng bộ nhúng Day 6 để chạy phần lập chỉ mục và truy xuất, với chỉ mục riêng cho tài liệu mới.

```powershell
$env:PYTHONUTF8 = '1'
& $py -m pip install PyMuPDF==1.27.2.3
$pdf = '../phan-doan-2.pdf'
$e5 = Join-Path $day6 '.local/e5'
$idx = '.local/bonus'
$ocr = '.local/bonus-tessdata'
New-Item -ItemType Directory -Force $ocr | Out-Null
curl.exe -fSL -o "$ocr/vie.traineddata" 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/vie.traineddata'
& $py -m bonus.ingest --pdf $pdf --tessdata $ocr --output $idx --workers 4
& $py -m bonus.index --folder $idx --embedding $e5
```

Bước nhập liệu kiểm hash PDF và trọng số OCR trước khi xử lý. Khi đổi phiên bản đầu vào hoặc mã trích xuất, chỉ định một thư mục chỉ mục mới. Nội dung gốc gồm các khối văn bản từ lớp chữ PDF, dòng theo cột từ lưới bảng phát hiện được, OCR tiếng Việt của trang scan và các thẻ hình/biểu đồ gắn với vùng ảnh. Các thẻ mô tả cấu trúc hình và ghi số liệu nhìn thấy từ biểu đồ. Kết quả OCR đáng đọc cùng ảnh gốc, nhất là các bảng scan, chữ nhỏ và số có dấu phân cách. [Chú giải trực quan](../data/bonus_visuals.json)

## Chạy và chấm

Khởi động llama.cpp b8259 Vulkan ở cổng 8090. Lượt đo chính thức dùng Qwen3-4B-Instruct-2507 Q4_K_M từ Ollama. Hash đầy đủ có trong biên bản chốt. [Nguồn trọng số](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M)

```powershell
$model = '.local/qwen3-4b-instruct-2507-q4_k_m.gguf'
$modelHash = '85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9'
curl.exe -fSL -o $model "https://registry.ollama.ai/v2/library/qwen3/blobs/sha256:${modelHash}"
if ((Get-FileHash $model).Hash.ToLowerInvariant() -ne $modelHash) {
    throw 'Trọng số không khớp SHA-256.'
}
.\.local\llama-vulkan\llama-server.exe -m $model --alias bonus-qwen3 --host 127.0.0.1 --port 8090 -c 4096 -t 4 -ngl 99 -np 1
```

Trong cửa sổ khác, đặt lại biến môi trường và đường dẫn. Tạo thư mục riêng cho từng lượt.

```powershell
$run = Join-Path '.local/bonus-runs' (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runArgs = @('--embedding', $e5, '--weights', $model, '--index', $idx,
             '--output', "$run/results", '--full', "$run/traces")
& $py -m bonus.benchmark dev --config routed @runArgs
& $py -m scripts.bonus_evidence --output "$run/results" --prepare-review dev routed
```

Đối chiếu trace đầy đủ trong `$run/traces/dev` với PDF. Điền `passed` và `reason` trong từng phiếu. Cấu hình cuối được so với các lượt dev có lịch sử trong `results/bonus/pilot` và `results/bonus/round2`. Tiêu chí ưu tiên số câu đạt nghiêm ngặt, số lỗi hệ thống thấp hơn, rồi độ trễ trung vị thấp hơn. Khi chốt, chương trình lưu hash bộ câu hỏi, mã, chỉ mục, model và phiếu chấm để xác nhận cùng đầu vào khi mở test.

```powershell
& $py -m bonus.benchmark freeze --config routed @runArgs
& $py -m bonus.benchmark test @runArgs
$chosen = (Get-Content "$run/results/selection.json" -Raw | ConvertFrom-Json).selected
& $py -m scripts.bonus_evidence --output "$run/results" --prepare-review test $chosen
```

Đọc từng trace test và đối chiếu vùng nguồn trên PDF. Điền phiếu test và chạy tổng hợp. Một câu chỉ đạt khi trả lời đúng và đủ, trích đúng vùng hoặc từ chối đúng theo đề. Lỗi hệ thống nằm trong mẫu số.

```powershell
& $py -m bonus.benchmark score-test --output "$run/results"
& $py -m scripts.bonus_evidence --pdf $pdf --output "$run/results" --verify-run
& $py -m scripts.bonus_evidence --pdf $pdf --case T15 --crop .local/bonus-audit/crops
```

Trace chia sẻ ghi ID, vùng, thứ hạng, lời truy xuất, tool call, ngữ cảnh theo ID và câu trả lời. Nội dung context đầy đủ nằm trong trace cục bộ. Có thể mở vùng gốc bằng lệnh tạo ảnh crop hoặc tra ID cùng vị trí trong PDF. Câu hỏi chuẩn và evidence dùng để chấm tách khỏi đầu vào agent. [Bộ dev](../data/bonus_dev.json) · [Bộ test](../data/bonus_test.json)

Khi kiểm tra bản đã nộp, có thể khôi phục nguyên văn trace test từ chỉ mục đã tái dựng nếu hash của tệp chunk khớp biên bản chốt.

```powershell
& $py -m scripts.bonus_evidence --pdf $pdf --index $idx --verify-run --restore .local/bonus-audit/restored
```

## Đợt đánh giá độc lập sau cải tiến

Lượt trước đạt 25/30. Năm câu lỗi được chuyển thành ca chẩn đoán `Rxx` cùng 18 câu dev gốc. Lượt sau dùng [30 câu test mới](../data/bonus_refined_test.json) mang ID `Nxx` với đủ sáu nhóm của đề. Mã bổ sung tìm vùng bảng ở trang liền kề và kiểm chứng câu trả lời bằng đúng dữ kiện từ vùng dẫn nguồn. Các ca chẩn đoán không tính vào điểm test lần hai. [Mã lần hai](../scripts/bonus_refined.py)

Dùng cùng server và cùng chỉ mục. Chọn thư mục mới cho lần chạy.

```powershell
$run = Join-Path '.local/bonus-refined-runs' (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runArgs = @('--embedding', $e5, '--weights', $model, '--index', $idx,
             '--output', "$run/results", '--full', "$run/traces")
& $py -m scripts.bonus_refined dev @runArgs
& $py -m scripts.bonus_evidence --output "$run/results" --prepare-review dev refined
```

Điền phiếu dev sau khi đọc nguồn và trace, rồi chốt trước test.

```powershell
& $py -m scripts.bonus_refined freeze @runArgs
& $py -m scripts.bonus_refined test @runArgs
& $py -m scripts.bonus_evidence --output "$run/results" --prepare-review test refined
```

Chấm từng câu trên PDF rồi tổng hợp và kiểm tra.

```powershell
& $py -m scripts.bonus_refined score-test --output "$run/results"
& $py -m scripts.bonus_evidence --pdf $pdf --refined --output "$run/results" --verify-run
& $py -m scripts.bonus_evidence --pdf $pdf --refined --case N14 --crop .local/bonus-audit/crops
```

## Đợt đánh giá với đối chiếu hàng và cột

Giữ nguyên PDF, chỉ mục và trọng số. Khởi động lại cùng llama.cpp với cửa sổ `-c 8192`. Mỗi lượt chạy cần thư mục đầu ra riêng. Bổ sung `--server` nếu đặt `llama-server.exe` ngoài đường dẫn mặc định. [Mã chạy](../scripts/bonus_verified.py)

```powershell
$pdf = (Resolve-Path $pdf).Path
$run = Join-Path '.local/bonus-verified-runs' (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runArgs = @('--pdf', $pdf, '--embedding', $e5, '--weights', $model, '--index', $idx,
             '--output', "$run/results", '--full', "$run/traces")
& $py -m scripts.bonus_verified dev @runArgs
& $py -m scripts.bonus_verified freeze @runArgs
& $py -m scripts.bonus_verified test @runArgs
```

Lượt dev gồm 18 câu ban đầu và 13 ca chẩn đoán được chuyển từ hai bộ test cũ. Khi chốt, chương trình kiểm tra mã và đầu vào có cùng hash với lượt dev vừa chạy. Mỗi câu test chỉ cung cấp nội dung câu hỏi cho agent. [Bộ test V01–V30](../data/bonus_verified_test.json)

Đọc `traces/test/verified.json` để đối chiếu nguồn đầy đủ. Chấm từng mục bằng PDF theo mẫu `verified.review.json` trong kết quả đã công bố. Đặt phiếu mới cạnh `results/test/verified.json` của lần chạy mới và điền SHA-256 của trace tương ứng vào `trace_sha256`. Phiếu phải có một mục `id`, `passed`, `reason` cho mỗi câu theo đúng thứ tự. Sau đó chạy tổng hợp.

```powershell
& $py -m scripts.bonus_verified score-test --output "$run/results"
```

## Đợt đánh giá với ràng buộc phạm vi, đại lượng và thứ tự

Dùng cùng model và server `-c 8192`. `scoped` bổ sung phạm vi theo tên mục, kiểm tra đơn vị và đọc quan hệ thứ tự trong danh sách hoặc sơ đồ. Chạy lại trong thư mục mới. [Benchmark S01–S30](../data/bonus_scoped_test.json)

```powershell
$run = Join-Path '.local/bonus-scoped-runs' (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runArgs = @('--pdf', $pdf, '--embedding', $e5, '--weights', $model, '--index', $idx,
             '--output', "$run/results", '--full', "$run/traces")
& $py -m scripts.bonus_scoped dev @runArgs
& $py -m scripts.bonus_scoped freeze @runArgs
& $py -m scripts.bonus_scoped test @runArgs
```

Đối chiếu `traces/test/scoped.json` với PDF theo cùng quy tắc chấm. Ghi một nhãn cho mỗi câu trong `results/test/scoped.review.json`, điền SHA-256 của `results/test/scoped.json` vào `trace_sha256`, rồi chạy tổng hợp.

```powershell
& $py -m scripts.bonus_scoped score-test --output "$run/results"
```

## Đợt đánh giá truy xuất theo đoạn và phần hồ sơ

Chạy cùng môi trường với đợt trên. Kết quả và mã của các đợt trước được giữ để đối chiếu. [Benchmark P01–P30](../data/bonus_passages_test.json)

```powershell
$run = Join-Path '.local/bonus-passages-runs' (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runArgs = @('--pdf', $pdf, '--embedding', $e5, '--weights', $model, '--index', $idx,
             '--output', "$run/results", '--full', "$run/traces")
& $py -m scripts.bonus_passages dev @runArgs
& $py -m scripts.bonus_passages freeze @runArgs
& $py -m scripts.bonus_passages test @runArgs
```

Đối chiếu `traces/test/passages.json` với PDF rồi ghi `results/test/passages.review.json` với đủ các trường `trace_sha256`, `labels`, và từng `id`, `passed`, `reason`. Khi đã có đủ 30 nhãn, chạy tổng hợp.

```powershell
& $py -m scripts.bonus_passages score-test --output "$run/results"
```

Bản sao của mã đúng hash đã khóa được lưu cùng kết quả. Sau khi chạy, phần tổng hợp được sửa để đếm mẫu số của từng nhóm. Mã truy xuất, trace, nhãn và tổng số câu đạt của lượt chạy giữ nguyên. [Bản sao cấu hình đã chạy](../results/bonus_passages/source/bonus_passages.py) · [Tổng hợp đã kiểm tra](../results/bonus_passages/test/summary.json)

## Đợt đánh giá truy xuất multi-hop phụ thuộc

Dùng cùng PDF, chỉ mục và server `-c 8192`. Hai cấu hình chạy trên cùng bộ dev. `parallel` lấy hình và các hàng bảng từ câu hỏi gốc, rồi sinh câu trả lời trong một lần. `dependent` đọc nhãn từ hình, đưa nhãn đó vào truy vấn bảng và đọc ô theo đúng hàng/cột. Test J01–J30 có bốn câu với tên đối tượng chỉ xuất hiện sau khi đọc hình. [Dev](../data/bonus_joined_dev.json) · [Test](../data/bonus_joined_test.json)

```powershell
$run = Join-Path '.local/bonus-joined-runs' (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runArgs = @('--pdf', $pdf, '--embedding', $e5, '--weights', $model, '--index', $idx,
             '--output', "$run/results", '--full', "$run/traces")
& $py -m scripts.bonus_joined dev @runArgs
```

Đối chiếu từng dòng trong `traces/dev/parallel.json` và `traces/dev/dependent.json` với PDF. Lập `results/dev/<config>.review.json` cho cả hai cấu hình. Mỗi phiếu có `trace_sha256` lấy từ trace chia sẻ cùng cấu hình và `labels` chứa `id`, `passed`, `reason` theo thứ tự. Chấm dev và kiểm tra hai tệp tổng hợp trước khi chốt.

```powershell
& $py -m scripts.bonus_joined score-dev --output "$run/results"
& $py -m scripts.bonus_joined freeze @runArgs
& $py -m scripts.bonus_joined test @runArgs
```

Điều kiện chọn cấu hình là đủ bốn chuỗi phụ thuộc được chấm đạt trên dev. Biên bản khóa chứa SHA-256 trace, phiếu, bảng tổng hợp và số điểm của cả hai cấu hình. Test xác minh lại toàn bộ các tệp đó, cấu hình được chọn, mã và đầu vào trước khi sinh câu trả lời. Với mỗi câu multi-hop, kiểm tra `hop_bind.value`, `hop_search_2.query` và `hop_read_cell.source_id` trong trace. Tên dùng ở truy vấn thứ hai phải do bước đọc hình trả ra và liên kết với hàng được dẫn. Hai vùng chuẩn dùng cho chấm, phía agent chỉ nhận chuỗi câu hỏi.

Sau khi đối chiếu toàn bộ test với PDF, viết phiếu `results/test/<cấu hình được chọn>.review.json` theo cùng định dạng rồi chạy tổng hợp.

```powershell
& $py -m scripts.bonus_joined score-test --output "$run/results"
```
