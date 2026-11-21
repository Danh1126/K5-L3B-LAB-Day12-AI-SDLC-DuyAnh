# Nhật ký dùng AI (theo phase và theo người)

| Phase | Người | Công cụ / model | Việc | Token / chi phí ước tính | Ghi chú (AI sai ở đâu?) |
|---|---|---|---|---|---|
| Phase 1 | DuyAnh | Gemini | Thiết lập CI (`TEAM.md`, `check_team.py`), sinh logic mô phỏng tất định `gather.py` và `quan.py`, tạo kịch bản smoke test và tài liệu kiểm chứng | ~15k tokens (miễn phí) | Lần đầu sửa `check_team.py` về `1..6` làm fail unit test `test_too_few_members` (vì test check chuỗi `"4 đến 6"` với 3 người); lệnh PowerShell `Out-File -Encoding utf8` tạo BOM làm Python báo lỗi JSON, đã sửa bằng `UTF8Encoding($false)` |