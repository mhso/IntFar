const POINT_GAIN_CORRECT = [2, 3, 4];
const POINT_LOSSES_WRONG = [0, 1, 2];

var countdownInterval;
var activeRound;
var activeQuestionNum;
var activeAnswer;
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

function incrementScore(delta) {
    let cookieSplit = document.cookie.split(";");
    let newCookie = null;
    let team = activeTeamBlue ? "blue" : "red";
    for (let i = 0; i < cookieSplit.length; i++) {
        let kv = cookieSplit[i].trim();
        let kvSplit = kv.split("=");
        if (kvSplit[0] == "score_" + team) {
            let score = Number.parseInt(kvSplit[1]);
            newCookie = "score_" + team + "=" + (score + delta);
        }
    }
    if (newCookie == null) {
        console.log("Error: Couldn't increment score (cookie not found)!")
    }
    else {
        let date = new Date();
        date.setTime(date.getTime() + (6 * 60 * 60 * 1000));
        document.cookie = newCookie + "; expires=" + date.toUTCString() + "; path=/intfar/quiz; samesite=strict";
    }
}

function getRandomSound(sounds) {
    let index = Math.floor(Math.random() * sounds.length);
    return sounds.item(index);
}

function playCorrectSound() {
    let sounds = document.getElementsByClassName("quiz-sound-correct");
    let sound = getRandomSound(sounds);
    sound.play();
}

function playWrongSound() {
    let sounds = document.getElementsByClassName("quiz-sound-wrong");
    let sound = getRandomSound(sounds);
    sound.play();
}

function correctAnswer() {
    let pointsGained = POINT_GAIN_CORRECT[activeRound-1];

    let reasonElem = document.getElementById("quiz-correct-reason");
    reasonElem.textContent = reasonElem.textContent + " (+" + pointsGained + " point)"
    let elem = document.getElementById("quiz-answer-correct");
    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playCorrectSound();
    }, 100);

    incrementScore(pointsGained);
}

function wrongAnswer(reason) {
    let pointsLost = POINT_LOSSES_WRONG[activeRound-1];

    let reasonElem = document.getElementById("quiz-wrong-reason");
    let reasonText = reason;
    if (pointsLost > 0) {
        reasonText += " (-" + pointsLost + " point)";
    }
    reasonElem.textContent = reasonText;
    let elem = document.getElementById("quiz-answer-wrong");
    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playWrongSound();
    }, 100);


    incrementScore(-pointsLost);
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
    let question = getCurrentQuestion();
    let endpoint = null;
    if (activeRound < 3) {
        endpoint = "/intfar/quiz/" + activeRound + "/" + (question + 1);
    }
    else {
        endpoint = "/intfar/quiz/selection/" + (question + 1);
    }
    window.location.href = getBaseURL() + endpoint;
}

function keyIsNumeric(key, min, max) {
    let keys = Array.apply(null, Array(max - min + 1)).map(function (x, i) { return "" + (i + min); });
    return keys.includes(key)
}

function answerQuestion(event) {
    if (keyIsNumeric(event.key, 1, 4)) {
        questionAnswered = true;

        window.onkeydown = function(e) {
            if (e.key == "NumLock") {
                startNextRound();
            }
        }

        let elem = document.getElementById("quiz-answer-" + event.key);
        let answerElem = elem.getElementsByClassName("quiz-answer-text").item(0);
        // Clear countdown.
        clearInterval(countdownInterval);
        document.getElementById("quiz-countdown-wrapper").classList.add("d-none");
        // Highlight element as having been selected as the answer.
        let delay = 2500
        elem.classList.add("quiz-answering");
        setTimeout(function() {
            elem.classList.remove("quiz-answering");
            if (answerElem.textContent == activeAnswer) {
                elem.classList.add("quiz-answered-correct");
                correctAnswer();
            }
            else {
                elem.classList.add("quiz-answered-wrong");
                wrongAnswer("Forkert");
            }
        }, delay);
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

function startCountdown() {
    if (questionAnswered) { // Question has already been answered very quickly.
        return;
    }

    let countdownWrapper = document.getElementById("quiz-countdown-wrapper");
    countdownWrapper.style.opacity = 1;
    let countdownBar = document.getElementById("quiz-countdown-filled");
    let countdownText = document.getElementById("quiz-countdown-text");

    let green = 255
    let red = 136;

    let secs = 0;
    let iteration = 0;
    let maxSecs = 30;
    let delay = 50;

    let totalSteps = (maxSecs * 1000) / delay;
    let colorDelta = (green + red) / totalSteps;

    setCountdownText(countdownText, secs, maxSecs);
    setCountdownBar(countdownBar, (secs * 1000) + (iteration * delay), green, red, maxSecs * 1000);

    countdownInterval = setInterval(function() {
        iteration += 1;
        if (iteration * delay == 1000) {
            iteration = 0;
            secs += 1;
            setCountdownText(countdownText, secs, maxSecs);
        }
        if (red < 255) {
            red += colorDelta;
        }
        else if (green > 0) {
            green -= colorDelta;
        }

        setCountdownBar(countdownBar, (secs * 1000) + (iteration * delay), green, red, maxSecs * 1000);

        if (secs == maxSecs) {
            clearInterval(countdownInterval);
            countdownWrapper.classList.add("d-none")
            wrongAnswer("Ikke mere tid")
        }
    }, delay);
}

function showQuestion() {
    let questionElem = document.getElementById("quiz-question-header");

    questionElem.style.opacity = 1;
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            showAnswerChoice(0);
        }
    }
}

function showAnswerChoice(index) {
    let choiceElem = document.getElementsByClassName("quiz-answer-entry").item(index);
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

function questionAsked() {
    // Enable participants to answer only when NumLock has been pressed.
    window.onkeydown = function(e) {
        if (activeRound == 2) {
            if (e.key == "Enter") {
                activeTeamBlue = true;
            }
            else if (e.key == "Escape") {
                activeTeamBlue = false;
            }
            if (e.key == "Enter" || e.key == "Escape") {
                // Buzzer has been hit, let the team answer.
                document.getElementById("quiz-buzzer-sound").play();
                window.onkeydown = function(e) {
                    answerQuestion(e);
                }
            }
        }
        else {
            answerQuestion(e);
        }
    }
    setTimeout(function() {
        startCountdown();
    }, 1500);
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

function setVariables(round, playerData, turns, questionNum) {
    activeRound = round;
    playerData.forEach((data) => {
        playerNames.push(data["name"]);
        playerScores.push(data["score"]);
        playerColors.push(data["color"]);
    });
    playerTurns = turns;
    activeQuestionNum = questionNum;
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

function setPlayerTurn(player) {
    let playerEntries = document.getElementsByClassName("selection-contestant-entry");
    playerEntries.item(player).style.height = "100%";
    playerTurns.push(player);
}

function chooseStartingPlayer() {
    let playerEntries = document.getElementsByClassName("selection-contestant-entry");
    let minIters = 20;
    let maxIters = 32;
    let iters = minIters + (maxIters - minIters) * Math.random();
    let minWait = 30;
    let maxWait = 400;

    let player = 0;

    function showStartPlayerCandidate(iter) {
        let wait = minWait + (maxWait - minWait) * (iter / iters);

        setTimeout(() => {
            playerEntries.item(player).style.height = "100px";
            player = iter % playerEntries.length;
            playerEntries.item(player).style.height = "100%";

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