let funVar = function(){
    console.log('1. 일반 함수(함수표현식 문법 format)');
    console.log('명령어 여러줄')
};
funVar();
// 명령어 블록에 명령어가 1줄/여러줄 있을 때/return 한줄은 return 생략
// 매개변수 1개/ 그외
funVar = () => {
    console.log('2. 매개변수가 없는 2줄짜리 화살표 함수');
    console.log('명령어 여러줄')
};
funVar();
funVar = a => { //매개변수가 1개일 때만 괄호를 생략하고 쓰는 편
    console.log('3. 매개변수가 한개인 2줄짜리 화살표 함수');
    console.log('a = '+a)
};
funVar(10);

funVar = a => console.log('4. 매개변수가 한개인 1줄짜리 화살표 함수 a=',a);
funVar(20);

funVar=function(a){
    return a*a;
}
funVar=a => a*a;
console.log('5. 매개변수 1개, return문 1줄이 있는 화살표 함수 고출 결과 :',funVar(5));

funVar=function(a,b){
    return a*10 + b;
}

funVar=(a,b) => a*10 + b;
console.log('6. 매개변수 2개, return문 1줄이 있는 화살표 함수 고출 결과 :',funVar(5,4));