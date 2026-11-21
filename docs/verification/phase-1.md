# Ma trận truy vết Phase 1

| AC | Cách kiểm chứng | Bằng chứng (link `docs/proof/phase-1/...`) | Kết quả (đạt / chưa đạt — ghi trung thực) |
|---|---|---|---|
| AC-P1-01 | Đầy đủ trường `game.contract.json`, `team_size` khớp `TEAM.md` | `python tools/check_team.py` trả về mã 0 (`OK: 1 thành viên: DuyAnh953`) | ĐẠT |
| AC-P1-02 | Unit test & smoke test khung chạy xanh | `python -m unittest discover -s tests -v` (`Ran 32 tests ... OK`) | ĐẠT |
| AC-P1-03 | Logic buổi sáng (`gather`): oxy, ngạt, hái nút, bắt cá, giỏ LIFO, cập bến xuất kho | `docs/proof/phase-1/gather.jsonl` và `docs/proof/phase-1/catch.json` | ĐẠT |
| AC-P1-04 | Logic buổi tối (`quan`): nhận kho từ `catch.json`, giữ chỗ, nấu, bưng, phục vụ, tính tiền/boa/uy tín | `docs/proof/phase-1/quan.jsonl` (tick 0 nạp đúng `{"bong_sung":2,"ca_loc":1}`) | ĐẠT |
| AC-P1-05 | Tính tất định (cùng seed cho đầu ra giống nhau từng byte) | Kiểm thử qua `Streams(seed)` tách luồng và bộ test unit | ĐẠT |

## Đánh giá ngắn
- Yêu cầu nào đạt / chưa đạt:
- Điều cần chỉnh cho phase sau:
