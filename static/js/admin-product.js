/* Back office product form: show only the boxes that matter for the kind of
 * product chosen. Hidden boxes keep their values and are still saved. */
(function () {
  'use strict';

  function kind() {
    var checked = document.querySelector('input[name="product_type"]:checked');
    return checked ? checked.value : null;
  }

  function show(selector, on) {
    document.querySelectorAll(selector).forEach(function (el) {
      el.style.display = on ? '' : 'none';
    });
  }

  function tidyRows() {
    // A row whose every box is hidden would leave an empty band behind.
    document.querySelectorAll('.field-row').forEach(function (row) {
      var lines = row.querySelectorAll('.field-line');
      if (!lines.length) return;
      var anyShown = Array.prototype.some.call(lines, function (l) {
        return l.style.display !== 'none';
      });
      row.style.display = anyShown ? '' : 'none';
    });
  }

  function apply() {
    var k = kind();
    if (!k) return;
    var tracked = document.getElementById('id_track_inventory');
    tracked = !tracked || tracked.checked;
    var sized = k === 'sized';

    show('.field-line.field-base_meters, .field-line.field-additional_meter_price,' +
         ' .field-line.field-max_additional_meters', k === 'cloth');
    show('.field-line.field-size_stock', tracked && sized);
    show('.field-line.field-stock', tracked && !sized);
    // Colour rows: sized products count stock per size, the rest one figure.
    show('td.field-size_stock, th.column-size_stock', sized);
    show('td.field-stock, th.column-stock', !sized);
    tidyRows();
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('input[name="product_type"], #id_track_inventory')
      .forEach(function (input) { input.addEventListener('change', apply); });
    apply();
  });
  document.addEventListener('formset:added', apply);
})();
