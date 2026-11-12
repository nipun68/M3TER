const http = require("http") // 'http' is a built-in Node.js module for creating web servers

// createServer() creates a new HTTP server
// req: the request object (incoming HTTP request)
// res: the response object (used to send data back to the client)
const server = http.createServer((req, res) => {
    // Set the response content type to plain text
    res.writeHead(200, { "Content-Type": "text/plain" })
    // res.end() sends the response body to the client and ends the response
    res.end("We are running server on port 8080")
})

// listen() starts the server on the specified port (8080)
// The callback runs once the server is successfully running and listening for requests
server.listen(8080, () => {
    console.log("Running in 8080")
})