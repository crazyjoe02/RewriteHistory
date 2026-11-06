(function () {
    function rowIsPinned(row) {
        // Rows like the bold "Career" summary row use colspan and should stay pinned at the bottom.
        return Array.prototype.some.call(row.cells, function (td) {
            return td.hasAttribute("colspan");
        });
    }

    function getCellSortValue(td) {
        if (td.hasAttribute("data-sort")) {
            var v = td.getAttribute("data-sort");
            var n = parseFloat(v);
            return isNaN(n) ? v.toLowerCase() : n;
        }
        var text = td.textContent.trim();
        var cleaned = text.replace(/,/g, "");
        if (cleaned !== "" && !isNaN(parseFloat(cleaned)) && /^-?[0-9.]+$/.test(cleaned)) {
            return parseFloat(cleaned);
        }
        return text.toLowerCase();
    }

    function sortTable(table, colIndex, asc) {
        var tbody = table.tBodies[0];
        if (!tbody) return;
        var rows = Array.prototype.slice.call(tbody.rows);
        var pinned = rows.filter(rowIsPinned);
        var sortable = rows.filter(function (r) { return !rowIsPinned(r); });

        sortable.sort(function (a, b) {
            var va = getCellSortValue(a.cells[colIndex]);
            var vb = getCellSortValue(b.cells[colIndex]);
            if (va < vb) return asc ? -1 : 1;
            if (va > vb) return asc ? 1 : -1;
            return 0;
        });

        sortable.concat(pinned).forEach(function (r) { tbody.appendChild(r); });
    }

    function initTable(table) {
        var thead = table.tHead;
        if (!thead || !thead.rows.length) return;
        var headerRow = thead.rows[thead.rows.length - 1];

        Array.prototype.forEach.call(headerRow.cells, function (th, idx) {
            th.classList.add("sortable-col");
            th.addEventListener("click", function () {
                var newAsc = th.getAttribute("data-sort-dir") !== "asc";
                Array.prototype.forEach.call(headerRow.cells, function (h) {
                    h.removeAttribute("data-sort-dir");
                    h.classList.remove("sorted-asc", "sorted-desc");
                });
                th.setAttribute("data-sort-dir", newAsc ? "asc" : "desc");
                th.classList.add(newAsc ? "sorted-asc" : "sorted-desc");
                sortTable(table, idx, newAsc);
            });
        });
    }

    document.querySelectorAll("table.stats").forEach(initTable);
})();
