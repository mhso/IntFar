function toggleView(view, show) {
    let elem = document.getElementById(view);
    elem.style.display = show ? "block" : "none"
}

function sendPost(url, data, onsuccess=null, ondone=null) {
    let address = window.location.protocol + "//" + window.location.hostname + ":" + window.location.port + "/intfar/lists/";
    $.post(address + url, data).fail(function(response) {
        let errorElem = document.getElementsByClassName("list-error-wrapper").item(0);
        errorElem.textContent = response.responseText;
    }).done(function(response) {
        if (onsuccess != null) {
            onsuccess(response);
        }
    }).fail(function(response) {
        let errorElem = document.getElementsByClassName("list-error-wrapper").item(0);
        errorElem.textContent = response.responseText;
    }).always(function(response) {
        if (ondone != null) {
            let errorElem = document.getElementsByClassName("list-error-wrapper").item(0);
            errorElem.textContent = response.responseText;
            ondone(response);
        }
    });
}

function changeListTitle(listId, button, field) {
    button.onclick = function() {
        editListTitle(listId, button);
    }

    toggleView("edit-name-img", false);
    toggleView("accept-edit-img", false);
    toggleView("lists-load-icon", true);

    let newName = field.value;
    field.disabled = true;
    sendPost(listId + "/rename", {name: newName}, null, function() {
        toggleView("edit-success-img", true);
        toggleView("lists-load-icon", false);
        setTimeout(function() {
            let editSuccessImg = document.getElementById("edit-success-img");
            editSuccessImg.style.opacity = 0;
            setTimeout(function() {
                toggleView("edit-success-img", false);
                toggleView("edit-name-img", true);
                editSuccessImg.style.opacity = 1;
            }, 1000);
        }, 1000);
    });
}

function editListTitle(listId, button) {
    let field = document.getElementById("list-view-name");
    field.disabled = false;
    field.focus();

    toggleView("edit-name-img", false);
    toggleView("accept-edit-img", true);

    button.onclick = function() {
        changeListTitle(listId, button, field);
    }
}

function goToList(url, e) {
    let deleteBtns = document.getElementsByClassName("delete-list-btn");
    if (deleteBtns.length == 0) { // No delete button exists.
        window.location.href = url;
    }
    else {
        let isClickOnBtn = false;
        // Ensure we didn't click on a 'delete_list' button.
        for (let i = 0; i < deleteBtns.length; i++) {
            let btn = deleteBtns.item(i);
            let img = btn.getElementsByTagName("img").item(0);
            if (e.srcElement == btn || e.srcElement == img) {
                isClickOnBtn = true;
                break;
            }
        }
        if (!isClickOnBtn) {
            window.location.href = url;
        }
    }
}

function showPlaceholder(placeholderId) {
    let placeholder = document.getElementById(placeholderId);
    placeholder.classList.remove("d-none");
    placeholder.classList.add("d-block");
}

function deleteList(listId, deleteBtn) {
    sendPost(listId + "/delete_list", null, function(response) {
        let parent = deleteBtn.parentNode;
        let wrapper = parent.parentNode;
        wrapper.removeChild(parent);
        if (wrapper.getElementsByClassName("list-entry-wrapper").length == 0) {
            showPlaceholder("no-lists-placeholder");
        }
    });
}

function deleteItem(itemId, deleteBtn) {
    sendPost(itemId + "/delete_item", null, function(response) {
        let parent = deleteBtn.parentNode;
        let wrapper = parent.parentNode;
        wrapper.removeChild(parent);
        if (wrapper.getElementsByClassName("list-items-wrapper").length == 0) {
            showPlaceholder("no-items-placeholder");
        }
    });
}

function filterLists() {
    let checkbox = document.getElementById("show-owned-lists");
    let listElements = document.getElementsByClassName("list-entry-wrapper");
    for (let i = 0; i < listElements.length; i++) {
        let listElem = listElements.item(i);
        if (!checkbox.checked) {
            listElem.style.display = "block";
        }
        else if (!listElem.classList.contains("owned-list")) {
            listElem.style.display = "none";
        }
    }
}

function highlightRandomChamp() {
    let items = document.getElementsByClassName("list-items-entry");
    let numItems = items.length;

    if (numItems == 0) {
        return;
    }

    let randomNum = Math.floor(Math.random() * numItems);

    let highlightedElems = document.getElementsByClassName("highlighted-entry");
    for (let i = 0; i < highlightedElems.length; i++) {
        highlightedElems.item(i).classList.remove("highlighted-entry");
    }

    items.item(randomNum).classList.add("highlighted-entry");
}

function createColorScheme() {
    let listEntries = document.getElementsByClassName("list-entry-wrapper");
    let red = 14;
    let green = 59;
    let blue = 166;
    let alpha = 0.37;

    let deltaRed = 10;
    let deltaGreen = 18;
    let deltaBlue = 4;

    for (let i = 0; i < listEntries.length; i++) {
        let entry = listEntries.item(i);
        let color = "rgba(" + red + ", " + green + ", " + blue + ", " + alpha + ")";
        entry.style.backgroundColor = color;

        red += deltaRed;
        green += deltaGreen;
        blue -= deltaBlue;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    createColorScheme();
});