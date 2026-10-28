# Crypto & Macro Data Collection Pipeline (ProfinK)

Pipeline Python thu thập, làm giàu và chuẩn hóa dữ liệu đa khung thời gian cho Crypto, kết hợp dữ liệu kinh tế vĩ mô và 12 chỉ báo kỹ thuật theo đúng đặc tả tại [DataInfo.txt](docs/DataInfo.txt).

---

## 📌 Đặc tả kỹ thuật (Specification)

- **Binance API**: `https://data-api.binance.vision/api/v3/` (hỗ trợ tự động fallback sang `https://api.binance.com/api/v3/`)
- **Symbols**: `BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LINKUSDT` (tự động mapping từ alias `BTCUSTD...`)
- **Timeframes**: `1m, 15m, 1h, 4h`
- **Time Duration**: Mặc định 1 năm (365 ngày từ thời điểm hiện tại về trước)
- **Time zone**: UTC, timestamp dạng millisecond (int64)
- **Thư mục đầu ra**: Lưu tự động vào `data/1m/`, `data/15m/`, `data/1h/`, `data/4h/` với cả 2 định dạng:
  - `.csv`: Format tiêu chuẩn
  - `.parquet`: Tối ưu dung lượng và tốc độ nạp dữ liệu cho phân tích định lượng / huấn luyện mô hình.

---

## 📊 Cấu trúc 35 trường dữ liệu chuẩn (Canonical Schema)

| STT | Trường dữ liệu | Kiểu dữ liệu | Nguồn / Công thức tính |
|:---:|:---|:---:|:---|
| **0** | `Symbol` | string | Mã cặp giao dịch (vd: `BTCUSDT`) |
| **1** | `Open Time` | int64 | Timestamp mở nến (milisecond UTC) |
| **2** | `Average Price` | float64 | Giá bình quân: VWAP = `Quote asset volume / Volume` (hoặc `(O+H+L+C)/4`) |
| **3** | `Open` | float64 | Giá mở cửa nến |
| **4** | `High` | float64 | Giá cao nhất nến |
| **5** | `Low` | float64 | Giá thấp nhất nến |
| **6** | `Close` | float64 | Giá đóng cửa nến |
| **7** | `Volume` | float64 | Khối lượng base asset giao dịch |
| **8** | `Close Time` | int64 | Timestamp đóng nến (milisecond UTC) |
| **9** | `Quote asset volume` | float64 | Khối lượng quote asset giao dịch (USDT) |
| **10** | `Number of trades` | int64 | Số lượng giao dịch khớp lệnh trong nến |
| **11** | `Taker buy base asset volume` | float64 | Khối lượng lệnh mua chủ động (base asset) |
| **12** | `Taker buy quote asset volume` | float64 | Khối lượng lệnh mua chủ động (quote asset) |
| **13** | `Taker sell base asset volume` | float64 | `Volume - Taker buy base asset volume` |
| **14** | `Taker sell quote asset volume` | float64 | `Quote asset volume - Taker buy quote asset volume` |
| **15** | `FED` | float64 | Lãi suất điều hành FED (Treasury yield ngắn hạn / Fed Funds Rate) |
| **16** | `Global M2` | float64 | Cung tiền M2 toàn cầu / US M2 |
| **17** | `DXY` | float64 | Chỉ số Dollar Index (Yahoo: `DX-Y.NYB`) |
| **18** | `CPI` | float64 | Chỉ số giá tiêu dùng CPI / TIPS kỳ vọng lạm phát |
| **19** | `PCE` | float64 | Chỉ số chi tiêu tiêu dùng cá nhân |
| **20** | `NFP` | float64 | Bảng lương phi nông nghiệp Mỹ |
| **21** | `VIX` | float64 | Chỉ số đo lường mức độ biến động S&P 500 (Yahoo: `^VIX`) |
| **22** | `S&P 500` | float64 | Chỉ số chứng khoán Mỹ S&P 500 (Yahoo: `^GSPC`) |
| **23** | `SMA` | float64 | Simple Moving Average (Chu kỳ 20) |
| **24** | `EMA` | float64 | Exponential Moving Average (Chu kỳ 20) |
| **25** | `RSI` | float64 | Relative Strength Index (Chu kỳ 14) với Wilder's Smoothing |
| **26** | `MACD` | float64 | Đường MACD (12, 26) |
| **27** | `Signal` | float64 | Đường tín hiệu Signal (EMA 9 của MACD) |
| **28** | `Hist` | float64 | MACD Histogram = `MACD - Signal` |
| **29** | `Bollinger Bands` | float64 | Vị trí giá %B: `(Close - Lower) / (Upper - Lower)` |
| **30** | `Slope` | float64 | Độ dốc hồi quy tuyến tính của giá Close qua 5 nến |
| **31** | `isHammer` | bool | Nhận diện mô hình nến Búa (`True` / `False`) |
| **32** | `isBullEngulf` | bool | Nhận diện mô hình nến Nhấn chìm tăng (`True` / `False`) |
| **33** | `Sup` | float64 | Mức giá hỗ trợ / đáy cục bộ gần nhất (Local Support) |
| **34** | `Rep` | float64 | Mức giá kháng cự / đỉnh cục bộ gần nhất (Local Resistance) |

