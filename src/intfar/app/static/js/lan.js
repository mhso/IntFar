var gamesPlayed = 0;
var isActiveGame = false;
var isLanActive = false;

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port;
}

function refreshPage() {
    window.location.href = getBaseURL() + "/intfar/lan"
}

function getLiveData(lanDate) {
    let baseUrl = getBaseURL();
    $.ajax(baseUrl + "/intfar/lan/live_data/" + lanDate, {
        method: "GET",
        data: {filter: "active_game,games_played"}
    }).then((data) => {
        if (data.games_played != null && data.active_game == null && isActiveGame) {
            console.log("Finished game!"); // Game finished. Refresh page.
            isActiveGame = false;
            refreshPage();
        }
        if (data.active_game != null && !isActiveGame) {
            console.log("Active game started!");
            isActiveGame = true; // Active game started. Refresh page.
            refreshPage();
        }
        if (data.games_played != null && data.games_played > gamesPlayed) {
            refreshPage();
        }
    });
}

function getSongPlaying(lanDate) {
    let baseUrl = getBaseURL();
    $.ajax(baseUrl + "/intfar/lan/now_playing/" + lanDate, {
        method: "GET"
    }).then((data) => {
        let song_str = null;
        if (data.artist == "nothing") {
            song_str = data.song;
        }
        else {
            song_str = data.artist + " - " + data.song;
        }
        let elem = document.getElementById("lan-now-playing");
        if (elem != null) {
            document.getElementById("lan-now-playing").textContent = song_str
        }
    }, (error) => {
        
    });
}

function showLiveGameFeed(feedWrapper) {
    feedWrapper.style.opacity = 1;
}

function hideLiveGameFeed(feedWrapper) {
    feedWrapper.style.opacity = 0;
}

function getLiveLeagueData() {
    let feedWrapper = document.getElementById("lan-live-game-feed-wrapper");
    if (feedWrapper == null) {
        return;
    }

    let baseUrl = getBaseURL();
    $.ajax(baseUrl + "/intfar/lan/live_league_data", {
        method: "GET"
    }).then((data) => {
        if (data["events"].length > 0) {
            showLiveGameFeed(feedWrapper);
            feedWrapper.dataset["fade"] = "5";
        }
        else {
            let value = Number.parseInt(feedWrapper.dataset["fade"]);
            if (value > 0) {
                feedWrapper.dataset["fade"] = (value - 1).toString();
            }
        }

        if (feedWrapper.dataset["fade"] == "0") {
            hideLiveGameFeed(feedWrapper);
        }

        data["events"].forEach((event, index) => {
            let wrapperElem = document.createElement("div");
            wrapperElem.classList.add("lan-game-feed-entry");
            wrapperElem.classList.add(event["category"]);

            let descElem = document.createElement("div");
            descElem.className = "lan-game-feed-entry-desc";
            descElem.textContent = event["description"];
            wrapperElem.appendChild(descElem);

            let iconElem = document.createElement("img");
            iconElem.className = "lan-game-feed-entry-icon";
            if (event["icon"] != null) {
                iconElem.src = event["icon"];
            }
            else {
                iconElem.style.opacity = 0;
            }
            wrapperElem.appendChild(iconElem);

            wrapperElem.style.opacity = 0;
            setTimeout(function() {
                wrapperElem.style.animationName = "addToFeed"
            }, 0.5 + (250 * index));

            feedWrapper.children[0].appendChild(wrapperElem);
            feedWrapper.children[0].scrollTo({left: 0, top: feedWrapper.children[0].scrollHeight, behavior: "smooth"});
        });
    });
}

function parseDuration(duration) {
    let split = duration.split(",");

    let years = 0;
    let months = 0;
    let days = 0;
    let hours = 0;
    let minutes = 0;
    let seconds = 0;

    for (let i = 0; i < split.length; i++) {
        let unit = split[i].trim();
        if (unit.includes("years")) {
            let split2 = unit.split(" ")
            years = Number.parseInt(split2[0]);
        }
        else if (unit.includes("months")) {
            let split2 = unit.split(" ")
            months = Number.parseInt(split2[0]);
        }
        else if (unit.includes("days")) {
            let split2 = unit.split(" ")
            days = Number.parseInt(split2[0]);
        }
        else if (unit.includes("h")) {
            hours = Number.parseInt(unit.substring(0, unit.length-1));
        }
        else if (unit.includes("m")) {
            minutes = Number.parseInt(unit.substring(0, unit.length-1));
        }
        else if (unit.includes("s")) {
            seconds = Number.parseInt(unit.substring(0, unit.length-1));
        }
        else if (unit.includes("&")) {
            let split2 = unit.split("&");
            let splitMins = split2[0].trim().split(" ")
            minutes = Number.parseInt(splitMins[0]);
            let splitSecs = split2[1].trim().split(" ")
            seconds = Number.parseInt(splitSecs[0]);
        }
        else if (unit.includes("seconds")) {
            let split2 = unit.split(" ")
            seconds = Number.parseInt(split2[0]);
        }
    }
    
    return hours * 3600 + minutes * 60 + seconds;
}

