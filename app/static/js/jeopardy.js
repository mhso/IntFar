const POINT_GAIN_CORRECT = [2, 3, 4];
const POINT_LOSSES_WRONG = [0, 1, 2];
const TIME_FOR_BUZZING = 5;
const TIME_FOR_ANSWERING = 10;
const TIME_FOR_WAGERING = 60;
const TIME_FOR_FINAL_ANSWER = 30;

var countdownInterval;
var activeRound;
var activeQuestionNum;
var activeAnswer;
var activeValue;
var activePlayer = null;
var questionAnswered = false;

var playerNames = [];
let playerColors = [];
var playerScores = [];
let playerTurns = [];

function getCurrentQuestion() {
    let currentUrl = window.location.href;
    let split = currentUrl.split("/");
    let lastIndex = split[split.length-1] == "" ? split.length - 2 : split.length - 1;
    let question = Number.parseInt(split[lastIndex]);
    return question;
}

function getRandomSound(sounds) {
    let index = Math.floor(Math.random() * sounds.length);
    return sounds.item(index);
}

function playCorrectSound() {
    let sounds = document.getElementsByClassName("question-sound-correct");
    let sound = getRandomSound(sounds);
    sound.play();
}

function playWrongSound() {
    let sounds = document.getElementsByClassName("question-sound-wrong");
    let sound = getRandomSound(sounds);
    sound.play();
}

function revealAnswerImageIfPresent() {
    let elem = document.getElementById("question-answer-image");
    if (elem != null) {
        elem.opacity = 1;
    }
}

function correctAnswer() {
    let elem = document.getElementById("question-answer-correct");

    let valueElem = elem.getElementsByClassName("question-answer-value").item(0);
    valueElem.textContent = "(+" + activeValue + " GBP)";

    revealAnswerImageIfPresent();

    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playCorrectSound();
    }, 100);

    playerScores[activePlayer] += activeValue;
}

function wrongAnswer(reason) {
    let elem = document.getElementById("question-answer-wrong");

    let reasonElem = document.getElementById("question-wrong-reason-text");
    reasonElem.textContent = reason;

    revealAnswerImageIfPresent();

    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playWrongSound();
    }, 100);

    if (activePlayer != null) {
        // Deduct points from player if someone buzzed in
        let valueElem = elem.getElementsByClassName("question-answer-value").item(0);
        valueElem.textContent = "(-" + activeValue + " GBP)";
        playerScores[activePlayer] -= activeValue;
    }

    if (playerTurns.length > 1) {
        // Player turn is now the previous player who had the turn
        playerTurns.pop();
    }
}

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port;
}

function getQueryParams() {
    // Encode player information and turns into URL query strings
    let playerNameQueries = new Array();
    playerNames.forEach((name, index) => {
        playerNameQueries.push(`p${index+1}=${encodeURIComponent(name)}`);
    });
    let namesQueryStr = playerNameQueries.join("&");

    let playerScoreQueries = new Array();
    playerScores.forEach((score, index) => {
        playerScoreQueries.push(`s${index+1}=${encodeURIComponent(score)}`);
    });
    let scoresQueryStr = playerScoreQueries.join("&");

    let playerColorQueries = new Array();
    playerColors.forEach((color, index) => {
        playerColorQueries.push(`c${index+1}=${encodeURIComponent(color)}`);
    });
    let colorsQueryStr = playerColorQueries.join("&");

    let playerTurnStr = playerTurns.join(",");

    return `${namesQueryStr}&${scoresQueryStr}&${colorsQueryStr}&turns=${playerTurnStr}`
}

function getSelectionURL(round, question) {
    return `${getBaseURL()}/intfar/jeopardy/${round}/${question}?${getQueryParams()}`
}

function getQuestionURL(round, category, difficulty) {
    return `${getBaseURL()}/intfar/jeopardy/${round}/${category}/${difficulty}?${getQueryParams()}`
}

function startNextRound() {
    window.location.href = getSelectionURL(activeRound, activeQuestionNum + 1);
}

function keyIsNumeric(key, min, max) {
    let keys = Array.apply(null, Array(max - min + 1)).map(function (x, i) { return "" + (i + min); });
    return keys.includes(key);
}

function stopCountdown() {
    clearInterval(countdownInterval);
    let countdownElem = document.getElementById("question-countdown-wrapper");
    countdownElem.classList.add("d-none");
    countdownElem.style.opacity = 0;
}

function isQuestionMultipleChoice() {
    return document.getElementsByClassName("question-answer-entry").length > 0;
}

