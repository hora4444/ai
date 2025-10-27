// 2.js : 동적인 부분(파일->다른이름으로저장->utf-8선택 후 저장)

name = prompt("이름은?", "홍길동") // 취소를 클릭시 'null' 리턴
if (name != 'null') {
    document.write(name + '님 반갑습니다<br>');
}