console.log(pow(5,3));
console.log(pow(5));
console.log(pow())

function pow(x=1,y=2){
    let result = 1
    for(let cnt=1; cnt<=y; cnt++){
        result *=x; 
    }
    return result;
}