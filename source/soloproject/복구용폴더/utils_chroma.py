# utils_chroma.py
from typing import Iterable, List, Dict, Any, Sequence
import os
import time
import random

# Windows에서 토크나이저 병렬 경고 억제 (간혹 멈춤/잡음 유발 방지)
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def chunks(lst: List[Any], size: int) -> Iterable[List[Any]]:
    """
    리스트를 지정한 크기의 소배치로 나눕니다.
    예) list(chunks([1,2,3,4,5], 2)) -> [[1,2], [3,4], [5]]
    """
    if size <= 0:
        raise ValueError("size must be a positive integer")
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def ensure_str_metadata(meta: Dict[str, Any]) -> Dict[str, str]:
    """
    메타데이터의 모든 값을 문자열로 변환합니다.
    - 리스트는 ', ' 로 join
    - None은 빈 문자열로
    - 숫자/불리언 등은 str()로 캐스팅
    """
    safe: Dict[str, str] = {}
    meta = meta or {}
    for k, v in meta.items():
        if v is None:
            safe[k] = ""
        elif isinstance(v, (list, tuple, set)):
            safe[k] = ", ".join(map(str, v))
        else:
            safe[k] = str(v)
    return safe


def backoff_sleep(attempt: int, base: float = 0.3, jitter: float = 0.2, cap: float = 3.0) -> None:
    """
    지수 백오프 + 지터로 대기 시간을 부여합니다.
    - attempt: 0부터 시작 (0,1,2,...)
    - base: 기본 대기(초)
    - jitter: 0~jitter 범위 랜덤 가산
    - cap: 최대 대기 상한
    """
    if attempt < 0:
        attempt = 0
    wait = min(cap, base * (2 ** attempt)) + random.uniform(0, jitter)
    time.sleep(wait)