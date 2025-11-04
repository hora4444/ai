function sumAll(){
    let result = 0;
    if(arguments.length>=1){
        for(let idx=0; idx<arguments.length;idx++){
            result += arguments[idx];
        }
    }else{
        result += -999;
    }
    return result;
}