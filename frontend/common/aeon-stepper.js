/* Aeon 数字步进组件：给数字输入加 UI 适配的上下箭头
   用法：aeonStepper.attach(inputEl, { step: 0.01, min: 0, decimals: 2 })
   自动包裹 .num-stepper，隐藏原生 number 箭头 */
(function(){
  function attach(input, opts = {}){
    if (!input) return;
    const step = opts.step || parseFloat(input.step) || 1;
    const min = opts.min !== undefined ? opts.min : (parseFloat(input.min) || -Infinity);
    const decimals = opts.decimals !== undefined ? opts.decimals : (String(step).split('.')[1] || '').length;

    // 原生 number 箭头隐藏（只对 number 有效）
    input.style.MozAppearance = 'textfield';
    input.style.webkitAppearance = 'none';
    input.style.appearance = 'textfield';
    const hideArrows = document.createElement('style');
    hideArrows.textContent = `.num-stepper input::-webkit-outer-spin-button,.num-stepper input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}`;
    document.head.appendChild(hideArrows);

    // 包裹
    const wrap = document.createElement('div');
    wrap.className = 'num-stepper';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.innerHTML += `<div class="ns-arrows"><button type="button" class="up">▲</button><button type="button" class="down">▼</button></div>`;

    const arrows = wrap.querySelector('.ns-arrows');
    arrows.querySelector('.up').addEventListener('click', e => {
      e.preventDefault();
      change(step);
    });
    arrows.querySelector('.down').addEventListener('click', e => {
      e.preventDefault();
      change(-step);
    });
    // 滚轮
    wrap.addEventListener('wheel', e => {
      if (document.activeElement === input){
        e.preventDefault();
        change(e.deltaY < 0 ? step : -step);
      }
    }, { passive: false });

    function change(delta){
      let v = parseFloat(input.value);
      if (isNaN(v)) v = 0;
      v = Math.round((v + delta) * Math.pow(10, decimals)) / Math.pow(10, decimals);
      if (min !== -Infinity && v < min) v = min;
      input.value = v.toFixed(decimals);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  window.aeonStepper = { attach };
})();
