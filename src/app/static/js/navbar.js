var gameIsActive = false;
var activeGameGuilds = [];
var activeGamesData = [];
var monitorInterval = null;
var scrollIndex = 0;

function getBaseURL(game=null) {
    let base = window.location.protocol + "//" + window.location.hostname + ":" + window.location.port + "/intfar";
    if (game != null) {
        return base + "/" + game
    }
    return base;
}

function formatDuration(duration) {
    let secs = duration;
    let mins = 0;
    if (duration >= 60) {
        mins = secs / 60;
        secs = secs % 60;
    }
    let secDesc = secs > 1 ? " secs." : " sec.";
    let result = Number.parseInt(secs) + "" + secDesc;
    if (mins > 0) {
        let minDesc = mins > 1 ? " mins." : " min.";
        result = Number.parseInt(mins) + "" + minDesc + " & " + result;
    }
    return result;
}

function setActiveGuilds(activeGuilds) {
    activeGameGuilds = [];
    for (let i = 0; i < activeGuilds.length; i++) {
        activeGameGuilds.push(activeGuilds[2]);
    }
}

function removeGameDivs() {
    let wrapper = document.getElementsByClassName("navbar-active-game-wrapper").item(0);
    while (wrapper.children.length > 0) {
        wrapper.removeChild(wrapper.children[0]);
    }
}

function createActiveGameDiv(gameData) {
    removeGameDivs();
    let wrapper = document.getElementsByClassName("navbar-active-game-wrapper").item(0);

    for (let i = 0; i < gameData.length; i++) {
        let gameDuration = gameData[i][0];
        let gameMode = gameData[i][1];
        let gameGuild = gameData[i][2];
        let gameDiv = document.createElement("div");
        gameDiv.className = "navbar-active-game";
        gameDiv.innerHTML = (
            "Active game: <span class='active-game-mode'>" + gameMode + "</span> in <span class='emph'>" + gameGuild +  "</span><br>" +
            "Time since start: <span class='active-game-duration'>" + gameDuration + " secs.</span>"
        )
        wrapper.appendChild(gameDiv);
    }
}

function activeGamesChanged(activeGames) {
    if (activeGames.length != activeGameGuilds.length) {
        return true;
    }
    for (let i = 0; i < activeGames.length; i++) {
        if (activeGames[i][2] != activeGameGuilds[i]) {
            return true;
        }
    }
    return false;
}

function resizeNav() {
    let wrapper = document.getElementsByClassName("intfar-navbar").item(0);
    let navHeight = 50;
    if (window.outerWidth < 992) {
        if (activeGamesData.length > 0) {
            navHeight += 45;
        }
        if (window.outerWidth < 600) {
            navHeight += 25;
        }
    }
    wrapper.style.setProperty("height", navHeight + "px");
}

function hideDropdownMenu(menu) {
    menu.style.opacity = 0;
    setTimeout(function() {
        menu.style.display = "none";
    }, 1000);
}

function toggleDropdownMenu() {
    let elem = document.getElementById("navbar-menu-dropdown");
    if (elem.style.display == "block") {
        hideDropdownMenu(elem);
    }
    else {
        elem.style.opacity = 0;
        elem.style.display = "block";
        elem.style.opacity = 1;

        // window.addEventListener("click", function(event) {
        //     if (event.target != elem) {
        //         hideDropdownMenu(elem);
        //         window.removeEventListener("click", this);
        //     }
        // })
    }
}

function startMonitor(game) {
    let delaySecs = 60;
    monitorInterval = setInterval(function() {
        let baseUrl = getBaseURL(game);
        $.ajax(baseUrl + "/active_game", {
            method: "GET"
        }).then((objData) => {
            let data = JSON.parse(objData.response.split("'").join("\""));
            if (activeGamesChanged(data)) {
                createActiveGameDiv(data);
            }
            setActiveGuilds(data);
            activeGamesData = data;
            if (!gameIsActive) {
                resizeNav();
                gameIsActive = true;
                updateDuration();
            }
        }, (error) => {
            removeGameDivs();
            activeGamesData = [];
            gameIsActive = false;
        });
    }, delaySecs * 1000);
}