---

## 🚀 Hướng dẫn cài đặt và sử dụng

### 1. Cài đặt môi trường
Các thư viện cần thiết đã có sẵn trong Python environment hoặc có thể cài đặt bằng lệnh:
```bash
pip install -r requirements.txt
```

### 2. Kiểm tra nhanh (Smoke Test)
Chạy thử nghiệm nhanh tải dữ liệu BTC khung 1h trong 7 ngày:
```bash
python main.py --test
```

### 3. Thu thập dữ liệu toàn diện (Full Run)
Thu thập toàn bộ 6 đồng coin (`BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LINKUSDT`), đầy đủ 4 khung thời gian (`1m, 15m, 1h, 4h`) trong vòng 1 năm:
```bash
python main.py --days 365
```

### 4. Thu thập theo tùy chọn linh hoạt
- **Chỉ tải các khung lớn (15m, 1h, 4h)**:
  ```bash
  python main.py --timeframes 15m,1h,4h --days 365
  ```
- **Chỉ tải một số đồng coin cụ thể (vd: BTC và ETH)**:
  ```bash
  python main.py --symbols BTCUSDT,ETHUSDT --timeframes 1h,4h --days 365
  ```
- **Chỉ xuất file Parquet (bỏ qua CSV để tiết kiệm dung lượng ổ đĩa)**:
  ```bash
  python main.py --symbols BTCUSDT --timeframes 1m --no-csv
  ```

---

## 🏗️ Cấu trúc thư mục mã nguồn

```
ProKit/
├── docs/
│   ├── DataInfo.txt                 # Đặc tả gốc của yêu cầu
│   └── CoinList.txt                 # Danh mục tiền điện tử phân loại
├── src/
│   ├── __init__.py
│   ├── config.py                    # Cấu hình symbols, endpoints, timeframe, 35 cột
│   ├── binance_fetcher.py           # Fetch klines phân trang 1000 nến, retry, volume balance
│   ├── macro_fetcher.py             # Fetch Yahoo Finance & FRED, cache & backward merge_asof
│   ├── indicators.py                # Tính toán 12 chỉ báo kỹ thuật, nến & Support/Resistance
│   └── pipeline.py                  # Điều phối toàn bộ luồng thu thập & lưu trữ
├── data/
│   ├── 1m/                          # Chứa {SYMBOL}_1m.csv / .parquet
│   ├── 15m/                         # Chứa {SYMBOL}_15m.csv / .parquet
│   ├── 1h/                          # Chứa {SYMBOL}_1h.csv / .parquet
│   ├── 4h/                          # Chứa {SYMBOL}_4h.csv / .parquet
│   └── macro_indicators_cache.parquet
├── main.py                          # CLI runner chính
├── requirements.txt                 # Danh sách gói phụ thuộc
└── README.md                        # Tài liệu hướng dẫn sử dụng
```