function answerQuestion(event) {
    if (keyIsNumeric(event.key, 1, 4)) {
        questionAnswered = true;

        window.onkeydown = function(e) {
            if (e.key == "NumLock") {
                startNextRound();
            }
        }

        let elem = document.getElementById("question-answer-" + event.key);
        let answerElem = elem.getElementsByClassName("question-answer-text").item(0);

        // Clear countdown and name of who is answering
        stopCountdown();

        if (isQuestionMultipleChoice()) {
            // Highlight element as having been selected as the answer.
            let delay = 2500
            elem.classList.add("question-answering");
            setTimeout(function() {
                elem.classList.remove("question-answering");
                if (answerElem.textContent == activeAnswer) {
                    elem.classList.add("question-answered-correct");
                    correctAnswer();
                }
                else {
                    elem.classList.add("question-answered-wrong");
                    wrongAnswer("Forkert");
                }
            }, delay);
        }
        else {
            if (event.key == 1) {
                elem.classList.add("question-answered-correct");
                correctAnswer();
            }
            else {
                elem.classList.add("question-answered-wrong");
                wrongAnswer("Forkert");
            }
        }
    }
}

function setCountdownText(countdownText, seconds, maxSecs) {
    countdownText.textContent = (maxSecs - seconds);
}

function setCountdownBar(countdownBar, milis, green, red, maxMilis) {
    let width = (milis / maxMilis) * 100;
    countdownBar.style.width = width + "%";
    countdownBar.style.backgroundColor = "rgb(" + red.toFixed(0) + ", " + green.toFixed(0) + ", 0)";
}

function startCountdown(duration) {
    if (questionAnswered) { // Question has already been answered very quickly.
        return;
    }

    let countdownWrapper = document.getElementById("question-countdown-wrapper");
    if (countdownWrapper.classList.contains("d-none")) {
        countdownWrapper.classList.remove("d-none");
    }
    countdownWrapper.style.opacity = 1;
    let countdownBar = document.getElementById("question-countdown-filled");
    let countdownText = document.getElementById("question-countdown-text");

    let green = 255
    let red = 136;

    let secs = 0;
    let iteration = 0;
    let delay = 50;

    let totalSteps = (duration * 1000) / delay;
    let colorDelta = (green + red) / totalSteps;

    setCountdownText(countdownText, secs, duration);
    setCountdownBar(countdownBar, (secs * 1000) + (iteration * delay), green, red, duration * 1000);

    countdownInterval = setInterval(function() {
        iteration += 1;
        if (iteration * delay == 1000) {
            iteration = 0;
            secs += 1;
            setCountdownText(countdownText, secs, duration);
        }
        if (red < 255) {
            red += colorDelta;
        }
        else if (green > 0) {
            green -= colorDelta;
        }

        setCountdownBar(countdownBar, (secs * 1000) + (iteration * delay), green, red, duration * 1000);

        if (secs >= duration) {
            stopCountdown();
            wrongAnswer("Ikke mere tid");
        }
    }, delay);
}

function questionAsked() {
    if (activeRound < 3) {
        // Enable participants to buzz in if we are in round 1 or 2
        window.onkeydown = function(e) {
            if (keyIsNumeric(e.key, 1, 4)) {
                // Buzzer has been hit, let the player answer.
                activePlayer = e.key - 1;
                document.getElementById("question-buzzer-sound").play();

                // Clear buzz-in countdown.
                stopCountdown();

                // Show who was fastest at buzzing in
                setPlayerTurn(activePlayer, false);

                // Add a small delay before we can answer
                setTimeout(() => {
                    startCountdown(TIME_FOR_ANSWERING);

                    window.onkeydown = function(e) {
                        answerQuestion(e);
                    }
                }, 1000);
            }
        }
    }

    setTimeout(function() {
        startCountdown(TIME_FOR_BUZZING);
    }, 500);
}

function showAnswerChoice(index) {
    let choiceElem = document.getElementsByClassName("question-answer-entry").item(index);
    choiceElem.style.opacity = 1;

    if (index < 3) {
        window.onkeydown = function(e) {
            if (e.key == "NumLock") {
                showAnswerChoice(index + 1);
            }
        }
    }
    else {
        questionAsked();
    }
}

function showQuestion() {
    document.getElementById("question-question-header").style.opacity = 1;
    document.getElementById("question-question-image").style.opacity = 1;

    if (isQuestionMultipleChoice()) {
        // If question is multiple-choice, show each choice one by one
        window.onkeydown = function(e) {
            if (e.key == "NumLock") {
                showAnswerChoice(0);
            }
        }
    }
    else {
        questionAsked();
    }
}

function scaleAnswerChoices() {
    let choiceElems = document.getElementsByClassName("quiz-answer-entry");
    for (let i = 0; i < choiceElems.length; i++) {
        let wrapper = choiceElems.item(i)
        let textElem = wrapper.getElementsByTagName("p").item(0);
        if (textElem.offsetHeight > wrapper.offsetHeight * 0.75) {
            wrapper.style.fontSize = "16px";
            if (textElem.offsetHeight > wrapper.offsetHeight * 0.75) {
                wrapper.style.paddingTop = "4px";
            }
            else {
                wrapper.style.paddingTop = "16px";
            }
        }
    }
}

function setVariables(round, playerData, turns, questionNum=null, answer=null, value=null) {
    console.log(round, playerData, turns, questionNum, answer, value);
    activeRound = round;
    playerData.forEach((data) => {
        playerNames.push(data["name"]);
        playerScores.push(data["score"]);
        playerColors.push(data["color"]);
    });
    playerTurns = turns;
    activeQuestionNum = questionNum;
    activeAnswer = answer;
    activeValue = value;
}

