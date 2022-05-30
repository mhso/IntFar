var LOGGED_IN_USER = null;
var buttonCooldowns = [];
var channelNames = [];

function setChannelNames(names) {
    let parsedNames = JSON.parse(names.split("&#39;").join("\""));
    channelNames = parsedNames;
}

function setLoggedInUser(disc_id) {
    LOGGED_IN_USER = disc_id;
}

function setBetStatus(status, error) {
    let className = error ? "error" : "success";
    let statusElem = document.getElementById("bet-status");
    statusElem.className = className;
    statusElem.innerHTML = status;
}

function clearBetStatus() {
    let statusElem = document.getElementById("bet-status");
    statusElem.className = "";
}

function getAllBetDetails() {
    let tableRows = document.getElementsByClassName("event-row");
    let events = [];
    let amounts = [];
    let targets = [];
    let targetNames = [];

    for (let i = 1; i < tableRows.length; i++) {
        let row = tableRows.item(i);
        let cols = row.getElementsByTagName("td");
        let event = cols[0].dataset["value"];
        let amount = cols[1].dataset["value"];
        let target = cols[2].dataset["value"];
        let targetName = cols[2].textContent;
        events.push(event);
        amounts.push(amount);
        targets.push(target);
        targetNames.push(targetName);
    }

    let playersInput = document.getElementById("bet-players");
    let players = "1";
    if (playersInput.checkValidity() && playersInput.value != "") {
        players = playersInput.value;
    }
    let guildSelect = document.getElementById("bet-guild");
    let guildId = guildSelect.options[guildSelect.selectedIndex].value;

    return {
        events: events, amounts: amounts, targets: targets,
        targetNames: targetNames, disc_id: LOGGED_IN_USER,
        players: players, guildId: guildId
    };
}

function getCurrentBetDetails() {
    let eventInput = document.getElementById("bet-event");
    let amountInput = document.getElementById("bet-amount");
    let targetInput = document.getElementById("bet-target");

    let eventIndex = eventInput.selectedIndex;
    let eventId = eventInput.options[eventIndex].value;

    let noTarget = eventIndex < 3

    let amount = amountInput.value;
    let target = targetInput.options[targetInput.selectedIndex].value;
    let targetName = targetInput.options[targetInput.selectedIndex].textContent;
    if (targetInput.disabled) {
        target = "invalid";
    }

    let guildSelect = document.getElementById("bet-guild");
    let guildId = guildSelect.options[guildSelect.selectedIndex].value;

    return {
        valid: amountInput.checkValidity(),
        data: {
            amount: amount, event: eventId, eventIndex: eventIndex,
            eventDesc: eventInput.options[eventIndex].textContent,
            target: target, targetName: targetName, noTarget: noTarget,
            guildId: guildId
        }
    };
}

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port;
}

async function sendBetRequest(endpoint) {
    let baseUrl = getBaseURL();

    let betDetails = getAllBetDetails();

    return new Promise((resolve, reject) => {
        if (betDetails.amounts.length == 0) {
            reject({responseJSON: {response: "Error: You must first add a bet event."}});
        }
        else {
            resolve();
        }
    }).then(() => {
        return $.ajax(baseUrl + "/intfar/betting/" + endpoint, {
            data: JSON.stringify(betDetails),
            method: "POST",
            contentType: "application/json",
            content: "application/json"
        });
    }, (err) => {
        return new Promise((resolve, reject) => {
            reject(err);
        })
    });
}

function betEventChanged() {
    let target_input = document.getElementById("bet-target");
    let betDetails = getCurrentBetDetails();

    target_input.disabled = betDetails.data.noTarget;
    if (betDetails.data.noTarget) {
        target_input.options[target_input.selectedIndex].selected = false;
        target_input.options[0].selected = true;
        target_input.options[0].textContent = "No Target"
    }
    else {
        target_input.options[0].textContent = "Any Target"
    }
}

async function betModified() {
    await sendBetRequest("payout").then((response) => {
        let cost = response.cost;
        let payout = response.payout;
        let costElem = document.getElementById("bet-cost-value");
        let priceElem = document.getElementById("bet-payout-value");
        costElem.textContent = cost + " GBP";
        priceElem.textContent = payout + " GBP";
        document.getElementById("bet-submit").disabled = false;
    },
    (error) => setBetStatus(error.responseJSON.response, true));
}