function parseData(data) {
    let regexNames = RegExp("(\&\#39\;([^#]+)\&\#39\;)", "g");
    let regexNum = RegExp("([0-9]+\.[0-9]+)\,", "g");

    let parsedNames = [];
    while (true) {
        let stuff = regexNames.exec(data)
        if (stuff == null) {
            break;
        }
        parsedNames.push(stuff[2]);
    }
    let parsedNums = [];
    while (true) {
        let stuff = regexNum.exec(data);
        if (stuff == null) {
            break;
        }
        parsedNums.push(stuff[1]);
    }

    let reshaped = [];
    for (let i = 0; i < parsedNums.length; i++) {
        let array = [];
        array.push(parsedNums[i]);
        array.push(parsedNames[i*2]);
        array.push(parsedNames[i*2+1]);
        reshaped.push(array);
    }

    let parsedData = reshaped;
    setActiveGuilds(parsedData);
    activeGamesData = parsedData;
    resizeNav();
    updateDuration();
}

function scrollToNewGame(data) {
    let wrapper = document.getElementsByClassName("navbar-active-game-wrapper").item(0);
    scrollIndex += 1;
    if (scrollIndex == data.length) {
        scrollIndex = 0;
    }
    let height = wrapper.offsetHeight;
    wrapper.scrollTo({ top: height * scrollIndex, behavior: 'smooth' })
}

function updateDuration() {
    let durationElems = document.getElementsByClassName("active-game-duration");
    if (activeGamesData.length > 0) {
        let gamesCopy = JSON.parse(JSON.stringify(activeGamesData));
        for (let i = 0; i < gamesCopy.length; i++) {
            gamesCopy[i][0] = Number.parseInt(gamesCopy[i][0])
            durationElems.item(i).textContent = formatDuration(gamesCopy[i][0]);
            gamesCopy[i][0] += 1
        }
    
        if (activeGamesData.length > 0) {
            activeGamesData = gamesCopy;
        }

        if (gamesCopy[0][0] % 10 == 0 && gamesCopy.length > 1) {
            scrollToNewGame(gamesCopy);
        }
    }

    if (gameIsActive) {
        setTimeout(function() {
            updateDuration();
        }, 1000);
    }
}

function pollUntilAnswer(game, attempt=0, limit=20, waitTime=1000) {
    console.log("Waiting for restart " + attempt + "/" + limit + "...");

    if (attempt == limit) {
        // It's taking too long to restart...
        alert("Something went wrong when restarting :(");
    }

    let baseUrl = getBaseURL(game);

    let timeBefore = Date.now();

    $.ajax(baseUrl + "/heartbeat", {
        method: "GET",
        timeout: 1000
    }).then(() => {
        let button = document.getElementById("admin-restart-btn");
        button.getElementsByClassName("admin-restart-waiting").item(0).style.display = "none";

        let successImg = button.getElementsByClassName("admin-restart-success").item(0);
        successImg.style.display = "block";
        successImg.style.opacity = 1;

        setTimeout(function() {
            successImg.style.opacity = 0;

            setTimeout(function() {
                let initBtn = button.getElementsByClassName("admin-restart-init").item(0)
                initBtn.style.display = "block";
                initBtn.style.opacity = 1;
            }, 1000);
        }, 1500);
    }, () => {
        let timeAfter = Date.now();
        let diff = timeAfter - timeBefore;
        let timeToWait = diff < waitTime ? waitTime - diff : 10;

        // Wait a bit before polling again.
        setTimeout(function() {
            pollUntilAnswer(game, attempt + 1, limit, waitTime);
        }, timeToWait);
    });
}

function restartIntfar(game) {
    let baseUrl = getBaseURL(game);

    let button = document.getElementById("admin-restart-btn");
    let initBtn = button.getElementsByClassName("admin-restart-init").item(0)
    initBtn.style.opacity = 0;
    initBtn.style.display = "none";
    button.getElementsByClassName("admin-restart-waiting").item(0).style.display = "block";

    $.ajax(baseUrl + "/restart", {
        method: "POST"
    });

    pollUntilAnswer(game);
}

window.addEventListener("resize", function() {
    resizeNav();
});
