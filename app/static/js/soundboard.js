const ORDER_ARROW_POS = "calc(50% + 46px)";
var sortMode = "alphabetical";
var sortAscending = true;

function sort_by_name(a, b) {
    return a.dataset.name.toLowerCase().localeCompare(b.dataset.name.toLowerCase());
}

function sort_by_time(a, b) {
    return a.dataset.ctime == b.dataset.ctime ? 0 : (a.dataset.ctime > b.dataset.ctime ? 1 : -1);
}

function adjustOrderArrow() {
    let showName = sortAscending ? "ascending" : "descending";
    let hideName = sortAscending ? "descending" : "ascending";

    let showArrow = document.getElementById("sounds-sort-" + showName);
    let hideArrow = document.getElementById("sounds-sort-" + hideName);

    let showPos = sortMode == "alphabetical" ? "right" : "left";
    let unsetPos = sortMode == "alphabetical" ? "left" : "right";
    showArrow.style.setProperty(showPos, ORDER_ARROW_POS);
    showArrow.style.setProperty(unsetPos, "unset");
    hideArrow.style.setProperty("left", "unset");
    hideArrow.style.setProperty("right", "unset");

    showArrow.style.display = "block";
    hideArrow.style.display = "none";
}

function sortSounds(mode, target) {
    let sortButtons = document.getElementsByClassName("sounds-sort-button");
    for (let i = 0; i < sortButtons.length; i++) {
        let btn = sortButtons.item(i);
        if (btn.classList.contains("sounds-highlighted-sort-btn")) {
            btn.classList.remove("sounds-highlighted-sort-btn");
        }
        if (btn.isSameNode(target)) {
            btn.classList.add("sounds-highlighted-sort-btn");
        }
    }

    let ascending = mode == sortMode ? !sortAscending : true;
    sortMode = mode;
    sortAscending = ascending;

    let elements = $(".all-sounds-wrapper > .audio-player-wrapper").get();

    let sortFunc = sortMode == "alphabetical" ? sort_by_name : sort_by_time

    elements.sort(sortFunc);
    if (!sortAscending) {
        elements.reverse();
    }

    for (let i = 0; i < elements.length; i++) {
        elements[i].parentNode.appendChild(elements[i]);
    }

    adjustOrderArrow();
}
