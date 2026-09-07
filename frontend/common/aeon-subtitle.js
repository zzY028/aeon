/* Aeon 页面字幕：淡淡的电影旁白 + 打字机动画
   用法：aeonSubtitle.show('ledger') — 显示指定页面的字幕
   每页在 DOM 加 <div class="subtitle" id="aeonSubtitle"></div> */
(function(){
  let timer = null;
  const api = {
    async show(pageKey){
      const el = document.getElementById('aeonSubtitle');
      if (!el) return;
      const TOKEN = (window.aeonGetToken ? aeonGetToken() : (localStorage.getItem('aeon_token') || ''));
      let text = '';
      try {
        // 尝试 AI 字幕
        const r = await fetch('/api/life/subtitles', {
          method: 'POST',
          headers: { 'Content-Type':'application/json', 'Authorization':'Bearer '+TOKEN }
        });
        if (r.ok){
          const d = await r.json();
          text = (d.subtitles || {})[pageKey] || '';
        }
      } catch(e) {}
      if (!text){
        // 降级：生活簿生成简单字幕
        try {
          const r = await fetch('/api/life/book', {
            headers: { 'Authorization':'Bearer '+TOKEN }
          });
          if (r.ok){
            const d = await r.json();
            text = api.fallback(d, pageKey);
          }
        } catch(e) {}
      }
      if (!text) return;
      // 打字机动画
      el.textContent = '';
      el.classList.add('visible');
      let i = 0;
      clearInterval(timer);
      timer = setInterval(() => {
        el.textContent = text.slice(0, ++i);
        if (i >= text.length) clearInterval(timer);
      }, 55);
    },
    fallback(d, pageKey){
      const lb = d.ledger || {};
      const hb = d.habits || {};
      const sb = d.schedule || {};
      const rd = d.reading || [];
      switch(pageKey){
        case 'index': return lb.today_out > 0 ? `今天花了 ¥${lb.today_out}，共 ${lb.today_count} 笔。` : '今天还没花钱，日子安安静静。';
        case 'ledger': return `本月支出 ¥${lb.month_out}，收入 ¥${lb.month_in}。`;
        case 'habits': return `今日习惯完成 ${hb.done_today}/${hb.total} 项。`;
        case 'schedule': return sb.today_count > 0 ? `今日 ${sb.today_count} 件事待办，别忘啦。` : '今天日程空空的，自由一天。';
        case 'wishlist': return '待买清单还躺着几样东西，冷静期过了再决定。';
        case 'media': return rd.length ? `《${rd[0].title}》读到 ${rd[0].percent}% 了，慢慢来。` : '书架还空着，找本书来读吧。';
        case 'briefing': return '今天的早报已更新，去看看吧。';
        default: return '';
      }
    }
  };
  window.aeonSubtitle = api;
})();
