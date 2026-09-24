const AUTH_URL = "http://localhost:8003";
const POLL_URL = "http://localhost:8001"; 
const VOTE_URL = "http://localhost:8002";

function getToken() {
    return localStorage.getItem("token");
}

function getUsername() {
    return localStorage.getItem("username");
}

function setSession(token, username) {
    localStorage.setItem("token", token);
    localStorage.setItem("username", username);
    updateAuthUI();
}

function clearSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    updateAuthUI();
}

function updateAuthUI() {
    const token = getToken();
    const username = getUsername();
    const loggedOutSection = document.getElementById("auth-logged-out");
    const loggedInSection = document.getElementById("auth-logged-in");
    const loggedUsername = document.getElementById("logged-username");

    if (token && username) {
        loggedOutSection.style.display = "none";
        loggedInSection.style.display = "block";
        loggedUsername.textContent = username;
    } else {
        loggedOutSection.style.display = "block";
        loggedInSection.style.display = "none";
        loggedUsername.textContent = "";
    }
}

// Authentication procedures:

//-Registration
async function register() {
    const usernameInput = document.getElementById("auth-username");
    const passwordInput = document.getElementById("auth-password");
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();

    if (!username || !password) {
        alert("Please enter both username and password!");
        return;
    }

    try {
        const response = await fetch(`${AUTH_URL}/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || `HTTP Error: ${response.status}`);
        }

        alert("Registration successful! You are now logged in as " + data.username);
        setSession(data.access_token, data.username);
        usernameInput.value = "";
        passwordInput.value = "";
        getPolls();
    } catch (error) {
        console.error("Registration error:", error);
        alert("Registration failed: " + error.message);
    }
}
//-Login
async function login() {
    const usernameInput = document.getElementById("auth-username");
    const passwordInput = document.getElementById("auth-password");
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();

    if (!username || !password) {
        alert("Please enter both username and password!");
        return;
    }

    try {

        const response = await fetch(`${AUTH_URL}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || `HTTP Error: ${response.status}`);
        }

        alert("Login successful! Welcome " + data.username);
        setSession(data.access_token, data.username);
        usernameInput.value = "";
        passwordInput.value = "";
        getPolls();
    } catch (error) {
        console.error("Login error:", error);
        alert("Login failed: " + error.message);
    }
}
//-Logout
function logout() {
    clearSession();
    alert("You have logged out.");
    getPolls();
}

// Polls operations:
//-PollFetch, connected to getPolls to visualize all the Polls present
function pollsfetch() {
    let currentTime = new Date();
    const lbl = document.getElementById("lbllist");
    if (lbl) {
        lbl.innerHTML = "Refreshed at: " + currentTime.getHours() + ":" + String(currentTime.getMinutes()).padStart(2, '0') + ":" + String(currentTime.getSeconds()).padStart(2, '0');
    }
    getPolls();
}

async function getPolls() {
    try {
        const response = await fetch(`${POLL_URL}/polls`);
        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status}`);
        }

        const polls = await response.json();
        const container = document.getElementById("pollslist");
        container.innerHTML = "";
        console.log("All the polls:", polls);

        const currentUsername = getUsername();

        if (polls.length === 0) {
            container.innerHTML = "<p>No polls available yet. Create the first one above!</p>";
            return;
        }

        polls.forEach(poll => {
            const form = document.createElement("form");

            // Titolo della domanda
            const questionElement = document.createElement("h3");
            questionElement.textContent = poll.question;
            form.appendChild(questionElement);

            // Informazioni creatore del sondaggio
            const creator = poll.created_by || "Anonymous";
            const metaElement = document.createElement("small");
            metaElement.textContent = `Created by: ${creator}`;

            // Controllo se l'utente ha già votato questo sondaggio
            const alreadyVoted = currentUsername && poll.voted_by && poll.voted_by.includes(currentUsername);
            if (alreadyVoted) {
                metaElement.textContent += " - [You have already voted on this poll]";
            }
            form.appendChild(metaElement);
            form.appendChild(document.createElement("br"));
            form.appendChild(document.createElement("br"));

            // Generazione opzioni di voto radio (stile standard HTML)
            poll.options.forEach((option, index) => {
                const optionWrapper = document.createElement("div");

                const radioInput = document.createElement("input");
                radioInput.type = "radio";
                radioInput.name = `poll-${poll.id}`;
                radioInput.value = option.text;
                radioInput.id = `poll-${poll.id}-opt-${index}`;

                if (alreadyVoted) {
                    radioInput.disabled = true;
                }

                const label = document.createElement("label");
                label.htmlFor = radioInput.id;
                label.textContent = ` ${option.text} (Votes: ${option.votes})`;

                optionWrapper.appendChild(radioInput);
                optionWrapper.appendChild(label);
                form.appendChild(optionWrapper);
            });

            form.appendChild(document.createElement("br"));

            const submitBtn = document.createElement("button");
            submitBtn.type = "submit";
            submitBtn.textContent = "Vote";

            if (alreadyVoted) {
                submitBtn.disabled = true;
                submitBtn.textContent = "Already Voted";
            }

            form.appendChild(submitBtn);
            form.appendChild(document.createElement("br"));
            form.appendChild(document.createElement("hr"));

            //Submit of the vote, REST call to VoteService
            form.addEventListener("submit", async (e) => {
                e.preventDefault();

                const token = getToken();
                if (!token) {
                    alert("Please log in to cast your vote!");
                    return;
                }

                const selectedOption = form.querySelector(`input[name="poll-${poll.id}"]:checked`);
                if (!selectedOption) {
                    alert("Select an option before voting");
                    return;
                }

                try {
                    const voteResponse = await fetch(`${VOTE_URL}/polls/${poll.id}/vote`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${token}`
                        },
                        body: JSON.stringify({ "option": selectedOption.value })
                    });

                    const voteData = await voteResponse.json();
                    if (!voteResponse.ok) {
                        throw new Error(voteData.detail || `HTTP Error: ${voteResponse.status}`);
                    }

                    alert("Your vote was recorded successfully!");
                    getPolls();
                } catch (error) {
                    alert("Error voting: " + error.message);
                    console.error("Error adding the vote:", error);
                }
            });

            container.appendChild(form);
        });
    } catch (error) {
        console.error("There was a problem retrieving polls:", error);
    }
}

// Creation of the new Poll
async function newPoll() {
    const token = getToken();
    if (!token) {
        alert("You must be logged in to create a poll!");
        return;
    }

    const name = document.getElementById("pollname").value.trim();
    const option1 = document.getElementById("firstoption").value.trim();
    const option2 = document.getElementById("secondoption").value.trim();

    if (!name) {
        alert("Please fill in the name of the poll!");
        return;
    }
    if (!option1 || !option2) {
        alert("Please fill in both options!");
        return;
    }

    const pollData = {
        question: name,
        options: [option1, option2]
    };

    try {
        const response = await fetch(`${POLL_URL}/polls`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(pollData)
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || `HTTP Error: ${response.status}`);
        }

        alert("The Poll '" + name + "' was created successfully!");

        document.getElementById("pollname").value = "";
        document.getElementById("firstoption").value = "";
        document.getElementById("secondoption").value = "";

        getPolls();
    } catch (error) {
        console.error("Error creating the poll:", error);
        alert("There was an error creating the poll: " + error.message);
    }
}

//Initialization after the loading of the document
document.addEventListener("DOMContentLoaded", () => {
    updateAuthUI();
    getPolls();
});
