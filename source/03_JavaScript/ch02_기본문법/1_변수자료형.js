// 자료형 : string, number, boolean, function, object(array), undifined
var variable;
console.log('1. variable의 타입', typeof(variable), ' - 값 :',variable );
variable ="이름은 '홍길동' 입니다.";
console.log('2. variable의 타입', typeof(variable), ' - 값 :',variable );
variable=-313131313131313313.123;
console.log('3. variable의 타입', typeof(variable), ' - 값 :',variable );
variable=false;
console.log('4. variable의 타입', typeof(variable), ' - 값 :',variable );
variable = function(){
    alert('함수 속');
};
console.log('5. variable의 타입', typeof(variable), ' - 값 :',variable );
variable={'name':"홍길동", 'age':20}; //객체
console.log('6. variable의 타입', typeof(variable), ' - 값 :',variable.name, variable.age );
variable=['홍길동',10,function(){},true,{'name':'홍길동'},[1,2,3]];//배열
        //{0:'홍길동', 1:10, 2:}
console.log('7. variable의 타입', typeof(variable), ' - 값 :',variable );