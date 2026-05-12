import"./style-qVGqHsGO.js";function e(){let e=new Date;return`${e.getFullYear()} 年 ${e.getMonth()+1} 月 ${e.getDate()} 日（週${[`日`,`一`,`二`,`三`,`四`,`五`,`六`][e.getDay()]}）`}function t(e){let[,t,n]=e.split(`-`);return`${t} / ${n}`}function n(e){return`週${[`日`,`一`,`二`,`三`,`四`,`五`,`六`][new Date(e+`T00:00:00`).getDay()]}`}function r(e){let[t,n]=e.split(`-`);return`${t} 年 ${parseInt(n)} 月`}function i(e,t=2){return e==null||isNaN(e)?`—`:e.toLocaleString(`en-US`,{minimumFractionDigits:t,maximumFractionDigits:t})}function a(e,t=2){return e==null||isNaN(e)?`—`:Number(e).toLocaleString(`en-US`,{minimumFractionDigits:t,maximumFractionDigits:t})}function o(e){if(!e)return`—`;let t=new Date(e);return`${String(t.getHours()).padStart(2,`0`)}:${String(t.getMinutes()).padStart(2,`0`)}`}function s(e){return String(e??``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`).replace(/'/g,`&#39;`)}async function c(){let e=await fetch(`/data/index.json`);if(!e.ok)throw Error(`index.json 讀取失敗`);return e.json()}function l(e){let i=document.getElementById(`article-list`);if(!e.length){i.innerHTML=`<p style="color:var(--text-2);font-size:.88rem;padding:1rem 0">尚無文章</p>`;return}let a=new Map;e.forEach(e=>{let t=r(e.date);a.has(t)||a.set(t,[]),a.get(t).push(e)});let o=``;a.forEach((e,r)=>{o+=`<div class="month-group">`,a.size>1&&(o+=`<div class="month-label">${s(r)}</div>`),e.forEach(e=>{let r=t(e.date),i=n(e.date),a=(e.tags||[]).slice(0,4).map(e=>`<span class="item-tag">${s(e)}</span>`).join(``);o+=`
        <a class="article-item" href="article.html?date=${s(e.date_key)}" aria-label="${s(e.title)}">
          <span class="article-item-date">${s(r)}<br><span style="color:var(--text-3)">${s(i)}</span></span>
          <span class="article-item-body">
            <span class="article-item-title">${s(e.title)}</span>
            <span class="article-item-tags">${a}</span>
          </span>
          <svg class="article-item-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="5" y1="12" x2="19" y2="12"/>
            <polyline points="12 5 19 12 12 19"/>
          </svg>
        </a>`}),o+=`</div>`}),i.innerHTML=o}function u(){let e=document.documentElement,t=document.querySelector(`.ticker-wrap`),n=document.querySelector(`.site-header`),r=document.querySelector(`.tab-nav`);if(!e||!t||!n||!r)return;let i=Math.round(t.getBoundingClientRect().height||40),a=Math.round(n.getBoundingClientRect().height||52),o=Math.round(r.getBoundingClientRect().height||56);e.style.setProperty(`--ticker-h`,`${i}px`),e.style.setProperty(`--header-h`,`${a}px`),e.style.setProperty(`--tab-nav-h`,`${o}px`)}function d(){let e=document.querySelectorAll(`.tab-btn`),t=document.querySelectorAll(`.tab-pane`),n=n=>{document.body.classList.toggle(`dashboard-tab-active`,n===`tab-dashboard`),e.forEach(e=>e.classList.remove(`active`)),t.forEach(e=>e.classList.remove(`active`));let r=Array.from(e).find(e=>e.getAttribute(`data-target`)===n);r&&r.classList.add(`active`);let i=document.getElementById(n);i&&i.classList.add(`active`);let a=()=>{window.scrollTo(0,0),document.documentElement.scrollTop=0,document.body.scrollTop=0};if(a(),requestAnimationFrame(()=>{a(),u(),requestAnimationFrame(a)}),u(),n===`tab-dashboard`||n===`tab-video`){[120,320,700,1200,1800].forEach(e=>{setTimeout(a,e)});let e=Date.now()+1800,t=n=>{if(Date.now()>e){document.removeEventListener(`focusin`,t,!0);return}i&&i.contains(n.target)&&a()};document.addEventListener(`focusin`,t,!0)}};e.forEach(e=>{e.addEventListener(`click`,()=>{n(e.getAttribute(`data-target`))})})}function f(){let e=document.querySelector(`.hero-rotator`);if(!e)return;let t=Array.from(e.querySelectorAll(`.hero-slide`)),n=e.querySelector(`#hero-dots`),r=e.querySelector(`#hero-prev`),i=e.querySelector(`#hero-next`);if(!t.length||!n||!r||!i)return;let a=0,o=null,s=t.map((e,t)=>{let r=document.createElement(`button`);return r.className=`hero-dot${t===0?` is-active`:``}`,r.type=`button`,r.setAttribute(`aria-label`,`切換到第 ${t+1} 張 Banner`),r.addEventListener(`click`,()=>{c(t),p()}),n.appendChild(r),r});function c(e){a=(e+t.length)%t.length,t.forEach((e,t)=>e.classList.toggle(`is-active`,t===a)),s.forEach((e,t)=>e.classList.toggle(`is-active`,t===a))}function l(){c(a+1)}function u(){c(a-1)}function d(){o||=setInterval(l,6200)}function f(){o&&=(clearInterval(o),null)}function p(){f(),d()}i.addEventListener(`click`,()=>{l(),p()}),r.addEventListener(`click`,()=>{u(),p()}),e.addEventListener(`mouseenter`,f),e.addEventListener(`mouseleave`,d),e.addEventListener(`focusin`,f),e.addEventListener(`focusout`,d),document.addEventListener(`visibilitychange`,()=>{document.hidden?f():d()}),d()}function p(e,t,n){if(!t||t.length<2)return;let r=Math.min(...t),i=Math.max(...t)-r||1,a=t.map((e,n)=>[3+n/(t.length-1)*194,43-(e-r)/i*40]),o=a.map(e=>e.join(`,`)).join(` `),s=[...a,[a[a.length-1][0],43],[a[0][0],43]].map(e=>e.join(`,`)).join(` `),c=`spk`+Math.random().toString(36).slice(2,7);e.innerHTML=`
    <defs>
      <linearGradient id="${c}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"   stop-color="${n}" stop-opacity="0.28"/>
        <stop offset="100%" stop-color="${n}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <polygon
      points="${s}"
      fill="url(#${c})"
    />
    <polyline
      points="${o}"
      fill="none"
      stroke="${n}"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  `}function m(e){let t=document.getElementById(`ticker-track`);if(!t||!e?.length)return;let n=e.map(e=>{let t=e.change>=0,n=t?`+`:``,r=t?`up`:`down`;return`
      <div class="ticker-item">
        <span class="ti-name">${s(e.name)}</span>
        <span class="ti-price">${i(e.price)}</span>
        <span class="ti-change ${r}">${n}${e.change.toFixed(2)}</span>
        <span class="ti-sep">·</span>
        <span class="ti-pct ${r}">${n}${e.changePct.toFixed(2)}%</span>
      </div>
    `}).join(``);t.innerHTML=n+n}function h(e){let t=document.getElementById(`market-overview-grid`);!t||!e?.length||(t.innerHTML=e.map(e=>{let t=e.price!=null&&!isNaN(e.price),n=Number(e.change)>=0,r=n?`+`:``,a=n?`market-up`:`market-down`,o=e.decimals??2,c=e.fresh?`即時/準即時`:`快取/待更新`,l=e.fresh?`fresh`:`stale`;return`
      <article class="market-overview-card ${t?``:`is-empty`}">
        <div class="market-card-topline">
          <span class="market-card-group">${s(e.group||e.market||``)}</span>
          <span class="market-card-status ${l}">${c}</span>
        </div>
        <h4 class="market-card-name">${s(e.name)}</h4>
        <div class="market-card-price">${t?i(e.price,o):`—`}</div>
        <div class="market-card-change ${t?a:``}">
          ${t?`${r}${Number(e.change).toFixed(o)} · ${r}${Number(e.changePct).toFixed(2)}%`:`資料待補`}
        </div>
        <div class="market-card-date">資料日：${s(e.date||`—`)}</div>
      </article>
    `}).join(``))}function g(e){let t=document.getElementById(`watchlist-body`);!t||!e?.length||(t.innerHTML=e.map(e=>{let t=e.price!=null&&!isNaN(e.price),n=Number(e.change)>=0,r=n?`+`:``,a=n?`market-up`:`market-down`,o=e.decimals??2;return`
      <tr class="${e.fresh?``:`is-stale`}">
        <td>
          <span class="watch-name">${s(e.name)}</span>
          <span class="watch-symbol">${s(e.symbol||``)}</span>
        </td>
        <td><span class="watch-market">${s(e.market||`—`)}</span></td>
        <td class="num">${t?i(e.price,o):`—`}</td>
        <td class="num ${t?a:``}">
          ${t?`${r}${Number(e.change).toFixed(o)} / ${r}${Number(e.changePct).toFixed(2)}%`:`—`}
        </td>
        <td>
          <span class="watch-date">${s(e.date||`—`)}</span>
          ${e.fresh?``:`<span class="watch-cache">快取</span>`}
        </td>
      </tr>
    `}).join(``))}function _(e){let t={usdtwd:`#60a5fa`,twse:`#22c55e`,brent:`#fb923c`,gold:`#f59e0b`,copper:`#f97316`};document.querySelectorAll(`.macro-data[data-key]`).forEach(n=>{let r=n.dataset.key,a=e[r];if(!a)return;let o=a.change>=0,s=o?`+`:``,c=a.decimals??2,l=n.dataset.color||t[r]||`#888`;n.querySelector(`.macro-price-num`).textContent=i(a.price,c);let u=n.querySelector(`.macro-price-chg`);u.textContent=`${s}${a.change.toFixed(c)}   ${s}${a.changePct.toFixed(2)}%`,u.className=`macro-price-chg ${o?`market-up`:`market-down`}`;let d=n.querySelector(`.macro-spark`);d&&a.closes?.length>=2&&p(d,a.closes,l)})}function v(e){e&&document.querySelectorAll(`.macro-stat-item[data-stat-key]`).forEach(t=>{let n=e[t.dataset.statKey];if(!n)return;let r=t.querySelector(`.macro-stat-value`),i=t.querySelector(`.macro-stat-date`);if(!r||!i)return;let o=n.decimals??2,s=n.unit?` ${n.unit}`:``;r.textContent=`${a(n.value,o)}${s}`,i.textContent=`更新：${n.date||`—`}${n.fresh===!1?`（快取）`:``}`})}async function y(){try{let e=await fetch(`/api/market-data`);if(!e.ok)throw Error(`HTTP ${e.status}`);let t=await e.json();t.overview?.length&&h(t.overview),t.watchlist?.length&&g(t.watchlist),t.ticker?.length&&m(t.ticker),t.macro&&_(t.macro),t.macroStats&&v(t.macroStats);let n=document.getElementById(`macro-update-time`);n&&t.ts&&(n.textContent=`資料來源：Stooq + 官方機構 · 更新 ${o(t.ts)}${t.stale?` · 使用快取`:``}`);let r=document.getElementById(`market-freshness`);r&&t.ts&&(r.textContent=`資料來源：Stooq + TradingView · 更新 ${o(t.ts)}${t.stale?` · 使用快取`:``}`)}catch(e){console.warn(`[market-data]`,e.message)}}function b(e){return String(e??``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`)}function x(e){if(!e)return``;let[,t,n]=e.split(`-`);return`${parseInt(t)} 月 ${parseInt(n)} 日`}async function S(){let e=document.getElementById(`video-featured-container`),t=document.getElementById(`video-grid-container`);if(e)try{let n=await fetch(`/data/videos.json`);if(!n.ok)throw Error(`no videos.json`);let{videos:r}=await n.json();if(!r||!r.length)return;let i=r[0],a=encodeURIComponent(i.video_id);e.innerHTML=`
      <div class="yt-embed-container">
        <iframe
          src="https://www.youtube.com/embed/${a}?rel=0&modestbranding=1&autoplay=0"
          title="${b(i.title)}"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowfullscreen
        ></iframe>
      </div>
      <div class="yt-featured-meta">
        <span class="yt-featured-date">${b(x(i.date))}</span>
        <h4 class="yt-featured-title">${b(i.title)}</h4>
        <a class="yt-featured-link" href="https://www.youtube.com/watch?v=${a}" target="_blank" rel="noopener noreferrer">在 YouTube 觀看 ↗</a>
      </div>`;let o=document.querySelector(`#tab-video .yt-channel-desc`);o&&(o.textContent=`最新影片：${i.date}　·　每日 AI 自動生成財經解析短影音`),r.length>1&&(t.innerHTML=`
        <h4 class="yt-past-heading">過往影片</h4>
        <div class="yt-past-grid">${r.slice(1).map(e=>{let t=encodeURIComponent(e.video_id);return`
          <a class="yt-past-item" href="https://www.youtube.com/watch?v=${t}" target="_blank" rel="noopener noreferrer">
            <div class="yt-past-thumb">
              <img src="https://img.youtube.com/vi/${t}/mqdefault.jpg" alt="${b(e.title)}" loading="lazy">
              <div class="yt-past-play">▶</div>
            </div>
            <div class="yt-past-info">
              <span class="yt-past-date">${b(x(e.date))}</span>
              <div class="yt-past-title">${b(e.title)}</div>
            </div>
          </a>`}).join(``)}</div>`)}catch{}}async function C(){try{let e=await fetch(`/data/accuracy.json`);if(!e.ok)return;let t=await e.json(),n=document.getElementById(`acc-rows`),r=document.getElementById(`acc-updated`);if(!n)return;if(t.last_updated){let[,e,n]=t.last_updated.split(`-`);r.textContent=`更新 ${e}/${n}`}n.innerHTML=[{key:`combined`,label:`綜合`},{key:`technical`,label:`技術面`},{key:`fundamental`,label:`基本面`}].map(({key:e,label:n})=>{let r=t[e],i=r&&r.total>0?r.pct:null;return`
        <div class="acc-row">
          <span class="acc-label">${n}</span>
          <span class="acc-pct ${e}">${i===null?`—`:i+`%`}</span>
          <div class="acc-bar-wrap">
            <div class="acc-bar ${e}" style="width:${i??0}%"></div>
          </div>
          <span class="acc-count">${r&&r.total>0?r.total+` 筆`:`累積中`}</span>
        </div>`}).join(``)}catch{}}async function w(){document.getElementById(`header-date`).textContent=e(),u(),window.addEventListener(`resize`,u),window.addEventListener(`orientationchange`,u),requestAnimationFrame(u),setTimeout(u,300),setTimeout(u,1200),d(),f(),S();try{let{articles:e}=await c();l(e||[])}catch(e){console.error(e),document.getElementById(`article-list`).innerHTML=`<p style="color:var(--text-2);font-size:.88rem;padding:1rem 0">資料載入失敗，請稍後再試。</p>`}C(),y(),setInterval(y,300*1e3)}document.addEventListener(`DOMContentLoaded`,w);