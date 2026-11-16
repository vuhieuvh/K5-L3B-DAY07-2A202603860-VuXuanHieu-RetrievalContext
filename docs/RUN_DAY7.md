# Chạy bài Day 7 của Vũ Xuân Hiếu

**2A202603860 · L3B · Python 3.11**

## Dữ liệu và mô hình

- Corpus là bản có lớp chữ gồm 52 trang Quy chế 3626/QĐ-ĐHQGHN từ Day 6. Trang trong trace là trang của bản có lớp chữ, tương ứng trang kế tiếp trong PDF scan có trang quyết định ở đầu. Day 7 đọc collection `structured` gồm 180 chunk của cấu hình B. Nếu cần tái tạo đầu vào, dùng commit Day 6 `79ad9cfaa45352b8a8a9d36c55aa5be54132ef37` và làm theo README của commit đó. [README Day 6 đã ghim](https://github.com/vuhieuvh/K5-L3B-DAY06-VuXuanHieu-2A202603860-DataIngestion/blob/79ad9cfaa45352b8a8a9d36c55aa5be54132ef37/README.md) · [Manifest đã ghim](https://github.com/vuhieuvh/K5-L3B-DAY06-VuXuanHieu-2A202603860-DataIngestion/blob/79ad9cfaa45352b8a8a9d36c55aa5be54132ef37/data/manifest.json) · [Nguồn công bố Quy chế](https://fos.ussh.vnu.edu.vn/vi/laws/detail/Quy-che-dao-tao-dai-hoc-tai-Dai-hoc-Quoc-gia-Ha-Noi-Ap-dung-tu-khoa-QH-2022-X-5/)
- Dùng `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 384 chiều, bản ONNX INT8 trên CPU và tiền tố `query: ` cho truy vấn. Qdrant local tìm cosine exact. [Embedding model](https://huggingface.co/intfloat/multilingual-e5-small)
- Agent dùng **Qwen2.5 3B Instruct Q4_K_M** từ Ollama registry qua **llama.cpp b8259 Vulkan** trên Intel Iris Xe (37/37 lớp trên GPU). Tất cả prompt, đoạn tài liệu và suy luận của lần đánh giá chạy ở localhost. Cấu hình gọi model dùng JSON object, temperature 0, seed 42 và tối đa 240 token đầu ra mỗi lượt. [Gói Qwen 3B trên Ollama](https://ollama.com/library/qwen2.5:3b) · [llama.cpp b8259](https://github.com/ggml-org/llama.cpp/releases/tag/b8259)

## Chuẩn bị từ thư mục gốc

Chạy PowerShell. Thay giá trị `$day6` bằng đường dẫn tới repo Day 6 đã có `.local/qdrant` và `.local/e5`. Bản sao index cho phép chạy Day 7 mà không giữ khóa trên index gốc.

```powershell
$env:PYTHONUTF8 = '1'
$day6 = 'E:\duong_dan\repo_day_6_da_chay'
python -m venv .venv
$py = '.\.venv\Scripts\python.exe'
& $py -m pip install -r requirements.txt
New-Item -ItemType Directory -Force .local | Out-Null
if (-not (Test-Path .local/qdrant)) {
    Copy-Item -LiteralPath (Join-Path $day6 '.local/qdrant') -Destination .local/qdrant -Recurse
}
$e5 = Join-Path $day6 '.local/e5'
```

Tải hai tệp công khai vào `.local`. Kiểm tra hash GGUF trước khi khởi động server.

```powershell
curl.exe -fSL -o .local/llama-vulkan.zip 'https://github.com/ggml-org/llama.cpp/releases/download/b8259/llama-b8259-bin-win-vulkan-x64.zip'
Expand-Archive .local/llama-vulkan.zip -DestinationPath .local/llama-vulkan
$hash = '5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6'
$weights = '.local/qwen2.5-3b-ollama.gguf'
curl.exe -fSL -o $weights "https://registry.ollama.ai/v2/library/qwen2.5/blobs/sha256:${hash}"
if ((Get-FileHash $weights).Hash.ToLowerInvariant() -ne $hash) {
    throw 'Trọng số tải về không khớp SHA-256.'
}
.\.local\llama-vulkan\llama-server.exe -m $weights --alias qwen2.5-3b --host 127.0.0.1 --port 8088 -c 4096 -t 4 -ngl 99 -np 1
```

## Hỏi thử và đánh giá

Trong cửa sổ PowerShell thứ hai, đặt lại `$env:PYTHONUTF8 = '1'`, `$py`, `$e5` và `$weights` như trên.

```powershell
& $py -m unittest discover -s tests -v
$endpoint = 'http://127.0.0.1:8088'
$runtime = 'llama.cpp b8259 Vulkan Iris Xe (37/37 layers)'
$runRoot = Join-Path '.local/runs' (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$out = Join-Path $runRoot 'results'
$full = Join-Path $runRoot 'full'
$labels = Join-Path $runRoot 'reviews'
& $py -m src.benchmark ask --embedding $e5 --base-url $endpoint --config dense --question 'Khóa luận tốt nghiệp có khối lượng bao nhiêu tín chỉ?'
& $py -m src.benchmark dev --embedding $e5 --base-url $endpoint --runtime $runtime --model-file $weights --output $out --private $full
& $py -m src.benchmark prepare-review-dev --output $out --reviews $labels
```

Đọc các trace đầy đủ trong `$full/dev` và điền mẫu mới trong `$labels`. Giữ giá trị `trace_sha256` do lệnh chuẩn bị tạo. Điền một boolean cho mỗi citation trong `citation_support` và ghi `reason`. Với câu có đáp án, ghi `context_grade` và `answer_grade` từ 0 đến 2. Với câu thiếu bằng chứng, ghi `abstention_correct`. Lỗi hệ thống đã có trong trace. Tổng hợp kiểm tra hash trace trước khi đọc nhãn và ghi lại cả hash trace lẫn hash phiếu chấm.

```powershell
& $py -m src.benchmark freeze --output $out --reviews $labels
& $py -m src.benchmark test --embedding $e5 --base-url $endpoint --runtime $runtime --model-file $weights --output $out --private $full --reviews $labels
& $py -m src.benchmark prepare-review-test --output $out --reviews $labels
```

Đọc `$full/test`, điền phiếu test trong `$labels`, rồi tổng hợp.

```powershell
& $py -m src.benchmark review-test --output $out --reviews $labels
```

Mỗi lần tái lập dùng thư mục lượt chạy mới. Pha test từ chối nếu thư mục test chia sẻ hoặc thư mục trace test đầy đủ đã tồn tại. Khi lỗi ở bước retrieval của query gốc, trace ghi `original_query_error`, lượt agent của câu đó được tính là lỗi hệ thống và benchmark tiếp tục sang câu kế tiếp.

Dùng `--retrieval-only` với pha `dev` để kiểm tra ranking khi server model chưa chạy. Kết quả nằm ở `retrieval_dev`. Unit test kiểm tra hợp đồng code với fixture, còn kết quả benchmark agent phải đến từ model thật.

Nếu máy chỉ có CPU, dùng gói `llama-b8259-bin-win-cpu-x64.zip` từ cùng release, bỏ `-ngl 99` và đặt `--runtime` đúng theo backend đã dùng ở cả dev lẫn test. Thời gian và nội dung sinh có thể khác theo backend.

Trace chia sẻ giữ thứ hạng, score, chunk ID, nguồn, trang, offsets, thứ tự context, tool call và câu trả lời. Trace đầy đủ trong `.local` giữ cả nội dung đoạn theo mỗi lượt. Có thể dùng ID trong Qdrant hoặc lấy chuỗi tại `start:end` trên trang đã chuẩn hóa bằng hàm `load_pdf` của Day 6. Trọng số, index và PDF gốc được đặt ngoài cây Git.

## Kiểm tra minh chứng

Lệnh sau dùng PDF đã ghim tại `$day6/.local/3626-text.pdf` để khôi phục nguyên văn context và kết quả tool. Script dựa trên trace trong repo và không cần khởi động model hay Qdrant. Có thể bỏ `--export` để chỉ kiểm tra. Lần chạy đã đối chiếu **75 trace và 83 chunk**. Các JSON khôi phục khớp với trace đầy đủ của lần benchmark.

```powershell
& $py -m pip install PyMuPDF==1.27.2.3
& $py -m scripts.verify_submission --day6 $day6 --export .local/audit-rebuilt
```

Mở `.local/audit-rebuilt/test/dense.json`, xem `agent.events` và `agent.context`, rồi đối chiếu với [phiếu chấm test](../reviews/test_dense.json). Phần kiểm tra tự động xác nhận nguồn, thứ tự context, phép cộng điểm và hash đã khóa. Ý nghĩa của câu trả lời và nguồn vẫn cần đọc đối chiếu.

Benchmark đã lưu dùng các phiên bản agent, runner và retrieval trong [hồ sơ lần đo gốc](../results/frozen_protocol). Script kiểm chứng xác nhận SHA-256 theo biên bản chốt. Hồ sơ cũng chứa các hash ghép trace và phiếu chấm đã được ghi khi rà soát sau lần đo. Dùng `src.benchmark` cho lượt chạy mới.

## Thiết kế và tiêu chí chọn trước khi chạy test

| Cấu hình | Phương pháp | Candidate mỗi lượt | Context |
|---|---|---:|---:|
| `dense` (baseline) | E5 và Qdrant cosine | 3 | 1.800 ký tự |
| `lexical` | TF-IDF cosine theo token Unicode của starter | 3 | 1.800 ký tự |
| `hybrid` | RRF k=60 của top 10 dense và top 10 lexical | 3 | 1.800 ký tự |
| `hybrid_context` | Cùng RRF, lấy rộng hơn | 5 | 3.100 ký tự |

Bốn cấu hình dùng cùng model, corpus, câu hỏi và tối đa hai lượt gọi công cụ. Lượt tìm đầu dùng nguyên câu hỏi. Model có thể viết lại query một lần. Agent dùng endpoint `/completion` của llama.cpp với schema cho từng hành động. Agent gộp theo ID, ưu tiên thứ hạng tốt nhất rồi ưu tiên lượt mới khi đồng hạng. Context giữ nguyên văn từng đoạn trong giới hạn số ký tự JSON. Agent dừng khi có câu trả lời kèm ID hợp lệ, model từ chối, lặp query hoặc hết lượt gọi. Phép kiểm ID chỉ xác nhận citation có trong context. Phiếu chấm kiểm tra nội dung từng nguồn.

Thử nghiệm 1 dùng hybrid thay cho dense để xem từ khóa và ngữ nghĩa có bổ sung cho nhau. Thử nghiệm 2 mở rộng top-k và ngân sách trên hybrid để xem thêm bằng chứng có vào context. Hai tham số của thử nghiệm 2 thay đổi cùng nhau, vì vậy chỉ đo được hiệu ứng của cả cấu hình. Mọi cấu hình đều chạy query gốc với cutoff cố định 1 và 3. Trace agent lưu thêm từng query viết lại.

Tiêu chí đã ghi trong mã trước test. Ưu tiên điểm grounded answer trung bình trên dev, rồi số context chấm 2, số từ chối đúng, và trung vị thời gian agent. Trường hợp hòa hoàn toàn ưu tiên theo thứ tự trong bảng. Cấu hình có lỗi model hoặc store bị loại khi chọn. Bộ test dùng file lựa chọn đã chốt và kiểm tra hash code, index, embedding, model và benchmark trước khi chạy.

## Đánh giá lại Điều 39 và Điều 32

Suite `revised` dùng cùng Day 6 Qdrant và embedding. Trên dev, D18 làm rõ câu hội đồng chấm khóa luận cho chương trình tài năng và chất lượng cao tại khoản 5 Điều 39. D19 đưa câu hỏi tiền thưởng T07 vào chẩn đoán. Bộ R01–R07 dùng các câu hỏi khác để kiểm tra khả năng phân biệt khoản, mức điểm và đơn vị. [Dev sửa đổi](../data/benchmark_revised_dev.json) · [Test mới](../data/benchmark_revised_test.json)

Khởi động Qwen3-4B-Instruct-2507 Q4_K_M tại cổng 8088, thay đường dẫn `$weights` bằng tệp đã kiểm hash trong [hướng dẫn phần nâng cao](RUN_BONUS_DAY7.md). Dùng `-c 8192 -t 4 -ngl 99 -np 1`. Trong cửa sổ chạy benchmark, chỉ định ba thư mục mới.

```powershell
$weights = '.local/qwen3-4b-instruct-2507-q4_k_m.gguf'
$runRoot = Join-Path '.local/basic-revised-runs' (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runArgs = @('--suite', 'revised', '--embedding', $e5, '--base-url', 'http://127.0.0.1:8088',
             '--model', 'qwen3-4b-instruct-2507', '--model-file', $weights,
             '--runtime', 'llama.cpp b8259 Vulkan Iris Xe, n_ctx 8192',
             '--output', "$runRoot/results", '--private', "$runRoot/full", '--reviews', "$runRoot/reviews")
& $py -m src.benchmark dev --retrieval-only @runArgs
& $py -m src.benchmark dev @runArgs
& $py -m src.benchmark prepare-review-dev @runArgs
```

Đối chiếu trace dev đầy đủ với PDF rồi chấm phiếu của `dense` và `clause_grounded`. Lượt chỉ retrieval so sánh các phương pháp trên cùng 19 câu dev. Trước khi xếp hạng hai cấu hình agent, cấu hình phải có context và câu trả lời D18 đạt 2 với nguồn đúng, từ chối D19 đúng và hoàn tất không lỗi hệ thống. Chạy test sau khi khóa.

```powershell
& $py -m src.benchmark freeze @runArgs
& $py -m src.benchmark test @runArgs
& $py -m src.benchmark prepare-review-test @runArgs
# Điền phiếu test bằng cách đối chiếu từng câu với PDF trước khi tổng hợp.
& $py -m src.benchmark review-test @runArgs
```

Để hỏi trực tiếp bằng bản sửa, dùng `ask --suite revised --config clause_grounded`. Trace cho thấy danh sách đoạn tra theo khoản trong `context_candidates`, nguồn chứa mở đầu khoản trong `scope_anchor_ids` và kết quả kiểm tra trích dẫn trong sự kiện `verify`.

Có thể kiểm tra minh chứng đã lưu và tái dựng ngữ cảnh từ PDF Day 6 bằng lệnh dưới đây.

```powershell
& $py -m scripts.verify_submission --suite revised --day6 $day6 --export .local/basic-revised-audit
```
