def safe_index(lst,item,start=0):
    """
    첫번째 매개변수 lst : 리스트, 튜플
    두번쩨 매게변수 item :리스트나 튜플에서 찾을 데이터 
    세번째 매개변수 satrt : 몇 번째 ondex부터 찾을지 index tn(기본값=0) 
    itme 요소가 없으면 -1 반환
    """
    return lst.index(item,start) if item in lst[start:] else -1
#     if item in lst[start:]:
#         return lst.index(item,start) #sater번쨰 부터 item이 있는 index를 반환
#     return -1