// 测试用模拟快照数据
// URL 中带 ?test=mock 时，supabase-config.js 会自动启用 mock URL
// 包含 6 天的历史快照，部分日期有新成交和退房
window.SUPABASE_MOCK_DATA = {
  daily_project_snapshots: [
    { id: 1, project_code: 'changan_jinhe_jiayuan', snapshot_date: '2026-09-01', signed_count: 320, signed_area: 31600, avg_price: 61000, total_houses: 355, total_area: 38145, extracted_at: '2026-09-01T23:00:00Z' },
    { id: 2, project_code: 'changan_jinhe_jiayuan', snapshot_date: '2026-09-03', signed_count: 325, signed_area: 32100, avg_price: 61050, total_houses: 355, total_area: 38145, extracted_at: '2026-09-03T23:00:00Z' },
    { id: 3, project_code: 'changan_jinhe_jiayuan', snapshot_date: '2026-09-05', signed_count: 330, signed_area: 32600, avg_price: 61100, total_houses: 355, total_area: 38145, extracted_at: '2026-09-05T23:00:00Z' },
    { id: 4, project_code: 'changan_jinhe_jiayuan', snapshot_date: '2026-09-07', signed_count: 335, signed_area: 33100, avg_price: 61150, total_houses: 355, total_area: 38145, extracted_at: '2026-09-07T23:00:00Z' },
    { id: 5, project_code: 'changan_jinhe_jiayuan', snapshot_date: '2026-09-09', signed_count: 340, signed_area: 33600, avg_price: 61200, total_houses: 355, total_area: 38145, extracted_at: '2026-09-09T23:00:00Z' },
    { id: 6, project_code: 'changan_jinhe_jiayuan', snapshot_date: '2026-09-11', signed_count: 345, signed_area: 34153, avg_price: 56731, total_houses: 355, total_area: 38145, extracted_at: '2026-09-11T23:00:00Z' },
  ],
  house_status_snapshots: {
    '2026-09-01': [
      { house_key: 'A-1#住宅楼 1单元-1101', building: 'A-1#住宅楼', house_no: '1单元-1101', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1102', building: 'A-1#住宅楼', house_no: '1单元-1102', status: '已签约', building_area: 89.5, unit_price: 61000, total_price: 5459500 },
    ],
    '2026-09-03': [
      { house_key: 'A-1#住宅楼 1单元-1101', building: 'A-1#住宅楼', house_no: '1单元-1101', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1102', building: 'A-1#住宅楼', house_no: '1单元-1102', status: '已签约', building_area: 89.5, unit_price: 61000, total_price: 5459500 },
      { house_key: 'A-1#住宅楼 1单元-1201', building: 'A-1#住宅楼', house_no: '1单元-1201', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
    ],
    '2026-09-05': [
      { house_key: 'A-1#住宅楼 1单元-1101', building: 'A-1#住宅楼', house_no: '1单元-1101', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1102', building: 'A-1#住宅楼', house_no: '1单元-1102', status: '已签约', building_area: 89.5, unit_price: 61000, total_price: 5459500 },
      { house_key: 'A-1#住宅楼 1单元-1201', building: 'A-1#住宅楼', house_no: '1单元-1201', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1301', building: 'A-1#住宅楼', house_no: '1单元-1301', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
    ],
    '2026-09-07': [
      { house_key: 'A-1#住宅楼 1单元-1101', building: 'A-1#住宅楼', house_no: '1单元-1101', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1102', building: 'A-1#住宅楼', house_no: '1单元-1102', status: '已签约', building_area: 89.5, unit_price: 61000, total_price: 5459500 },
      { house_key: 'A-1#住宅楼 1单元-1201', building: 'A-1#住宅楼', house_no: '1单元-1201', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1301', building: 'A-1#住宅楼', house_no: '1单元-1301', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1401', building: 'A-1#住宅楼', house_no: '1单元-1401', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
    ],
    '2026-09-09': [
      { house_key: 'A-1#住宅楼 1单元-1101', building: 'A-1#住宅楼', house_no: '1单元-1101', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1102', building: 'A-1#住宅楼', house_no: '1单元-1102', status: '已签约', building_area: 89.5, unit_price: 61000, total_price: 5459500 },
      // 注: A-1#住宅楼 1单元-1201 在09-09已退房，09-11不再存在
      { house_key: 'A-1#住宅楼 1单元-1301', building: 'A-1#住宅楼', house_no: '1单元-1301', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1401', building: 'A-1#住宅楼', house_no: '1单元-1401', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1501', building: 'A-1#住宅楼', house_no: '1单元-1501', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
    ],
    '2026-09-11': [
      { house_key: 'A-1#住宅楼 1单元-1101', building: 'A-1#住宅楼', house_no: '1单元-1101', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1102', building: 'A-1#住宅楼', house_no: '1单元-1102', status: '已签约', building_area: 89.5, unit_price: 61000, total_price: 5459500 },
      { house_key: 'A-1#住宅楼 1单元-1301', building: 'A-1#住宅楼', house_no: '1单元-1301', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1401', building: 'A-1#住宅楼', house_no: '1单元-1401', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1501', building: 'A-1#住宅楼', house_no: '1单元-1501', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
      { house_key: 'A-1#住宅楼 1单元-1601', building: 'A-1#住宅楼', house_no: '1单元-1601', status: '已签约', building_area: 78.86, unit_price: 60862, total_price: 4800000 },
    ],
  }
};
