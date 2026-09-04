/* Aeon 2.5 公共请求层：乐观更新 + 本地缓存
   ─────────────────────────────────────────────
   核心思想（SWR + Optimistic UI）：
   1. 打开页面 → 先渲染 localStorage 缓存 → 立即有内容（无延迟感）
   2. 后台静默请求新数据 → 到了就替换
   3. 用户操作（记账/打卡/删除）→ 先本地改界面（乐观）→ 后台同步
      → 失败才回滚 + 提示
   
   用法：
     aeonData.get('/api/ledger')            → 带缓存读取
     aeonData.mutate('/api/ledger', data)   → 乐观更新（先改界面）
     aeonData.refresh()                     → 页面加载时刷新所有
   ───────────────────────────────────────────── */
(function(){
  const CACHE_PREFIX = 'aeon_cache_';
  const CACHE_TTL = 5 * 60 * 1000; // 5 分钟缓存

  // 读取缓存（带过期检查）
  function readCache(key){
    try {
      const raw = localStorage.getItem(CACHE_PREFIX + key);
      if (!raw) return null;
      const d = JSON.parse(raw);
      if (Date.now() - d.ts > CACHE_TTL) return null;
      return d.data;
    } catch(e) { return null; }
  }
  // 写缓存
  function writeCache(key, data){
    try {
      localStorage.setItem(CACHE_PREFIX + key, JSON.stringify({ ts: Date.now(), data }));
    } catch(e) {}
  }

  // 带缓存的 GET：先返回缓存（如果有），同时后台刷新
  async function getCached(key, fetcher){
    const cached = readCache(key);
    if (cached !== null){
      // 有缓存 → 先返回，后台刷新（不阻塞）
      fetcher().then(fresh => {
        if (fresh !== undefined){
          writeCache(key, fresh);
          window.dispatchEvent(new CustomEvent('aeon:data', { detail: { key, data: fresh } }));
        }
      }).catch(() => {});
      return cached;
    }
    // 无缓存 → 直接请求
    const fresh = await fetcher();
    if (fresh !== undefined) writeCache(key, fresh);
    return fresh;
  }

  // 乐观更新：先写缓存（界面立即用），再后台同步，失败回滚
  async function optimistic(key, doOptimistic, fetcher){
    const prev = readCache(key);
    // 1. 立即乐观应用
    if (doOptimistic) doOptimistic();
    try {
      // 2. 后台同步
      const fresh = await fetcher();
      if (fresh !== undefined){
        writeCache(key, fresh);
        window.dispatchEvent(new CustomEvent('aeon:data', { detail: { key, data: fresh } }));
      }
      return fresh;
    } catch(e) {
      // 3. 失败回滚
      if (prev !== null) writeCache(key, prev);
      window.dispatchEvent(new CustomEvent('aeon:rollback', { detail: { key } }));
      throw e;
    }
  }

  window.aeonData = {
    readCache,
    writeCache,
    getCached,
    optimistic,
    clear(){
      const keys = [];
      for (let i = 0; i < localStorage.length; i++){
        const k = localStorage.key(i);
        if (k && k.startsWith(CACHE_PREFIX)) keys.push(k);
      }
      keys.forEach(k => localStorage.removeItem(k));
    }
  };
})();
