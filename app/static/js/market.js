// Панель «Анализ рынка»: при изменении формы запрашивает у сервера
// подходящие вакансии и оценку зарплаты.
(() => {
    const DEBOUNCE_MS = 1200;

    const form = document.getElementById("resume-form");
    const status = document.getElementById("market-status");
    const result = document.getElementById("market-result");
    const level = document.getElementById("market-level");
    const salary = document.getElementById("market-salary");
    const list = document.getElementById("market-vacancies");
    const source = document.getElementById("market-source");

    const money = new Intl.NumberFormat("ru-RU");
    let timer = null;
    let controller = null;
    let lastPayload = null;

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function formatSalary(min, max) {
        if (min && max && min !== max) return `${money.format(min)} – ${money.format(max)} ₽`;
        if (min) return `от ${money.format(min)} ₽`;
        if (max) return `до ${money.format(max)} ₽`;
        return "з/п не указана";
    }

    function formatExperience(years) {
        if (years === null) return "";
        return years === 0 ? "без опыта" : `опыт от ${years} г.`;
    }

    function renderSalary(data, expectations) {
        salary.replaceChildren();
        if (!data) {
            salary.append(el("p", "muted", "Недостаточно данных о зарплатах."));
            return;
        }
        salary.append(el("p", "salary-value", `≈ ${money.format(data.median)} ₽`));
        const details = data.low === data.high
            ? `по ${data.sample_size} вакансиям`
            : `обычно ${money.format(data.low)} – ${money.format(data.high)} ₽, по ${data.sample_size} вакансиям`;
        salary.append(el("p", "muted", details));
        if (data.approximate) {
            salary.append(el("p", "muted", "Вакансий вашего уровня мало, учтены все подходящие."));
        }
        if (expectations) {
            salary.append(el("p", "expectations", expectations));
        }
    }

    function renderVacancies(vacancies) {
        list.replaceChildren();
        for (const vacancy of vacancies) {
            const item = el("li");
            const link = el("a", null, vacancy.title);
            link.href = vacancy.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            item.append(link);

            const meta = [vacancy.company, vacancy.region].filter(Boolean).join(" · ");
            if (meta) item.append(el("div", "muted", meta));

            const terms = [formatSalary(vacancy.salary_min, vacancy.salary_max),
                formatExperience(vacancy.experience_years)].filter(Boolean).join(" · ");
            item.append(el("div", null, terms));

            if (vacancy.matched_skills.length) {
                item.append(el("div", "skills", `Совпадают навыки: ${vacancy.matched_skills.join(", ")}`));
            }
            if (vacancy.formats.length) {
                const formatClass = { true: "format-match", false: "format-mismatch" }[vacancy.format_match];
                const note = vacancy.format_match === false ? " — не совпадает с выбранным" : "";
                item.append(el("div", formatClass || "muted", `${vacancy.formats.join(", ")}${note}`));
            }
            list.append(item);
        }
    }

    function render(report) {
        level.textContent = `Ваш опыт: ${report.experience} · уровень ${report.level}`;
        source.replaceChildren();
        if (report.source_name) {
            source.append("Источник: ");
            const link = el("a", null, `«${report.source_name}»`);
            link.href = report.source_url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            source.append(link);
        }

        if (!report.queries.length) {
            status.textContent = report.message;
            result.hidden = true;
            return;
        }

        renderSalary(report.salary, report.expectations);
        renderVacancies(report.vacancies);
        const searchInfo = `Поиск: ${report.queries.map((q) => `«${q}»`).join(", ")}.`;
        const formatSelected = form.querySelector('[name="employment"]:checked');
        const formatInfo = formatSelected ? ` Из них в выбранном формате работы: ${report.format_matches}.` : "";
        status.textContent = report.message
            ? `${searchInfo} ${report.message}`
            : `${searchInfo} Подходящих вакансий: ${report.total_found}.${formatInfo}`;
        result.hidden = false;
    }

    function buildPayload() {
        const data = new FormData(form);
        data.delete("photo");
        return data;
    }

    async function update() {
        const data = buildPayload();
        const signature = new URLSearchParams(data).toString();
        if (signature === lastPayload) return;
        lastPayload = signature;

        if (controller) controller.abort();
        controller = new AbortController();
        status.textContent = "Ищу вакансии… Поиск по новой должности или навыку может занять до 15 секунд.";

        try {
            const response = await fetch(form.dataset.marketUrl, {
                method: "POST",
                body: data,
                signal: controller.signal,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            render(await response.json());
        } catch (error) {
            if (error.name === "AbortError") return;
            lastPayload = null;
            status.textContent = "Не удалось получить данные о вакансиях. Попробуйте позже.";
        }
    }

    function schedule() {
        clearTimeout(timer);
        timer = setTimeout(update, DEBOUNCE_MS);
    }

    form.addEventListener("input", schedule);
    form.addEventListener("change", schedule);
    form.addEventListener("click", (event) => {
        if (event.target.closest("[data-remove-entry]")) schedule();
    });
    update();
})();
