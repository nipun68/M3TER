// BCRYPT PASSWORD HASHING EXAMPLE - INTERVIEW FOCUSED
// This file demonstrates a basic authentication flow using bcrypt for password hashing.
// NOTE: This is a simplified example for learning. Production systems require additional
// considerations like databases, input validation, error handling, and security best practices.

// Import the Express framework - essential for creating HTTP servers and defining API routes.
const express = require("express");
// Create an Express application instance. This 'app' object is used to:
//   - Define routes (HTTP endpoints)
//   - Attach middleware
//   - Start the server
const app = express();

// Import the bcrypt library - a popular npm package for secure password hashing.
// Why bcrypt? It's designed to be slow (configurable work factor) to resist brute-force attacks.
// It automatically handles salt generation and storage (the salt is included in the hash).
const bcrypt = require("bcrypt");

// MIDDLEWARE: Parse incoming JSON request bodies.
// Without this, req.body would be undefined for POST/PUT requests with Content-Type: application/json.
// This is essential for APIs that consume JSON data (like our registration/login endpoints).
app.use(express.json());

// HOME PAGE ROUTE
// Handles GET requests to the root URL ("/").
// Sends a simple welcome message as plain text.
app.get("/", (req, res) => {
    res.send("Welcome to homepage");
});

// IN-MEMORY USER STORAGE (DEMONSTRATION ONLY)
// WARNING: This is NOT suitable for production! 
//   - Data is lost when the server restarts (not persistent)
//   - Only stores ONE user (overwrites previous registrations)
//   - Not scalable or thread-safe in multi-instance environments
// In a real application, you would use a database (e.g., PostgreSQL, MongoDB) to store user records.
let user = {};

// USER REGISTRATION ENDPOINT
// Handles POST requests to "/register".
// Expects JSON body: { "email": "string", "password": "string" }
// Uses async/await because bcrypt.hash() returns a Promise (it's I/O bound - computationally intensive).
app.post("/register", async (req, res) => {
    try {
        // DESTRUCTURING ASSIGNMENT
        // Extracts email and password properties from req.body into separate variables.
        // Equivalent to: const email = req.body.email; const password = req.body.password;
        const { email, password } = req.body;

        // BASIC INPUT VALIDATION
        // In production, you'd want more robust validation (email format, password strength, etc.)
        if (!email || !password) {
            return res.status(400).json({ error: "Email and password are required" });
        }

        // PASSWORD HASHING WITH BCRYPT
        // bcrypt.hash(password, saltRounds) -> Returns a Promise that resolves to the hashed password.
        // The salt is automatically generated and included in the resulting hash.
        // Cost factor (10): 2^10 = 1024 iterations. Higher = more secure but slower.
        // Typical production values: 10-12 (adjust based on hardware and performance requirements).
        const hashedPassword = await bcrypt.hash(password, 10);

        // STORE USER DATA (IN-MEMORY ONLY FOR DEMO)
        // In a real app, you would insert a record into your users table:
        //   INSERT INTO users (email, password_hash) VALUES (email, hashedPassword)
        user = {
            useremail: email,        // Note: Consider renaming to 'email' for consistency
            userpassword: hashedPassword // NEVER store plain-text passwords!
        };

        // SUCCESS RESPONSE
        // We return the stored user data (hashed password included for demo purposes).
        // In production, you would typically NOT return the hashed password.
        res.status(201).json({ 
            message: "User registered successfully", 
            user: { email: user.useremail } // Only return non-sensitive data
        });
        
        // SERVER-SIDE LOGGING (BE CAREFUL IN PRODUCTION)
        // Avoid logging sensitive information like passwords or hashes.
        console.log(`New user registered: ${email}`);
    } catch (error) {
        // CENTRALIZED ERROR HANDLING
        // Catches any asynchronous errors (e.g., bcrypt.hash failure) or synchronous thrown errors.
        console.error("Registration error:", error);
        // Generic error message to avoid leaking implementation details to the client.
        res.status(500).json({ error: "Internal server error" });
    }
});

// USER LOGIN ENDPOINT
// Handles POST requests to "/login".
// Expects JSON body: { "email": "string", "password": "string" }
// Uses async/await because bcrypt.compare() returns a Promise.
app.post("/login", async (req, res) => {
    try {
        const { email, password } = req.body;

        // BASIC INPUT VALIDATION
        if (!email || !password) {
            return res.status(400).json({ error: "Email and password are required" });
        }

        // CHECK IF ANY USER IS REGISTERED (EDGE CASE HANDLING)
        // Since we're using in-memory storage for a single user, we check if we have data.
        // In a real app with a database, you would query for the user by email.
        if (!user.useremail) {
            return res.status(401).json({ error: "Invalid credentials" });
        }

        // EMAIL VERIFICATION
        // Note: In a real system, you would retrieve the user record by email from the database.
        // Here we compare directly with our in-memory user object.
        if (email !== user.useremail) {
            // Using the same generic message for both email and password failures
            // prevents user enumeration attacks (attackers can't tell if an email exists).
            return res.status(401).json({ error: "Invalid credentials" });
        }

        // PASSWORD VERIFICATION
        // bcrypt.compare(plainTextPassword, hashedPassword) -> Returns a Promise resolving to boolean.
        // It safely handles the comparison including the salt extraction from the hash.
        const passwordMatches = await bcrypt.compare(password, user.userpassword);

        if (!passwordMatches) {
            // Again, use generic message to prevent user enumeration.
            return res.status(401).json({ error: "Invalid credentials" });
        }

        // SUCCESSFUL LOGIN
        // In a real app, you would generate a session token (JWT) or set a cookie here.
        res.status(200).json({ 
            message: "User logged in successfully",
            user: { email: user.useremail } // Return non-sensitive user data
        });
        console.log(`User logged in: ${email}`);
    } catch (error) {
        console.error("Login error:", error);
        res.status(500).json({ error: "Internal server error" });
    }
});

// SERVER STARTUP
// Binds the Express app to a port and starts listening for incoming connections.
// The callback function executes once the server is successfully bound.
app.listen(1000, () => {
    console.log("Server is running at http://localhost:1000/");
    // In production, you might want to log additional startup details (environment, etc.)
});