function zeroPad(number) {
    if (number < 10) {
        return "0" + number
    }
    return "" + number
}

function setNewDuration(durationElem, durationDate) {
    let years = durationDate.getUTCFullYear();
    let months = durationDate.getUTCMonth();
    let days = durationDate.getUTCDate();
    let hours = durationDate.getUTCHours();
    let minutes = durationDate.getUTCMinutes();
    let seconds = durationDate.getUTCSeconds();

    let str = "";
    if (minutes == 0) {
        str = seconds + " seconds";
    }
    else {
        str = zeroPad(minutes) + " minutes & " + zeroPad(seconds) + " seconds"
    }
    if (hours > 0) {
        str = zeroPad(hours) + "h" + ", " + zeroPad(minutes) + "m, " + zeroPad(seconds) + "s"
    }
    if (days > 0) {
        str = days + " days, " + str
    }
    if (months > 0) {
        str = months + " months, " + str
    }
    if (years > 0) {
        str = years + " years, " + str
    }

    durationElem.textContent = str;
}

function incrementDuration(durationElem) {
    let duration = parseDuration(durationElem.textContent) * 1000;
    let newTime = (new Date()).getTime() + duration + 1000;
    let newDate = new Date(newTime);
    setNewDuration(durationElem, newDate);
}

function count() {
    let timeSinceStartElem = document.getElementById("lan-duration").getElementsByTagName("span").item(0);

    setInterval(function() {
        if (isLanActive) {
            incrementDuration(timeSinceStartElem);
        }
    }, 1000);
}

function monitor(playedGames, activeGame, lanOver, lanDate) {
    gamesPlayed = playedGames;
    isActiveGame = activeGame != "None";
    isLanActive = lanOver;
    console.log("Games on load: " + gamesPlayed)
    console.log("Active games on load: " + isActiveGame)
    console.log("LAN active on load: " + isLanActive)

    let lanDataDelay = 10 * 1000
    let songDelay = 5 * 1000
    let lolDataDelay = 2 * 1000

    let lolDataInterval = setInterval(function() {
        getLiveLeagueData();
    }, lolDataDelay);

    let songInterval = setInterval(function() {
        getSongPlaying(lanDate)
    }, songDelay);

    let lanDataInterval = setInterval(function() {
        if (!isLanActive) {
            clearInterval(lanDataInterval);
            clearInterval(songInterval);
            clearInterval(lolDataInterval);
        }
        else {
            getLiveData(lanDate);
            getSongPlaying(lanDate)
        }
    }, lanDataDelay);
}

document.addEventListener("DOMContentLoaded", function() {
    let entries = document.getElementsByClassName("lan-bingo-entry");
    for (let i = 0; i < entries.length; i++) {
        let entry = entries.item(i);
        let entryHeight = entry.getBoundingClientRect().height;
        let padding = 5 + (entryHeight * 0.05);

        // Center description
        let descElem = entry.getElementsByClassName("lan-bingo-desc").item(0);
        let y = (entryHeight / 2 - descElem.getBoundingClientRect().height / 2) - padding;

        descElem.style.top = y + "px";
    
        // Fill up progress meter
        if ("progress" in entry.dataset) {
            let progress = Number.parseFloat(entry.dataset["progress"]);
            let total = Number.parseFloat(entry.dataset["total"]);
            
            let progressElem = entry.getElementsByClassName("lan-bingo-progress-bar").item(0);
            if (progressElem != null) {
                let ratio = progress / total;
                progressElem.style.height = ((ratio * entryHeight) - 2) + "px";
            }
        }

        let personElem = entry.getElementsByClassName("lan-bingo-person");
        if (personElem.length != 0) {
            let imageElem = personElem.item(0).getElementsByTagName("img").item(0);
            let intervalId = setInterval(function() {
                let imgHeight = imageElem.getBoundingClientRect().height;
                if (imgHeight > 0) {
                    clearInterval(intervalId);
                    let shift = ((imgHeight - entryHeight) * 0.5) + 10;
                    imageElem.style.top = -shift + "px";
                }
            }, 10);
        }
    }
});