function addEvent() {
    let betDetails = getCurrentBetDetails();

    if (!betDetails.valid) {
        setBetStatus("Error: Bet has invalid or missing values.", true);
        return;
    }

    clearBetStatus();

    let eventTable = document.getElementById("bet-events-list");

    let eventRow = document.createElement("tr");
    eventRow.className = "event-row";

    let betData = betDetails.data;
    
    let eventDesc = document.createElement("td");
    eventDesc.dataset["value"] = betData.eventIndex;
    eventDesc.textContent = betData.eventDesc;
    eventRow.appendChild(eventDesc);

    let eventAmount = document.createElement("td");
    eventAmount.dataset["value"] = betData.amount;
    eventAmount.textContent = betData.amount + " GBP";
    eventRow.appendChild(eventAmount);

    let eventTarget = document.createElement("td");
    eventTarget.dataset["value"] = betData.target;
    eventTarget.textContent = betData.target == "invalid" ? "" : betData.targetName;
    eventRow.appendChild(eventTarget);

    let deleteBtnData = document.createElement("td");
    let deleteBtn = document.createElement("button");
    deleteBtn.innerHTML = "&times;";
    deleteBtn.classList.add("delete-btn");
    deleteBtn.classList.add("cooldown-btn");
    buttonCooldowns.push({
        btn: deleteBtn,
        lastClick: 0
    });
    deleteBtn.onclick = function() {
        buttonClick(deleteBtn, function() {
            eventTable.children[0].removeChild(eventRow);
            if (document.getElementsByClassName("event-row").length > 1) {
                betModified();
            }
            else {
                let statusElem = document.getElementById("bet-status");
                let priceElem = document.getElementById("bet-payout-value");
                let costElem = document.getElementById("bet-cost-value");
                priceElem.textContent = "0 GBP";
                costElem.textContent = "0 GBP";
                statusElem.textContent = "";
                document.getElementById("bet-submit").disabled = true;
            }
        });
    }
    deleteBtnData.appendChild(deleteBtn);
    eventRow.appendChild(deleteBtnData);
    eventTable.children[0].appendChild(eventRow);

    betModified();
}

function removeBetRows(betId, betType) {
    let activeBetsDiv = document.getElementById("bets-active");
    let activeBetsTable = activeBetsDiv.getElementsByClassName("nice-table").item(0);
    let rows = activeBetsTable.getElementsByClassName("list-entry");
    let dataType = betType == "single" ? "bet_id" : "ticket";
    let rowsToDelete = [];
    for (let i = 1; i < rows.length; i++) {
        let row = rows.item(i);

        let rowBetId = Number.parseInt(row.dataset[dataType]);

        if (rowBetId == betId) {
            rowsToDelete.push(row);
        }
    }

    for (let i = 0; i < rowsToDelete.length; i++) {
        activeBetsTable.children[0].removeChild(rowsToDelete[i]);
    }

    if (activeBetsTable.getElementsByClassName("list-entry").length == 1) {
        let noActiveBetsElem = document.createElement("p");
        noActiveBetsElem.textContent = "There are currently no active bets."
        noActiveBetsElem.id = "no-active-bets";
        activeBetsTable.classList.add("empty-list");
        activeBetsDiv.appendChild(noActiveBetsElem);
    }
}

function sendDeleteRequest(betId, guildId, betType) {
    if (confirm("Are you sure you want to cancel this bet?")) {
        let baseUrl = getBaseURL();
        $.ajax(baseUrl + "/intfar/betting/delete", {
            data: {betId: betId, guildId: guildId, betType: betType, disc_id: LOGGED_IN_USER},
            method: "POST"
        }).then((response) => {
            removeBetRows(betId, betType);
            let balanceElem = document.getElementById("bet-balance-value");
            balanceElem.textContent = response.betting_balance + " GBP";
        },
        (error) => alert(error.responseJSON.response));
    }
}

function deleteMultiBet(ticket, guildId) {
    sendDeleteRequest(Number.parseInt(ticket), guildId, "multi");
}

function deleteBet(betId, guildId) {
    sendDeleteRequest(Number.parseInt(betId), guildId, "single");
}

