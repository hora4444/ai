let num1 = 20;
let num2 = 21;

//let differnce =(num1>num2) ? num1-num2 : num2- num1; // 차잇값 저장할 예정
let differnce = Math.abs(num1-num2); //Math.abs() 절댓값

// msg = (num1> num2) ? ('첫번째 수가 ' + differnce + ' 만큼 더 크다') : 
//                     (num2>num1) ? ('두번째 수가 ' + differnce + ' 만큼 더 크다'):
//                                 ('두 수는 같다');

if(num1>num2){
    var msg = '첫번째 수가 ' + differnce + ' 만큼 더 크다';
}else if(num2>num1){
    var msg = '두번째 수가 ' + differnce + ' 만큼 더 크다';
}else{
    var msg = '두 수는 같다';
}
console.log(msg)

//console.log("두 수의 차이는", differnce)