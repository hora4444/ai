class Student{
    constructor(name,kor,mat,eng,sci){
        this.name=name;
        this.kor =kor;
        this.mat =mat;
        this.eng = eng;
        this.sci = sci;
    }
    getSum(){
        return this.kor + this.mat + this.eng + this.sci;
    }
    getAvg(){
        return this.getSum()/4
    }
    toString(){
        return 'name :' + this.name +
                'kor :' + this.kor +
                'mat :' + this.mat +
                'eng :' + this.eng +
                'sci :' + this.sci +
                'sum :' + this.getSum() + //함수 호출 시 괄호는 꼭 넣자
                'avg :' + this.getAvg() ;
    }
}
let hong = new Student('홍길동',99,90,94,98);
console.log(`hong = ${hong}`);
console.log(hong);