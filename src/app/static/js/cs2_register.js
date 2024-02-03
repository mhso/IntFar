function formSubmit(event) {
    event.preventDefault();
    
    let inputIds = ["cs2-register-id", "cs2-register-token", "cs2-register-code"]
    let inputLengths = [17, 34, 15];
    const inputErrorClass = "cs2-input-error";
    
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
    let steamInput = document.getElementById("cs2-register-id");
    if (!steamInput.classList.contains(inputErrorClass)) {
        let steamIdPrefix = "765";
        if (!steamInput.value.startsWith(steamIdPrefix)) {
            let errorLabel = document.getElementById("cs2-register-id-error");
            errorLabel.textContent = "Invalid Steam ID. It should start with '" + steamIdPrefix + "'.";
            anyErrors = true;
            steamInput.classList.add(inputErrorClass);
        }
    }

    let matchTokenInput = document.getElementById("cs2-register-token");
    if (!matchTokenInput.classList.contains(inputErrorClass)) {
        let dashSplit = matchTokenInput.value.split("-");
        let splitLengths = [4, 5, 5, 5, 5, 5];
        let tokenPrefix = "CSGO";
        let errors = false;
        if (!matchTokenInput.value.startsWith(tokenPrefix)) {
            errors = true;
        }
        else {
            for (let i = 0; i < splitLengths.length; i++) {
                if (i >= dashSplit.length || splitLengths[i] != dashSplit[i].length) {
                    errors = true;
                    break
                }
            }
        }
        if (errors) {
            anyErrors = true;
            let errorLabel = document.getElementById("cs2-register-token-error");
            errorLabel.textContent = "Invalid Recent Match Token. It should be of the form 'CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX'.";
            authCodeInput.classList.add(inputErrorClass);
        }
    }

    let authCodeInput = document.getElementById("cs2-register-code");
    if (!authCodeInput.classList.contains(inputErrorClass)) {
        let dashSplit = authCodeInput.value.split("-");
        let splitLengths = [4, 5, 4];
        for (let i = 0; i < splitLengths.length; i++) {
            if (i >= dashSplit.length || splitLengths[i] != dashSplit[i].length) {
                let errorLabel = document.getElementById("cs2-register-code-error");
                errorLabel.textContent = "Invalid Match History Code. It should be of the form 'XXXX-XXXXX-XXXX'.";
                anyErrors = true;
                authCodeInput.classList.add(inputErrorClass);
                break
            }
        }
    }

    if (!anyErrors) {
        for (let i = 0; i < inputIds.length; i++) {
            document.getElementById(inputIds[i]).classList.add("cs2-input-success");
        }

        let form = document.getElementById("cs2-register-form");
        form.submit();
    }
}

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById("cs2-register-form").addEventListener("submit", formSubmit);
});