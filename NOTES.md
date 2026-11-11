# Ghi chú phân tích · Day 04

Họ và tên: Nguyễn Trung Duy

MSSV: 2A202603387

## 1. Case được chọn

- **H2:** kiểm tra khẳng định GitHub Actions đang gặp sự cố dựa trên incident `t89g2q1800fr`.
- Câu hỏi yêu cầu kiểm tra cả snapshot, tình trạng incident và dẫn nguồn.
- Điểm lần đầu: **50/100**. Raw judge score là 95 nhưng kiểm tra bằng code giới hạn còn 50 vì thiếu get_status.

Trích câu trả lời lần đầu:

> Do đó, khẳng định GitHub Actions đang outage dựa trên incident này là không chính xác vì sự cố đã được khắc phục. Nếu bạn gặp vấn đề, nguyên nhân có thể không liên quan tới incident này.

Agent nhận ra incident đã resolved nhưng chưa lấy trạng thái Actions trong snapshot. Một incident cũ đã resolved chưa đủ chứng minh component đang operational vì vẫn có thể có sự cố khác.

## 2. Bằng chứng trong trace

Trace H2 trong eval_before.json chỉ có một tool call. Đoạn dưới trích các trường liên quan, lược bỏ updates và metadata:

```json
[
  {"event": "model", "step": 1, "finish": "tool_calls", "tool_calls": 1},
  {
    "event": "tool",
    "step": 1,
    "name": "get_incident_details",
    "arguments": {"provider": "github", "incident_id": "t89g2q1800fr"},
    "result": {
      "ok": true,
      "status": "resolved",
      "captured_at": "2026-11-09T03:50:47.065020+00:00",
      "url": "https://stspg.io/lv4q3xm9r0rk"
    }
  },
  {"event": "model", "step": 2, "finish": "stop", "tool_calls": 0},
  {"event": "completed", "step": 2}
]
```

`grade.mechanical.violations` ghi: `Chưa gọi tool cần thiết: get_status`.

Prompt cũ chưa yêu cầu rõ phải kiểm tra cả status và chi tiết incident. Vì vậy, model thấy incident đã resolved thì dừng. Câu trả lời có URL nên vượt qua bước kiểm tra nguồn, dù vẫn thiếu dữ liệu status.

## 3. Thay đổi đã thực hiện

Đối chiếu agent_before.py với agent.py, thay đổi nằm ở system message trong run_agent. Prompt bổ sung:

> Khi hỏi dịch vụ có đang outage hay không, phải lấy cả status snapshot và chi tiết incident được nhắc tới; incident đã resolved không tự chứng minh component hiện operational.

Thay đổi này nhằm tránh việc agent kết luận quá sớm như ở H2. Agent vẫn chọn tool và tham số dựa trên câu hỏi, không có đáp án hoặc ID incident viết sẵn trong code.

Các hướng dẫn khác được thêm vào prompt gồm:

- Dùng tên component tiếng Anh ngắn và thử lại bộ lọc nếu không có kết quả.
- Đọc thêm incident liên quan khi thấy liên kết trong update, tránh đọc lặp.
- Không nhầm updated_at với thời điểm bắt đầu hoặc kết thúc sự cố.
- Không coi danh sách trả về là toàn bộ lịch sử incident.

Do sửa nhiều hướng dẫn cùng lúc, chưa biết riêng thay đổi nào giúp tăng bao nhiêu điểm.

Cơ chế kiểm tra nguồn hiện có: lưu URL từ get_incident_details thành công; nếu câu trả lời không chứa URL nào đã quan sát thì ghi validation_missing_source và yêu cầu sửa trong max_steps. Cơ chế này đã có ở cả hai file agent, không phải thay đổi mới giữa hai phiên bản.

Kiểm tra offline: `python -m unittest discover -s tests -v` — **37/37 tests pass**, bao gồm tests kiểm tra nguồn trong tests/test_validation.py.

## 4. So sánh hai lần chạy

Hai lần chạy đều dùng OpenAI, model gpt-4.1-mini cho cả agent và phần chấm điểm, max_steps = 8 và bộ case core. Cả hai đều chấm đủ 22 case. File kết quả không lưu mã phiên bản code hoặc snapshot, nên không thể chỉ nhìn config để kiểm tra toàn bộ điều kiện chạy.

| **Chỉ số** | **`eval_before.json`** | **`eval_after.json`** |
|---|---:|---:|
| Điểm tổng | 90,64/100 | 96,18/100 |
| Điểm case đã chọn | H2: 50/100 | H2: 100/100 |
| Số model calls | 52 | 52 |
| Token, chi phí nếu có | 83.599 token | 97.554 token |

Số model calls trong bảng là của agent trên toàn bộ 22 case. Tổng token bao gồm agent và judge:

- Trước cải tiến: agent 45.949 token, judge 37.650 token.
- Sau cải tiến: agent 60.759 token (53.621 prompt + 7.138 completion), judge 36.795 token.
- Riêng H2: model calls tăng từ 2 lên 3; số tool calls tăng từ 1 lên 2.

