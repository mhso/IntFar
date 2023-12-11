const TIME_FOR_BUZZING = 5;
const TIME_FOR_ANSWERING = 10;
const TIME_FOR_WAGERING = 60;
const TIME_FOR_FINAL_ANSWER = 30;
const CONTESTANT_KEYS = ["z",  "q", "p", "m"]

var countdownInterval;
var activeRound;
var activeQuestionNum;
var activeQuestionId;
var activeAnswer;
var activeValue;
var answeringPlayer = null;
var activePlayers = [];
var questionAnswered = false;

let playerTurn = 0;
var playerNames = [];
let playerColors = [];
var playerScores = [];

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

    return `${namesQueryStr}&${scoresQueryStr}&${colorsQueryStr}&turn=${playerTurn}`
}

function getSelectionURL(round, question) {
    return `${getBaseURL()}/intfar/jeopardy/${round}/${question}?${getQueryParams()}`;
}

function getQuestionURL(round, category, difficulty) {
    return `${getBaseURL()}/intfar/jeopardy/${round}/${category}/${difficulty}?${getQueryParams()}`;
}

function getFinaleURL(question_id) {
    return `${getBaseURL()}/intfar/jeopardy/${question_id}?${getQueryParams()}`;
}

function getEndscreenURL() {
    return `${getBaseURL()}/intfar/jeopardy/endscreen?${getQueryParams()}`;
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

function placeAnswerImageIfPresent() {
    let img = document.getElementById("question-answer-image");

    function imgLoaded() {
        let width = img.getBoundingClientRect().width / 2;
        img.style.left = `calc(50% - ${width}px)`;
    }

    if (img != null) {
        if (img.complete) {
            imgLoaded();
        }
        else {
            img.addEventListener("load", imgLoaded)
        }
    }
}

function revealAnswerImageIfPresent() {
    let elem = document.getElementById("question-answer-image");
    if (elem != null) {
        elem.style.setProperty("display", "block");
        elem.style.setProperty("opacity", 1);
    }
}

function afterQuestion() {
    activeAnswer = null;
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            window.location.href = getSelectionURL(activeRound, activeQuestionNum + 1);
        }
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

    // Add value to player score
    playerScores[answeringPlayer] += activeValue;

    if (playerTurn != answeringPlayer) {
        // Set player as having the turn, if they didn't already
        setPlayerTurn(answeringPlayer, true);
    }

    // Move on to next question
    afterQuestion();
}

function wrongAnswer(reason) {
    let elem = document.getElementById("question-answer-wrong");

    let reasonElem = document.getElementById("question-wrong-reason-text");
    reasonElem.textContent = reason;

    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playWrongSound();
    }, 100);

    if (answeringPlayer != null) {
        // Deduct points from player if someone buzzed in
        let valueElem = elem.getElementsByClassName("question-answer-value").item(0);
        valueElem.textContent = "(-" + activeValue + " GBP)";
        playerScores[answeringPlayer] -= activeValue;
    }

    if (activePlayers.every((v) => !v) || (reason == "Ikke mere tid" && answeringPlayer == null)) {
        // No players are eligible to answer, go to next question
        revealAnswerImageIfPresent();

        let answerElem = document.getElementById("question-actual-answer");
        answerElem.classList.remove("d-none");

        afterQuestion();
    }
}

function hideAnswerIndicator() {
    let correctElem = document.getElementById("question-answer-correct");
    if (!correctElem.classList.contains("d-none")) {
        correctElem.classList.add("d-none");
        correctElem.style.setProperty("opacity", 0);
    }

    let wrongElem = document.getElementById("question-answer-wrong");
    if (!wrongElem.classList.contains("d-none")) {
        wrongElem.classList.add("d-none");
        wrongElem.style.setProperty("opacity", 0);
    }
}

function keyIsNumeric(key, min, max) {
    let keys = Array.apply(null, Array(max - min + 1)).map(function (x, i) { return "" + (i + min); });
    return keys.includes(key);
}

