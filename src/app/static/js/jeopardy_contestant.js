const socket = io();

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port + "/intfar/jeopardy";
}

function getSelectionURL() {
    return `${getBaseURL()}/selection`;
}

function getQuestionURL() {
    return `${getBaseURL()}/question`;
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

function makeDailyDoubleWager(userId) {
    let btn = document.getElementById("contestant-wager-btn");
    if (btn.disabled) {
        return;
    }

    btn.disabled = true;
    let value = document.getElementById("question-wager-input").value;
    socket.emit("make_daily_wager", userId, value);
}

function makeFinalJeopardyWager(userId) {
    let btn = document.getElementById("contestant-wager-btn");

    let value = document.getElementById("finale-wager-amount").value;
    socket.emit("make_finale_wager", userId, value);
    socket.once("finale_wager_made", function() {
        btn.style.backgroundColor = "#00b000";
    });
}

function giveFinalJeopardyAnswer(userId) {
    let btn = document.getElementById("contestant-wager-btn");

    let answer = document.getElementById("finale-answer").value;
    socket.emit("give_finale_answer", userId, answer);
    socket.once("finale_answer_given", function() {
        btn.style.backgroundColor = "#00b000";
    });
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

function resetBuzzerStatusImg(elem) {
    elem.style.animationName = "none";
    elem.offsetHeight; // Trigger reflow
    elem.style.animationName = null;
    elem.classList.add("d-none");
}

function monitorGame(turnId) {
    let buzzerActive = document.getElementById("buzzer-active");
    let buzzerInactive = document.getElementById("buzzer-inactive");
    let buzzerPressed = document.getElementById("buzzer-pressed");
    let buzzerStatus = document.getElementById("contestant-buzzer-status");
    let pingElem = document.getElementById("contestant-game-ping");
    let buzzerWinnerImg = document.getElementById("buzzer-winner");
    let buzzerLoserImg = document.getElementById("buzzer-loser");

    socket.on("state_changed", function() {
        window.location.reload();
    });

    // Called when question has been asked and buzzing has been enabled.
    socket.on("buzz_enabled", function(activeIds) {
        resetBuzzerStatusImg(buzzerWinnerImg);
        resetBuzzerStatusImg(buzzerLoserImg);

        if (activeIds.includes(turnId)) {
            buzzerStatus.classList.add("d-none");
            buzzerStatus.style.opacity = 0;

            buzzerInactive.classList.add("d-none");
            buzzerActive.classList.remove("d-none");
        }
    });

    // Called when a person has been declared as the fastest to buzz in during a question.
    socket.on("buzz_winner", function(winnerId) {
        if (!buzzerStatus.classList.contains("d-none")) {
            // We already buzzed in (and answered incorrectly) previously
            return;
        }

        buzzerActive.classList.add("d-none");
        buzzerInactive.classList.remove("d-none");
        buzzerPressed.classList.add("d-none");

        let img;
        if (winnerId == turnId) {
            img = buzzerWinnerImg;
        }
        else {
            img = buzzerLoserImg;
        }
        buzzerStatus.classList.remove("d-none");
        buzzerStatus.style.opacity = 1;
        img.classList.remove("d-none");
        img.style.animationName = "showBuzzerStatus";
    });

    // Called whenever the server has calculated our ping.
    socket.on("ping_calculated", function(ping) {
        pingElem.textContent = ping + " ms";
        let pingNum = Number.parseFloat(ping);

        if (pingNum < 50) {
            pingElem.className = "contestant-low-ping";
        }
        else if (pingNum < 100) {
            pingElem.className = "contestant-moderate-ping";
        }
        else {
            pingElem.className = "contestant-high-ping";
        }
    });

    // Called when person has made a wager that is invalid
    socket.on("invalid_wager", function(maxWager) {
        alert("Ugyldig mængde point, skal være mellem 100 og " + maxWager);
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
    // let elem = document.getElementById("contestant-game-waiting");
    // setInterval(function() {
    //     if (elem.textContent.endsWith("...")) {
    //         elem.textContent = elem.textContent.slice(0, elem.textContent.length-3);
    //     }
    //     else {
    //         elem.textContent += ".";
    //     }
    // }, 1000);
}