// ============================================================
// EXPRESS.JS - BASIC WEB SERVER
// This file sets up a simple HTTP server using the Express framework.
// Express is a minimal and flexible Node.js web application framework
// that provides a robust set of features for web and mobile apps.
// ============================================================

// Import the Express module from the node_modules folder.
// "express" is an npm package — a third-party library that simplifies
// building web servers in Node.js.
const e = require("express");

// Create an Express application instance.
// Calling express() returns an app object that has methods to define
// routes, middleware, and start the server.
const app = e();

// ------------------------------------------------------------
// ROUTES — A route defines how the server responds to a client request
// at a specific URL path (endpoint) and HTTP method (GET, POST, etc.).
// app.get() handles HTTP GET requests to the given path.
// ------------------------------------------------------------

// Route 1: Root endpoint ("/")
// When a user visits the homepage (http://localhost:4000/),
// the server sends back "Welcome to Express" as the response body.
// req  = request object (contains info about the incoming HTTP request)
// res  = response object (used to send data back to the client)
app.get("/",(req,res)=>{
    // res.send() sends the HTTP response (text, JSON, file, etc.)
    res.send("Welcome to Express");
});

// Route 2: About page endpoint ("/about")
// When a user visits http://localhost:4000/about,
// the server sends back "About Page".
app.get("/about",(req,res)=>{
    res.send("About Page");
});

// Route 3: Users page endpoint ("/users")
// When a user visits http://localhost:4000/users,
// the server sends back "User Page".
app.get("/users",(req,res)=>{
    res.send("User Page");
});

// ------------------------------------------------------------
// STARTING THE SERVER
// app.listen() starts the HTTP server and makes it listen for
// incoming requests on a specific port.
// A port is a network endpoint — think of it as a door on the
// computer where web traffic enters. Port 4000 is commonly used
// for development servers.
// The callback function runs once the server starts successfully.
// ------------------------------------------------------------
app.listen(4000,()=>{
    // This message appears in the terminal to confirm the server is live.
    console.log("Server is running on http://localhost:4000/");
});