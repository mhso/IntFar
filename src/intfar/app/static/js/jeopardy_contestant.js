const socket = io({"transports": ["websocket", "polling"]});
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
    socket.once("daily_wager_made", function(amount) {
        btn.style.backgroundColor = "#00b000";
    });
    socket.emit("make_daily_wager", userId, value);
}

function makeFinalJeopardyWager(userId) {
    let btn = document.getElementById("contestant-wager-btn");

    let value = document.getElementById("finale-wager-amount").value;
    socket.once("finale_wager_made", function() {
        btn.style.backgroundColor = "#00b000";
    });
    socket.emit("make_finale_wager", userId, value);
}

function giveFinalJeopardyAnswer(userId) {
    let btn = document.getElementById("contestant-wager-btn");

    let answer = document.getElementById("finale-answer").value;
    socket.once("finale_answer_given", function() {
        btn.style.backgroundColor = "#00b000";
    });
    socket.emit("give_finale_answer", userId, answer);
}

function pressBuzzer(userId) {
    console.log("Pressing buzzer:", userId);
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

    setTimeout(function() {
        let buzzerWinnerImg = document.getElementById("buzzer-winner");
        let buzzerLoserImg = document.getElementById("buzzer-loser");

        // Reset and hide buzzer status after a delay
        resetBuzzerStatusImg(buzzerWinnerImg);
        resetBuzzerStatusImg(buzzerLoserImg);

        buzzerStatus.classList.add("d-none");
        buzzerStatus.style.opacity = 0;
    }, 1600);
}

function usePowerUp(playerId, powerId) {
    let btn = document.getElementById(`contestant-power-btn-${powerId}`);
    btn.disabled = true;

    socket.emit("use_power_up", playerId, powerId);
}

function togglePowerUpsEnabled(playerId, powerIds, enabled) {
    console.log(`${enabled ? "Enabled" : "Disabled"} '${powerIds}' power-up(s) for ${playerId}`);

    powerIds.forEach((powerId) => {
        let btn = document.getElementById(`contestant-power-btn-${powerId}`);
        let powerIcon = btn.getElementsByClassName("contestant-power-icon").item(0);

        if (enabled && powerIcon.classList.contains("power-disabled")) {
            powerIcon.classList.remove("power-disabled");
            btn.onclick = () => usePowerUp(playerId, powerId);
        }
        else if (!enabled && !powerIcon.classList.contains("power-disabled")) {
            powerIcon.classList.add("power-disabled");
        }

        btn.disabled = !enabled;
    });
}

function monitorGame(playerId, turnId) {
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
        if (activeIds.includes(turnId)) {
            buzzerInactive.classList.add("d-none");
            buzzerActive.classList.remove("d-none");
        }
    });

    socket.on("buzz_disabled", function() {
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

    // Called whenever a powerup is available to use
    socket.on("power_up_enabled", function(powerId) {
        togglePowerUpsEnabled(playerId, [powerId], true);
    });

    // Called whenever a powerup is no longer available to use
    socket.on("power_ups_disabled", function(powerIds) {
        togglePowerUpsEnabled(playerId, powerIds, false);
    });

    // Called whenever we have successfully used a power-up
    socket.on("power_up_used", function(powerId) {
        let usedIcon = document.querySelector(`#contestant-power-btn-${powerId} > .contestant-power-used`);
        usedIcon.classList.remove("d-none");

        if (powerId == "freeze") {
            return;
        }

        if (!buzzerStatus.classList.contains("d-none")) {
            buzzerStatus.classList.add("d-none");
            buzzerStatus.style.opacity = 0;
        }
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

        console.log("Ping received:", pingNum);

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

window.addEventListener("DOMContentLoaded", function() {
    let questionHeader = document.getElementById("question-category-header");
    if (questionHeader != null) {
        let size = (window.innerWidth / questionHeader.textContent.length * 2.2);
        questionHeader.style.fontSize = size + "px";
        let questionChoices = document.getElementById("question-choices-indicator");
        if (questionChoices != null) {
            questionChoices.style.height = (size - 5) + "px";
        }
    }
});