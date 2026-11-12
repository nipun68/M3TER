const http = require("http"); // Import Node.js built-in 'http' module to create a web server

// createServer() creates a new HTTP server
// Each incoming request triggers the callback function
// req: request object — contains request data (URL, method, headers, etc.)
// res: response object — used to send data back to the client
const server = http.createServer((req, res) => {
    // Route handling: check the requested URL path (req.url)
    if (req.url == "/") {
        // If the URL path is "/" (root), return the homepage content
        res.end("welcome to homepage");
    } else if (req.url == "/about") {
        // If the URL path is "/about", return the about page content
        res.end("Welecome to about");
    } else if (req.url == "/cart") {
        // If the URL path is "/cart", return the cart page content
        res.end("Welecome to cart");
    }
    // If none of the paths match, the response is implicitly left empty (no res.end() is called)
});

// listen() starts the server on port 8081
// The callback runs once the server is up and ready to accept requests
server.listen(8081, () => {
    console.log("Running in 8081");
});