async function makeBet(submitBtn) {
    let btnText = document.getElementById("bet-submit-text");
    let loadIcon = submitBtn.getElementsByClassName("loading-icon").item(0);
    let hiddenClass = "d-none";
    let visibleClass = "hidden";
    btnText.classList.add(visibleClass);
    loadIcon.classList.remove(hiddenClass);

    await sendBetRequest("create").then((data) => {
        setBetStatus(
            "Bet succesfully placed!<br>" +
            "See details in <span class='discord-command'>#" +
            data.channel_name + ".</span>",
            false
        );
        let activeBetsDiv = document.getElementById("bets-active");
        let activeBetsTable = activeBetsDiv.getElementsByClassName("nice-table").item(0);
        let noActiveBetsElem = document.getElementById("no-active-bets");
        if (noActiveBetsElem != null) {
            activeBetsDiv.removeChild(noActiveBetsElem);
            activeBetsTable.classList.remove("empty-list");
        }
        let tbody = activeBetsTable.children[0];

        let events = data.events;
        
        for (let i = 0; i < events.length; i++) {
            let row = document.createElement("tr");
            row.classList.add("bets-list-entry");
            row.classList.add("list-entry");
            if (events.length == 1) {
                row.classList.add("bet-single");
            }
            else if (i == 0) {
                row.classList.add("bet-main");
            }
            else {
                row.classList.add("bet-follow");
            }

            if (data.bet_type == "single") {
                row.dataset["bet_id"] = data.bet_id;
            }
            else {
                row.dataset["ticket"] = data.ticket;
            }

            let eventArr = events[i];
            let event = eventArr[0];
            let amount = eventArr[1];

            let avatarTd = document.createElement("td");
            let nameTd = document.createElement("td");
            if (i == 0) {
                let avatarImg = document.createElement("img");
                avatarImg.src = data.avatar;
                avatarImg.className = "discord-avatar";
                avatarImg.alt = "Discord Avatar";
                avatarTd.appendChild(avatarImg);

                nameTd.textContent = data.name;
            }

            let guildTd = document.createElement("td");
            guildTd.textContent = data.guild_name;

            let eventTd = document.createElement("td");
            if (i > 0) {
                eventTd.innerHTML = "<span class='emph'>and</span> ";
            }
            eventTd.innerHTML = eventTd.innerHTML + event;

            let amountTd = document.createElement("td");
            amountTd.textContent = amount;

            let ticketTd = document.createElement("td");
            if (data.ticket != null) {
                ticketTd.textContent = data.ticket;
            }
            if (i == 0) {
                let deleteBtn = document.createElement("button");
                deleteBtn.innerHTML = "&times;";
                deleteBtn.classList.add("delete-btn");
                deleteBtn.classList.add("cooldown-btn");
                buttonCooldowns.push({
                    btn: deleteBtn,
                    lastClick: 0
                });
                deleteBtn.onclick = function() {
                    buttonClick(deleteBtn, function() {
                        if (data.bet_type == "single") {
                            deleteBet(data.bet_id, data.guild_id);
                        }
                        else {
                            deleteMultiBet(data.ticket, data.guild_id);
                        }
                    })
                }
                ticketTd.appendChild(deleteBtn);
            }

            row.appendChild(avatarTd);
            row.appendChild(nameTd);
            row.appendChild(guildTd);
            row.appendChild(eventTd);
            row.appendChild(amountTd);
            row.appendChild(ticketTd);
            
            tbody.insertBefore(row, tbody.children[i + 1]);
        }

        // Remove current bet from current bet table.
        let betTable = document.getElementById("bet-events-list");
        let rows = betTable.getElementsByClassName("event-row");
        let rowsToDelete = [];
        for (let i = 0; i < rows.length; i++) {
            if (!rows.item(i).classList.contains("header")) {
                rowsToDelete.push(rows.item(i));
            }
        }
        for (let i = 0; i < rows.length; i++) {
            betTable.children[0].removeChild(rowsToDelete[i]);
        }
        // Set updated token balance and reset cost/value of current bet.
        let balanceElem = document.getElementById("bet-balance-value");
        let costElem = document.getElementById("bet-cost-value");
        let priceElem = document.getElementById("bet-payout-value");
        balanceElem.textContent = data.betting_balance + " GBP";
        costElem.textContent = "0 GBP";
        priceElem.textContent = "0 GBP";

        // Save selected guild in a cookie for future bets.
        let guildSelect = document.getElementById("bet-guild");
        let guildId = guildSelect.options[guildSelect.selectedIndex].value;
        var expirDate = new Date();
        expirDate.setTime(expirDate.getTime() + (420*24*60*60*1000));
        var expires = "; expires="+ expirDate.toUTCString();
        document.cookie = "main_guild_id=" + guildId + expires;

        document.getElementById("bet-submit").disabled = false;
        btnText.classList.remove(visibleClass);
        loadIcon.classList.add(hiddenClass);
        submitBtn.disabled = true;
    },
    (error) => {
        setBetStatus(error.responseJSON.response, true);
        btnText.classList.remove(visibleClass);
        loadIcon.classList.add(hiddenClass);
    });
}

function buttonClick(btn, callback, ...param) {
    let delay = 1000;
    let cooldownBtn = null;
    for (let i = 0; i < buttonCooldowns.length; i++) {
        if (btn === buttonCooldowns[i].btn) {
            cooldownBtn = buttonCooldowns[i].btn;
        }
    }
    let lastClick = cooldownBtn.lastClick;
    if (Date.now() - lastClick < delay) {
        console.log("Not allowed!");
        return;
    }
    cooldownBtn.lastClick = Date.now();
    callback.apply(this, param)
}

function initCooldownButtons() {
    let cooldownBtns = document.getElementsByClassName("cooldown-btn");
    for (let i = 0; i < cooldownBtns.length; i++) {
        buttonCooldowns.push({
            btn: cooldownBtns.item(i),
            lastClick: 0
        });
    }
}

document.addEventListener('DOMContentLoaded', function () {
    initCooldownButtons();
});