const TIME_FOR_BUZZING = 8;
const TIME_FOR_ANSWERING = 6;
const TIME_FOR_DOUBLE_ANSWER = 10;
const TIME_FOR_WAGERING = 60;
const TIME_FOR_FINAL_ANSWER = 40;
const socket = io();

var countdownInterval;
var activeRound;
var activeQuestionId;
var activeAnswer;
var activeValue = null;
var answeringPlayer = null;
var activePlayers = [];
var questionAnswered = false;
var isDailyDouble = false;
let chosenPlayers = [];
let menuPlayerData;

let playerTurn = 0;
var questionNum = 0;
var playerIds = [];
let playerColors = [];
var playerScores = [];

function canPlayersBuzzIn() {
    return activeRound < 3 && !isDailyDouble;
}

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port + "/intfar/jeopardy/presenter";
}

function getQueryParams() {
    // Encode player information and turns into URL query strings
    let playerNameQueries = new Array();
    playerIds.forEach((name, index) => {
        playerNameQueries.push(`i${index+1}=${encodeURIComponent(name)}`);
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

    return `${namesQueryStr}&${scoresQueryStr}&${colorsQueryStr}&turn=${playerTurn}&question=${questionNum}`
}

function getSelectionURL(round) {
    return `${getBaseURL()}/${round}?${getQueryParams()}`;
}

function getQuestionURL(round, category, difficulty) {
    return `${getBaseURL()}/${round}/${category}/${difficulty}?${getQueryParams()}`;
}

function getFinaleURL(question_id) {
    return `${getBaseURL()}/finale/${question_id}?${getQueryParams()}`;
}

function getEndscreenURL() {
    return `${getBaseURL()}/endscreen?${getQueryParams()}`;
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

function listenForBuzzIn() {
    if (activePlayers.length != 0) {
        socket.emit("enable_buzz", JSON.stringify(activePlayers));
    }
}

function afterQuestion() {
    activeAnswer = null;
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            questionNum += 1;
            window.location.href = getSelectionURL(activeRound);
        }
    }
}

function afterAnswer() {
    // Reset who is answering
    answeringPlayer = null;
    setPlayerTurn(-1, false);

    let buzzFeed = document.getElementById("question-buzz-feed");
    buzzFeed.classList.add("d-none");
    buzzFeed.getElementsByTagName("ul").item(0).innerHTML = "";

    if (activeAnswer == null) {
        socket.emit("disable_buzz");
        return;
    }

    let videoElem = document.getElementById("question-question-video");

    let delay = 4000;

    // Immediately allow other players to buzz in
    if (videoElem != null && !videoElem.ended) {
        videoElem.onended = afterShowQuestion;

        // Let players interrupt the video and buzz in early
        listenForBuzzIn();

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

function updatePlayerScore(player, delta) {
    playerScores[player] += delta;
    let scoreElem = document.getElementsByClassName("footer-contestant-entry-score").item(player);
    scoreElem.textContent = `${playerScores[player]} GBP`;
}

function correctAnswer() {
    let elem = document.getElementById("question-answer-correct");

    let valueElem = elem.getElementsByClassName("question-answer-value").item(0);
    valueElem.textContent = "+" + activeValue;

    let coinElem = elem.getElementsByClassName("question-result-gbp").item(0);
    if (coinElem.classList.contains("d-none")) {
        coinElem.classList.remove("d-none");
    }

    revealAnswerImageIfPresent();

    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playCorrectSound();
    }, 100);

    // Add value to player score
    updatePlayerScore(answeringPlayer, activeValue);

    if (playerTurn != answeringPlayer) {
        // Set player as having the turn, if they didn't already
        setPlayerTurn(answeringPlayer, true);
    }

    // Move on to next question
    afterQuestion();
    afterAnswer();
}

function wrongAnswer(reason) {
    let elem = document.getElementById("question-answer-wrong");
    let valueElem = elem.getElementsByClassName("question-answer-value").item(0);
    let coinElem = elem.getElementsByClassName("question-result-gbp").item(0);

    let reasonElem = document.getElementById("question-wrong-reason-text");
    reasonElem.textContent = reason;

    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playWrongSound();
    }, 100);

    if (answeringPlayer != null) {
        // Deduct points from player if someone buzzed in
        valueElem.textContent = "-" + activeValue;
        updatePlayerScore(answeringPlayer, -activeValue);

        if (coinElem.classList.contains("d-none")) {
            coinElem.classList.remove("d-none");
        }
    }

    let outOfTime = reason == "Ikke mere tid" && answeringPlayer == null;

    if (activePlayers.every((v) => !v) || outOfTime) {
        if (outOfTime && !coinElem.classList.contains("d-none")) {
            valueElem.textContent = "";
            coinElem.classList.add("d-none");
        }

        // No players are eligible to answer, go to next question
        revealAnswerImageIfPresent();

        let answerElem = document.getElementById("question-actual-answer");
        answerElem.classList.remove("d-none");

        afterQuestion();
    }
    afterAnswer();
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
            }, delay);
        }
        else {
            if (event.key == 1) {
                correctAnswer();
            }
            else {
                wrongAnswer("Forkert...");
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

function startCountdown(duration, callback=null) {
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
            if (callback != null) {
                callback();
            }
            else {
                wrongAnswer("Ikke mere tid");
            }
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

function startAnswerCountdown(duration) {
    startCountdown(duration, () => wrongAnswer("Ikke mere tid"));

    // NumLock has to be pressed before an answer can be given (for safety)
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            // Pause video if one is playing
            pauseVideo();

            // Clear countdown
            stopCountdown();

            window.onkeydown = function(e) {
                answerQuestion(e);
            }
        }
    }
}

function addToBuzzFeed(playerId, timeTaken) {
    let playerFooterElem = document.getElementsByClassName("footer-contestant-entry").item(playerId);
    let color = playerFooterElem.style.backgroundColor;
    let name = playerFooterElem.getElementsByClassName("footer-contestant-entry-name").item(0).textContent;

    let wrapper = document.getElementById("question-buzz-feed");
    wrapper.classList.remove("d-none");
    let listParent = wrapper.getElementsByTagName("ul").item(0);
    let listElem = document.createElement("li");
    listElem.innerHTML = `<span style="color: ${color}; font-weight: 800">${name}</span> buzzede ind efter ${timeTaken} sekunder`;
    listParent.appendChild(listElem);
}

function playerBuzzedIn(playerId, timeTaken, isWinner) {
    addToBuzzFeed(playerId, timeTaken);

    if (!isWinner || !activePlayers[playerId] || answeringPlayer != null) {
        return; // Player already buzzed in once this question or didn't buzz in first
    }

    // Buzzer has been hit, let the player answer.
    answeringPlayer = playerId;
    activePlayers[playerId] = false;
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
        startAnswerCountdown(TIME_FOR_ANSWERING);
    }, 500);
}

