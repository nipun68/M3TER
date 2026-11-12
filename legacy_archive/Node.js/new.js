const fs = require("fs");
// fs.readFile("new.txt", "utf-8", (err, data) => {
//     if (err) {
//         console.log(err);
//     }
//     else {
//         console.log(data);
//     }
// });


// Existing the file and write the content in it

// const fs = require("fs");
// fs.writeFile("new.txt", "Miln lyi smpark kro", (err) => {
//     if (err) {
//         console.log(err);
//     }
//     else {
//         console.log("File created successfully");
//     }
// });

// Appending the file(Data is added in the existing file)

// fs.appendFile("new.txt", "\nHello World", (err) => {
//     if (err) {
//         console.log(err);
//     }
//     else {
//         console.log("File appended successfully");
//     }
// });


// Delete the file(If file is not found then error is shown)

// fs.unlink("new.txt", (err) => {
//     if (err) {
//         console.log("File not found");
//     }
//     else {
//         console.log("File deleted successfully");
//     }
// });


// How to create the folder (Synch)

// fs.mkdirSync("new_folder", (err) => {
//     if (err) {
//         console.log(err);
//     }
//     else {
//         console.log("Folder created successfully");
//     }
// });

// how to read the folder

fs.readdir(".", (err, files) => {
    if (err) {
        console.log(err);
    }
    else {
        console.log(files);
    }
});