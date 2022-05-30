var anyGamesPlayed = false;
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
        method: "GET"
    }).then((data) => {
        if (data.games_played != null && data.active_game == null && isActiveGame) {
            console.log("Finished game!"); // Game finished. Refresh page.
            anyGamesPlayed = true;
            isActiveGame = false;
            refreshPage();
        }
        if (data.active_game != null && !isActiveGame) {
            console.log("Active game started!");
            isActiveGame = true; // Active game started. Refresh page.
            refreshPage();
        }
    }, (error) => {
        console.log("ERROR!!! " + error);
    });
}

function parseDuration(duration) {
    let split = duration.split(",");

    let obj = {
        years: 0, months: 0, days: 0,
        hours: 0, minutes: 0, seconds: 0
    };
    for (let i = 0; i < split.length; i++) {
        let unit = split[i].trim();
        if (unit.includes("years")) {
            let split2 = unit.split(" ")
            obj.years = Number.parseInt(split2[0]);
        }
        else if (unit.includes("months")) {
            let split2 = unit.split(" ")
            obj.months = Number.parseInt(split2[0]);
        }
        else if (unit.includes("days")) {
            let split2 = unit.split(" ")
            obj.days = Number.parseInt(split2[0]);
        }
        else if (unit.includes("h")) {
            obj.hours = Number.parseInt(unit.substring(0, unit.length-1));
        }
        else if (unit.includes("m")) {
            obj.minutes = Number.parseInt(unit.substring(0, unit.length-1));
        }
        else if (unit.includes("s")) {
            obj.seconds = Number.parseInt(unit.substring(0, unit.length-1));
        }
        else if (unit.includes("&")) {
            let split2 = unit.split("&");
            let splitMins = split2[0].trim().split(" ")
            obj.minutes = Number.parseInt(splitMins[0]);
            let splitSecs = split2[1].trim().split(" ")
            obj.seconds = Number.parseInt(splitSecs[0]);
        }
        else if (unit.includes("seconds")) {
            let split2 = unit.split(" ")
            obj.seconds = Number.parseInt(split2[0]);
        }
    }
    return obj;
}

function zeroPad(number) {
    if (number < 10) {
        return "0" + number
    }
    return "" + number
}

function setNewDuration(durationElem, durationDate) {
    let years = durationDate.getYear();
    let months = durationDate.getMonth();
    let days = durationDate.getDate();
    let hours = durationDate.getHours();
    let minutes = durationDate.getMinutes();
    let seconds = durationDate.getSeconds();

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
    let duration = parseDuration(durationElem.textContent);

    let date = new Date(
        duration.years, duration.months, duration.days,
        duration.hours, duration.minutes, duration.seconds
    );
    let newTime = date.getTime() + 1000;
    let newDate = new Date(newTime);
    setNewDuration(durationElem, newDate);
}

function count() {
    let timeSinceStartElem = document.getElementById("lan-duration").getElementsByTagName("span").item(0);
    let timeSinceGameElem = document.getElementById("lan-game-duration");

    setInterval(function() {
        if (isLanActive) {
            incrementDuration(timeSinceStartElem);
        }
        incrementDuration(timeSinceGameElem);
    }, 1000);
}

function autoScroll() {
    let scrollElem = document.getElementById("lan-teamcomp-scroll");
    let allChildren = scrollElem.children;
    
    let totalHeight = 0;
    for (let i = 0; i < allChildren.length; i++) {
        totalHeight += allChildren.item(0).offsetHeight;
    }

    let delay = 40;
    let thresholdOffset = 216;
    setInterval(function() {
        scrollElem.scrollBy(0, 1);
        if (scrollElem.scrollTop >= totalHeight + thresholdOffset) {
            scrollElem.scrollTo(0, 0);
        }
    }, delay);
}

function monitor(gamesPlayed, activeGame, lanOver, lanDate) {
    anyGamesPlayed = gamesPlayed != "None";
    isActiveGame = activeGame != "None";
    isLanActive = lanOver == "False";
    console.log("Games on load: " + anyGamesPlayed)
    console.log("Active games on load: " + isActiveGame)
    console.log("LAN active on load: " + isLanActive)

    let delay = 15 * 1000
    let intervalId = setInterval(function() {
        if (!isLanActive) {
            clearInterval(intervalId);
        }
        else {
            getLiveData(lanDate);
        }
    }, delay);
    if (anyGamesPlayed) {
        if (isLanActive) {
            count();
        }
        if (!isActiveGame) {
            autoScroll();
        }
    }
}