function questionAsked(countdownDelay) {
    setTimeout(function() {
        if (answeringPlayer == null && canPlayersBuzzIn()) {
            hideAnswerIndicator();
            startCountdown(TIME_FOR_BUZZING);
        }
        else if (isDailyDouble) {
            startAnswerCountdown(TIME_FOR_DOUBLE_ANSWER);
        }
        else {
            // Go to finale screen after countdown is finished if it's round 3
            document.getElementById("question-finale-suspense").play();
            startCountdown(TIME_FOR_FINAL_ANSWER, () => window.location.href = getFinaleURL(activeQuestionId));
        }
    }, countdownDelay);

    if (canPlayersBuzzIn()) {
        // Enable participants to buzz in if we are in round 1 or 2
        listenForBuzzIn();
    }
    else if (isDailyDouble) {
        answeringPlayer = playerTurn;
        setPlayerTurn(answeringPlayer, false);
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
    if (activePlayers.length != 0) {
        return;
    }

    for (let i = 0; i < playerIds.length; i++) {
        activePlayers.push(isDailyDouble ? false : true);
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

                        if (canPlayersBuzzIn()) {
                            // Let players interrupt the video and buzz in early
                            listenForBuzzIn();
                        }
                    }
                }
            }
        }
        else {
            if (isQuestionMultipleChoice()) {
                imageElem.style.opacity = 1;
                afterShowQuestion();
            }
            else {
                window.onkeydown = function(e) {
                    if (e.key == "NumLock") {
                        imageElem.style.opacity = 1;
                        afterShowQuestion();
                    }
                }
            }
        }
    }
    else {
        afterShowQuestion();
    }
}

