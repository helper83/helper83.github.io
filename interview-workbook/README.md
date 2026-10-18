# 헬퍼손 AI 면접 실습 워크북

대학생을 위한 면접 실습 웹앱. 경험 발굴, STAR 답변, 자기소개·지원동기, 직무별 예상 질문, 모의면접, 평가표, JSON 백업·복원 등.

## 이용
- 웹앱(정적 페이지): https://helper83.github.io/interview-workbook/
- 원본 HTML: ./index.html
- GitHub Pages에서 **AI 직접 코칭은 동작하지 않습니다.** `/api/coach`와 `/api/health`를 제공하는 별도 백엔드가 필요합니다.
- AI 서버는 `server.py`를 사용해 실행할 수 있으나 현재 개발·시범운영용입니다. 공개 배포 전 인증, 학생별 사용량 제한, 비용 모니터링, HTTPS, 개인정보 검토가 필요합니다.

## 서버 로컬 실행 (Python 3.10+)
```powershell
$env:OPENAI_API_KEY="발급받은_API_키"
$env:OPENAI_MODEL="gpt-4.1-mini"
python server.py
```
브라우저에서 http://localhost:8765/interview-workbook/ 가 아니라 서버와 `index.html`이 동일 폴더에 있는 구성으로 접속해야 합니다. GitHub 저장소의 `interview-workbook/` 폴더만 따로 받아 해당 폴더에서 `python server.py` 실행 후 http://localhost:8765 으로 엽니다.

## 보안 주의
- API 키는 절대 index.html이나 GitHub에 넣지 않습니다.
- GitHub Pages는 Python 서버를 실행하지 못합니다.
- 학생이 입력한 질문과 답변은 AI 코칭 요청 시 외부 API로 전송됩니다.
- 점수는 교육용 참고이며 실제 채용 합격 확률이 아닙니다.