function keyIsContestant(key) {
    return CONTESTANT_KEYS.includes(key);
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

function afterAnswer() {
    // Reset who is answering
    answeringPlayer = null;
    setPlayerTurn(-1, false);

    if (activeAnswer == null) {
        return;
    }

    let videoElem = document.getElementById("question-question-video");

    let delay = 4000;

    // Immediately allow other players to buzz in
    if (videoElem != null) {
        videoElem.onended = afterShowQuestion;

        // Let players interrupt the video and buzz in early
        window.onkeydown = function(e) {
            if (keyIsContestant(e.key)) {
                playerBuzzedIn(CONTESTANT_KEYS.indexOf(e.key));
            }
        }

        setTimeout(function() {
            // Resume playing video after a delay if no one has buzzed in
            if (answeringPlayer == null) {
                hideAnswerIndicator();
                videoElem.play();
                videoElem.onended = afterShowQuestion;
            }
        }, delay);
    }
    else {
        questionAsked(delay);
    }
}

function answerQuestion(event) {
    if (keyIsNumeric(event.key, 1, 4)) {
        if (isQuestionMultipleChoice()) {
            // Highlight element as having been selected as the answer.
            let delay = 2500
            let elem = document.getElementById("question-answer-" + event.key);
            let answerElem = elem.getElementsByClassName("question-answer-text").item(0);
            elem.classList.add("question-answering");

            setTimeout(function() {
                elem.classList.remove("question-answering");

                if (answerElem.textContent == activeAnswer) {
                    elem.classList.add("question-answered-correct");
                    correctAnswer();
                }
                else {
                    elem.classList.add("question-answered-wrong");
                    wrongAnswer("Forkert...");
                }

                afterAnswer();
            }, delay);
        }
        else {
            if (event.key == 1) {
                correctAnswer();
            }
            else {
                wrongAnswer("Forkert...");
            }

            afterAnswer();
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

function pauseVideo() {
    let videoElem = document.getElementById("question-question-video");
    if (videoElem != null) {
        videoElem.onended = null;
        videoElem.pause();
    }
}

function playerBuzzedIn(player) {
    if (!activePlayers[player]) {
        return; // Player already buzzed in once this question
    }

    // Buzzer has been hit, let the player answer.
    answeringPlayer = player;
    activePlayers[player] = false;
    document.getElementById("question-buzzer-sound").play();

    // Pause video if one is playing
    pauseVideo();

    // Clear buzz-in countdown.
    stopCountdown();

    // Clear previous anwer indicator (if it was shown)
    hideAnswerIndicator();

    // Show who was fastest at buzzing in
    setPlayerTurn(answeringPlayer, false);

    // Start new countdown for answering after small delay
    setTimeout(function() {
        startCountdown(TIME_FOR_ANSWERING);

        // NumLock has to be pressed before an answer can be given (for safety)
        window.onkeydown = function(e) {
            if (e.key == "NumLock") {
                // Clear countdown
                stopCountdown();

                window.onkeydown = function(e) {
                    answerQuestion(e);
                }
            }
        }
    }, 500);
}

function questionAsked(countdownDelay) {
    setTimeout(function() {
        if (answeringPlayer == null) {
            hideAnswerIndicator();
            startCountdown(TIME_FOR_BUZZING);
        }
    }, countdownDelay);

    if (activeRound < 3) {
        // Enable participants to buzz in if we are in round 1 or 2
        window.onkeydown = function(e) {
            if (keyIsContestant(e.key)) {
                playerBuzzedIn(CONTESTANT_KEYS.indexOf(e.key));
            }
        }
    }
    else {
        window.onkeydown = function(e) {
            if (e.key == "NumLock") {
                window.location.href = getFinaleURL(activeQuestionId);
            }
        }
    }
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
        questionAsked(500);
    }
}

function afterShowQuestion() {
    if (isQuestionMultipleChoice()) {
        // If question is multiple-choice, show each choice one by one
        window.onkeydown = function(e) {
            if (e.key == "NumLock") {
                showAnswerChoice(0);
            }
        }
    }
    else {
        questionAsked(500);
    }
}

function showQuestion() {
    for (let i = 0; i < playerNames.length; i++) {
        activePlayers.push(true);
    }

    // Show the question, if it exists
    let questionElem = document.getElementById("question-question-header");
    if (questionElem != null) {
        questionElem.style.opacity = 1;
    }

    let imageElem = document.getElementById("question-question-image");
    let videoElem = document.getElementById("question-question-video");

    let hasAnswerImage = document.getElementById("question-answer-image") != null;

    if (imageElem != null || videoElem != null) {
        // If there is an answer image, first show the question, then show
        // the image after pressing NumLock again. Otherwise show image instantly
        if (hasAnswerImage || videoElem != null) {
            window.onkeydown = function(e) {
                if (e.key == "NumLock") {
                    if (imageElem != null) {
                        imageElem.style.opacity = 1;
                        afterShowQuestion();
                    }
                    else {
                        videoElem.style.opacity = 1;
                        videoElem.play();
                        videoElem.onended = afterShowQuestion;

                        if (activeRound < 3) {
                            // Let players interrupt the video and buzz in early
                            window.onkeydown = function(e) {
                                if (keyIsContestant(e.key)) {
                                    playerBuzzedIn(CONTESTANT_KEYS.indexOf(e.key));
                                }
                            }
                        }
                    }
                }
            }
        }
        else {
            imageElem.style.opacity = 1;
            afterShowQuestion();
        }
    }
    else {
        afterShowQuestion();
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

function setVariables(round, playerData, turn, questionNum=null, answer=null, value=null, questionId=null) {
    activeRound = round;
    playerData.forEach((data) => {
        playerNames.push(data["name"]);
        playerScores.push(data["score"]);
        playerColors.push(data["color"]);
    });
    playerTurn = turn;
    activeQuestionNum = questionNum;
    activeAnswer = answer;
    activeValue = value;
    activeQuestionId = questionId;
}

function goToQuestion(div, category, tier) {
    if (div.tagName == "SPAN") {
        div = div.parentElement;
    }
    else if (div.classList.contains("selection-category-entry")) {
        return;
    }

    div.style.zIndex = 999;

    let bbox = div.getBoundingClientRect();
    let distX = (window.innerWidth / 2) - (bbox.x + bbox.width / 2);
    let distY = (window.innerHeight / 2) - (bbox.y + bbox.height / 2);

    div.style.transition = "all 2.5s";
    div.style.transform = `translate(${distX}px, ${distY}px) scale(11)`;

    setTimeout(() => {
        window.location.href = getQuestionURL(activeRound, category, tier);
    }, 2800);
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
        playerTurn = player;
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
    playerTurn = -1;

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

function showFinaleCategory(category) {
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            let header1 = document.getElementById("selection-finale-header1");
            header1.style.setProperty("opacity", 1);
    
            setTimeout(function() {
                let header2 = document.getElementById("selection-finale-header2");
                header2.style.setProperty("opacity", 1);
    
                let header3 = document.getElementById("selection-finale-header3");
                header3.style.setProperty("opacity", 1);
            }, 2000);

            window.onkeydown = function(e) {
                if (e.key == "NumLock") {
                    window.location.href = getQuestionURL(3, category, 1);
                }
            }
        }
    }
}

function showFinaleResult() {
    let wagerDescElems = document.getElementsByClassName("finale-wager-desc");
    let wagerInputElems = document.getElementsByClassName("finale-wager-amount");

    function showNextResult(player) {
        let playerElem = ldocument.getElementsByClassName("finale-wager-name").item(player);
        playerElem.style.color = "#" + playerColors[player];
        playerElem.classList.remove("d-none");
        playerElem.style.opacity = 1;

        if (player == playerNames.length - 1) {
            setTimeout(function() {
                let teaserElem = document.getElementById("endscreen-teaser");
                teaserElem.style.opacity = 1;
                teaserElem.classList.remove("d-none");
            }, 1000);
        }

        window.onkeydown = function(e) {
            let descElem = wagerDescElems.item(player);
            let amount = parseInt(wagerInputElems.item(player).value);

            if (e.key == 1) {
                // Current player answered correctly
                descElem.classList.add("wager-answer-correct");
                descElem.textContent = `svarede rigtigt og vinder ${amount} GBP!`;
            }
            else if (e.key == 2) {
                // Current player answered incorrectly
                descElem.classList.add("wager-answer-wrong");
                descElem.textContent = `svarede forkert og taber ${amount} GBP!`;
            }
            else if (e.key == "NumLock") {
                if (i == playerNames.length) {
                    window.location.href = getEndscreenURL();
                }
                else {
                    showNextResult(player + 1)
                }
            }
        }
    }

    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            showNextResult(0);
        }
    }

    let answerElem = document.getElementById("finale-answer");
    answerElem.classList.remove("d-none");
    answerElem.style.opacity = 1;
}

function startWinnerParty() {
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            document.getElementById("endscreen-confetti-video").play();
            document.getElementById("endscreen-music").play();
            let overlay = document.getElementById("endscreen-techno-overlay");

            overlay.classList.remove("d-none");

            let colors = ["#1dd8267e", "#1d74d87e", "#c90f0f89", "#deb5117c"];
            let colorIndex = 0;

            let initialDelay = 320;
            let intervalDelay = 472;

            setTimeout(() => {
                overlay.style.backgroundColor = colors[colorIndex];
                colorIndex += 1;

                setInterval(() => {
                    overlay.style.backgroundColor = colors[colorIndex];
    
                    colorIndex += 1;
    
                    if (colorIndex == colors.length) {
                        colorIndex = 0;
                    }
                }, intervalDelay);
            }, initialDelay);
        }
    }
}