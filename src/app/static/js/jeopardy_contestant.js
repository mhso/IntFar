const socket = io();
let gameIntervalId;

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port + "/intfar/jeopardy";
}

function getSelectionURL() {
    return `${getBaseURL()}/selection`;
}

function getQuestionURL() {
    return `${getBaseURL()}/question`;
}

function pressBuzzer(userId) {
    let activeBuzzer = document.getElementById("buzzer-active");
    if (activeBuzzer.classList.contains("d-none")) {
        return;
    }

    activeBuzzer.classList.add("d-none");

    document.getElementById("buzzer-pressed").classList.remove("d-none");

    socket.emit("buzzer_pressed", userId);
}

function setRandomColor() {
    let colorInput = document.getElementById("contestant-lobby-color");

    let randRed = (Math.random() * 255).toString(16).split(".")[0];
    if (randRed == "0") {
        randRed = "00";
    }
    let randGreen = (Math.random() * 255).toString(16).split(".")[0];
    if (randGreen == "0") {
        randGreen = "00";
    }
    let randBlue = (Math.random() * 255).toString(16).split(".")[0];
    if (randBlue == "0") {
        randBlue = "00";
    }

    colorInput.type = "color";
    colorInput.value = `#${randRed}${randGreen}${randBlue}`;
}

function monitorGame(turnId) {
    socket.on("state_changed", function() {
        window.location.href = `${getBaseURL()}/game`;
    });
    socket.on("buzz_winner", function(winnerId) {
        document.getElementById("buzzer-pressed").classList.add("d-none");
        document.getElementById("buzzer-inactive").classList.remove("d-none");
        let status;
        if (winnerId == turnId) {
            status = "Du var hurtigst!"
        }
        else {
            status = "Du var for langsom."
        }
        document.getElementById("contestant-buzzer-status").textContent = status;
    });
}

function sendPingMessage(user_id) {
    setTimeout(function() {
        now = new Date().getTime();
        socket.emit("calculate_ping", user_id, now);
        sendPingMessage(user_id);
    }, 1000);
}

function animateWaitingText() {
    let elem = document.getElementById("contestant-game-waiting");
    setInterval(function() {
        if (elem.textContent.endsWith("...")) {
            elem.textContent = elem.textContent.slice(0, elem.textContent.length-3);
        }
        else {
            elem.textContent += ".";
        }
    }, 1000);
}