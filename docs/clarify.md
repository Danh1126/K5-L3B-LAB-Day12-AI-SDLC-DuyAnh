# Clarify — câu hỏi và câu trả lời (PO ghi, cả nhóm dùng chung)

| # | Ngày giờ | Câu hỏi | Trả lời / giả định | Ai quyết |
|---|---|---|---|---|
| 1 | 21/11/2026 11:15 | Thực hiện bài lab theo hình thức cá nhân nhưng `tools/check_team.py` và `.github/ruleset-main.json` yêu cầu 4–6 người và 1 người khác approve PR. | Giả định cấu hình cho phép 1 thành viên: đặt `team_size: 1` trong `game.contract.json`, sửa `check_team.py` chấp nhận 1 hoặc 4–6 thành viên (giữ nguyên chuỗi lỗi chuẩn để pass `test_team_check.py`) và không bật rule bắt buộc người khác approve PR. | Duy Anh|