function afterDailyDoubleWager(amount) {
    let wrapper = document.getElementById("question-wager-wrapper");
    if (wrapper.classList.contains("d-none")) {
        return;
    }
    activeValue = amount;
    wrapper.classList.add("d-none");
    showQuestion();
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

function setVariables(round, playerData, turn, question, answer=null, value=null, questionId=null, dailyDouble=false) {
    activeRound = round;
    playerData.forEach((data) => {
        playerIds.push(data["disc_id"]);
        playerScores.push(data["score"]);
        playerColors.push(data["color"]);
    });
    playerTurn = turn;
    questionNum = question;
    activeAnswer = answer;
    activeValue = value;
    activeQuestionId = questionId;
    isDailyDouble = dailyDouble;
}

function goToQuestion(div, category, tier, isDouble) {
    if (activeRound == 1 && playerTurn == -1) {
        alert("Choose a starting player first (you idiot)");
        return;
    }

    if (div.tagName == "SPAN") {
        div = div.parentElement;
    }
    else if (div.classList.contains("selection-category-entry")) {
        return;
    }

    div.style.zIndex = 999;

    if (isDouble) {
        div.getElementsByTagName("span").item(0).textContent = "Daily Double!";
    }

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
    let contestantEntries = document.getElementsByClassName("footer-contestant-entry");
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

function chooseStartingPlayer(callback) {
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
            else {
                callback(player);
            }
        }, wait);
    }

    showStartPlayerCandidate(0);

    let questionBoxes = document.getElementsByClassName("selection-question-box");
    for (let i = 0; i < questionBoxes.length; i++) {
        questionBoxes.item(i).classList.remove("inactive");
    }

    return player;
}

function beginJeopardy() {
    let contestantEntries = document.getElementsByClassName("menu-contestant-entry");

    playerIds = [];
    playerColors = [];
    playerScores = [];
    playerTurn = -1;

    for (let i = 0; i < contestantEntries.length; i++) {
        let elem = contestantEntries.item(i);
        playerIds.push(elem.dataset["disc_id"]);
        playerColors.push(elem.dataset["color"].replace("#", ""));
        playerScores.push(0);
    }

    window.location.href = getSelectionURL(1);
}

function resetUsedQuestions(button) {
    let baseUrl = getBaseURL();
    $.ajax(baseUrl + "/reset_questions", {
        method: "POST"
    }).then((data) => {
        console.log(data)
        button.style.backgroundColor = "rgb(9, 142, 24)";
    }, (error) => {
        console.log("ERROR when resetting questions: " + error);
        button.style.backgroundColor = "red";
    });
}

function addPlayerDiv(id, index, name, avatar, color) {
    let wrapper = document.getElementById("menu-contestants");

    let div = document.createElement("div");
    div.dataset["disc_id"] = id;
    div.dataset["color"] = color;
    div.className = "menu-contestant-entry";
    div.style.border = "2px solid " + color;

    let avatarElem = document.createElement("img");
    avatarElem.className = "menu-contestant-avatar";
    avatarElem.src = avatar;

    let nameElem = document.createElement("div");
    nameElem.className = "menu-contestant-id";
    nameElem.textContent = name;

    div.appendChild(avatarElem);
    div.appendChild(nameElem);

    if (index >= wrapper.children.length) {
        wrapper.appendChild(div);
    }
    else {
        wrapper.insertBefore(div, wrapper.children[index]);
    }
}

