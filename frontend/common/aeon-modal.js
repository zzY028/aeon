/* Aeon 弹窗组件：替换原生 confirm/alert/prompt
   用法：aeonConfirm(msg) → Promise<boolean>
        aeonAlert(msg)   → Promise<void>
        aeonPrompt(msg, placeholder) → Promise<string|null> */
(function(){
  let maskEl = null;
  function ensureMask(){
    if (maskEl) return maskEl;
    maskEl = document.createElement('div');
    maskEl.className = 'modal-mask';
    maskEl.innerHTML = `
      <div class="modal">
        <button class="m-close" aria-label="关闭">✕</button>
        <div class="m-title"></div>
        <div class="m-msg"></div>
        <input class="m-input" style="display:none">
        <div class="m-actions">
          <button class="btn m-cancel">取消</button>
          <button class="btn btn-primary m-ok">确定</button>
        </div>
      </div>`;
    document.body.appendChild(maskEl);
    maskEl.addEventListener('click', e => { if (e.target === maskEl) hide(null); });
    maskEl.querySelector('.m-close').addEventListener('click', () => hide(null));
    maskEl.querySelector('.m-cancel').addEventListener('click', () => hide(null));
    maskEl.querySelector('.m-ok').addEventListener('click', () => {
      const inp = maskEl.querySelector('.m-input');
      hide(inp.style.display === 'none' ? true : inp.value);
    });
    return maskEl;
  }
  let resolver = null;
  function hide(result){
    if (maskEl) maskEl.classList.remove('open');
    if (resolver){ resolver(result); resolver = null; }
  }
  function show(title, msg, opts = {}){
    const el = ensureMask();
    el.querySelector('.m-title').textContent = title;
    el.querySelector('.m-msg').textContent = msg;
    const inp = el.querySelector('.m-input');
    if (opts.input){
      inp.style.display = '';
      inp.value = opts.placeholder || '';
      inp.focus();
    } else {
      inp.style.display = 'none';
    }
    el.querySelector('.m-ok').textContent = opts.okText || '确定';
    el.querySelector('.m-cancel').style.display = opts.cancel === false ? 'none' : '';
    el.classList.add('open');
    return new Promise(res => { resolver = res; });
  }
  window.aeonConfirm = (msg) => show('确认', msg, { okText: '确认' });
  window.aeonAlert   = (msg) => show('提示', msg, { okText: '知道了', cancel: false });
  window.aeonPrompt  = (msg, ph) => show('输入', msg, { okText: '确定', input: true, placeholder: ph });
})();
