function addUser(){
    let user_name = document.getElementById("username").value;
    let email = document.getElementById("email").value;
    let age = document.getElementById("age").value;
    if(user_name.trim() && email.trim() && age) {
        let table = document.getElementsByClassName("form-box")[0];
        let tbody = table.querySelector("tbody") || table;
        tbody.innerHTML += 
        `<tr>
        <td>${user_name}</td>
        <td>${email}</td>
        <td>${age}</td>
        <td><button onclick="deleteUser(this)">Delete</button></td>
        </tr>`;
    }
    document.getElementById("username").value = "";
    document.getElementById("email").value = "";
    document.getElementById("age").value = "";
}

function deleteUser(btn) {
   btn.closest("tr").remove();
}