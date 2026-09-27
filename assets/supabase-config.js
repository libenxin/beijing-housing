// Supabase 前端只读配置
// 首次使用时填入你的 Project URL 和 anon public key
window.SUPABASE_CONFIG = {
  enabled: true,
  url: 'https://emlyfidyvqgmuayhxpee.supabase.co',
  anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVtbHlmaWR5dnFnbXVheWh4cGVlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkxMjgyNjgsImV4cCI6MjEwNDcwNDI2OH0.eP1g47fw6y9ne0c_7h8PLYhKuIFMDPQQexT2c9b1ufo',
  // 多项目共享同一个 Supabase 实例，通过 project_code 区分不同小区
  tablePrefix: ''
};

// 测试模式：URL 中带 ?test=mock 或 window.SUPABASE_USE_MOCK===true 时，自动启用 mock 数据
(function(){
  var useMock = (typeof window !== 'undefined') && (
    window.SUPABASE_USE_MOCK === true ||
    (window.location && window.location.search && window.location.search.indexOf('test=mock') !== -1)
  );
  if (useMock && window.SUPABASE_MOCK_DATA) {
    window.SUPABASE_CONFIG = Object.assign({}, window.SUPABASE_CONFIG, {
      enabled: true,
      url: 'https://mock.supabase.example.com',
      anonKey: 'mock_anon_key_for_testing'
    });
    console.log('[Supabase Mock] 已启用 mock 数据模式');
  }
})();
