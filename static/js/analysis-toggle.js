/* Issue #28 — Analysis detail panel toggle */

function toggleAnalysisDetail(btn) {
  var expanded = btn.getAttribute('aria-expanded') === 'true';
  var panel = document.getElementById(btn.getAttribute('aria-controls'));
  if (!panel) return;
  btn.setAttribute('aria-expanded', String(!expanded));
  panel.hidden = expanded;
  btn.textContent = expanded ? '질문별 분석 보기' : '질문별 분석 접기';

  /* Fire UI event on expand (fail silently) */
  if (!expanded) {
    var wedge = btn.closest('.analysis-wedge');
    var sessionId = wedge ? wedge.getAttribute('data-session-id') : null;
    if (sessionId) {
      fetch('/sessions/' + sessionId + '/analysis/detail-opened', {
        method: 'POST',
        credentials: 'same-origin',
      }).catch(function () { /* silent */ });
    }
  }
}

document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    var panel = document.getElementById('analysis-detail-panel');
    if (panel && !panel.hidden) {
      var toggle = document.querySelector(
        '[aria-controls="analysis-detail-panel"]'
      );
      if (toggle) {
        toggleAnalysisDetail(toggle);
        toggle.focus();
      }
    }
  }
});
