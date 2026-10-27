// 시세 자료 받기
// 화면 코드는 예전 Apps Script 화면에서 쓰던 google.script.run 방식 그대로 두고,
// 여기서 그 호출을 Apps Script 웹 앱 주소(KKOT_CONFIG.API_URL)로 보내는 fetch 요청으로 바꿉니다.
// 디자인을 바꿀 때 이 파일은 건드리지 않아도 됩니다.
(function () {
  var TIMEOUT_MS = 30000;

  function call(name, args) {
    var base = (window.KKOT_CONFIG && window.KKOT_CONFIG.API_URL) || '';
    if (!base) return Promise.reject(new Error('시세 서버 주소가 설정되지 않았습니다 (js/config.js).'));
    var url = new URL(base);
    url.searchParams.set('api', name);
    if (args.length) url.searchParams.set('args', JSON.stringify(args));
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS);
    return fetch(url.toString(), { redirect: 'follow', signal: ctrl.signal })
      .then(function (r) {
        if (!r.ok) throw new Error('시세 서버 응답 오류 (' + r.status + ')');
        return r.json();
      })
      .then(function (j) {
        if (!j || !j.ok) throw new Error((j && j.error) || '시세 서버 오류');
        return j.data;
      })
      .catch(function (e) {
        if (e && e.name === 'AbortError') throw new Error('시세 서버가 응답하지 않습니다. 잠시 후 새로고침해 주세요.');
        throw e;
      })
      .finally(function () { clearTimeout(timer); });
  }

  function runner(ok, fail) {
    return new Proxy({}, {
      get: function (_, prop) {
        if (prop === 'withSuccessHandler') return function (f) { return runner(f, fail); };
        if (prop === 'withFailureHandler') return function (f) { return runner(ok, f); };
        return function () {
          var args = Array.prototype.slice.call(arguments);
          call(String(prop), args)
            .then(function (d) { if (ok) ok(d); })
            .catch(function (e) { if (fail) fail(e); else console.error(e); });
        };
      }
    });
  }

  window.google = { script: { get run() { return runner(null, null); } } };
})();
