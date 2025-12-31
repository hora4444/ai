from database.connection import conn
from models import Todo
from typing import List # 타입 체크용
# get_todos의 매개변수는 문자로 order를 전달받아 return dict list를 반환 
def get_todos(order: str='asc') -> List[dict]:
    cursor = conn.cursor()
    if order == 'asc':
        sql = "SELECT * FROM TODO ORDER BY ID"
    else:
        sql = "SELECT * FROM TODO ORDER BY ID DESC"
    cursor.execute(sql)
    result = cursor.fetchall()
    # ["id", "content", "is_done"]
    keys = [desc[0].lower() for desc in cursor.description]
    todos = [dict(zip(keys, row)) for row in result]
    cursor.close()
    return todos

def get_next_id() -> int:
    cursor = conn.cursor()
    sql = "SELECT NVL(MAX(ID),0)+1 FROM TODO"
    cursor.execute(sql)
    result = cursor.fetchone() # 반환값은 (4,) 형태의 tuple
    cursor.close()
    return result[0]

def get_todo(id: int) -> Todo:
    cursor = conn.cursor()
    sql = "SELECT * FROM TODO WHERE ID = :id"
    cursor.execute(sql, {'id': id})
    result = cursor.fetchone() # 반환값은 tuple
    keys = [desc[0].lower() for desc in cursor.description] # ['id', 'content', 'is_done']
    todo = dict(zip(keys, result))
    cursor.close()
    return todo

def create_todo(todo: Todo) -> int:
    corsor = conn.cursor()
    sql = "INSERT INTO TODO (ID, CONTENT) VALUES (TODO_SQ.NEXTVAL, :content)"
    corsor.execute(sql, {'content': todo.content})
    rows= corsor.rowcount # insert된 row 수
    corsor.close()
    return rows # insert 성공시 1 반환

def update_todo(todo: Todo) -> int:
    corsor = conn.cursor()
    sql = "UPDATE TODO SET CONTENT = :content, IS_DONE = :is_done WHERE ID = :id"
    corsor.execute(sql, todo.model_dump())
    conn.commit()
    rows= corsor.rowcount # update된 row 수
    corsor.close()
    if rows:
        return f'{todo.id}번 {todo.content} 수정 성공'
    return f'{todo.id}번 {todo.content} 수정 실패'

def delete_todo(id: int) -> dict:
    corsor = conn.cursor()
    sql = "DELETE FROM TODO WHERE ID = :id"
    corsor.execute(sql, {'id': id})
    conn.commit()
    rows= corsor.rowcount # delete된 row 수
    corsor.close()
    if rows:
        return f'{id}번 항목 삭제 성공'
    return f'{id}번 항목 삭제 실패'

if __name__ == "__main__":
    print('전체목록',get_todos())

# 실행방법 python -m database.repository
