"""헬퍼손 AI 면접 코칭 서버 (시범운영 전용). Python 3.10+."""
import os, json, time, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from collections import defaultdict, deque
from pathlib import Path

ROOT=Path(__file__).resolve().parent
history=defaultdict(deque)
lock=threading.Lock()
requests_today=0
day_stamp=""
slots=threading.BoundedSemaphore(int(os.getenv("MAX_CONCURRENT_AI","6")))
MAX_DAILY=int(os.getenv("MAX_DAILY_AI_REQUESTS","500"))

SYSTEM="""당신은 한국 대학생의 면접 전문 코치입니다. 한국어로 답하세요.
학생의 경험·성과·수치를 지어내지 말고 불확실한 부분은 [확인 필요]로 표시하세요.
실제 기업 기출이나 평가기준을 검증 없이 단정하지 마세요. 평가 점수는 교육용 참고값이며 합격 예측이 아닙니다.
음성을 직접 받지 않았으면 발음, 목소리, 표정을 평가하지 마세요. 민감한 개인정보를 요구하지 마세요.
모드별 지침:
diagnose: 질문 적합성20, 논리성20, 행동의 구체성20, 직무 적합성20, 신뢰성10, 표현 명확성10으로 평가, 장점·개선점·추가 질문·개선 답변을 제시.
star: 상황-과제-행동-결과를 차례로 질문 하나씩 묻고 기다림. '최종 정리' 요청에 사실 기반 답변 작성.
mock: 실제 면접처럼 질문 하나씩 묻고 답변에 따라 꼬리질문. '면접 종료' 후 종합 평가.
compare: 이전 답변과 개선 답변의 달라진 근거, 잔여 문제 비교.
questions: 인성2·경험3·직무3·산업1·상황1의 예상 질문 10개를 평가 의도와 함께 제시.
"""

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT),**kwargs)
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def respond(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path=='/api/health':
            return self.respond(200,{'ok':True,'ai_configured':bool(os.getenv('OPENAI_API_KEY')),'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini')})
        return super().do_GET()
    def do_POST(self):
        global requests_today, day_stamp
        if self.path!='/api/coach':
            return self.respond(404,{'error':'경로 없음'})
        origin=self.headers.get('Origin','')
        host=self.headers.get('Host','')
        if origin and origin.rstrip('/') not in ('http://'+host,'https://'+host):
            return self.respond(403,{'error':'다른 사이트에서의 요청을 허용하지 않습니다.'})
        key=os.getenv('OPENAI_API_KEY')
        if not key:
            return self.respond(503,{'error':'서버에 OPENAI_API_KEY를 설정해 주세요.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not (1<=length<=32000):
                return self.respond(413,{'error':'요청 크기 제한 초과'})
            now=time.time()
            with lock:
                today=time.strftime('%Y-%m-%d',time.gmtime(now))
                if today!=day_stamp:
                    day_stamp=today
                    requests_today=0
                if requests_today>=MAX_DAILY:
                    return self.respond(429,{'error':'오늘의 전체 AI 사용 한도에 도달했습니다.'})
                q=history[self.client_address[0]]
                while q and now-q[0]>3600: q.popleft()
                if len(q)>=25:
                    return self.respond(429,{'error':'시간당 요청 한도 초과'})
                q.append(now)
                requests_today+=1
            data=json.loads(self.rfile.read(length))
            mode=str(data.get('mode','diagnose'))
            if mode not in ('diagnose','star','mock','compare','questions'):
                return self.respond(400,{'error':'알 수 없는 모드'})
            message=str(data.get('message','')).strip()
            if not (1<=len(message)<=14000):
                return self.respond(400,{'error':'입력 길이 오류'})
            context=data.get('context',{})
            if not isinstance(context,dict):context={}
            context={k:str(context[k])[:400] for k in ('industry','company','role') if k in context}
            messages=[]
            raw=data.get('history',[])
            if isinstance(raw,list):
                for m in raw[-12:]:
                    if isinstance(m,dict) and m.get('role') in ('user','assistant') and isinstance(m.get('content'),str):
                        messages.append({'role':m['role'],'content':m['content'][:5500]})
            messages.append({'role':'user','content':message})
            payload={'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini'),
                     'instructions':SYSTEM+'\n모드: '+mode+'\n지원 배경: '+json.dumps(context,ensure_ascii=False),
                     'input':messages,'max_output_tokens':1300,'store':False}
            request=urllib.request.Request('https://api.openai.com/v1/responses',
                data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
                method='POST')
            if not slots.acquire(blocking=False):
                return self.respond(429,{'error':'현재 AI 요청이 많습니다. 잠시 후 다시 시도하세요.'})
            try:
                with urllib.request.urlopen(request,timeout=55) as response:
                    output=json.load(response)
            finally:
                slots.release()
            answer=output.get('output_text','')
            if not answer:
                answer='\n'.join(part.get('text','') for item in output.get('output',[])
                    for part in item.get('content',[]) if part.get('type')=='output_text')
            return self.respond(200,{'reply':answer or '빈 응답입니다. 다시 시도하세요.'})
        except urllib.error.HTTPError as e:
            return self.respond(502,{'error':f'AI API 오류: HTTP {e.code}'})
        except (ValueError,TypeError,KeyError):
            return self.respond(400,{'error':'요청 형식이 올바르지 않습니다.'})
        except Exception as e:
            return self.respond(502,{'error':'AI 처리 실패: '+type(e).__name__})

if __name__=='__main__':
    port=int(os.getenv('PORT','8765'))
    print(f'헬퍼손 AI 면접 워크북: http://localhost:{port}')
    ThreadingHTTPServer((os.getenv('HOST','127.0.0.1'),port),Handler).serve_forever()
