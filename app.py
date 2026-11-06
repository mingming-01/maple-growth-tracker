"""WSGI 호환 진입점과 로컬 개발 서버 실행 파일."""
import sys

from tracker.application import create_app
from tracker import runtime

runtime.app = create_app()

if __name__ == "__main__":
    runtime.app.run(debug=True, host="0.0.0.0", port=5000)
else:
    # 이전 테스트와 운영 스크립트가 사용하던 app 모듈 속성 접근을 유지한다.
    sys.modules[__name__] = runtime