Số lượt gọi model và token được cộng từ result.usage; token chấm điểm lấy từ grade.judge_usage. Một lượt model có thể gọi nhiều tools. File chỉ lưu token, chưa có số tiền API đã tính.

### Kết quả sau cải tiến

H2 tăng 50 điểm. Trace sau cải tiến có cả get_status(provider='github', component='actions') và get_incident_details ở step 1; toàn bộ run dùng 3 model calls. Snapshot cho biết Actions operational, incident t89g2q1800fr resolved; mechanical không còn violation.

Điểm tổng tăng **5,54 điểm**: 7 case tăng, 13 case giữ nguyên, 2 case giảm. E1 tăng 85 → 100, E5 tăng 93 → 94, A5 tăng 90 → 100, H2 tăng 50 → 100, H3 tăng 98 → 100, H4 tăng 80 → 100 và H6 tăng 60 → 100. Model có thể trả lời khác giữa các lần chạy nên mức tăng này chưa chắc chỉ do sửa prompt.

H6 đã đọc tiếp incident liên kết: step 1 gọi get_status và đọc h02n9572mx9y; step 2 đọc xr3myzj7ms51; step 3 trả lời. Có thể dùng trace này để demo điều tra nhiều bước.

### Lỗi còn lại hoặc kết quả giảm

- **H1:** giữ ở 60 điểm. Mechanical ghi thiếu tool calls ở ít nhất hai model steps khác nhau; agent chưa hoàn thành chuỗi điều tra tiếp incident liên kết. Dù H6 đã cải thiện, yêu cầu nhiều bước chưa được giải quyết ổn định trên mọi case.
- **H7:** giữ ở 80 điểm. Câu trả lời mới vẫn kết luận Cloudflare Spectrum operational dù timeout. Đây là kết luận thiếu bằng chứng; cần báo chưa xác minh được khi không có dữ liệu.
- **A6:** giảm 98 → 94. Judge đề nghị làm rõ hơn việc không biến tác động thành nguyên nhân và phần chưa xác nhận khi dữ liệu bị cắt; mechanical không có violation.
- **H8:** giảm 100 → 88. Judge đề nghị nhấn mạnh hơn rằng dữ liệu 50 incident gần nhất không đủ để liệt kê đầy đủ giai đoạn 2020–2026; mechanical không có violation.
- Model calls giữ ở 52 nhưng agent tokens tăng 14.810; tổng token agent và judge tăng 13.955. Số lượt gọi bằng nhau không đồng nghĩa chi phí bằng nhau.

## 5. Giới hạn

- Điểm LLM judge là ước lượng, có thể sai hoặc tự mâu thuẫn. H2 lần đầu có raw judge score 95 nhưng thiếu tool bắt buộc; cần đọc cả mechanical, answer và trace.
- Agent và phần chấm điểm cùng dùng gpt-4.1-mini nên có thể cùng bỏ sót lỗi. Điểm cao chưa có nghĩa mọi kết luận đều đúng.
- Dữ liệu bài chính là snapshot ngày 09/11/2026. Từ “hiện tại” trong câu trả lời lưu phải hiểu theo thời điểm snapshot, không phải thời điểm đọc báo cáo.
- Tools chỉ tìm trong 50 incident gần nhất, trả tối đa 5 incident khớp và rút gọn updates. Không tìm thấy không chứng minh không có sự cố; không đủ dữ liệu khẳng định lịch sử đầy đủ hay nguyên nhân lỗi riêng của người dùng.
- eval_after.json đã được chạy lại và ghi đè. Bảng dùng kết quả mới nhất 96,18, không phải kết quả cũ 94,73. Chưa có bộ kết quả lặp được lưu đầy đủ để đo độ ổn định; thay đổi điểm có thể chịu ảnh hưởng của biến động agent và judge.
- Kiểm tra URL chỉ xác nhận có ít nhất một URL incident đã quan sát, không xác nhận mọi kết luận có nguồn hoặc đã dẫn đủ nguồn từng provider.
- Tests offline kiểm tra contract bằng fake provider, không thay thế đánh giá với model thật. H1 cho thấy tests pass vẫn có thể thiếu bước điều tra.
- Kết quả bonus đủ 10 case được ghi riêng ở mục 6; không cộng trực tiếp điểm eval bài chính với điểm bonus.

## 6. Phần bonus: triển khai và kết quả cuối

### Cấu hình và điểm

Kết quả trong eval_bonus.json là lần chạy đủ 10 case. Cấu hình dùng OpenAI, model gpt-4.1-mini cho cả agent và phần chấm điểm, max_steps = 16, bộ case bonus.

| Chỉ số | Kết quả cuối |
|---|---:|
| Case được chấm | 10/10 |
| Case unscored | 0 |
| Điểm trung bình | 100/100 |
| Điểm bonus tham khảo | 15/15 |
| Model calls của agent | 30 |
| Agent prompt tokens | 80.030 |
| Agent completion tokens | 6.001 |
| Tổng agent tokens | 86.031 |
| Tổng judge tokens | 31.512 |
| Tổng token agent + judge | 117.543 |

