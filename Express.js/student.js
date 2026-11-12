// ============================================================
// STUDENT API — Express REST Endpoint
// This file demonstrates how to build a simple REST API in Express
// that reads data from a JSON file and returns it to clients.
// ============================================================

// Import the Express framework — the core library for building web servers in Node.js.
const e = require("express");

// Import the fs (file system) module — built-in Node.js module to read/write files.
const fs = require("fs");

// Create an Express application instance.
// This object provides methods for defining routes, middleware, and starting the server.
const app = e();

// Middleware: app.use(e.json())
// This enables Express to parse incoming JSON request bodies.
// Without it, req.body would be undefined for POST/PUT requests.
// It's essential for APIs that accept JSON data from clients.
app.use(e.json());

// ------------------------------------------------------------
// ROUTE 1: Home page
// Handles GET requests to the root URL ("/").
// Sends a plain text welcome message.
// ------------------------------------------------------------
app.get("/",(req,res)=>{
    // res.send() sends an HTTP response with the given content.
    // By default, Express sets Content-Type to "text/html".
    res.send("welcome to Express Application");
});

// ------------------------------------------------------------
// ROUTE 2: Students endpoint
// Handles GET requests to "/students".
// Reads student data from the local JSON file and returns it.
// This is a basic pattern for serving static data from files.
// ------------------------------------------------------------
app.get('/students',(req,res)=>{
    // Read the student.json file synchronously.
    // 'utf-8' encoding ensures we get a string, not a Buffer.
    // Note: readFileSync is blocking — it stops execution until the file is read.
    // For large files or high-traffic apps, consider using async methods like fs.promises.readFile().
    const data = fs.readFileSync('student.json','utf-8');

    // Parse the JSON string into a JavaScript object/array.
    // JSON.parse() converts text into a usable JS data structure.
    const students = JSON.parse(data);

    // Send the parsed data as the response.
    // Express automatically converts objects/arrays to JSON and sets
    // Content-Type to "application/json".
    res.send(students);
});

app.get('/students/:id',(req,res)=>{
    const data = fs.readFileSync('student.json','utf-8');

    const students = JSON.parse(data);

    const id = Number(req.params.id);


    const student = students.find((s)=> s.id === id);

    if(!student){
        return res.send("Students Not Found");

    }
    res.send(student);
});


// ------------------------------------------------------------
// ROUTE 3: Add a new student (POST)
// Handles POST requests to "/students".
// This is a write operation — it accepts new student data in the
// request body, appends it to the existing list, and saves it
// back to the JSON file.
// ------------------------------------------------------------
app.post('/students',(req,res)=>{
    // Read the current student data from the JSON file.
    const data = fs.readFileSync('student.json','utf-8');
    // Parse the JSON string into a mutable JavaScript array.
    const students = JSON.parse(data);

    // Create a new student object using the spread operator.
    // id: students.length + 1 — generates a simple auto-increment ID
    // based on the current array length (works for small datasets;
    // for production, use a database or UUID).
    // ...req.body — copies all properties sent in the request body
    // (e.g., name, email, course) into the new student object.
    const newStudent = {
        id: students.length + 1,
        ...req.body
    };

    // Add the new student to the array.
    students.push(newStudent);

    // Write the updated array back to the JSON file.
    // JSON.stringify() converts the JS object back to a JSON string.
    // The file is overwritten with the new data.
    fs.writeFileSync('student.json', JSON.stringify(students, null, 2));

    // Send a success response with the newly created student.
    // Status 201 is the REST convention for "Created".
    res.status(201).json(newStudent);
});

// ------------------------------------------------------------
// ROUTE 4: Update a student by ID (PUT)
// Handles PUT requests to "/students/:id".
// Replaces the entire student resource with the provided data.
// In REST, PUT is idempotent — multiple identical requests have the same effect.
// Note: This implementation merges fields (PATCH behavior).
// For true PUT, validate that all required fields are present.
// ------------------------------------------------------------
app.put('/students/:id', (req, res) => {
    // Read and parse the current student data from the JSON file.
    const data = fs.readFileSync('student.json', 'utf-8');
    const students = JSON.parse(data);

    // Extract and coerce the ID from route parameters.
    // req.params.id is a string — convert to Number for strict comparison.
    const id = Number(req.params.id);

    // Find the index of the student with the matching ID.
    // findIndex returns the position (index) or -1 if not found.
    // Using index allows direct array mutation.
    const index = students.findIndex((x) => x.id === id);

    // If not found, return 404 with JSON error (REST best practice).
    if (index === -1) {
        return res.status(404).json({ error: 'Student Not Found' });
    }

    // Merge existing student with updates from request body.
    // Spread operator (...) copies all properties.
    // This is PARTIAL UPDATE (PATCH semantics).
    // For true PUT, you would replace entirely: students[index] = { id, ...req.body }
    // and validate required fields are present.
    students[index] = {
        ...students[index],
        ...req.body,
        id // ensure ID cannot be changed via body
    };

    // Write the updated array back to the JSON file.
    // JSON.stringify with (null, 2) pretty-prints the output.
    // 'utf-8' encoding ensures consistent text writing.
    fs.writeFileSync('student.json', JSON.stringify(students, null, 2), 'utf-8');

    // Return the updated student with 200 OK.
    // REST convention: return the modified resource after PUT/PATCH.
    res.status(200).json(students[index]);
});
// ------------------------------------------------------------
// START THE SERVER
// Begin listening for incoming HTTP requests on port 3000.
// The callback function runs once the server is successfully started.
// ------------------------------------------------------------
app.listen(3000,()=>{
    console.log("Server is running on http://localhost:3000/");
});

