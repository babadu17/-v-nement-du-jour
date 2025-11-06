const stars = document.querySelectorAll(".star");
const noteInput = document.getElementById("note-value");

stars.forEach(star => {
  star.addEventListener("click", () => {
    const note = star.getAttribute("data-value");
    noteInput.value = note;

    stars.forEach(s => s.classList.remove("active"));
    star.classList.add("active");
    let prev = star.previousElementSibling;
    while(prev) {
      prev.classList.add("active");
      prev = prev.previousElementSibling;
    }
  });
});
