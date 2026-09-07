/* aeon-auth.js · 全站登录门禁
 * 1) getToken()  统一取 token：localStorage（自动登录）优先，其次 sessionStorage（会话级）
 * 2) requireLogin() 页面加载即检查，无 token 直接跳 login.html（带 redirect 回跳）
 * 3) toLogin()  401 时统一调用，跳登录页
 * 用法：在页面 <head> 或 body 顶部引入 <script src="common/aeon-auth.js"></script>
 *       然后 requireLogin(); 再 let TOKEN = aeonGetToken();
 */
(function (w) {
  const LS = 'aeon_token', LU = 'aeon_user';

  function getToken() {
    return localStorage.getItem(LS) || sessionStorage.getItem(LS) || '';
  }
  function getUser() {
    return localStorage.getItem(LU) || sessionStorage.getItem(LU) || '';
  }
  function toLogin() {
    const back = encodeURIComponent(location.pathname.split('/').pop() + location.search);
    location.replace('login.html?redirect=' + back);
  }
  function requireLogin() {
    if (!getToken()) toLogin();
  }
  function logout() {
    localStorage.removeItem(LS); localStorage.removeItem(LU);
    sessionStorage.removeItem(LS); sessionStorage.removeItem(LU);
    location.replace('login.html');
  }

  w.aeonGetToken = getToken;
  w.aeonGetUser = getUser;
  w.aeonToLogin = toLogin;
  w.aeonRequireLogin = requireLogin;
  w.aeonLogout = logout;
})(window);