B1, B2, B3, B4, B5, B6, B7, B8, B9 và B10 đều đạt **100/100**, status completed và không có mechanical violation. File không ghi chi phí tiền API. Điểm bonus là tham khảo để giảng viên đối chiếu; không cộng trực tiếp 15 vào điểm eval bài chính 96,18 vì rubric bài chính có thang tối đa 85.

### Kết nối tools, retry và pagination

Agent lấy danh sách tools và prompt từ tools.schemas và tools.system_prompt nếu có; nếu không thì dùng bộ mặc định của bài chính. Bonus hỗ trợ GitHub, Cloudflare, Vercel, npm và DigitalOcean. Câu trả lời cần có nguồn và thời gian snapshot riêng từng bên, không tự thêm trạng thái của dịch vụ ngoài danh sách hỗ trợ.

Mỗi yêu cầu được nhận diện bằng tên tool và JSON arguments. Sau ba lần thực thi trả RATE_LIMITED cho cùng yêu cầu, loop chặn thực thi tiếp. Với bonus, tool đã hết lượt còn được gỡ khỏi schemas ở các model steps tiếp theo và có lời nhắc dừng. Các provider khác vẫn khả dụng. Đây là giới hạn retry nội bộ của agent, không phải chính sách rate limit của hãng.

Khi gọi API thật, agent đọc thời gian chờ từ retry_after hoặc retry_after_seconds. Nếu gọi lại quá sớm thì trả RETRY_DEFERRED. Agent có thể báo phần đã kiểm tra được thay vì chờ lâu. Lỗi 429 hoặc timeout chỉ cho biết chưa lấy được dữ liệu, không cho biết dịch vụ đang hoạt động hay gặp sự cố. Với INVALID_ARGUMENTS, model nhận lỗi để sửa tham số và thử lại trong số bước còn lại.

Timeline được chia thành nhiều trang. Agent dùng next_offset để đọc trang tiếp theo, với offset là số nguyên không âm và limit từ 1 đến 3. Nếu chưa đọc hết thì phải nói rõ. Các mục nhiễu vẫn được gửi cho model, nhưng không nên đưa vào câu trả lời. Code chưa có bước tự rút gọn dữ liệu này.

### Lỗi đã phân tích và cải tiến

- **B6:** lần đầu thiếu get_incident_details nên bị giới hạn 50 điểm. Bổ sung validation_incomplete_evidence: với câu hỏi đối chiếu incident, nhắc đọc chi tiết provider còn thiếu trước final. ID được lấy từ observation, không hard-code đáp án hay mã case. Lần cuối đạt 100.
- **B10:** lần đầu dừng sau 429, bị 50 điểm. Theo dõi yêu cầu retriable chưa hết giới hạn/cooldown và nhắc model retry trước final. Sau đó đạt 89 nhưng final chỉ viết phần bổ sung Vercel; tiếp tục yêu cầu viết lại toàn bộ báo cáo, giữ status/source/captured_at từng bên, nêu số lần retry thực tế và không bịa chính sách hãng. Lần cuối đạt 100.
- **B4:** một lần chạy có raw judge score 100 nhưng mechanical giới hạn 50 vì model yêu cầu Vercel lần thứ tư. Dù loop không thực thi API lần đó, trace vẫn ghi tool call và bị tính vượt giới hạn. Sửa bằng cách gỡ tool đã hết lượt khỏi schemas và nhắc dừng sau khi trả đầy đủ observations; không xóa hoặc đổi tên trace để né chấm. Lần cuối đạt 100.

Các lần chạy lại đã ghi đè file kết quả cũ. Điểm cũ nêu trên được ghi lại trong lúc phân tích lỗi; bảng cuối dùng kết quả của một lần chạy đủ 10 case.

### Kiểm tra offline và giới hạn

```powershell
python -m unittest discover -s bonus -p "test_*.py" -v
# 11 tests: OK
python -m unittest discover -s tests -v
# 37 tests: OK
```

Hai lệnh trên chạy tổng cộng 48 tests và đều pass. Các tests kiểm tra cách trả kết quả tool, đọc trang tiếp theo, xử lý lỗi và dừng retry đúng giới hạn. Tests dùng model giả lập nên không cần API key và không phát sinh phí gọi model.

Một số giới hạn còn lại:

- Bonus đạt 100 ở lần chạy cuối, nhưng chưa chắc các lần sau đều đạt như vậy.
- Eval dùng dữ liệu snapshot và lỗi giả lập; chưa kiểm tra đầy đủ với API thật.
- Agent và model chấm điểm đều là gpt-4.1-mini nên điểm chấm có thể thiên lệch.
- Code có kiểm tra việc đọc chi tiết và dẫn URL, nhưng chưa bảo đảm mọi kết luận đều đủ bằng chứng.
- Khi một tool hết lượt retry, agent gỡ cả tool đó trong phần còn lại của run. Vì vậy, các yêu cầu khác dùng cùng tool cũng không được tiếp tục.

