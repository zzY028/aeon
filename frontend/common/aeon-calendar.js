/* Aeon 胶片风日历组件
   用法：<input id="xxx" type="date"> → aeonCalendar.attach(inputEl, onChange)
   点击输入框弹出自绘日历，选完回填 YYYY-MM-DD */
(function(){
  let calEl = null, targetInput = null, viewYear = 0, viewMonth = 0;

  function ensureCal(){
    if (calEl) return calEl;
    calEl = document.createElement('div');
    calEl.className = 'aeon-cal';
    calEl.innerHTML = `
      <div class="cal-head">
        <button class="cal-prev" type="button">‹</button>
        <div class="cal-title"></div>
        <button class="cal-next" type="button">›</button>
      </div>
      <div class="cal-grid">
        <span class="cal-dow">日</span><span class="cal-dow">一</span><span class="cal-dow">二</span>
        <span class="cal-dow">三</span><span class="cal-dow">四</span><span class="cal-dow">五</span>
        <span class="cal-dow">六</span>
      </div>
      <div class="cal-days"></div>
      <div class="cal-foot"><button class="cal-today" type="button">今天</button></div>`;
    document.body.appendChild(calEl);
    calEl.querySelector('.cal-prev').addEventListener('click', () => {
      viewMonth--;
      if (viewMonth < 0){ viewMonth = 11; viewYear--; }
      render();
    });
    calEl.querySelector('.cal-next').addEventListener('click', () => {
      viewMonth++;
      if (viewMonth > 11){ viewMonth = 0; viewYear++; }
      render();
    });
    calEl.querySelector('.cal-today').addEventListener('click', () => {
      const now = new Date();
      viewYear = now.getFullYear(); viewMonth = now.getMonth();
      pick(now);
    });
    document.addEventListener('click', e => {
      if (calEl && calEl.classList.contains('open') &&
          !calEl.contains(e.target) && e.target !== targetInput){
        calEl.classList.remove('open');
      }
    });
    return calEl;
  }

  function render(){
    if (!calEl) return;
    const title = calEl.querySelector('.cal-title');
    title.textContent = `${viewYear} 年 ${viewMonth + 1} 月`;
    const daysEl = calEl.querySelector('.cal-days');
    const today = new Date();
    const first = new Date(viewYear, viewMonth, 1);
    const startDow = first.getDay();
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
    let html = '';
    for (let i = 0; i < startDow; i++) html += '<span class="cal-d empty"></span>';
    for (let d = 1; d <= daysInMonth; d++){
      const isToday = viewYear === today.getFullYear() && viewMonth === today.getMonth() && d === today.getDate();
      const val = `${viewYear}-${String(viewMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      html += `<span class="cal-d${isToday?' today':''}" data-v="${val}">${d}</span>`;
    }
    daysEl.innerHTML = html;
    daysEl.querySelectorAll('.cal-d:not(.empty)').forEach(el => {
      el.addEventListener('click', () => pick(new Date(el.dataset.v + 'T00:00:00')));
    });
    // 定位：贴在输入框下方
    if (targetInput){
      const rect = targetInput.getBoundingClientRect();
      calEl.style.top = Math.min(rect.bottom + 6, window.innerHeight - 320) + 'px';
      calEl.style.left = Math.min(rect.left, window.innerWidth - 260) + 'px';
    }
  }

  function pick(d){
    const val = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    if (targetInput){
      targetInput.value = val;
      targetInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
    if (calEl) calEl.classList.remove('open');
  }

  const api = {
    attach(inputEl){
      if (!inputEl) return;
      inputEl.addEventListener('click', e => {
        e.stopPropagation();
        const now = new Date();
        if (inputEl.value){
          const p = inputEl.value.split('-').map(Number);
          if (p.length === 3 && !isNaN(p[0])){ viewYear = p[0]; viewMonth = p[1] - 1; }
        } else { viewYear = now.getFullYear(); viewMonth = now.getMonth(); }
        ensureCal();
        targetInput = inputEl;
        render();
        calEl.classList.add('open');
      });
    }
  };
  window.aeonCalendar = api;
})();
