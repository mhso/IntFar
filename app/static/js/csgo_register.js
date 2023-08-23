function formSubmit(event) {
    event.preventDefault();
    
    let inputIds = ["csgo-register-id", "csgo-register-code"]
    let inputLengths = [17, 15];
    const inputErrorClass = "csgo-input-error";
    
    let anyErrors = false;

    // Validate the length of the given input values
    for (let i = 0; i < inputIds.length; i++) {
        let input = document.getElementById(inputIds[i]);
        let length = inputLengths[i];
        let errorLabel = document.getElementById(inputIds[i] + "-error");

        if (input.value.length != length) {
            errorLabel.textContent = "Invalid length. Should be " + length + " characters.";
            anyErrors = true;
            if (!input.classList.contains(inputErrorClass)) {
                input.classList.add(inputErrorClass);
            }
        }
        else {
            errorLabel.textContent = "";
            if (input.classList.contains(inputErrorClass)) {
                input.classList.remove(inputErrorClass);
            }
        }
    }

    // Validate the contents of the given input values
    let steamInput = document.getElementById("csgo-register-id");
    if (!steamInput.classList.contains(inputErrorClass)) {
        let steamIdPrefix = "765";
        if (!steamInput.value.startsWith(steamIdPrefix)) {
            let errorLabel = document.getElementById("csgo-register-id-error");
            errorLabel.textContent = "Invalid Steam ID. It should start with '" + steamIdPrefix + "'.";
            anyErrors = true;
            steamInput.classList.add(inputErrorClass);
        }
    }

    let authCodeInput = document.getElementById("csgo-register-code");
    if (!authCodeInput.classList.contains(inputErrorClass)) {
        console.log("???");
        let dashSplit = authCodeInput.value.split("-");
        console.log(dashSplit);
        if (dashSplit.length != 3 || dashSplit[0].length != 4 || dashSplit[1].length != 5 || dashSplit[2].length != 4) {
            console.log("WAT");
            let errorLabel = document.getElementById("csgo-register-code-error");
            errorLabel.textContent = "Invalid Match History Code. It should be of the form 'XXXX-XXXXX-XXXX'.";
            anyErrors = true;
            authCodeInput.classList.add(inputErrorClass);
        }
    }

    if (!anyErrors) {
        for (let i = 0; i < inputIds.length; i++) {
            document.getElementById(inputIds[i]).classList.add("csgo-input-success");
        }

        let form = document.getElementById("csgo-register-form");
        form.submit();
    }
}

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById("csgo-register-form").addEventListener("submit", formSubmit);
});