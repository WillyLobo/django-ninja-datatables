/*!
 * ninja-datatable.js — DataTables client for django-ninja-datatables endpoints.
 * https://github.com/WillyLobo/django-ninja-datatables
 * Copyright (c) 2026 WillyLobo, MIT License.
 *
 * The row-expansion handler and row-detail loader are adapted from
 * django-ajax-datatable (https://github.com/morlandi/django-ajax-datatable),
 * Copyright (c) 2017, Mario Orlandi, used under the MIT License (see the
 * package's THIRD_PARTY_NOTICES file for the full text).
 *
 * Requires jQuery and DataTables 2.x (server-side mode). Columns are declared
 * statically in each template and requests use a flat query-string contract:
 *   draw, start, length, search, order_by ("-col1,col2"), filters (JSON {col: value})
 * The expected response is {draw, recordsTotal, recordsFiltered, data}.
 *
 * Usage:
 *   NinjaDatatableUtils.initialize_table($('#table'), '/api/datatables/items/', columns, {
 *       detailUrl: '/api/datatables/items/{id}/detail/',
 *   });
 *
 * Column options on top of DataTables' own:
 *   filterable: false              no filter for this column
 *   filterType: 'select' | 'date'  (default: free text)
 *   filterChoices: [[value, label], ...]
 *   filterChoicesUrl: URL returning {choices: [[value, label], ...]}
 *
 * Translations: load a file defining window.DATATABLES_<LANG> (DataTables'
 * `language` object) and window.NINJA_DATATABLES_I18N ({loadingText, errorText}),
 * e.g. i18n/es.js, or pass `language`/`loadingText`/`errorText` as options.
 */
