# Định dạng dữ liệu

## Benchmark của bài làm

`benchmark_dev.json` có 15 câu có đáp án từ split dev Day 6 đã đối chiếu lại với bản PDF đã ghim, cùng 2 câu thiếu bằng chứng mới. `benchmark_test.json` có 5 câu có đáp án mới và 2 câu thiếu bằng chứng mới. Bảy câu test được soạn trước khi chạy benchmark agent Day 7, không sử dụng lại câu test Day 6.

Nhãn của bài làm dùng `evidence_groups`. Mỗi nhóm có một hoặc nhiều vị trí thay thế hợp lệ, với trang bản có lớp chữ và offsets `[start, end)` sau chuẩn hóa. Các nhóm đều cần có mặt để chấm đủ bằng chứng trong context. Với T04, câu về số thành viên nằm ở ranh giới hai chunk, nên ghi riêng đoạn xác định hội đồng và đoạn có hai con số. Hit@1 và Evidence Hit@3 ghi nhận một phần bằng chứng trong cutoff. Report chấm độ đầy đủ riêng ở bước context.

## Dữ liệu mẫu của đề bài

Các file `example_*.json` chỉ minh họa định dạng, không đủ để nộp bài. Dữ liệu thật là JSON array UTF-8; nếu dùng định dạng khác, ghi cách chuyển trong README.

- **Chunk:** `id`, `text`, `source_id`, `source`, `page`, `metadata`. ID phải duy nhất; giữ phiên bản hoặc ngày nếu có.
- **Câu có đáp án:** `id`, `split` (`dev` hoặc `test`), `question`, `expected_answer`, `gold`: danh sách `{source_id, page, evidence}`. Với schema mẫu, mỗi evidence phải nằm trọn trong một chunk đúng nguồn và trang; các phần tử `gold` là evidence thay thế. Với câu multi-hop cần nhiều đoạn, bạn có thể mở rộng schema, ghi rõ nhóm evidence bắt buộc và cách chấm. Có thể thêm `filter` do người dùng cung cấp trước.
- **Câu thiếu evidence:** `id`, `split`, `question`, `answerable: false`, `expected_behavior: "search_and_abstain"`, `absence_reason`. Xem `agent_cases_example.json`.

Không đưa `gold` hoặc nhãn đáp án vào model và retrieval tool. Ghi nguồn dữ liệu và quyền sử dụng. Cách chuyển một số định dạng Day 6: [starter/README.md](../starter/README.md).
