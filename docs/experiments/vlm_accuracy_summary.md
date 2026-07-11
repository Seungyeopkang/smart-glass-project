# VLM extraction accuracy (corrected aliases)

> Portfolio lightweight experiment over cached gemma4:31b-cloud outputs.
> Recall = filename-derived label object present in VLM detectedObjects/objects.
> Alias "키" removed (it partial-matched "키보드" and inflated key recall).

## Overall

| Metric | Value |
|---|---:|
| Samples | 10 |
| Correct (recall) | 4 |
| Recall | 40.0% |
| Avg latency | 27.112 sec |

## By label

| Label | Samples | Correct | Recall |
|---|---:|---:|---:|
| key | 5 | 0 | 0.0% |
| wallet | 5 | 4 | 80.0% |

## Per-image

| Image | Label | Detected (first 4) | Matched | OK | Latency(s) |
|---|---|---|---|---|---:|
| key_1 | key | 식물, 고양이, 식물, 고양이 | — | ✗ | 19.1948 |
| key_10 | key | 모니터, 키보드, 스피커, 모니터 받침대 | — | ✗ | 30.6648 |
| key_11 | key | 모니터, 수납장, 이불, 모니터 | — | ✗ | 16.5761 |
| key_12 | key | 서랍장, 침대 시트, 수납장, 서랍장 | — | ✗ | 27.7657 |
| key_13 | key | 디자인 의자, 바구니, 비닐봉지, 디자인 의자 | — | ✗ | 17.1401 |
| wallet_1 | wallet | 모서리 보호대, 자전거, 선풍기, 모서리 보호대 | — | ✗ | 24.1984 |
| wallet_10 | wallet | 지갑, 검은색 가죽 지갑 | 지갑 | ✓ | 23.002 |
| wallet_11 | wallet | 검은색 지갑, 전선, 검은색 지갑, 전선 | 지갑 | ✓ | 33.9095 |
| wallet_12 | wallet | 지갑, 전선, 남색 지갑, 검은색 전선 | 지갑 | ✓ | 23.5483 |
| wallet_13 | wallet | 파란색 지갑, 신발, 자전거 바퀴, 선풍기 | 지갑 | ✓ | 55.1169 |