(function(root, $) {
    'use strict';

    var DEFAULTS = {
        order: [[0, 'desc']],
        lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
        language: undefined,          // defaults to window.DATATABLES_ES when loaded
        columnFilters: true,          // per-column filter row below the header
        filterDelay: 300,             // ms to wait after typing in a text filter
        detailUrl: null,              // '/.../{id}/detail/' -> expandable rows
        idField: 'id',                // row field that replaces {id} in detailUrl
        loadingText: undefined,       // defaults to NINJA_DATATABLES_I18N or 'Loading...'
        errorText: undefined,         // defaults to NINJA_DATATABLES_I18N or 'Could not load details.'
        extraFilters: null,           // function() -> {key: value} merged into the filters
        classes: {
            filterRow: 'ninja-datatable-filter-row',
            input: 'form-control form-control-sm',
            select: 'form-select form-select-sm',
            detailWrapper: 'row-details-wrapper',
            loading: 'loading'
        },
        layout: {
            topStart: 'search',
            topEnd: 'pageLength',
            bottomStart: 'info',
            bottomEnd: 'paging'
        },
        dataTableOptions: {}          // raw DataTables options, override everything above
    };

    function _load_row_details(rowData, opts) {
        var div = $('<div/>')
            .addClass(opts.classes.detailWrapper + ' ' + opts.classes.loading)
            .text(opts.loadingText);
        var url = opts.detailUrl.replace('{id}', encodeURIComponent(rowData[opts.idField]));
        $.ajax({ url: url, dataType: 'json' })
            .done(function(json) {
                div.html(json.html).removeClass(opts.classes.loading);
            })
            .fail(function() {
                div.text(opts.errorText).removeClass(opts.classes.loading);
            });
        return div;
    }

    // Clicking any cell of a row expands/collapses a child row with its details.
    function _bind_row_expand(table, opts) {
        table.on('click', 'td', function(event) {
            var tr = $(this).closest('tr');
            if (tr.hasClass('details') && !$(event.target).hasClass('btn-close')) {
                return;
            }
            // Clicks on links/buttons inside the cell (e.g. actions) don't expand.
            if ($(event.target).closest('a, button, input, select, label').length) {
                return;
            }
            var row = table.row(tr);
            if (!row.data()) {
                return;
            }
            if (row.child.isShown()) {
                row.child.hide();
                tr.removeClass('shown');
                return;
            }
            table.rows().every(function() { this.child.hide(); });
            table.$('tr').removeClass('shown');
            row.child(_load_row_details(row.data(), opts), 'details').show();
            tr.addClass('shown');
        });
    }

    // Supports multi-column ordering (shift+click): each entry is sent as
    // "-key" (desc) or "key" (asc), comma-separated.
    function _order_by_param(dtOrder, columns) {
        if (!dtOrder || !dtOrder.length) {
            return '';
        }
        return dtOrder.map(function(o) {
            var col = columns[o.column];
            var key = (col && (col.name || col.data)) || 'id';
            return (o.dir === 'desc' ? '-' : '') + key;
        }).join(',');
    }

    function _apply_filter_value(table, columnFilters, key, value) {
        if (value) {
            columnFilters[key] = value;
        } else {
            delete columnFilters[key];
        }
        table.draw();
    }

    function _fill_select_choices(select, choices) {
        choices.forEach(function(choice) {
            $('<option></option>').attr('value', choice[0]).text(choice[1]).appendTo(select);
        });
    }

    function _build_filter(table, columnFilters, col, key, opts) {
        var field;
        if (col.filterType === 'select') {
            field = $('<select><option value=""></option></select>').addClass(opts.classes.select);
            if (col.filterChoices) {
                _fill_select_choices(field, col.filterChoices);
            } else if (col.filterChoicesUrl) {
                $.getJSON(col.filterChoicesUrl, function(data) {
                    _fill_select_choices(field, data.choices || []);
                });
            }
            field.on('change', function() {
                _apply_filter_value(table, columnFilters, key, $(this).val());
            });
        } else if (col.filterType === 'date') {
            // The value reaches the backend as ISO yyyy-mm-dd, ready for a DateField.
            field = $('<input type="date">').addClass(opts.classes.input);
            field.on('change', function() {
                _apply_filter_value(table, columnFilters, key, $(this).val());
            });
        } else {
            var timer = null;
            var last = '';
            field = $('<input type="text" placeholder="...">').addClass(opts.classes.input);
            field.on('keyup change', function() {
                var value = $(this).val();
                if (value === last) {
                    return;
                }
                clearTimeout(timer);
                timer = setTimeout(function() {
                    last = value;
                    _apply_filter_value(table, columnFilters, key, value);
                }, opts.filterDelay);
            });
        }
        return field;
    }

    // Adds a row of per-column filters below the header.
    function _bind_column_filters(table, element, columns, columnFilters, opts) {
        var filterRow = $('<tr></tr>').addClass(opts.classes.filterRow);
        columns.forEach(function(col) {
            var cell = $('<th></th>');
            if (col.filterable !== false && col.searchable !== false && col.data) {
                var key = col.name || col.data;
                cell.append(_build_filter(table, columnFilters, col, key, opts));
            }
            filterRow.append(cell);
        });
        element.find('thead').append(filterRow);
    }

    function initialize_table(element, url, columns, options) {
        options = options || {};
        // Shallow merge: arrays such as order/lengthMenu are replaced whole.
        // Only `classes` is merged key by key.
        var opts = $.extend({}, DEFAULTS, options);
        opts.classes = $.extend({}, DEFAULTS.classes, options.classes || {});
        // Translations are read here rather than at load time, so script order doesn't matter.
        var i18n = root.NINJA_DATATABLES_I18N || {};
        if (opts.language === undefined) {
            opts.language = root.DATATABLES_ES;
        }
        if (opts.loadingText === undefined) {
            opts.loadingText = i18n.loadingText || 'Loading...';
        }
        if (opts.errorText === undefined) {
            opts.errorText = i18n.errorText || 'Could not load details.';
        }
        var columnFilters = {};

        var dtOptions = $.extend({
            processing: true,
            serverSide: true,
            autoWidth: false,
            language: opts.language,
            layout: opts.layout,
            columns: columns,
            order: opts.order,
            lengthMenu: opts.lengthMenu,
            ajax: {
                url: url,
                type: 'GET',
                data: function(d) {
                    var extraFilters = opts.extraFilters ? opts.extraFilters() : {};
                    return {
                        draw: d.draw,
                        start: d.start,
                        length: d.length,
                        search: d.search.value,
                        order_by: _order_by_param(d.order, columns),
                        filters: JSON.stringify($.extend({}, columnFilters, extraFilters))
                    };
                }
            }
        }, opts.dataTableOptions);

        var table = element.DataTable(dtOptions);

        if (opts.columnFilters !== false) {
            _bind_column_filters(table, element, columns, columnFilters, opts);
        }
        if (opts.detailUrl) {
            _bind_row_expand(table, opts);
        }
        return table;
    }

    root.NinjaDatatableUtils = {
        defaults: DEFAULTS,
        initialize_table: initialize_table
    };

})(window, window.jQuery);