function categorySelection() {
    let categoryElems = document.getElementsByClassName("quiz-category-entry");
    window.onkeydown = function(e) {
        if (keyIsNumeric(e.key, 1, categoryElems.length)) {
            let num = Number.parseInt(e.key);
            let elem = categoryElems.item(num-1);
            if (!elem.classList.contains("quiz-category-inactive")) {
                let category = elem.dataset.category;
                let question = getCurrentQuestion();

                elem.classList.add("quiz-category-selected");

                setTimeout(function() {
                    let url = getBaseURL() + "/intfar/quiz/" + category + "/" + question;
                    window.location.href = url;
                }, 1500);
            }
        }
    }
}

function goToQuestion(div, category, tier) {
    if (!div.classList.contains("question-box")) {
        div = div.parentElement;
    }

    div.style.zIndex = 999;

    let bbox = div.getBoundingClientRect();
    let distX = (window.innerWidth / 2) - (bbox.x + bbox.width / 2);
    let distY = (window.innerHeight / 2) - (bbox.y + bbox.height / 2);

    div.style.transition = "all 2.5s";
    div.style.transform = `translate(${distX}px, ${distY}px) scale(11)`;

    setTimeout(() => {
        window.location.href = getQuestionURL(activeRound, category, tier)
    }, 3000);
}

function setContestantTextColors() {
    let contestantEntries = document.getElementsByClassName("jeopardy-contestant-entry");
    for (let i = 0; i < contestantEntries.length; i++) {
        let bgColor = contestantEntries.item(i).style.backgroundColor;
        let split = bgColor.replace("rgb(", "").replace(")", "").split(",");

        let red = parseInt(split[0]).toString(16);  
        let green = parseInt(split[1]).toString(16);
        let blue = parseInt(split[2]).toString(16); 

        let fgColor = red * 0.299 + green * 0.587 + blue * 0.114 > 160 ? "black" : "white";
        contestantEntries.item(i).style.color = fgColor;
    }
}

function setPlayerTurn(player, save) {
    let playerEntries = document.getElementsByClassName("footer-contestant-entry");
    for (let i = 0; i < playerEntries.length; i++) {
        let size = i == player ? "100%" : "60%";
        playerEntries.item(i).style.height = size;
    }
    if (save) {
        playerTurns.push(player);
    }
}

function chooseStartingPlayer() {
    let playerEntries = document.getElementsByClassName("footer-contestant-entry");
    let minIters = 20;
    let maxIters = 32;
    let iters = minIters + (maxIters - minIters) * Math.random();
    let minWait = 30;
    let maxWait = 400;

    let player = 0;

    function showStartPlayerCandidate(iter) {
        let wait = minWait + (maxWait - minWait) * (iter / iters);

        setTimeout(() => {
            setPlayerTurn(player, false);
            player = iter % playerEntries.length;

            if (iter < iters) {
                showStartPlayerCandidate(iter + 1);
            }
        }, wait);
    }

    showStartPlayerCandidate(0);

    return player;
}

function beginJeopardy() {
    let contestantNameElems = document.getElementsByClassName("jeopardy-contestant-name");
    let contestantColorElems = document.getElementsByClassName("jeopardy-contestant-color");

    playerNames = [];
    playerColors = [];
    playerScores = [];
    playerTurns = [-1];

    for (let i = 0; i < contestantNameElems.length; i++) {
        playerNames.push(contestantNameElems.item(i).value);
        playerColors.push(contestantColorElems.item(i).value.replace("#", ""));
        playerScores.push(0);
    }

    window.location.href = getSelectionURL(1, 0);
}

function resetUsedQuestions(button) {
    let baseUrl = getBaseURL();
    $.ajax(baseUrl + "/intfar/jeopardy/reset_questions", {
        method: "POST"
    }).then((data) => {
        console.log(data)
        button.style.backgroundColor = "rgb(9, 142, 24)";
    }, (error) => {
        console.log("ERROR when resetting questions: " + error);
        button.style.backgroundColor = "red";
    });
}

function addPlayerDiv() {
    let wrapper = document.getElementById("jeopardy-menu-contestants");

    let div = document.createElement("div");
    div.className = "jeopardy-contestant-entry";

    let nameInput = document.createElement("input");
    nameInput.className = "jeopardy-contestant-name";
    nameInput.placeholder = "Navn";

    let colorInput = document.createElement("input");
    colorInput.className = "jeopardy-contestant-color";

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

    let deleteButton = document.createElement("button");
    deleteButton.className = "jeopardy-contestant-delete";
    deleteButton.innerHTML = "&times;";
    deleteButton.onclick = () => wrapper.removeChild(div);

    div.appendChild(nameInput);
    div.appendChild(colorInput);
    div.appendChild(deleteButton);

    wrapper.appendChild(div);
}

function addWinnerSoundEvent() {
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            document.getElementById("score-winner-sound").play();
        }
    }
}