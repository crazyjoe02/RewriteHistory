(function () {
    var input = document.getElementById("site-search-input");
    var resultsBox = document.getElementById("site-search-results");
    var header = document.querySelector(".site-header");
    if (!input || !resultsBox || !header) return;

    var root = header.getAttribute("data-root") || "./";
    var index = null;
    var activeIndex = -1;

    function loadIndex() {
        if (index) return Promise.resolve(index);
        return fetch(root + "static/search-index.json")
            .then(function (r) { return r.json(); })
            .then(function (data) { index = data; return data; });
    }

    function render(matches, query) {
        resultsBox.innerHTML = "";
        activeIndex = -1;
        if (!query) {
            resultsBox.classList.remove("open");
            return;
        }
        if (matches.length === 0) {
            var empty = document.createElement("div");
            empty.className = "search-empty";
            empty.textContent = "No matches";
            resultsBox.appendChild(empty);
            resultsBox.classList.add("open");
            return;
        }
        matches.slice(0, 15).forEach(function (item) {
            var a = document.createElement("a");
            a.href = root + item.url;
            a.className = "search-result";
            a.innerHTML =
                '<span class="search-result-name">' + escapeHtml(item.name) + '</span>' +
                '<span class="search-result-meta">' + escapeHtml(item.type) + (item.sub ? " \u00b7 " + escapeHtml(item.sub) : "") + '</span>';
            resultsBox.appendChild(a);
        });
        resultsBox.classList.add("open");
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function search(query) {
        var q = query.trim().toLowerCase();
        if (!q) { render([], ""); return; }
        loadIndex().then(function (data) {
            var starts = [];
            var contains = [];
            for (var i = 0; i < data.length; i++) {
                var name = data[i].name.toLowerCase();
                if (name.indexOf(q) === 0) {
                    starts.push(data[i]);
                } else if (name.indexOf(q) !== -1) {
                    contains.push(data[i]);
                }
            }
            render(starts.concat(contains), q);
        });
    }

    var debounceTimer;
    input.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        var val = input.value;
        debounceTimer = setTimeout(function () { search(val); }, 80);
    });

    input.addEventListener("keydown", function (e) {
        var items = resultsBox.querySelectorAll(".search-result");
        if (e.key === "ArrowDown") {
            e.preventDefault();
            if (items.length === 0) return;
            activeIndex = (activeIndex + 1) % items.length;
            updateActive(items);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            if (items.length === 0) return;
            activeIndex = (activeIndex - 1 + items.length) % items.length;
            updateActive(items);
        } else if (e.key === "Enter") {
            if (activeIndex >= 0 && items[activeIndex]) {
                window.location.href = items[activeIndex].href;
            } else if (items.length > 0) {
                window.location.href = items[0].href;
            }
        } else if (e.key === "Escape") {
            resultsBox.classList.remove("open");
            input.blur();
        }
    });

    function updateActive(items) {
        items.forEach(function (el, i) {
            el.classList.toggle("active", i === activeIndex);
        });
        if (items[activeIndex]) {
            items[activeIndex].scrollIntoView({ block: "nearest" });
        }
    }

    document.addEventListener("click", function (e) {
        if (!header.contains(e.target)) {
            resultsBox.classList.remove("open");
        }
    });

    input.addEventListener("focus", function () {
        if (input.value.trim()) search(input.value);
    });
})();
