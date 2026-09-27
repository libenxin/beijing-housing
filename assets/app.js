(function(){
  // ========== 全局状态 ==========
  var state = {
    currentView: 'home', // 'home' | 'detail'
    currentProject: null,
    currentProjectData: null,
    filter: {
      search: '',
      district: '',
      location: ''
    },
    viewMode: 'desktop',
    cloudState: {configured:false, loaded:false, message:'', current:null, previous:null},
    chartArea: null,
    latestAreaRows: null,
    chartResizeBound: false
  };

  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var chartSale = style.getPropertyValue('--chartSale').trim();
  var chartUnavailable = style.getPropertyValue('--chartUnavailable').trim();

  // ========== 工具函数 ==========
  function fmtInt(n){ return Number(n || 0).toLocaleString('zh-CN'); }
  function fmtArea(n){ return Number(n || 0).toLocaleString('zh-CN',{maximumFractionDigits:2,minimumFractionDigits:2}) + '㎡'; }
  function fmtMoney(n){ return Number(n || 0).toLocaleString('zh-CN',{maximumFractionDigits:0}) + '元'; }
  function fmtPrice(n){ return Number(n || 0).toLocaleString('zh-CN',{maximumFractionDigits:2,minimumFractionDigits:2}) + '元/㎡'; }
  function pct(a,b){ return b ? (a / b * 100).toFixed(1) + '%' : '-'; }

  // 已签约/已预订/已备案 3 种都算"去化"（不可售）
  var signedLike = {'已签约':true,'已预订':true,'网上联机备案':true};
  function isSigned(h){ return !!signedLike[h.status]; }
  function statusClass(status){ return status === '已签约' || status === '网上联机备案' ? 'dealed' : status === '已预订' ? 'reserved' : status === '不可售' ? 'disabled' : ''; }
  function statusName(status){ return status === '已签约' || status === '网上联机备案' ? '已成交' : status; }

  // ========== 路由管理 ==========
  function getRoute(){
    var hash = window.location.hash.replace('#','');
    if (hash && hash.indexOf('project=') === 0) {
      return { view: 'detail', projectCode: hash.replace('project=', '') };
    }
    return { view: 'home', projectCode: null };
  }

  function setRoute(projectCode){
    if (projectCode) {
      window.location.hash = 'project=' + projectCode;
    } else {
      window.location.hash = '';
    }
  }

  function handleRoute(){
    var route = getRoute();
    if (route.view === 'detail' && route.projectCode) {
      var project = findProject(route.projectCode);
      if (project) {
        showDetailView(project);
      } else {
        showHomeView();
      }
    } else {
      showHomeView();
    }
  }

  function findProject(code){
    var projects = window.PROJECTS_INDEX || [];
    for (var i = 0; i < projects.length; i++) {
      if (projects[i].code === code) return projects[i];
    }
    return null;
  }

  // ========== 首页视图 ==========
  function showHomeView(){
    state.currentView = 'home';
    state.currentProject = null;
    state.currentProjectData = null;
    document.getElementById('homeView').style.display = 'block';
    document.getElementById('detailView').style.display = 'none';
    renderHomeMeta();
    renderFilterOptions();
    renderProjectGrid();
    // 从 Supabase 拉最新数据，拉到后刷新首页卡片
    loadAllProjectsCloudData().then(function(){
      renderProjectGrid();
      renderHomeMeta();
    });
  }

  function renderHomeMeta(){
    var projects = window.PROJECTS_INDEX || [];
    document.getElementById('homeMeta').innerHTML = [
      '项目总数：' + projects.length + '个',
      '覆盖区县：' + getUniqueDistricts().length + '个',
      '数据来源：北京市住建委'
    ].map(function(t){ return '<span class="pill">'+t+'</span>'; }).join('');
    document.getElementById('footer').textContent = '数据源：北京市住房和城乡建设委员会项目公示与楼盘表页面；历史快照建议存储于 Supabase，所有访问者统一读取同一份云端数据。';
  }

  function getUniqueDistricts(){
    var projects = window.PROJECTS_INDEX || [];
    var districts = {};
    projects.forEach(function(p){ if(p.district) districts[p.district] = true; });
    return Object.keys(districts);
  }

  function renderFilterOptions(){
    var districtSel = document.getElementById('districtFilter');
    var locationSel = document.getElementById('locationFilter');
    var districts = window.DISTRICTS || [];
    var locations = window.LOCATIONS || [];

    // 保留第一个"全部"选项
    districtSel.innerHTML = '<option value="">全部区县</option>' +
      districts.map(function(d){ return '<option value="'+d+'">'+d+'</option>'; }).join('');
    locationSel.innerHTML = '<option value="">全部区位</option>' +
      locations.map(function(l){ return '<option value="'+l+'">'+l+'</option>'; }).join('');

    // 绑定事件
    document.getElementById('searchInput').addEventListener('input', function(e){
      state.filter.search = e.target.value.trim();
      renderProjectGrid();
    });
    districtSel.addEventListener('change', function(e){
      state.filter.district = e.target.value;
      renderProjectGrid();
    });
    locationSel.addEventListener('change', function(e){
      state.filter.location = e.target.value;
      renderProjectGrid();
    });
  }

  function filterProjects(){
    var projects = window.PROJECTS_INDEX || [];
    var f = state.filter;
    return projects.filter(function(p){
      if (f.search) {
        var keyword = f.search;
        var inName = p.name.indexOf(keyword) !== -1;
        var inMarketing = p.marketingName && p.marketingName.indexOf(keyword) !== -1;
        var inDistrict = p.district.indexOf(keyword) !== -1;
        var inDeveloper = p.developer && p.developer.indexOf(keyword) !== -1;
        if (!inName && !inMarketing && !inDistrict && !inDeveloper) return false;
      }
      if (f.district && p.district !== f.district) return false;
      if (f.location && p.location !== f.location) return false;
      return true;
    });
  }

  function renderProjectGrid(){
    var filtered = filterProjects();
    var grid = document.getElementById('projectGrid');
    var stats = document.getElementById('filterStats');

    stats.textContent = '共找到 ' + filtered.length + ' 个项目';

    if (filtered.length === 0) {
      grid.innerHTML = '<p class="empty" style="padding:40px;text-align:center;grid-column:1/-1">没有找到匹配的项目，请调整筛选条件。</p>';
      return;
    }

    grid.innerHTML = filtered.map(function(p){
      var signedCount = p.cloudSignedCount != null ? p.cloudSignedCount : (p.fullSignedCount || p.sellThroughCount || 0);
      var total = p.houseCount || 0;
      var available = Math.max(total - signedCount, 0);
      var soldPct = total ? Math.round(signedCount / total * 100) : 0;
      var label = p.cloudSignedCount != null ? '已签约' : '全口径已签';
      return '<div class="project-card" data-code="'+p.code+'">' +
        '<div class="project-top">' +
          '<div class="project-name">'+p.name+(p.marketingName?'（'+p.marketingName+'）':'')+'</div>' +
          '<div class="project-date">'+p.permitDate+'</div>' +
        '</div>' +
        '<div>' +
          '<span class="project-district">'+p.district+'</span>' +
          '<span class="project-location">'+p.location+'</span>' +
        '</div>' +
        '<div class="project-stats">' +
          '<div class="stat-item"><div class="label">'+label+'</div><div class="num">'+fmtInt(signedCount)+'套</div></div>' +
          '<div class="stat-item"><div class="label">可售</div><div class="num">'+fmtInt(available)+'套</div></div>' +
          '<div class="stat-item"><div class="label">去化率</div><div class="num">'+soldPct+'%</div></div>' +
        '</div>' +
      '</div>';
    }).join('');

    // 绑定点击事件
    grid.querySelectorAll('.project-card').forEach(function(card){
      card.addEventListener('click', function(){
        var code = card.getAttribute('data-code');
        setRoute(code);
      });
    });
  }

  // ========== 详情页视图 ==========
  function showDetailView(project){
    state.currentView = 'detail';
    state.currentProject = project;
    document.getElementById('homeView').style.display = 'none';
    document.getElementById('detailView').style.display = 'block';

    // 先显示基本信息
    var displayName = project.name + (project.marketingName ? '（' + project.marketingName + '）' : '');
    document.getElementById('detailEyebrow').textContent = displayName + ' 签约监测';
    document.getElementById('detailTitle').textContent = displayName + ' 项目房源看板';
    document.getElementById('detailSubtitle').textContent = project.district + ' · ' + project.location + ' · ' + project.developer;

    // 加载项目详情数据
    loadProjectData(project).then(function(data){
      if (!data) {
        document.getElementById('buildingList').innerHTML = '<p class="note">该项目详细数据正在整理中，敬请期待。</p>';
        return;
      }
      state.currentProjectData = data;
      renderDetailMeta();
      renderOverview();
      // 先渲染一次（无云端数据时的占位）
      renderDaily();
      renderBuildings();
      renderAreaLegend();
      // 异步加载云端快照后再刷新"近期成交情况"和概览（全口径卡片依赖首页权威值）
      return loadCloudData(project.code);
    }).then(function(){
      renderOverview();
      renderDaily();
      // 云数据加载完成后重新渲染楼栋网格，叠加官网已售出房源的成交状态
      renderBuildings();
    });
  }

  function loadProjectData(project){
    // 如果数据已经通过 PROJECT_DATA 全局变量加载了（如嘉华珺园）
    if (window.PROJECT_DATA && window.PROJECT_DATA.project &&
        window.PROJECT_DATA.project.name === project.name) {
      return Promise.resolve(window.PROJECT_DATA);
    }

    // 检查项目是否有完整数据文件
    if (!project.hasFullData || !project.dataFile) {
      return Promise.resolve(null);
    }

    // 动态加载数据文件
    return new Promise(function(resolve){
      var script = document.createElement('script');
      script.src = project.dataFile;
      script.onload = function(){
        // 数据文件应该设置 window.PROJECT_DATA
        resolve(window.PROJECT_DATA || null);
      };
      script.onerror = function(){
        resolve(null);
      };
      document.head.appendChild(script);
    });
  }

  function renderDetailMeta(){
    var data = state.currentProjectData;
    if (!data) return;
    var project = data.project;
    var buildings = data.buildings;
    var houses = buildings.flatMap(function(b){ return b.houses; });

    document.getElementById('detailMeta').innerHTML = [
      '数据提取：' + (project.extractedAt || project.snapshotDate || '-'),
      '楼栋：' + buildings.length + '栋',
      '房源：' + houses.length + '套',
      '官网项目：' + project.name,
      state.cloudState.loaded && state.cloudState.snapshots && state.cloudState.snapshots.length >= 2 ? '云端快照：Supabase' : '云端快照：待数据更新'
    ].map(function(t){ return '<span class="pill">'+t+'</span>'; }).join('');
  }

  // ========== 签约概览 ==========
  function getAreaTypes(){
    var data = state.currentProjectData;
    if (!data) return [];
    var houses = data.buildings.flatMap(function(b){ return b.houses; });
    var types = new Set();
    houses.forEach(function(h){ if(h.areaBucket) types.add(h.areaBucket); });
    return Array.from(types).sort(function(a,b){
      return Number(a.replace('平','')) - Number(b.replace('平',''));
    });
  }

  function renderOverview(){
    var data = state.currentProjectData;
    if (!data) return;
    var ov = data.project.overview || {};
    var houses = data.buildings.flatMap(function(b){ return b.houses || []; });
    var totalCount = houses.length;
    // 全口径总套数：各楼栋 houseCount 之和（含已售完楼栋）
    var fullTotal = data.buildings.reduce(function(s,b){ return s + (Number(b.houseCount)||0); }, 0) || totalCount;
    // 全口径已签：优先首页权威（云端快照），无云端时兜底明细
    var cloud = state.cloudState && state.cloudState.loaded && state.cloudState.current && state.cloudState.current.overview;
    var cloudSigned = cloud && cloud.signedCount ? Number(cloud.signedCount) : 0;
    var detailSigned = houses.filter(function(h){ return ['已签约','已预订','网上联机备案'].indexOf(h.status) !== -1; }).length;
    var fullSignedCount = cloudSigned > 0 ? cloudSigned : detailSigned;
    var availableCount = Math.max(fullTotal - fullSignedCount, 0);
    var sellThroughRate = fullTotal ? (fullSignedCount / fullTotal * 100).toFixed(1) + '%' : '-';
    document.getElementById('overviewStats').innerHTML = [
      ['全口径已签', fmtInt(fullSignedCount) + '套', '项目首页「期房签约统计」住宅行全口径已签约套数（含已售完楼栋）'],
      ['可售', fmtInt(availableCount) + '套', '全口径总套数减去全口径已签约'],
      ['去化率', sellThroughRate]
    ].map(function(s){ return '<div class="stat" title="'+(s[2]||'')+'"><div class="num">'+s[1]+'</div><div class="label">'+s[0]+'</div></div>'; }).join('');
  }

  function renderCharts(areaRows){
    state.latestAreaRows = areaRows;
    var isMobile = document.body.classList.contains('mobile-view');
    var chartDom = document.getElementById('chartArea100');
    if (!state.chartArea) state.chartArea = echarts.init(chartDom, null, {renderer:'svg'});
    state.chartArea.setOption({
      animation:false,
      tooltip:{
        trigger:'axis',
        appendToBody:true,
        formatter:function(params){
          var idx = params[0].dataIndex;
          var r = areaRows[idx];
          return r.type + '<br/>总套数：' + r.total + '套<br/>可售：' + r.available + '套<br/>成交：' + r.unavailable + '套';
        }
      },
      legend:{bottom:0,textStyle:{color:muted}},
      grid:{top:28,right:18,bottom:isMobile ? 48 : 72,left:12},
      xAxis:{
        type:'category',
        data:areaRows.map(function(r){return isMobile ? r.type : r.type + '\n总' + r.total + '套';}),
        axisLabel:{color:muted,lineHeight:18,interval:0,fontSize:isMobile ? 10 : 12},
        axisLine:{lineStyle:{color:rule}}
      },
      yAxis:{
        type:'value',
        max:100,
        show:false,
        axisLabel:{show:false},
        axisLine:{show:false},
        axisTick:{show:false},
        splitLine:{show:false}
      },
      color:[chartSale, chartUnavailable],
      series:[
        {
          name:'可售',
          type:'bar',
          stack:'total',
          barWidth:'54%',
          data:areaRows.map(function(r){return Number(r.availablePct.toFixed(2));}),
          label:{
            show:true,
            position:'inside',
            formatter:function(p){
              var r = areaRows[p.dataIndex];
              return r.available ? String(r.available) : '';
            },
            color:'#172033',
            fontWeight:700
          }
        },
        {
          name:'成交',
          type:'bar',
          stack:'total',
          barWidth:'54%',
          data:areaRows.map(function(r){return Number(r.unavailablePct.toFixed(2));}),
          label:{
            show:true,
            position:'inside',
            formatter:function(p){
              var r = areaRows[p.dataIndex];
              return r.unavailable ? String(r.unavailable) : '';
            },
            color:'#172033',
            fontWeight:700
          }
        }
      ]
    });
    if(!state.chartResizeBound){
      state.chartResizeBound = true;
      window.addEventListener('resize', function(){ state.chartArea && state.chartArea.resize(); });
    }
  }

  // ========== 近期成交情况 ==========
  function snapshotFromCurrent(){
    var data = state.currentProjectData;
    if (!data) return null;
    var project = data.project;
    var buildings = data.buildings;
    var houses = buildings.flatMap(function(b){ return b.houses.map(function(h){ return Object.assign({building:b.name}, h); }); });

    function houseKey(h){ return h.building + ' ' + h.houseNo; }

    return {
      savedAt: new Date().toISOString(),
      snapshotDate: project.snapshotDate || '',
      overview: project.overview,
      signedHouses: houses.filter(isSigned).map(function(h){ return {key:houseKey(h), building:h.building, houseNo:h.houseNo, area:h.buildingArea, status:h.status, unitPrice:h.unitPrice || 0, totalPrice:h.totalPrice || (h.buildingArea * (h.unitPrice || 0))}; })
    };
  }

  // 计算两个 snapshot 之间的差异
  function diffSnapshots(prev, cur){
    var prevMap = new Map(prev.signedHouses.map(function(h){ return [h.key, h]; }));
    var curMap = new Map(cur.signedHouses.map(function(h){ return [h.key, h]; }));
    // 具体成交/退房房源：用 house_status_snapshots 房源明细差异
    // 新增 key（之前不在已成交集合）== 新成交；同时在集合内但状态升级为"已签约"（如 已预订→已签约）也计入，
    // 因为首页权威 signedCount 只统计"已签约"，这类升级会使权威 +1 而 house 差集为 0
    var newSold = [];
    cur.signedHouses.forEach(function(h){
      if (!prevMap.has(h.key)) { newSold.push(h); return; }
      var p = prevMap.get(h.key);
      if (h.status === '已签约' && p.status !== '已签约') newSold.push(h);
    });
    var returned = prev.signedHouses.filter(function(h){ return !curMap.has(h.key); });

    // 成交套数/面积/均价：用 daily_project_snapshots 首页权威数据，按加权平均计算新增成交均价
    var prevSigned = Number(prev.overview.signedCount) || 0;
    var curSigned = Number(cur.overview.signedCount) || 0;
    var prevArea = Number(prev.overview.signedArea) || 0;
    var curArea = Number(cur.overview.signedArea) || 0;
    var prevAvg = Number(prev.overview.avgPrice) || 0;
    var curAvg = Number(cur.overview.avgPrice) || 0;

    var signedDelta = curSigned - prevSigned;
    var soldCount = Math.max(signedDelta, 0);          // 净新增成交套数
    var returnedCount = Math.max(-signedDelta, 0);     // 净退房套数
    var newArea = Math.max(curArea - prevArea, 0);     // 净新增成交面积
    // 新增成交均价 = (今日总额 - 昨日总额) / (今日面积 - 昨日面积)
    var newTotalPrice = curAvg * curArea - prevAvg * prevArea;
    var newAvg = newArea > 0 ? newTotalPrice / newArea : 0;
    // 退房面积（用于展示，若有明细则用明细，否则用面积差）
    var returnedArea = returned.reduce(function(s, h){ return s + (Number(h.area) || 0); }, 0);

    return {
      soldCount: soldCount,
      returnedCount: returnedCount,
      newArea: newArea,
      newTotalPrice: newTotalPrice,
      newAvg: newAvg,
      returnedArea: returnedArea,
      newSold: newSold,
      returned: returned
    };
  }

  function renderDaily(){
    var el = document.getElementById('dailyCompare');
    if (!el) return;

    var cloudMsg = state.cloudState.message || '';
    var snapshots = state.cloudState.snapshots || [];

    // 云端 house 快照的面积可能缺失（日度增量不抓面积），从本地 data.js 兜底回填真实建筑面积
    function localArea(building, houseNo){
      var data = state.currentProjectData;
      if (!data || !data.buildings) return 0;
      for (var i = 0; i < data.buildings.length; i++) {
        var b = data.buildings[i];
        if (b.name !== building) continue;
        var hs = b.houses || [];
        for (var j = 0; j < hs.length; j++) {
          if (String(hs[j].houseNo) === String(houseNo)) {
            var a = Number(hs[j].buildingArea) || 0;
            return (a > 0 && hs[j].source === 'official') ? a : 0;
          }
        }
        return 0;
      }
      return 0;
    }
    function houseArea(h){
      var a = Number(h.area) || 0;
      if (a > 0) return a;
      return localArea(h.building, h.houseNo);
    }

    // 如果 Supabase 未配置或没有快照数据
    if (!state.cloudState.loaded || snapshots.length < 2) {
      el.innerHTML = '<p class="note">待数据更新</p>';
      return;
    }

    // 按日期升序
    var sorted = snapshots.slice().sort(function(a, b){
      return String(a.snapshotDate).localeCompare(String(b.snapshotDate));
    });

    // 每天与前一日对比
    var dayDiffs = [];
    for (var i = 1; i < sorted.length; i++) {
      var prev = sorted[i - 1];
      var cur = sorted[i];
      var diff = diffSnapshots(prev, cur);
      dayDiffs.push({
        date: cur.snapshotDate,
        prevDate: prev.snapshotDate,
        diff: diff
      });
    }

    // 只保留有交易的日期（售出>0 或 退房>0），按日期倒序
    var activeDays = dayDiffs.filter(function(d){
      return d.diff.soldCount > 0 || d.diff.returnedCount > 0;
    }).reverse();

    if (activeDays.length === 0) {
      el.innerHTML = '<p class="hint">' + cloudMsg + '</p>' +
        '<p class="note">最近 2 周内无交易变化。</p>';
      return;
    }

    // 渲染每一天的 3 张卡片
    var html = '<p class="hint">' + cloudMsg + '</p>';
    activeDays.forEach(function(item){
      var d = item.diff;
      var dateText = item.date;
      // 卡片1：日期--成交面积--成交均价
      var card1 = '<div class="period-card">' +
        '<div class="period-card-row"><span class="period-label">日期</span><span class="period-value">' + dateText + '</span></div>' +
        '<div class="period-card-row"><span class="period-label">成交面积</span><span class="period-value">' + (d.newArea > 0 ? fmtArea(d.newArea) : '-') + '</span></div>' +
        '<div class="period-card-row"><span class="period-label">成交均价</span><span class="period-value">' + (d.newArea > 0 ? fmtPrice(d.newAvg) : '-') + '</span></div>' +
        (d.returnedCount > 0 ? '<div class="period-note">*若当天有退房房源，则成交均价无法计算，数据不准确，请勿参考</div>' : '') +
        '</div>';

      // 卡片2：成交套数--成交房源--成交价格
      var soldHouseText = d.newSold.length > 0
        ? d.newSold.map(function(h){
            var a = houseArea(h);
            var suffix = a > 0 ? '（' + a + '㎡）' : '';
            return h.building + ' ' + h.houseNo + suffix;
          }).join('<br>')
        : '-';
      var card2 = '<div class="period-card">' +
        '<div class="period-card-row"><span class="period-label">成交套数</span><span class="period-value">' + d.soldCount + '套</span></div>' +
        '<div class="period-card-row"><span class="period-label">成交房源</span><span class="period-value small-text">' + soldHouseText + '</span></div>' +
        '<div class="period-card-row"><span class="period-label">成交价格</span><span class="period-value">' + (d.newTotalPrice > 0 ? fmtMoney(d.newTotalPrice) : '-') + '</span></div>' +
        '</div>';

      // 卡片3：退房套数--退房房源
      var returnedText = d.returned.length > 0
        ? d.returned.map(function(h){
            var a = houseArea(h);
            var suffix = a > 0 ? '（' + a + '㎡）' : '';
            return h.building + ' ' + h.houseNo + suffix;
          }).join('<br>')
        : '-';
      var card3 = '<div class="period-card">' +
        '<div class="period-card-row"><span class="period-label">退房套数</span><span class="period-value">' + d.returnedCount + '套</span></div>' +
        '<div class="period-card-row"><span class="period-label">退房房源</span><span class="period-value small-text">' + returnedText + '</span></div>' +
        '<div class="period-card-row"><span class="period-label">退房面积</span><span class="period-value">' + (d.returnedArea > 0 ? fmtArea(d.returnedArea) : '-') + '</span></div>' +
        '</div>';

      html += '<div class="period-day">' + card1 + card2 + card3 + '</div>';
    });

    el.innerHTML = html;
  }

  function renderHouseList(list){
    if(!list || !list.length) return '<p class="empty">无</p>';
    return '<div class="table-wrap" style="margin-bottom:14px"><table><thead><tr><th>楼栋</th><th>房号</th><th>建筑面积</th><th>状态</th></tr></thead><tbody>' +
      list.map(function(h){ return '<tr><td>'+h.building+'</td><td><strong>'+h.houseNo+'</strong></td><td>'+fmtArea(h.area)+'</td><td>'+h.status+'</td></tr>'; }).join('') +
      '</tbody></table></div>';
  }

  // ========== 房源详情 ==========
  function renderAreaLegend(){
    var legend = document.getElementById('areaLegend');
    legend.innerHTML =
      '<span class="legend-item"><span class="area-dot available"></span>可售</span>' +
      '<span class="legend-item"><span class="area-dot dealed"></span>已成交/备案</span>';
  }

  // 楼栋自然排序：提取名中所有数字逐位比较（1#、2#、10#；1-1#、1-2#、1-10#）
  function buildingNumSeq(name){
    var m = String(name || '').match(/\d+/g) || [];
    return m.map(Number);
  }
  function cmpBuilding(a, b){
    var na = buildingNumSeq(a.name), nb = buildingNumSeq(b.name);
    var n = Math.max(na.length, nb.length);
    for (var i = 0; i < n; i++) {
      var x = na[i] || 0, y = nb[i] || 0;
      if (x !== y) return x - y;
    }
    return String(a.name).localeCompare(String(b.name), 'zh');
  }

  function renderBuildings(){
    var data = state.currentProjectData;
    if (!data) return;
    var buildings = data.buildings.slice().sort(cmpBuilding);

    document.getElementById('buildingList').innerHTML = buildings.map(function(b, idx){
      // 已售完楼栋：只显示楼栋级信息，不展示逐套房源
      if (b.status === '已售完' || !b.houses || b.houses.length === 0) {
        var houseCount = b.houseCount || 0;
        return '<div class="building-soldout">' +
          '<div class="building-soldout-header">' +
            '<span class="building-title">' + b.name + '</span>' +
            '<span class="badge-soldout">已售完</span>' +
          '</div>' +
          '<div class="building-soldout-info">' +
            '<span>总套数：' + houseCount + '套</span>' +
            (b.totalArea ? '<span>总面积：' + b.totalArea + '㎡</span>' : '') +
          '</div>' +
          '<p class="building-soldout-note">该楼栋已售完，政府网站不再提供逐套房源面积明细。</p>' +
        '</div>';
      }

      // 用 room 兜底计算 floor（末 2 位=户号），避免数据里 floor=0 时显示 0F
      function guessFloor(room){
        var s = String(room || '');
        if (!/^\d{3,4}$/.test(s)) return 0;
        return parseInt(s.slice(0, -2), 10) || 0;
      }
      var list = b.houses.slice();
      // 用云端最新已成交集合覆盖静态快照中"官网已售出但仍显示可售"的房源（data.js 是首次爬取快照，日度增量不更新它）
      var cs = (state.cloudState && state.cloudState.current && state.cloudState.current.signedHouses) || [];
      list.forEach(function(h){
        if (!h.floor || h.floor <= 0) h.floor = guessFloor(h.room);
        var ck = b.name + ' ' + h.houseNo;
        for (var i = 0; i < cs.length; i++) {
          if (cs[i].key === ck && signedLike[h.status] !== true) {
            h.status = cs[i].status || '已签约';
            break;
          }
        }
      });
      // 从上往下：从高到低。同一楼层 unit 升序，room 升序
      list.sort(function(a,b){ return (b.floor-a.floor) || (a.unit-b.unit) || String(a.room).localeCompare(String(b.room)); });
      // 楼栋 summary：共X套，已成交Y套；剩余可售按真实面积分组（xx平剩余x套）
      var totalCount = list.length;
      var availableList = list.filter(function(h){ return h.status === '可售'; });
      var availableCount = availableList.length;
      var soldCount = totalCount - availableCount;
      var summaryParts = ['<span>共' + totalCount + '套</span>', '<span>已成交' + soldCount + '套</span>'];
      var areaGroups = {};
      availableList.forEach(function(h){
        if (h.source === 'official' && h.buildingArea > 0) {
          var key = h.buildingArea;
          areaGroups[key] = (areaGroups[key] || 0) + 1;
        }
      });
      Object.keys(areaGroups).map(Number).sort(function(a,b){ return a - b; }).forEach(function(area){
        summaryParts.push('<span>' + area + '平剩余' + areaGroups[area] + '套</span>');
      });
      var bucketSummary = summaryParts.join('');
      var floors = Array.from(new Set(list.map(function(h){ return h.floor; }))).sort(function(a,b){ return b-a; });
      var grid = floors.map(function(f){
        var hs = list.filter(function(h){ return h.floor === f; });
        return '<div class="floor-row"><div class="floor-label">'+f+'F</div><div class="houses">' + hs.map(function(h){
          // 只有真实面积（source==='official' 且 buildingArea>0）才显示在房号下
          var realArea = h.source === 'official' && h.buildingArea > 0 ? h.buildingArea : null;
          var smallHtml = realArea ? '<small>' + realArea + '㎡</small>' : '';
          var areaText = realArea ? realArea + '㎡' : '';
          return '<div class="house '+statusClass(h.status)+'" title="'+b.name+' '+h.houseNo+'｜'+statusName(h.status)+(areaText?'｜'+areaText:'')+'"><span>'+h.houseNo+'</span>'+smallHtml+'</div>';
        }).join('') + '</div></div>';
      }).join('');
      return '<details '+(idx===0?'open':'')+'><summary><span class="building-title"><span>'+b.name+'</span><span class="building-hint">点击查看房源图详情</span></span><span class="building-summary">'+bucketSummary+'</span></summary><div class="building-body">'+grid+'</div></details>';
    }).join('');
  }

  // ========== Supabase 云端数据（多项目） ==========
  function getSupabaseConfig(){
    var cfg = window.SUPABASE_CONFIG || {};
    return {
      enabled: cfg.enabled === true,
      url: String(cfg.url || '').replace(/\/+$/,''),
      anonKey: String(cfg.anonKey || '')
    };
  }

  function hasSupabaseConfig(cfg){
    return !!(cfg.enabled && cfg.url && cfg.anonKey && cfg.url.indexOf('your-project') === -1 && cfg.anonKey.indexOf('your-anon-key') === -1);
  }

  function supabaseFetch(cfg, path){
    // 测试模式：当 cfg.url 包含 mock 时，从 window.SUPABASE_MOCK_DATA 返回数据
    if (cfg.url && cfg.url.indexOf('mock') !== -1 && window.SUPABASE_MOCK_DATA) {
      return mockSupabaseFetch(cfg, path);
    }
    var headers = {
      apikey:cfg.anonKey,
      Accept:'application/json'
    };
    if(cfg.anonKey.indexOf('sb_publishable_') !== 0){
      headers.Authorization = 'Bearer ' + cfg.anonKey;
    }
    return fetch(cfg.url + '/rest/v1/' + path, { headers:headers })
      .then(function(res){
        if(!res.ok) return res.text().then(function(text){ throw new Error(text || ('Supabase 请求失败：' + res.status)); });
        return res.json();
      });
  }

  function mockSupabaseFetch(cfg, path){
    return new Promise(function(resolve){
      setTimeout(function(){
        var mock = window.SUPABASE_MOCK_DATA;
        if (path.indexOf('daily_project_snapshots') !== -1) {
          resolve(mock.daily_project_snapshots);
          return;
        }
        if (path.indexOf('house_status_snapshots') !== -1) {
          // 解析 snapshot_date
          var m = path.match(/snapshot_date=eq\.([0-9-]+)/);
          if (m) {
            var date = m[1];
            resolve(mock.house_status_snapshots[date] || []);
            return;
          }
        }
        resolve([]);
      }, 50);
    });
  }

  function loadAllProjectsCloudData(){
    var cfg = getSupabaseConfig();
    if(!hasSupabaseConfig(cfg)){
      return Promise.resolve(null);
    }
    // 取所有项目最新一条 daily 快照
    var path = 'daily_project_snapshots?select=project_code,snapshot_date,signed_count,signed_area,avg_price&order=snapshot_date.desc';
    return supabaseFetch(cfg, path)
      .then(function(rows){
        if(!rows || !rows.length) return null;
        // 每个项目只保留最新一条
        var latest = {};
        rows.forEach(function(r){
          var code = r.project_code;
          if(!latest[code]) latest[code] = r;
        });
        // 用云端数据更新 PROJECTS_INDEX（signed_count = 纯已签约）
        var projects = window.PROJECTS_INDEX || [];
        projects.forEach(function(p){
          var d = latest[p.code];
          if(!d) return;
          p.cloudSignedCount = Number(d.signed_count) || 0;
          p.avgPrice = Number(d.avg_price) || 0;
          p.cloudSnapshotDate = d.snapshot_date;
        });
        return latest;
      })
      .catch(function(err){
        console.warn('[首页] 云端数据加载失败，使用本地静态数据:', err.message);
        return null;
      });
  }

  function loadCloudData(projectCode){
    var cfg = getSupabaseConfig();
    state.cloudState.configured = hasSupabaseConfig(cfg);
    if(!state.cloudState.configured){
      state.cloudState.message = 'Supabase 尚未配置，当前仅展示内置静态数据。';
      state.cloudState.current = snapshotFromCurrent();
      return Promise.resolve(state.cloudState);
    }
    var projectFilter = 'project_code=eq.' + encodeURIComponent(projectCode);
    // 读取最近 14 天快照
    return supabaseFetch(cfg, 'daily_project_snapshots?select=*&' + projectFilter + '&order=snapshot_date.desc&limit=14')
      .then(function(days){
        if(!days || !days.length){
          state.cloudState.message = 'Supabase 已连接，但还没有该项目的每日快照数据。';
          state.cloudState.current = snapshotFromCurrent();
          return state.cloudState;
        }
        // 按日期升序
        days = days.slice().sort(function(a,b){ return a.snapshot_date.localeCompare(b.snapshot_date); });
        // 读取每一天的房源状态快照
        var promises = days.map(function(d){
          var path = 'house_status_snapshots?select=*&' + projectFilter + '&snapshot_date=eq.' + encodeURIComponent(d.snapshot_date) + '&limit=2000';
          return supabaseFetch(cfg, path).then(function(rows){
            return { day: d, rows: rows || [] };
          });
        });
        return Promise.all(promises).then(function(dayDataList){
          state.cloudState.loaded = true;
          var latest = dayDataList[dayDataList.length - 1];
          state.cloudState.message = '已读取 Supabase 云端快照：' + latest.day.snapshot_date + '，共 ' + dayDataList.length + ' 天数据。';
          // 构建所有每日 snapshot 列表（按日期升序）
          state.cloudState.snapshots = dayDataList.map(function(item){
            return buildSnapshot(item.day, item.rows);
          });
          state.cloudState.current = state.cloudState.snapshots[state.cloudState.snapshots.length - 1] || null;
          state.cloudState.previous = state.cloudState.snapshots[state.cloudState.snapshots.length - 2] || null;
          return state.cloudState;
        });
      }).catch(function(err){
        state.cloudState.message = 'Supabase 读取失败，当前回退展示内置静态数据。错误信息：' + err.message;
        state.cloudState.current = snapshotFromCurrent();
        return state.cloudState;
      });
  }

  function buildSnapshot(day, rows){
    return {
      savedAt: day.extracted_at || day.snapshot_date,
      snapshotDate: day.snapshot_date,
      overview: {
        signedCount: Number(day.signed_count) || 0,
        signedArea: Number(day.signed_area) || 0,
        avgPrice: Number(day.avg_price) || 0
      },
      signedHouses: (rows || []).filter(function(r){ return !!signedLike[r.status]; }).map(function(r){
        return {
          key: r.house_key,
          building: r.building || '',
          houseNo: r.house_no || r.house_key,
          area: Number(r.building_area) || 0,
          unitPrice: Number(r.unit_price) || 0,
          totalPrice: Number(r.total_price) || (r.building_area && r.unit_price ? Number(r.building_area) * Number(r.unit_price) : 0),
          status: r.status
        };
      })
    };
  }

  // ========== 返回按钮 ==========
  function initBackButton(){
    document.getElementById('backBtn').addEventListener('click', function(){
      setRoute('');
    });
  }

  // ========== 初始化 ==========
  function init(){
    document.body.classList.add('mobile-view');
    initBackButton();
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
  }

  // DOM 就绪后初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
