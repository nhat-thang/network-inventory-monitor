// Select / unselect all device checkboxes.
function toggleAll(source) {
  document.querySelectorAll('input[name="device"]').forEach(function (cb) { cb.checked = source.checked; });
}

// Follow a running task through Server-Sent Events and update the table live.
function followTask(taskId) {
  var rows = {};
  var log = document.getElementById('progress');
  var status = document.getElementById('task-status');
  var source = new EventSource('/tasks/' + taskId + '/events');
  source.onmessage = function (msg) {
    var e = JSON.parse(msg.data);
    if (e.type === 'start') {
      e.devices.forEach(function (name) {
        var tr = document.createElement('tr');
        tr.innerHTML = '<td><b>' + name + '</b></td><td><span class="badge wait">ĐANG CHẠY</span></td>' +
                       '<td class="nowrap">' + e.time + '</td><td></td>';
        log.appendChild(tr);
        rows[name] = tr;
      });
    } else if (e.type === 'device') {
      var tr = rows[e.device];
      if (!tr) { tr = document.createElement('tr'); log.appendChild(tr); rows[e.device] = tr; }
      var badge = e.ok ? '<span class="badge good">XONG</span>' : '<span class="badge critical">LỖI</span>';
      tr.innerHTML = '<td><b>' + e.device + '</b></td><td>' + badge + '</td><td class="nowrap">' + e.time +
                     '</td><td><pre></pre></td>';
      tr.querySelector('pre').textContent = e.detail || '';
    } else if (e.type === 'done') {
      source.close();
      status.className = 'flash ' + (e.ok ? 'info' : '');
      status.textContent = (e.ok ? 'Hoàn tất: ' : 'Lỗi: ') + (e.message || '');
      if (e.link) {
        var a = document.createElement('a');
        a.href = e.link; a.textContent = ' ' + e.link_text; a.style.marginLeft = '8px';
        status.appendChild(a);
      }
      if (e.alerts && e.alerts.length) {
        var box = document.getElementById('alerts');
        box.style.display = '';
        e.alerts.forEach(function (a) {
          var tr = document.createElement('tr');
          tr.innerHTML = '<td><span class="badge ' + a.severity + '">' + a.severity.toUpperCase() +
                         '</span></td><td><b>' + a.device + '</b></td><td></td>';
          tr.lastChild.textContent = a.message;
          box.querySelector('tbody').appendChild(tr);
        });
      }
    }
  };
}
