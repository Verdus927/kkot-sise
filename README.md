# 꽃시세 (kkot-sise)

양재 aT 화훼공판장 절화 경매가를 품목·품종·등급별로 보는 시세 페이지입니다.

- 화면: 이 저장소 (GitHub Pages)
- 시세 자료: Google Apps Script 웹 앱이 aT 화훼유통정보시스템 경매 결과를 받아 미리 계산해 둔 값을 JSON으로 제공
- 자료 출처: 한국농수산식품유통공사 화훼유통정보시스템 (flower.at.or.kr), 양재 aT 화훼공판장 경매 결과

## 파일
- `index.html`: 화면
- `js/api.js`: 시세 자료를 받아 오는 부분 (화면 디자인을 바꿔도 그대로 둠)
- `js/config.js`: 시세 자료 주소 (Apps Script 웹 앱 `/exec` 주소)
