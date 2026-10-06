// Добавление и удаление записей об опыте работы и образовании.
document.addEventListener("click", (event) => {
    const addButton = event.target.closest("[data-add-entry]");
    if (addButton) {
        const type = addButton.dataset.addEntry;
        const template = document.getElementById(`template-${type}`);
        const container = document.querySelector(`[data-entries="${type}"]`);
        container.appendChild(template.content.cloneNode(true));
        return;
    }

    const removeButton = event.target.closest("[data-remove-entry]");
    if (removeButton) {
        removeButton.closest(".entry").remove();
    }
});

// Поля с data-autogrow растут по высоте вместе с текстом вместо внутренней прокрутки.
function autogrow(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight + 2}px`;
}

document.addEventListener("input", (event) => {
    if (event.target.matches("textarea[data-autogrow]")) {
        autogrow(event.target);
    }
});

document.querySelectorAll("textarea[data-autogrow]").forEach(autogrow);

// Галочка «По настоящее время» блокирует дату окончания. Неотмеченный checkbox
// не отправляется, поэтому флаг хранится в скрытом поле — по одному на запись.
// Поле окончания делается readonly, а не disabled: disabled-поля не отправляются,
// и даты окончания остальных записей сдвинулись бы.
document.addEventListener("change", (event) => {
    const toggle = event.target.closest("[data-current-toggle]");
    if (!toggle) {
        return;
    }
    const entry = toggle.closest(".entry");
    const endInput = entry.querySelector('[name="experience_end"]');
    entry.querySelector('[name="experience_current"]').value = toggle.checked ? "1" : "0";
    endInput.readOnly = toggle.checked;
    if (toggle.checked) {
        endInput.value = "";
    }
});