function monitorPlayersJoining() {
    socket.on("player_joined", addPlayerDiv);
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

            setTimeout(function() {
                document.getElementById("selection-jeopardy-theme").play();
            }, 3000);

            window.onkeydown = function(e) {
                if (e.key == "NumLock") {
                    window.location.href = getQuestionURL(3, category, 5);
                }
            }
        }
    }
}

function showFinaleResult() {
    let wagerDescElems = document.getElementsByClassName("finale-result-desc");
    let wagerInputElems = document.getElementsByClassName("finale-wager-amount");

    function showNextResult(player) {
        if (player == 0) {
            document.getElementById("finale-results-wrapper").style.opacity = 1;
        }

        if (player == playerIds.length) {
            let teaserElem = document.getElementById("endscreen-teaser");
            teaserElem.style.opacity = 1;

            setTimeout(function() {
                window.location.href = getEndscreenURL();
            }, 2000);
        }
        else {
            let playerElem = document.getElementsByClassName("finale-result-name").item(player);
            playerElem.style.color = "#" + playerColors[player];
            playerElem.style.opacity = 1;
    
            window.onkeydown = function(e) {
                let descElem = wagerDescElems.item(player);
                let amount = parseInt(wagerInputElems.item(player).textContent);
    
                if (e.key == 1) {
                    // Current player answered correctly
                    descElem.style.opacity = 1;
                    descElem.classList.add("wager-answer-correct");
                    descElem.innerHTML = `og <strong>vinder ${amount} GBP</strong>!`;
                    playerScores[player] += amount;
                }
                else if (e.key == 2) {
                    // Current player answered incorrectly
                    descElem.style.opacity = 1;
                    descElem.classList.add("wager-answer-wrong");
                    descElem.innerHTML = `og <strong>taber ${amount} GBP</strong>!`;
                    playerScores[player] -= amount;
                }
                else if (e.key == "NumLock") {
                    showNextResult(player + 1);
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
    answerElem.style.opacity = 1;
}

function startWinnerParty() {
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            document.getElementById("endscreen-confetti-video").play();
            document.getElementById("endscreen-music").play();
            let overlay = document.getElementById("endscreen-techno-overlay");

            overlay.classList.remove("d-none");

            let colors = ["#1dd8265e", "#1d74d85e", "#c90f0f69", "#deb5115c"];
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

function setVolume() {
    for (let volume = 1; volume <= 10; volume++) {
        let className = "volume-" + volume;
        let elems = document.getElementsByClassName(className);
        for (let i = 0; i < elems.length; i++) {
            elems.item(i).volume = parseFloat("0." + volume);
        }
    }
}

function champOPGG() {
    let tableRows = document.querySelector(".content > table").getElementsByTagName("tr");
    let playedDict = {};

    for (let i = 0; i < tableRows.length; i++) {
        let row = tableRows.item(i);
        let tdEntries = row.getElementsByTagName("td");
        if (tdEntries.length == 0) {
            continue;
        }

        let champName = tdEntries.item(1).getElementsByClassName("summoner-name").item(0).children[0].textContent;

        let playedEntry = tdEntries.item(2);
        let winRatioElem = playedEntry.getElementsByClassName("win-ratio");
        if (winRatioElem.length == 0) {
            playedDict[champName.replace('"', "").replace('"', "").trim()] = parseInt(playedEntry.textContent.replace("Played", ""));
        }
        else {
            let played = 0;
            let left = winRatioElem.item(0).getElementsByClassName("winratio-graph__text left");
            if (left.length != 0) {
                played += parseInt(left.item(0).textContent.replace("W", ""));
            }
            let right = winRatioElem.item(0).getElementsByClassName("winratio-graph__text right");
            if (right.length != 0) {
                played += parseInt(right.item(0).textContent.replace("L", ""));
            }

            playedDict[champName] = played;
        }
    }

    return playedDict;
}

function mergeOPGG(stats) {
    let playedDict = stuffs();
    for (var champ in playedDict) { stats[champ] = playedDict[champ] + (stats[champ] || 0); }
    return stats;
}
