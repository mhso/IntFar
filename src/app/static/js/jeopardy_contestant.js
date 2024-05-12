const socket = io();
var pingActive = true;

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
    socket.once("daily_wager_made", function(amount) {
        btn.style.backgroundColor = "#00b000";
    });
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

function handleBuzzInResult(imageToShow) {
    let buzzerActive = document.getElementById("buzzer-active");
    let buzzerInactive = document.getElementById("buzzer-inactive");
    let buzzerPressed = document.getElementById("buzzer-pressed");
    let buzzerStatus = document.getElementById("contestant-buzzer-status");

    buzzerActive.classList.add("d-none");
    buzzerPressed.classList.add("d-none");
    buzzerInactive.classList.remove("d-none");

    buzzerStatus.classList.remove("d-none");
    buzzerStatus.style.opacity = 1;
    imageToShow.classList.remove("d-none");
    imageToShow.style.animationName = "showBuzzerStatus";
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

    socket.on("buzz_disabled", function() {
        resetBuzzerStatusImg(buzzerWinnerImg);
        resetBuzzerStatusImg(buzzerLoserImg);

        buzzerActive.classList.add("d-none");
        buzzerPressed.classList.add("d-none");
        buzzerInactive.classList.remove("d-none");

        if (buzzerStatus.classList.contains("d-none")) {
            buzzerStatus.classList.remove("d-none");
            buzzerStatus.style.opacity = 1;
        }
    });

    // Called when this person was the fastest to buzz in during a question.
    socket.on("buzz_winner", function() {
        handleBuzzInResult(buzzerWinnerImg);
    });

    // Called when this person was not the fastest to buzz in during a question.
    socket.on("buzz_loser", function() {
        if (!buzzerStatus.classList.contains("d-none")) {
            // We already buzzed in (and answered incorrectly) previously
            return;
        }

        handleBuzzInResult(buzzerLoserImg);
    });

    // Called whenever the server has received our ping request.
    socket.on("ping_response", function(userId, timeSent) {
        let timeReceived = (new Date()).getTime();
        socket.emit("calculate_ping", userId, timeSent, timeReceived);
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
        let btn = document.getElementById("contestant-wager-btn");
        btn.disabled = false;
        alert("Ugyldig mængde point, skal være mellem 100 og " + maxWager);
    });
}

function getUTCTimestamp() {
    let date = new Date();
    return new Date(
        date.getUTCFullYear(),
        date.getUTCMonth(),
        date.getUTCDate(),
        date.getUTCHours(),
        date.getUTCMinutes(),
        date.getUTCSeconds(),
        date.getUTCMilliseconds()
    ).getTime();
}

function sendPingMessage(userId) {
    setTimeout(function() {
        if (!pingActive) {
            return;
        }
        now = (new Date()).getTime();
        socket.emit("ping_request", userId, now);
        sendPingMessage(userId);
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