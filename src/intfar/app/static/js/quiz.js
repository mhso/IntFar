const POINT_GAIN_CORRECT = [2, 3, 4];
const POINT_LOSSES_WRONG = [0, 1, 2];

var countdownInterval;
var activeTeamBlue;
var activeRound;
var activeAnswer;
var questionAnswered = false;

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
                setBackgroundColor(activeTeamBlue ? "True" : "False");
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

function setVariables(answer, round, isTeamBlue) {
    activeAnswer = answer;
    activeRound = Number.parseInt(round);
    if (round != 2) {
        activeTeamBlue = isTeamBlue == "True";
    }
}

function setBackgroundColor(isTeamBlue) {
    let elem = document.getElementById("bg-image");
    let color = null;
    if (isTeamBlue == "True") {
        //color = "linear-gradient(to right bottom, rgb(94, 106, 172) 25%, rgb(69, 75, 113) 50%, rgb(78, 85, 106) 100%)";
        color = "rgba(0, 135, 255, 0.3)";
    }
    else {
        //color = "linear-gradient(to right bottom, rgb(140, 54, 61) 25%, rgb(113, 42, 42) 50%, rgb(134, 56, 56) 100%)";
        color = "rgba(255, 0, 0, 0.3)";
    }

    elem.style.backgroundColor = color;
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

function beginQuiz() {
    let blueTeam = document.getElementById("quiz-team-blue").value;
    let redTeam = document.getElementById("quiz-team-red").value;

    // Save cookies with team names.
    let date = new Date();
    date.setTime(date.getTime() + (6 * 60 * 60 * 1000));
    document.cookie = "team_blue=" + blueTeam + "; expires=" + date.toUTCString() + "; path=/intfar/quiz; samesite=strict";
    document.cookie = "team_red=" + redTeam + "; expires=" + date.toUTCString() + "; path=/intfar/quiz; samesite=strict";

    window.location.href = getBaseURL() + "/intfar/quiz/1/1"
}

function resetUsedQuestions(button) {
    let baseUrl = getBaseURL();
    $.ajax(baseUrl + "/intfar/quiz/reset_questions", {
        method: "POST"
    }).then((data) => {
        console.log(data)
        button.style.backgroundColor = "rgb(9, 142, 24)";
    }, (error) => {
        console.log("ERROR when resetting questions: " + error);
        button.style.backgroundColor = "red";
    });
}

function addWinnerSoundEvent() {
    window.onkeydown = function(e) {
        if (e.key == "NumLock") {
            document.getElementById("score-winner-sound").play();
        }
    }
}