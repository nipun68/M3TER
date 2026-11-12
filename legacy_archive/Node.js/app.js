// This is the Old way to exceute the file (require the file from other file)

const math = require("./math");
console.log(math.add(10,20));
console.log(math.multiply(5,4));


// This is the Modern way to exceute the file (import the file from other file)

import { add, multiply } from "./math.js";
console.log(add(10, 20));
console.log(multiply(5, 4));    