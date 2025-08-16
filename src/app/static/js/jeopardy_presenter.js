const TIME_FOR_ANSWERING = 6;
const TIME_FOR_DOUBLE_ANSWER = 10;
const TIME_FOR_WAGERING = 60;
const TIME_FOR_FINAL_ANSWER = 40;
const TIME_BEFORE_FIRST_TIP = 4;
const TIME_BEFORE_EXTRA_TIPS = 4;
const IMG_MAX_HEIGHT = 420;
const PRESENTER_ACTION_KEY = "Space"
const socket = io({"transports": ["websocket", "polling"]});

var countdownInterval = null;
var activeRound;
var totalRounds;
var activeQuestionId;
var activeAnswer;
var activeValue = null;
var answeringPlayer = null;
var activePlayers = [];
var questionAnswered = false;
var buzzInTime = 10;
var isDailyDouble = false;
var activePowerUp = null;

let playerTurn = 0;
var questionNum = 0;
var playerIds = [];
var playerNames = [];
var playerScores = [];
let playerColors = [];
let playersBuzzedIn = [];

function canPlayersBuzzIn() {
    return activeRound < totalRounds && !isDailyDouble;
}

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port + "/intfar/jeopardy/presenter";
}

function getQueryParams() {
    // Encode player information and turns into URL query strings
    let playerIdQueries = new Array();
    playerIds.forEach((discId, index) => {
        playerIdQueries.push(`i${index+1}=${encodeURIComponent(discId)}`);
    });
    let idsQueryStr = playerIdQueries.join("&");

    let playerNameQueries = new Array();
    playerNames.forEach((name, index) => {
        playerNameQueries.push(`n${index+1}=${encodeURIComponent(name)}`);
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

    return `${idsQueryStr}&${scoresQueryStr}&${namesQueryStr}&${colorsQueryStr}&turn=${playerTurn}&question=${questionNum}`
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

function playCorrectSound() {
    let sound = document.getElementById("question-sound-correct");
    sound.play();
}

function playWrongSound() {
    let sounds = document.getElementsByClassName("question-sound-wrong");
    for (let i = 0; i < sounds.length; i++) {
        let sound = sounds.item(i);
        if (!sound.classList.contains("played")) {
            sound.play();
            sound.classList.add("played");
            return;
        }
    }
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

function disableBuzzIn() {
    socket.emit("disable_buzz");
}

function enablePowerUp(playerId, powerId) {
    socket.emit("enable_powerup", playerId, powerId);
}

function disablePowerUp(playerId=null, powerId=null) {
    socket.emit("disable_powerup", playerId, powerId);
}

function afterQuestion() {
    activeAnswer = null;
    hideTips();

    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
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
        // Question has been answered or time ran out
        if (!isDailyDouble) {
            disableBuzzIn();
        }
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
            if (answeringPlayer == null && activeAnswer != null) {
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
    // Disable all power-ups after question has been answered correctly
    disablePowerUp();
    activePowerUp = null;

    let elem = document.getElementById("question-answer-correct");

    let valueElem = elem.getElementsByClassName("question-answer-value").item(0);

    // Reduce the value of the question if tips are shown
    let shownTips = document.getElementsByClassName("tip-shown").length;
    activeValue *= (1 / 2 ** shownTips);

    // Reduce the value of the question by how few multiple choice answer are left
    let wrongAnswers = document.getElementsByClassName("question-answered-wrong").length;
    activeValue *= (1 / 2 ** wrongAnswers);

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

    // Send update to server
    socket.emit("correct_answer", answeringPlayer, activeValue);

    // Move on to next question
    afterQuestion();
    afterAnswer();
}

function wrongAnswer(reason, questionOver=false) {
    let outOfTime = questionOver && answeringPlayer == null;

    if (outOfTime) {
        // Disable all power-ups if time ran out
        disablePowerUp();
        activePowerUp = null;
    }

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

        // Send update to server
        socket.emit("wrong_answer", answeringPlayer);

        // Disable the use of 'freeze' power up, enable the use of 'rewind'
        activePowerUp = null;
        disablePowerUp(playerIds[answeringPlayer], "freeze");
        enablePowerUp(playerIds[answeringPlayer], "rewind");
    }

    if (activePlayers.every(v => !v) || outOfTime) {
        // No players are eligible to answer, go to next question
        if (outOfTime && !coinElem.classList.contains("d-none")) {
            valueElem.textContent = "";
            coinElem.classList.add("d-none");
        }

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
    if (!countdownElem.classList.contains("d-none")) {
        countdownElem.classList.add("d-none");
        countdownElem.style.opacity = 0;
    }
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

                if (answerElem.textContent === activeAnswer) {
                    elem.classList.add("question-answered-correct");
                    correctAnswer();
                }
                else {
                    elem.classList.add("question-answered-wrong");
                    wrongAnswer("Forkert...", false);
                }
            }, delay);
        }
        else {
            if (event.key == 1) {
                correctAnswer();
            }
            else {
                wrongAnswer("Forkert...", false);
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
                wrongAnswer("Ikke mere tid", true);
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
    startCountdown(duration, () => wrongAnswer("Ikke mere tid", true));

    // Action key has to be pressed before an answer can be given (for safety)
    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
            // Disable 'hijack' power-up after an answer has been given
            disablePowerUp(null, "hijack");

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

function getPlayerNameAndColor(playerId) {
    let playerFooterElem = document.getElementsByClassName("footer-contestant-entry").item(playerId);
    let color = playerFooterElem.style.backgroundColor;
    let name = playerFooterElem.getElementsByClassName("footer-contestant-entry-name").item(0).textContent;

    return [name, color];
}

function addToGameFeed(text) {
    let wrapper = document.getElementById("question-buzz-feed");
    wrapper.classList.remove("d-none");

    let listParent = wrapper.getElementsByTagName("ul").item(0);

    let listElem = document.createElement("li");
    listElem.innerHTML = text;

    listParent.appendChild(listElem);
}

function addBuzzToFeed(playerId, timeTaken) {
    if (playersBuzzedIn.includes(playerId)) {
        return;
    }

    let [name, color] = getPlayerNameAndColor(playerId);
    addToGameFeed(`<span style="color: ${color}; font-weight: 800">${name}</span> buzzede ind efter ${timeTaken} sekunder`);
}

function addPowerUseToFeed(playerId, powerId) {
    let [name, color] = getPlayerNameAndColor(playerId);
    addToGameFeed(`<span color='${color}'>${name}</span> brugte sin <strong>${powerId}</strong> power-up!`);
}

function afterBuzzIn(playerId) {
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

        // Enable 'freeze' for player who buzzed
        enablePowerUp(playerIds[playerId], "freeze");
    }, 500);
}

function playerBuzzedFirst(playerId) {
    if (activePowerUp != null) {
        return;
    }

    playersBuzzedIn.push(playerId);

    if (!activePlayers[playerId] || answeringPlayer != null) {
        return;
    }

    // Buzzer has been hit, let the player answer.
    answeringPlayer = playerId;
    activePlayers[playerId] = false;
    document.getElementById("question-buzzer-sound").play();
    setTimeout(function() {
        document.getElementById("question-buzzer-" + playerIds[playerId]).play();
    }, 600);

    afterBuzzIn(playerId);
}

function showPowerUpVideo(powerId) {
    return new Promise((resolve) => {
        let wrapper = document.getElementById("question-power-up-splash");
        wrapper.classList.remove("d-none");
    
        let video = wrapper.getElementsByTagName("video").item(0);
    
        video.onended = function() {
            wrapper.classList.add("d-none");
            resolve();
        };
    
        video.play();
    
        let powerUpIcon = document.getElementById(`question-power-up-${powerId}`);
        powerUpIcon.classList.remove("d-none");
    
        setTimeout(function() {
            powerUpIcon.classList.add("d-none");
        }, 3000);
    });
}

function onFreezeUsed() {
    stopCountdown();
}

function onRewindUsed(playerId) {
    if (answeringPlayer != null) {
        stopCountdown();
    }

    // Refund the score the player lost on the previous answer
    answeringPlayer = playerId;
    updatePlayerScore(answeringPlayer, activeValue);
}

function afterRewindUsed(playerId) {
    afterBuzzIn(playerId);
}

function onHijackUsed() {
    // If question has not been asked yet, hijack gives bonus points
    let beforeQuestionAsked = activePlayers.length == 0
    let afterBuzzIn = answeringPlayer != null;

    if (!beforeQuestionAsked && afterBuzzIn) {
        stopCountdown();
    }

    return [beforeQuestionAsked, afterBuzzIn];
}

function afterHijackUsed(playerId, beforeQuestionAsked, afterBuzzIn) {
    answeringPlayer = playerId;
    activePlayers = [];

    for (let i = 0; i < playerIds.length; i++) {
        activePlayers.push(false);
    }

    if (!beforeQuestionAsked) {
        afterBuzzIn(playerId);
    }
}

function powerUpUsed(playerId, powerId) {
    activePowerUp = powerId;
    window.onkeydown = null;

    console.log(`Player ${playerId} used power '${powerId}'`);

    callback = null;
    if (powerId == "freeze") {
        onFreezeUsed();
    }
    else if (powerId == "rewind") {
        onRewindUsed(playerId);
        callback = () => afterRewindUsed(playerId);
    }
    else {
        let [beforeQuestionAsked, afterBuzzIn] = onHijackUsed();
        callback = () => afterHijackUsed(playerId, beforeQuestionAsked, afterBuzzIn);
    }

    addPowerUseToFeed(playerId, powerId);
    showPowerUpVideo(powerId, playerId).then(() => {
        if (callback) callback();
    });
}

function hideTips() {
    let tipElems = document.getElementsByClassName("question-tip-wrapper");
    for (let i = 0; i < tipElems.length; i++) {
        tipElems.item(i).classList.add("d-none");
    }
}

function showTip(index) {
    let tipElems = document.getElementsByClassName("question-tip-wrapper");
    if (index >= tipElems.length) {
        return;
    }

    delay = index == 0 ? TIME_BEFORE_FIRST_TIP : TIME_BEFORE_EXTRA_TIPS;
    setTimeout(function() {
        if (activeAnswer == null) {
            // Question is over, don't show tip
            return;
        }
        if (answeringPlayer != null) {
            // Player is answering, don't show more tips while they answer
            showTip(index);
            return
        }
    
        let tipElem = tipElems.item(index);
        tipElem.style.setProperty("opacity", 1);
        tipElem.classList.add("tip-shown");

        showTip(index + 1);
    }, delay * 1000);
}

function questionAsked(countdownDelay) {
    window.onkeydown = null;
    setTimeout(function() {
        if (!activeAnswer) {
            return;
        }

        if (answeringPlayer == null && canPlayersBuzzIn()) {
            hideAnswerIndicator();
            showTip(0);
            if (buzzInTime == 0) {
                // Question has no timer, contestants can take their time
                window.onkeydown = function(e) {
                    if (e.code == PRESENTER_ACTION_KEY) {
                        wrongAnswer("Ingen kan/tør svare");
                    }
                };
            }
            else {
                startCountdown(buzzInTime);
            }
        }
        else if (isDailyDouble || activePowerUp == "hijack") {
            let timeToAnswer = isDailyDouble ? TIME_FOR_DOUBLE_ANSWER : buzzInTime;
            startAnswerCountdown(timeToAnswer);
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

    if (index == 3) {
        questionAsked(500);
    }
    else {
        window.onkeydown = function(e) {
            if (e.code == PRESENTER_ACTION_KEY) {
                showAnswerChoice(index + 1);
            }
        }
    }
}

function afterShowQuestion() {
    if (isQuestionMultipleChoice()) {
        window.onkeydown = function(e) {
            if (e.code == PRESENTER_ACTION_KEY) {
                showAnswerChoice(0);
            }
        }
    }
    else {
        questionAsked(500);
    }
}

function showImageOrVideo(elem) {
    if (elem.offsetHeight > IMG_MAX_HEIGHT) {
        document.getElementById("question-category-header").style.display = "none";
        document.getElementById("question-question-header").style.display = "none";
    }
    elem.style.opacity = 1;
}

function showQuestion() {
    for (let i = 0; i < playerIds.length; i++) {
        activePlayers.push(!isDailyDouble);
    }

    // Show the question, if it exists
    let questionElem = document.getElementById("question-question-header");
    if (questionElem != null) {
        questionElem.style.opacity = 1;
    }

    let questionImage = document.getElementById("question-question-image");
    let answerImage = document.getElementById("question-answer-image");
    let videoElem = document.getElementById("question-question-video");

    if (answerImage != null || videoElem != null) {
        // If there is an answer image, first show the question, then show
        // the image after pressing action key again. Otherwise show image instantly
        window.onkeydown = function(e) {
            if (e.code == PRESENTER_ACTION_KEY) {
                if (questionImage != null) {
                    showImageOrVideo(questionImage);
                    afterShowQuestion();
                }
                else {
                    showImageOrVideo(videoElem);
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
        // If there is no answer image, either show answer choices if question
        // is multiple choice, otherwise show question image/video
        if (isQuestionMultipleChoice()) {
            if (questionImage != null) {
                showImageOrVideo(questionImage);
            }
            afterShowQuestion();
        }
        else {
            if (questionImage != null) {
                showImageOrVideo(questionImage);
            }
            window.onkeydown = function(e) {
                if (e.code == PRESENTER_ACTION_KEY) {
                    afterShowQuestion();
                }
            }
        }
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

function setVariables(round, maxRounds, playerData, turn, question, answer=null, value=null, questionId=null, buzzTime=10, dailyDouble=false) {
    activeRound = round;
    totalRounds = maxRounds;
    playerData.forEach((data) => {
        playerIds.push(data["disc_id"]);
        playerScores.push(data["score"]);
        playerNames.push(data["name"]);
        playerColors.push(data["color"]);
    });
    playerTurn = turn;
    questionNum = question;
    activeAnswer = answer;
    activeValue = value;
    activeQuestionId = questionId;
    buzzInTime = buzzTime;
    isDailyDouble = dailyDouble;
}

function goToQuestion(div, category, tier, isDouble) {
    if (activeRound == 1 && playerTurn == -1) {
        alert("Choose a starting player first (you bellend)");
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
        div.style.animationName = "dailyDouble";
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

function goToSelectedCategory() {
    let boxes = document.getElementsByClassName("selection-question-box");
    for (let i = 0; i < boxes.length; i++) {
        let box = boxes.item(i);
        if (box.classList.contains("selected")) {
            box.classList.remove("selected");
            box.click();
            break;
        }
    }
}

function tabulateCategorySelection(key, cols) {
    // Find currently selected category box, if any
    let boxes = document.getElementsByClassName("selection-question-box");
    let selectedBox = null;
    let selectedIndex = 0;
    for (let i = 0; i < boxes.length; i++) {
        let box = boxes.item(i);
        if (box.classList.contains("selected")) {
            selectedBox = box;
            selectedIndex = i;
            break
        }
    }

    // Choose the next selected box based on input
    const rows = 5;
    let maxIndex = (cols + 1) * rows - 1;
    if (key == "ArrowRight") {
        selectedIndex = selectedBox == null ? 0 : selectedIndex + cols;
        if (selectedIndex > maxIndex) {
            selectedIndex = selectedIndex - maxIndex - 1;
        }
    }
    else if (key == "ArrowLeft") {
        selectedIndex = selectedBox == null ? cols * rows : selectedIndex - cols;
        if (selectedIndex < 0) {
            selectedIndex = maxIndex + selectedIndex + 1;
        }
    }
    else if (key == "ArrowUp") {
        selectedIndex = selectedBox == null ? cols : Math.max(selectedIndex - 1, 0);
    }
    else if (key == "ArrowDown") {
        selectedIndex = selectedBox == null ? 0 : Math.min(selectedIndex + 1, maxIndex);
    }

    if (selectedBox != null) {
        selectedBox.classList.remove("selected");
    }

    boxes.item(selectedIndex).classList.add("selected");
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
        let entry = playerEntries.item(i);
        if (entry.classList.contains("active-contestant-entry")) {
            entry.classList.remove("active-contestant-entry");
        }

        if (i == player) {
            entry.classList.add("active-contestant-entry");
        }
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

    function showStartPlayerCandidate(iter) {
        let wait = minWait + (maxWait - minWait) * (iter / iters);

        setTimeout(() => {
            player = iter % playerEntries.length;
            setPlayerTurn(player, false);

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
}

function beginJeopardy() {
    let contestantEntries = document.getElementsByClassName("menu-contestant-entry");

    playerIds = [];
    playerNames = [];
    playerColors = [];
    playerScores = [];
    playerTurn = -1;

    for (let i = 0; i < contestantEntries.length; i++) {
        let elem = contestantEntries.item(i);
        let nameElem = elem.getElementsByClassName("menu-contestant-id").item(0);
        playerIds.push(elem.dataset["disc_id"]);
        playerNames.push(nameElem.textContent);
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
        button.style.backgroundColor = "rgb(9, 142, 24)";
    }, (error) => {
        console.log("ERROR when resetting questions: " + error);
        button.style.backgroundColor = "red";
    });
}

function addPlayerDiv(id, index, name, avatar, color) {
    let wrapper = document.getElementById("menu-contestants");
    let placeholder = document.getElementById("menu-no-contestants-placeholder");
    if (placeholder != null) {
        wrapper.removeChild(placeholder);
    }

    let divId = "player_" + id;
    let existingDiv = document.getElementById(divId);
    let div = existingDiv != null ? existingDiv : document.createElement("div");

    div.id = divId;
    div.dataset["disc_id"] = id;
    div.dataset["index"] = index;
    div.dataset["color"] = color;
    div.className = "menu-contestant-entry";
    div.style.border = "2px solid " + color;

    if (existingDiv == null) {
        let avatarElem = document.createElement("img");
        avatarElem.className = "menu-contestant-avatar";
        avatarElem.src = avatar;
    
        let nameElem = document.createElement("div");
        nameElem.className = "menu-contestant-id";
        nameElem.textContent = name;
    
        div.appendChild(avatarElem);
        div.appendChild(nameElem);

        // Find the index of the contestant
        for (let i = 0; i < wrapper.children.length; i++) {
            let child = wrapper.children[i];
            if (child.dataset["index"] > index) {
                wrapper.insertBefore(div, child);
                return;
            }
        }
        wrapper.appendChild(div);
    }
}

function setPlayerReady(index) {
    console.log("Setting ready state for player:", index);
    let wrappers = document.getElementsByClassName("footer-contestant-entry");
    for (let i = 0; i < wrappers.length; i++) {
        let wrapper = wrappers.item(i);
        if (wrapper.dataset["index"] == index) {
            let readyIcon = wrapper.getElementsByClassName("footer-contestant-entry-ready").item(0);
            readyIcon.style.display = "block";
            break;
        }
    }
}

function showFinaleCategory(final_round, category) {
    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
            let header1 = document.getElementById("selection-finale-header1");
            header1.style.setProperty("opacity", 1);

            setTimeout(function() {
                let header2 = document.getElementById("selection-finale-header2");
                header2.style.setProperty("opacity", 1);

                let header3 = document.getElementById("selection-finale-header3");
                header3.style.setProperty("opacity", 1);
            }, 2000);

            setTimeout(function() {
                socket.emit("enable_finale_wager");
                document.getElementById("selection-jeopardy-theme").play();

                window.onkeydown = function(e) {
                    if (e.code == PRESENTER_ACTION_KEY) {
                        window.location.href = getQuestionURL(final_round, category, 5);
                    }
                }
            }, 3000);
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

                let amountRaw = wagerInputElems.item(player).textContent;
                let amount = 0;
                if (amountRaw != "intet") {
                    amount = parseInt(amountRaw);
                }

                if (e.key == 1 || e.key == 2) {
                    descElem.style.opacity = 1;
                    let className = null;
                    let desc = null;

                    if (amount == 0) { // Current player did not answer
                        className = "wager-answer-skipped";
                        desc = "og intet ændrer sig"
                    }
                    else if (e.key == 1) { // Current player answered correctly
                        className = "wager-answer-correct";
                        desc = `og <strong>vinder ${amount} GBP</strong>!`;
                    }
                    else if (e.key == 2) { // Current player answered incorrectly
                        className = "wager-answer-wrong";
                        desc = `og <strong>taber ${amount} GBP</strong>!`;
                    }

                    descElem.classList.add(className);
                    descElem.innerHTML = desc;
                    updatePlayerScore(player, amount);
                }
                else if (e.code == PRESENTER_ACTION_KEY) {
                    showNextResult(player + 1);
                }
            }
        }
    }

    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
            showNextResult(0);
        }
    }

    let answerElem = document.getElementById("finale-answer");
    answerElem.style.opacity = 1;
}

function startWinnerParty() {
    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
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
    let playedDict = champOPGG();
    for (var champ in playedDict) { stats[champ] = playedDict[champ] + (stats[champ] || 0); }
    return stats;
}
