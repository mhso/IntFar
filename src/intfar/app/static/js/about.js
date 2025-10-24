function addScrollListeners() {
    let scrollCards = document.getElementsByClassName("about-scroll-fade");
    let windowHeight = window.innerHeight;
    let pixelsToFade = 400;

    window.addEventListener("scroll", function(e) {
        for (let i = 0; i < scrollCards.length; i++) {
            let card = scrollCards.item(i);

            let distanceFromBot = windowHeight - card.getBoundingClientRect().y;

            if (distanceFromBot > 0) {
                let opacity = Math.min(1, distanceFromBot / pixelsToFade);
                card.style.opacity = opacity;
            }
            else {
                card.style.opacity = 0;
            }
        }
    })
}

document.addEventListener('DOMContentLoaded', function () {
    addScrollListeners();
});